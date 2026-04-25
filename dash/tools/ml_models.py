"""
ML Models
=========
Machine learning tools for the Analyst agent.
Pure Python functions — no agents, no extra servers.

4 tools:
- predict(): use pre-trained model from dash_ml_models
- feature_importance(): train quick LightGBM, return top factors
- detect_anomalies_ml(): use pre-trained IsolationForest
- llm_predict(): LLM fallback when no model exists

Auto-training:
- auto_create_models(): runs during training Step 14
- Detects date columns → forecast, numeric → predictor, always → anomaly
- Only trains on <1000 rows (fast, no RAM spike)
- Saves models to dash_ml_models PostgreSQL table (BYTEA)
"""

import json
import pickle
import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)


def init_ml_tables():
    """Create dash_ml_models table if not exists."""
    try:
        from sqlalchemy import text, create_engine
        from db.url import db_url
        engine = create_engine(db_url)
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS public.dash_ml_models (
                    id SERIAL PRIMARY KEY,
                    project_slug TEXT NOT NULL,
                    name TEXT NOT NULL,
                    model_type TEXT NOT NULL,
                    algorithm TEXT NOT NULL,
                    target_column TEXT,
                    features TEXT,
                    accuracy JSONB DEFAULT '{}',
                    row_count INTEGER DEFAULT 0,
                    model_bytes BYTEA,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS public.dash_ml_experiments (
                    id SERIAL PRIMARY KEY,
                    project_slug TEXT NOT NULL,
                    experiment_type TEXT NOT NULL,
                    model_name TEXT,
                    algorithm TEXT,
                    tier TEXT,
                    question TEXT,
                    session_id TEXT,
                    input_summary JSONB DEFAULT '{}',
                    result_data JSONB DEFAULT '{}',
                    accuracy JSONB DEFAULT '{}',
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            conn.commit()
    except Exception as e:
        logger.warning(f"ML tables init failed: {e}")


def auto_create_models(project_slug: str, engine=None, schema: str = None):
    """Auto-detect and train ML models during training Step 14.
    Only for small tables (<1000 rows). Saves to dash_ml_models."""
    init_ml_tables()

    try:
        import pandas as pd
        from sqlalchemy import text, inspect as sa_inspect
        from db import get_sql_engine

        eng = engine or get_sql_engine()
        insp = sa_inspect(eng)
        tables = insp.get_table_names(schema=schema) if schema else []

        if not tables:
            return {"status": "no_tables", "models_created": 0}

        models_created = 0

        for table_name in tables[:10]:  # Cap at 10 tables
            try:
                # Read table (small sample for safety)
                qualified = f'"{schema}"."{table_name}"' if schema else f'"{table_name}"'
                with eng.connect() as conn:
                    row_count = conn.execute(text(f"SELECT COUNT(*) FROM {qualified}")).scalar()

                if row_count < 5 or row_count > 1000:
                    continue  # Too small or too big

                df = pd.read_sql(f"SELECT * FROM {qualified} LIMIT 1000", eng)
                if len(df) < 5:
                    continue

                # Detect columns
                date_cols = [c for c in df.columns if df[c].dtype in ['datetime64[ns]', 'object'] and
                            pd.to_datetime(df[c], errors='coerce').notna().sum() > len(df) * 0.5]
                numeric_cols = [c for c in df.select_dtypes(include=['number']).columns
                               if c.lower() not in ('id', 'index', 'row_number')]

                # 1. Forecast model (if date + numeric columns)
                if date_cols and numeric_cols:
                    try:
                        date_col = date_cols[0]
                        value_col = numeric_cols[0]

                        df_ts = df[[date_col, value_col]].copy()
                        df_ts[date_col] = pd.to_datetime(df_ts[date_col], errors='coerce')
                        df_ts = df_ts.dropna().sort_values(date_col)

                        if len(df_ts) >= 10:
                            from statsforecast import StatsForecast
                            from statsforecast.models import AutoARIMA, AutoETS

                            # Prepare for statsforecast format
                            df_sf = df_ts.rename(columns={date_col: 'ds', value_col: 'y'})
                            df_sf['unique_id'] = '1'

                            sf = StatsForecast(
                                models=[AutoARIMA(season_length=min(12, len(df_sf) // 2) or 1)],
                                freq='MS',  # Monthly start
                                fallback_model=AutoETS(season_length=1),
                            )
                            sf.fit(df_sf)

                            # Save model
                            model_name = f"{table_name}_forecast"
                            model_bytes = pickle.dumps(sf)
                            accuracy = {"mape": "auto", "method": "AutoARIMA", "data_points": len(df_sf)}

                            _save_model(project_slug, model_name, "forecast", "statsforecast/AutoARIMA",
                                       value_col, date_col, accuracy, row_count, model_bytes)
                            models_created += 1
                            logger.info(f"Created forecast model: {model_name}")
                    except Exception as e:
                        logger.debug(f"Forecast model failed for {table_name}: {e}")

                # 2. Anomaly detector (always, for numeric columns)
                if len(numeric_cols) >= 2:
                    try:
                        from sklearn.ensemble import IsolationForest

                        df_num = df[numeric_cols].dropna()
                        if len(df_num) >= 10:
                            iso = IsolationForest(contamination=0.1, random_state=42, n_estimators=100)
                            iso.fit(df_num)

                            model_name = f"{table_name}_anomaly"
                            model_bytes = pickle.dumps({"model": iso, "columns": numeric_cols})
                            accuracy = {"method": "IsolationForest", "contamination": 0.1, "features": len(numeric_cols)}

                            _save_model(project_slug, model_name, "anomaly", "sklearn/IsolationForest",
                                       None, json.dumps(numeric_cols), accuracy, row_count, model_bytes)
                            models_created += 1
                            logger.info(f"Created anomaly model: {model_name}")
                    except Exception as e:
                        logger.debug(f"Anomaly model failed for {table_name}: {e}")

            except Exception as e:
                logger.debug(f"ML scan failed for {table_name}: {e}")
                continue

        return {"status": "ok", "models_created": models_created}
    except Exception as e:
        logger.warning(f"Auto ML failed: {e}")
        return {"status": "error", "error": str(e), "models_created": 0}


def _save_model(project_slug, name, model_type, algorithm, target, features, accuracy, row_count, model_bytes):
    """Save or update ML model in dash_ml_models."""
    try:
        from sqlalchemy import text
        from sqlalchemy import create_engine as _ce
        from db.url import db_url
        engine = _ce(db_url)
        with engine.connect() as conn:
            # Delete existing model with same name
            conn.execute(text(
                "DELETE FROM public.dash_ml_models WHERE project_slug = :slug AND name = :name"
            ), {"slug": project_slug, "name": name})
            # Insert new
            conn.execute(text(
                "INSERT INTO public.dash_ml_models (project_slug, name, model_type, algorithm, target_column, features, accuracy, row_count, model_bytes) "
                "VALUES (:slug, :name, :type, :algo, :target, :features, :acc, :rows, :model)"
            ), {"slug": project_slug, "name": name, "type": model_type, "algo": algorithm,
                "target": target, "features": features, "acc": json.dumps(accuracy),
                "rows": row_count, "model": model_bytes})
            conn.commit()
    except Exception as e:
        logger.warning(f"Save model failed: {e}")


def _load_model(project_slug: str, model_name: str = None, model_type: str = None):
    """Load ML model from dash_ml_models."""
    try:
        from sqlalchemy import text
        from sqlalchemy import create_engine as _ce
        from db.url import db_url
        engine = _ce(db_url)
        with engine.connect() as conn:
            if model_name:
                row = conn.execute(text(
                    "SELECT name, model_type, algorithm, target_column, features, accuracy, model_bytes "
                    "FROM public.dash_ml_models WHERE project_slug = :slug AND name = :name"
                ), {"slug": project_slug, "name": model_name}).fetchone()
            elif model_type:
                row = conn.execute(text(
                    "SELECT name, model_type, algorithm, target_column, features, accuracy, model_bytes "
                    "FROM public.dash_ml_models WHERE project_slug = :slug AND model_type = :type "
                    "ORDER BY created_at DESC LIMIT 1"
                ), {"slug": project_slug, "type": model_type}).fetchone()
            else:
                return None

            if row:
                return {
                    "name": row[0], "model_type": row[1], "algorithm": row[2],
                    "target_column": row[3], "features": row[4],
                    "accuracy": json.loads(row[5]) if isinstance(row[5], str) else (row[5] or {}),
                    "model": pickle.loads(row[6]) if row[6] else None,
                }
    except Exception as e:
        logger.warning(f"Load model failed: {e}")
    return None


def _save_experiment(project_slug, experiment_type, model_name, algorithm, tier, question="", input_summary=None, result_data=None, accuracy=None):
    """Save ML experiment result to dash_ml_experiments."""
    try:
        from sqlalchemy import text, create_engine as _ce
        from db.url import db_url
        engine = _ce(db_url)
        with engine.connect() as conn:
            conn.execute(text(
                "INSERT INTO public.dash_ml_experiments (project_slug, experiment_type, model_name, algorithm, tier, question, input_summary, result_data, accuracy) "
                "VALUES (:slug, :type, :name, :algo, :tier, :q, :inp, :res, :acc)"
            ), {
                "slug": project_slug, "type": experiment_type, "name": model_name,
                "algo": algorithm, "tier": tier, "q": question,
                "inp": json.dumps(input_summary or {}), "res": json.dumps(result_data or {}),
                "acc": json.dumps(accuracy or {}),
            })
            conn.commit()
    except Exception as e:
        logger.debug(f"Save experiment failed: {e}")


def create_predict_tool(project_slug: str):
    """Create predict tool for agent."""
    from agno.tools import tool

    @tool(name="predict", description="Predict future values using pre-trained ML model (statsforecast). Use when user asks to predict, forecast, or project. Returns predicted values with algorithm details. Args: periods (int, default 3) — number of periods to forecast")
    def predict(periods: int = 3) -> str:
        model_info = _load_model(project_slug, model_type="forecast")
        if not model_info or not model_info["model"]:
            return "No forecast model available. Use llm_predict instead."

        try:
            sf = model_info["model"]
            forecast = sf.predict(h=periods)

            rows = []
            for i, row in forecast.iterrows():
                for col in forecast.columns:
                    if col not in ('unique_id', 'ds'):
                        val = row[col]
                        rows.append(f"Period {i+1}: {val:,.0f}" if abs(val) > 100 else f"Period {i+1}: {val:.2f}")

            result = f"FORECAST ({model_info['algorithm']}):\n"
            result += f"Target: {model_info['target_column']}\n"
            result += f"Method: {model_info['algorithm']}\n"
            result += f"Trained on: {model_info['accuracy'].get('data_points', '?')} data points\n\n"
            result += "\n".join(rows)
            ml_tag = f"[ML:FORECAST|model={model_info['name']}|algorithm={model_info['algorithm']}|accuracy={model_info['accuracy'].get('mape','?')}|data={model_info['accuracy'].get('data_points','?')} rows|tier=instant]"
            result = ml_tag + "\n" + result

            forecast_rows = []
            for i, row in forecast.iterrows():
                for col in forecast.columns:
                    if col not in ('unique_id', 'ds'):
                        forecast_rows.append({"period": i+1, "value": float(row[col])})

            _save_experiment(project_slug, "forecast", model_info["name"], model_info["algorithm"], "instant",
                result_data={"predictions": forecast_rows, "periods": periods},
                accuracy=model_info["accuracy"])
            return result
        except Exception as e:
            return f"Prediction failed: {e}. Use llm_predict as fallback."

    return predict


def create_feature_importance_tool(project_slug: str, engine=None, schema: str = None):
    """Create feature importance tool for agent."""
    from agno.tools import tool

    @tool(name="feature_importance", description="Find what drives a metric — train quick LightGBM model and return top factors with percentages. Use when user asks 'what drives X', 'why is X', 'factors affecting X'. Args: table (str), target_column (str)")
    def feature_importance(table: str, target_column: str) -> str:
        try:
            import pandas as pd
            from db import get_sql_engine
            eng = engine or get_sql_engine()
            qualified = f'"{schema}"."{table}"' if schema else f'"{table}"'

            df = pd.read_sql(f"SELECT * FROM {qualified} LIMIT 1000", eng)
            if target_column not in df.columns:
                return f"Column '{target_column}' not found in table '{table}'"

            # Prepare features (numeric + encoded categoricals)
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            if target_column in numeric_cols:
                numeric_cols.remove(target_column)

            # Remove ID-like columns
            feature_cols = [c for c in numeric_cols if c.lower() not in ('id', 'index', 'row_number')]

            # Encode categorical columns (simple label encoding)
            cat_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
            for col in cat_cols[:5]:  # Max 5 categorical
                if df[col].nunique() < 50:
                    df[f"{col}_encoded"] = df[col].astype('category').cat.codes
                    feature_cols.append(f"{col}_encoded")

            if not feature_cols:
                return "Not enough features to analyze. Need at least 2 numeric columns."

            df_clean = df[feature_cols + [target_column]].dropna()
            if len(df_clean) < 10:
                return "Not enough clean data rows (need at least 10)."

            X = df_clean[feature_cols]
            y = df_clean[target_column]

            import lightgbm as lgb
            model = lgb.LGBMRegressor(n_estimators=100, max_depth=5, verbose=-1, random_state=42)
            model.fit(X, y)

            importances = model.feature_importances_
            total = sum(importances)
            if total == 0:
                return "Could not determine feature importance."

            features_ranked = sorted(
                zip(feature_cols, importances),
                key=lambda x: x[1], reverse=True
            )

            r2 = model.score(X, y)

            result = f"FEATURE IMPORTANCE (LightGBM, R\u00b2={r2:.2f}):\n"
            result += f"Target: {target_column}\n"
            result += f"Algorithm: LightGBM/GradientBoosting\n"
            result += f"Data: {len(df_clean)} rows, {len(feature_cols)} features\n\n"
            result += "TOP FACTORS:\n"
            for fname, imp in features_ranked[:10]:
                pct = imp / total * 100
                bar = "\u2588" * int(pct / 5)
                # Clean up encoded column names
                display_name = fname.replace("_encoded", "")
                result += f"  {bar} {display_name}: {pct:.1f}%\n"

            top3 = ", ".join(f"{fname.replace('_encoded','')} {imp/total*100:.0f}%" for fname, imp in features_ranked[:3])
            ml_tag = f"[ML:DRIVERS|algorithm=LightGBM|r2={r2:.2f}|target={target_column}|features={len(feature_cols)}|top={top3}|data={len(df_clean)} rows]"
            result = ml_tag + "\n" + result

            # Compute rich artifacts for ML Insights
            actual = y.tolist()[:50]
            predicted = model.predict(X).tolist()[:50]
            residuals = (y - model.predict(X)).tolist()[:50]

            # Column stats
            col_stats = {}
            for c in feature_cols:
                vals = df_clean[c].dropna()
                col_stats[c] = {"min": float(vals.min()), "max": float(vals.max()), "mean": float(vals.mean()), "std": float(vals.std())}

            # Correlation between features
            corr_data = {}
            try:
                corr = X.corr()
                for c1 in corr.columns:
                    for c2 in corr.columns:
                        if c1 < c2:
                            corr_data[f"{c1}__{c2}"] = round(float(corr.loc[c1, c2]), 3)
            except Exception:
                pass

            # Sample data (first 5 rows)
            sample = df_clean.head(5).values.tolist()
            sample_cols = list(df_clean.columns)

            _save_experiment(project_slug, "importance", f"{table}_{target_column}", "LightGBM", "on-demand",
                input_summary={"table": table, "target": target_column, "rows": len(df_clean), "features": len(feature_cols), "columns": feature_cols},
                result_data={
                    "factors": [{"name": fname.replace("_encoded",""), "importance": round(imp/total*100, 1)} for fname, imp in features_ranked[:10]],
                    "actual_vs_predicted": {"actual": actual, "predicted": predicted},
                    "residuals": residuals,
                    "correlation": corr_data,
                    "column_stats": col_stats,
                    "sample_data": sample,
                    "sample_columns": sample_cols,
                    "hyperparameters": {"n_estimators": 100, "max_depth": 5, "random_state": 42},
                },
                accuracy={"r2": round(r2, 4)})
            return result
        except ImportError:
            return "LightGBM not installed. Cannot compute feature importance."
        except Exception as e:
            return f"Feature importance failed: {e}"

    return feature_importance


def create_anomaly_ml_tool(project_slug: str, engine=None, schema: str = None):
    """Create ML anomaly detection tool for agent."""
    from agno.tools import tool

    @tool(name="detect_anomalies_ml", description="Detect anomalies using pre-trained IsolationForest ML model. More accurate than Z-score. Use when user asks about outliers, unusual data, anomalies. Args: table (str)")
    def detect_anomalies_ml(table: str) -> str:
        model_info = _load_model(project_slug, model_type="anomaly")
        if not model_info or not model_info["model"]:
            return "No anomaly model available. Use detect_anomalies tool (Z-score) instead."

        try:
            import pandas as pd
            import re as _re
            from db import get_sql_engine
            _schema = schema or _re.sub(r"[^a-z0-9_]", "_", project_slug.lower())[:63]
            _engine = engine or get_sql_engine()

            data = model_info["model"]
            iso_model = data["model"]
            columns = data["columns"]

            qualified = f'"{_schema}"."{table}"' if _schema else f'"{table}"'
            df = pd.read_sql(f"SELECT * FROM {qualified} LIMIT 1000", _engine)
            available_cols = [c for c in columns if c in df.columns]
            if not available_cols:
                return f"Model columns {columns} not found in table '{table}'"

            df_num = df[available_cols].dropna()
            if len(df_num) < 2:
                return "Not enough data for anomaly detection."

            predictions = iso_model.predict(df_num)
            scores = iso_model.decision_function(df_num)

            anomaly_idx = [i for i, p in enumerate(predictions) if p == -1]

            result = f"ANOMALY DETECTION (IsolationForest):\n"
            result += f"Algorithm: sklearn/IsolationForest\n"
            result += f"Scanned: {len(df_num)} rows, {len(available_cols)} features\n"
            result += f"Anomalies found: {len(anomaly_idx)}\n\n"

            if anomaly_idx:
                result += "ANOMALOUS ROWS:\n"
                for idx in anomaly_idx[:10]:  # Show max 10
                    row = df.iloc[idx]
                    row_desc = ", ".join(f"{c}={row[c]}" for c in available_cols[:5] if pd.notna(row[c]))
                    result += f"  Row {idx}: {row_desc} (score: {scores[idx]:.3f})\n"
                if len(anomaly_idx) > 10:
                    result += f"  ... and {len(anomaly_idx) - 10} more\n"
            else:
                result += "No anomalies detected — all data appears normal.\n"

            # Severity breakdown
            high = len([idx for idx in anomaly_idx if scores[idx] < -0.1])
            medium = len([idx for idx in anomaly_idx if -0.1 <= scores[idx] < -0.05])
            low = len(anomaly_idx) - high - medium

            # Full anomaly details with all column values
            anomaly_details = []
            for idx in anomaly_idx[:20]:
                row_data = {c: float(df.iloc[idx][c]) if c in available_cols else str(df.iloc[idx][c]) for c in df.columns[:8] if pd.notna(df.iloc[idx][c])}
                row_data["_row"] = int(idx)
                row_data["_score"] = float(scores[idx])
                row_data["_severity"] = "HIGH" if scores[idx] < -0.1 else "MEDIUM" if scores[idx] < -0.05 else "LOW"
                anomaly_details.append(row_data)

            # Normal data stats for comparison
            normal_idx = [i for i, p in enumerate(predictions) if p == 1]
            normal_stats = {}
            for c in available_cols:
                normal_vals = df_num.iloc[normal_idx][c]
                normal_stats[c] = {"mean": float(normal_vals.mean()), "std": float(normal_vals.std()), "min": float(normal_vals.min()), "max": float(normal_vals.max())}

            # Scatter plot data (first 2 features)
            scatter = None
            if len(available_cols) >= 2:
                scatter = {
                    "x_col": available_cols[0],
                    "y_col": available_cols[1],
                    "normal": [[float(df_num.iloc[i][available_cols[0]]), float(df_num.iloc[i][available_cols[1]])] for i in normal_idx[:100]],
                    "anomaly": [[float(df_num.iloc[i][available_cols[0]]), float(df_num.iloc[i][available_cols[1]])] for i in anomaly_idx],
                }

            ml_tag = f"[ML:ANOMALY|algorithm=IsolationForest|scanned={len(df_num)}|found={len(anomaly_idx)}|high={high}|features={len(available_cols)}]"
            result = ml_tag + "\n" + result
            _save_experiment(project_slug, "anomaly", f"{table}_anomaly", "IsolationForest", "instant",
                input_summary={"table": table, "rows": len(df_num), "features": len(available_cols), "columns": available_cols},
                result_data={
                    "total_anomalies": len(anomaly_idx),
                    "severity": {"high": high, "medium": medium, "low": low},
                    "anomalies": anomaly_details,
                    "normal_stats": normal_stats,
                    "scatter": scatter,
                    "contamination": 0.1,
                })
            return result
        except Exception as e:
            return f"Anomaly detection failed: {e}"

    return detect_anomalies_ml


def create_llm_predict_tool(project_slug: str, engine=None, schema: str = None):
    """Create LLM prediction fallback tool for agent."""
    from agno.tools import tool

    @tool(name="llm_predict", description="Predict future values using LLM analysis (fallback when no ML model exists). Gets historical data via SQL, sends to LLM for trend analysis. Args: table (str), date_column (str), value_column (str), periods (int, default 3)")
    def llm_predict(table: str, date_column: str, value_column: str, periods: int = 3) -> str:
        try:
            import pandas as pd
            from db import get_sql_engine
            from dash.settings import training_llm_call

            eng = engine or get_sql_engine()
            qualified = f'"{schema}"."{table}"' if schema else f'"{table}"'

            df = pd.read_sql(
                f"SELECT \"{date_column}\", \"{value_column}\" FROM {qualified} "
                f"WHERE \"{value_column}\" IS NOT NULL ORDER BY \"{date_column}\" DESC LIMIT 24",
                eng
            )

            if len(df) < 3:
                return "Not enough historical data (need at least 3 data points)."

            # Format data for LLM
            data_str = "\n".join(f"  {row[date_column]}: {row[value_column]}" for _, row in df.iterrows())

            prompt = f"""Analyze this time series data and predict the next {periods} periods.

Historical data ({value_column} by {date_column}):
{data_str}

Return ONLY valid JSON:
{{
  "predictions": [{{"period": "label", "value": number, "reasoning": "brief"}}],
  "trend": "increasing/decreasing/flat/seasonal",
  "confidence": "high/medium/low",
  "growth_rate": "X%",
  "method": "LLM trend analysis"
}}"""

            _t0 = time.time()
            raw = training_llm_call(prompt, "extraction")
            _duration = int((time.time() - _t0) * 1000)
            if not raw:
                return "LLM prediction failed — no response."

            # Parse response
            clean = raw.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            if clean.startswith("json"):
                clean = clean[4:].strip()

            parsed = json.loads(clean)

            result = f"PREDICTION (LLM Analysis):\n"
            result += f"Method: LLM trend analysis (Tier 2 — no pre-trained model)\n"
            result += f"Based on: {len(df)} historical data points\n"
            result += f"Trend: {parsed.get('trend', '?')}\n"
            result += f"Growth rate: {parsed.get('growth_rate', '?')}\n"
            result += f"Confidence: {parsed.get('confidence', '?')}\n\n"
            result += "FORECAST:\n"
            for p in parsed.get("predictions", []):
                result += f"  {p.get('period', '?')}: {p.get('value', '?')} — {p.get('reasoning', '')}\n"

            ml_tag = f"[ML:FORECAST|model=llm_analysis|algorithm=LLM|accuracy={parsed.get('confidence','?')}|data={len(df)} rows|tier=llm|trend={parsed.get('trend','?')}]"
            result = ml_tag + "\n" + result
            _save_experiment(project_slug, "forecast", f"{table}_{value_column}", "LLM", "llm",
                input_summary={"table": table, "date_col": date_column, "value_col": value_column, "rows": len(df), "training_duration_ms": _duration},
                result_data=parsed, accuracy={"confidence": parsed.get("confidence", "?")})
            return result
        except Exception as e:
            return f"LLM prediction failed: {e}"

    return llm_predict
