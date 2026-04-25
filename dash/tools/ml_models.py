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


def _preprocess_df(df, target_column=None):
    """Shared preprocessing: impute missing values, add temporal features, encode categoricals.
    Returns (X, y, feature_cols, preprocessing_info)."""
    import pandas as pd
    import numpy as np

    info = {"imputed_cols": [], "temporal_features": [], "encoded_cols": [], "original_rows": len(df), "rows_after": 0}

    # 1. Separate features
    numeric_cols = [c for c in df.select_dtypes(include=['number']).columns
                    if c.lower() not in ('id', 'index', 'row_number') and c != target_column]
    cat_cols = [c for c in df.select_dtypes(include=['object', 'category']).columns
                if c != target_column]

    # 2. Impute missing values (median for numeric, mode for categorical) — NOT dropna
    from sklearn.impute import SimpleImputer
    if numeric_cols:
        num_imputer = SimpleImputer(strategy='median')
        df[numeric_cols] = num_imputer.fit_transform(df[numeric_cols])
        imputed = [c for c in numeric_cols if df[c].isna().sum() == 0]
        info["imputed_cols"] = [c for c in numeric_cols]

    if cat_cols:
        cat_imputer = SimpleImputer(strategy='most_frequent')
        df[cat_cols] = cat_imputer.fit_transform(df[cat_cols])

    # 3. Temporal features from date columns
    date_cols = [c for c in df.columns if df[c].dtype in ['datetime64[ns]'] or
                 (df[c].dtype == 'object' and pd.to_datetime(df[c], errors='coerce').notna().sum() > len(df) * 0.5)]
    for dc in date_cols[:1]:  # First date column only
        dt = pd.to_datetime(df[dc], errors='coerce')
        if dt.notna().sum() > len(df) * 0.3:
            df['_month'] = dt.dt.month
            df['_quarter'] = dt.dt.quarter
            df['_dayofweek'] = dt.dt.dayofweek
            df['_is_weekend'] = (dt.dt.dayofweek >= 5).astype(int)
            numeric_cols.extend(['_month', '_quarter', '_dayofweek', '_is_weekend'])
            info["temporal_features"] = ['_month', '_quarter', '_dayofweek', '_is_weekend']

    # 4. Encode categoricals (label encoding for low cardinality)
    feature_cols = list(numeric_cols)
    for col in cat_cols[:5]:
        if df[col].nunique() < 50:
            df[f"{col}_enc"] = df[col].astype('category').cat.codes
            feature_cols.append(f"{col}_enc")
            info["encoded_cols"].append(col)

    # 5. Build X, y
    if target_column and target_column in df.columns:
        valid = df[feature_cols + [target_column]].dropna(subset=[target_column])
    else:
        valid = df[feature_cols].copy()

    info["rows_after"] = len(valid)
    X = valid[feature_cols] if feature_cols else valid
    y = valid[target_column] if target_column and target_column in valid.columns else None

    return X, y, feature_cols, info


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
            conn.execute(text("ALTER TABLE public.dash_ml_models ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active'"))
            conn.execute(text("ALTER TABLE public.dash_ml_models ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1"))
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

                if row_count < 5:
                    continue  # Too small
                if row_count > 1000:
                    # Queue to ML worker for heavy training
                    try:
                        _jeng = create_engine(db_url)
                        with _jeng.connect() as _jc:
                            _jc.execute(text(
                                "INSERT INTO public.dash_ml_jobs (project_slug, table_name, job_type) "
                                "VALUES (:s, :t, 'anomaly') ON CONFLICT DO NOTHING"
                            ), {"s": project_slug, "t": table_name})
                            _jc.commit()
                        _jeng.dispose()
                        logger.info(f"Queued ML job for {table_name} ({row_count} rows)")
                    except Exception:
                        pass
                    continue

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

                            # Validate on holdout
                            hold_out = max(2, len(df_sf) // 5)
                            if len(df_sf) > hold_out + 5:
                                train_sf = df_sf.iloc[:-hold_out]
                                test_sf = df_sf.iloc[-hold_out:]
                                sf_val = StatsForecast(models=[AutoARIMA(season_length=min(12, len(train_sf)//2) or 1)], freq='MS', fallback_model=AutoETS(season_length=1))
                                sf_val.fit(train_sf)
                                fc_val = sf_val.predict(h=hold_out)
                                try:
                                    from sklearn.metrics import mean_absolute_percentage_error
                                    mape_val = mean_absolute_percentage_error(test_sf['y'].values, fc_val['AutoARIMA'].values)
                                    accuracy["mape"] = round(mape_val * 100, 1)
                                except Exception:
                                    pass

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
    engine = None
    try:
        from sqlalchemy import text
        from sqlalchemy import create_engine as _ce
        from db.url import db_url
        engine = _ce(db_url)
        with engine.connect() as conn:
            # Archive old version instead of deleting
            conn.execute(text(
                "UPDATE public.dash_ml_models SET status = 'archived' WHERE project_slug = :slug AND name = :name AND (status IS NULL OR status = 'active')"
            ), {"slug": project_slug, "name": name})
            # Get next version number
            ver = conn.execute(text(
                "SELECT COALESCE(MAX(version), 0) + 1 FROM public.dash_ml_models WHERE project_slug = :slug AND name = :name"
            ), {"slug": project_slug, "name": name}).scalar()
            # Insert new
            conn.execute(text(
                "INSERT INTO public.dash_ml_models (project_slug, name, model_type, algorithm, target_column, features, accuracy, row_count, model_bytes, version) "
                "VALUES (:slug, :name, :type, :algo, :target, :features, :acc, :rows, :model, :ver)"
            ), {"slug": project_slug, "name": name, "type": model_type, "algo": algorithm,
                "target": target, "features": features, "acc": json.dumps(accuracy),
                "rows": row_count, "model": model_bytes, "ver": ver})
            conn.commit()
    except Exception as e:
        logger.warning(f"Save model failed: {e}")
    finally:
        if engine:
            engine.dispose()


def _load_model(project_slug: str, model_name: str = None, model_type: str = None):
    """Load ML model from dash_ml_models."""
    engine = None
    try:
        from sqlalchemy import text
        from sqlalchemy import create_engine as _ce
        from db.url import db_url
        engine = _ce(db_url)
        with engine.connect() as conn:
            if model_name:
                row = conn.execute(text(
                    "SELECT name, model_type, algorithm, target_column, features, accuracy, model_bytes "
                    "FROM public.dash_ml_models WHERE project_slug = :slug AND name = :name AND (status IS NULL OR status = 'active')"
                ), {"slug": project_slug, "name": model_name}).fetchone()
            elif model_type:
                row = conn.execute(text(
                    "SELECT name, model_type, algorithm, target_column, features, accuracy, model_bytes "
                    "FROM public.dash_ml_models WHERE project_slug = :slug AND model_type = :type AND (status IS NULL OR status = 'active') "
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
    finally:
        if engine:
            engine.dispose()
    return None


def _save_experiment(project_slug, experiment_type, model_name, algorithm, tier, question="", input_summary=None, result_data=None, accuracy=None):
    """Save ML experiment result to dash_ml_experiments."""
    engine = None
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
    finally:
        if engine:
            engine.dispose()


def create_predict_tool(project_slug: str, engine=None, schema: str = None):
    """Create predict tool for agent. Auto-falls back to LLM if no ML model exists."""
    from agno.tools import tool

    @tool(name="predict", description="Predict/forecast future values. Uses pre-trained ML model if available, falls back to LLM trend analysis. This is the ONLY tool for predictions — do NOT call any other forecast tool. Args: periods (int, default 3), table (str, optional), date_column (str, optional), value_column (str, optional)")
    def predict(periods: int = 3, table: str = "", date_column: str = "", value_column: str = "") -> str:
        # Try ML model first
        model_info = _load_model(project_slug, model_type="forecast")
        if model_info and model_info.get("model"):
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
                logger.warning(f"ML forecast failed, falling back to LLM: {e}")

        # Fallback: LLM trend analysis
        try:
            import pandas as pd
            from db import get_sql_engine
            from dash.settings import training_llm_call

            eng = engine or get_sql_engine()
            _schema = schema or __import__('re').sub(r"[^a-z0-9_]", "_", project_slug.lower())[:63]

            # Auto-detect table/columns if not provided
            if not table or not date_column or not value_column:
                from sqlalchemy import inspect as sa_inspect
                insp = sa_inspect(eng)
                tables = insp.get_table_names(schema=_schema)
                if not tables:
                    return "No data tables found for forecasting."
                # Find first table with date + numeric columns
                for t in tables[:5]:
                    qualified = f'"{_schema}"."{t}"'
                    try:
                        df_sample = pd.read_sql(f"SELECT * FROM {qualified} LIMIT 50", eng)
                        date_cols = [c for c in df_sample.columns if df_sample[c].dtype in ['datetime64[ns]', 'object'] and pd.to_datetime(df_sample[c], errors='coerce').notna().sum() > len(df_sample) * 0.3]
                        num_cols = [c for c in df_sample.select_dtypes(include=['number']).columns if c.lower() not in ('id', 'index', 'row_number')]
                        if date_cols and num_cols:
                            table, date_column, value_column = t, date_cols[0], num_cols[0]
                            break
                    except Exception:
                        continue
                if not table:
                    return "No suitable table with date + numeric columns found."

            qualified = f'"{_schema}"."{table}"'
            df = pd.read_sql(
                f'SELECT "{date_column}", "{value_column}" FROM {qualified} WHERE "{value_column}" IS NOT NULL ORDER BY "{date_column}" DESC LIMIT 24',
                eng
            )
            if len(df) < 3:
                return "Not enough historical data (need at least 3 data points)."

            data_str = "\n".join(f"  {row[date_column]}: {row[value_column]}" for _, row in df.iterrows())
            prompt = f"""Analyze this time series data and predict the next {periods} periods.

Historical data ({value_column} by {date_column}):
{data_str}

Return ONLY valid JSON:
{{"predictions": [{{"period": "label", "value": number, "reasoning": "brief"}}], "trend": "increasing/decreasing/flat/seasonal", "confidence": "high/medium/low", "growth_rate": "X%", "method": "LLM trend analysis", "historical_summary": "1-2 sentence summary of historical pattern"}}"""

            _t0 = time.time()
            raw = training_llm_call(prompt, "ml_prediction")
            _duration = int((time.time() - _t0) * 1000)
            if not raw:
                return "LLM prediction failed — no response."

            clean = raw.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            if clean.startswith("json"):
                clean = clean[4:].strip()
            parsed = json.loads(clean)

            # Build historical data for context
            df_sorted = df.sort_values(date_column)
            historical = []
            for _, row in df_sorted.iterrows():
                historical.append({"period": str(row[date_column])[:10], "value": float(row[value_column]) if pd.notna(row[value_column]) else 0})

            result = f"PREDICTION (LLM Analysis):\nMethod: LLM trend analysis (no pre-trained model, using GPT)\nBased on: {len(df)} historical data points\nTrend: {parsed.get('trend', '?')}\nGrowth rate: {parsed.get('growth_rate', '?')}\nConfidence: {parsed.get('confidence', '?')}\n\n"
            result += f"HISTORICAL DATA (last {min(len(historical), 12)} periods):\n"
            for h in historical[-12:]:
                result += f"  {h['period']}: {h['value']:,.2f}\n"
            result += f"\nFORECAST (next {periods} periods):\n"
            for p in parsed.get("predictions", []):
                result += f"  {p.get('period', '?')}: {p.get('value', '?')} — {p.get('reasoning', '')}\n"

            ml_tag = f"[ML:FORECAST|model=llm_analysis|algorithm=LLM|accuracy={parsed.get('confidence','?')}|data={len(df)} rows|tier=llm|trend={parsed.get('trend','?')}]"
            result = ml_tag + "\n" + result
            _save_experiment(project_slug, "forecast", f"{table}_{value_column}", "LLM", "llm",
                input_summary={"table": table, "date_col": date_column, "value_col": value_column, "rows": len(df), "training_duration_ms": _duration},
                result_data={**parsed, "historical": historical[-12:]},
                accuracy={"confidence": parsed.get("confidence", "?")})
            return result
        except Exception as e:
            return f"Prediction failed: {e}"

    return predict


def create_feature_importance_tool(project_slug: str, engine=None, schema: str = None):
    """Create feature importance tool for agent."""
    from agno.tools import tool

    @tool(name="feature_importance", description="Find what drives a metric — train quick LightGBM model and return top factors with percentages. Use when user asks 'what drives X', 'why is X', 'factors affecting X'. Args: table (str), target_column (str)")
    def feature_importance(table: str, target_column: str) -> str:
        try:
            import pandas as pd
            import numpy as np
            from db import get_sql_engine
            eng = engine or get_sql_engine()
            qualified = f'"{schema}"."{table}"' if schema else f'"{table}"'

            df = pd.read_sql(f"SELECT * FROM {qualified} LIMIT 1000", eng)
            if target_column not in df.columns:
                return f"Column '{target_column}' not found in table '{table}'"

            # Shared preprocessing: impute, temporal features, encode
            X, y, feature_cols, prep_info = _preprocess_df(df, target_column=target_column)

            if not feature_cols:
                return "Not enough features to analyze. Need at least 2 numeric columns."
            if len(X) < 10:
                return "Not enough data rows (need at least 10)."

            # Hyperparameter tuning with GridSearchCV
            import lightgbm as lgb
            from sklearn.model_selection import GridSearchCV, cross_val_score

            param_grid = {
                'n_estimators': [50, 100, 200],
                'max_depth': [3, 5, 7],
                'learning_rate': [0.05, 0.1],
            }
            n_cv = min(5, max(2, len(X) // 10))
            base_model = lgb.LGBMRegressor(verbose=-1, random_state=42)
            grid = GridSearchCV(base_model, param_grid, cv=n_cv, scoring='r2', n_jobs=-1, refit=True)
            grid.fit(X, y)
            model = grid.best_estimator_

            importances = model.feature_importances_
            total = sum(importances)
            if total == 0:
                return "Could not determine feature importance."

            features_ranked = sorted(
                zip(feature_cols, importances),
                key=lambda x: x[1], reverse=True
            )

            r2 = model.score(X, y)

            # Better metrics: RMSE, MAE
            from sklearn.metrics import mean_squared_error, mean_absolute_error
            y_pred = model.predict(X)
            rmse = float(np.sqrt(mean_squared_error(y, y_pred)))
            mae = float(mean_absolute_error(y, y_pred))

            # Cross-validation
            cv_data = {}
            try:
                cv_scores_arr = cross_val_score(model, X, y, cv=n_cv, scoring='r2')
                cv_data = {"cv_mean": round(float(cv_scores_arr.mean()), 4), "cv_std": round(float(cv_scores_arr.std()), 4), "cv_scores": [round(float(s), 4) for s in cv_scores_arr], "cv_folds": n_cv,
                           "best_params": grid.best_params_}
            except Exception:
                pass

            result = f"FEATURE IMPORTANCE (LightGBM, R\u00b2={r2:.2f}, RMSE={rmse:.2f}, MAE={mae:.2f}):\n"
            result += f"Target: {target_column}\n"
            result += f"Algorithm: LightGBM (tuned: {grid.best_params_})\n"
            result += f"Data: {len(X)} rows, {len(feature_cols)} features"
            if prep_info.get("temporal_features"):
                result += f" (+{len(prep_info['temporal_features'])} temporal)"
            if prep_info.get("imputed_cols"):
                result += f", {len(prep_info['imputed_cols'])} cols imputed"
            result += "\n\n"
            result += "TOP FACTORS:\n"
            for fname, imp in features_ranked[:10]:
                pct = imp / total * 100
                bar = "\u2588" * int(pct / 5)
                # Clean up encoded column names
                display_name = fname.replace("_encoded", "")
                result += f"  {bar} {display_name}: {pct:.1f}%\n"

            if cv_data:
                result += f"\nCROSS-VALIDATION ({cv_data.get('cv_folds',0)}-fold): R²={cv_data.get('cv_mean',0):.2f} ± {cv_data.get('cv_std',0):.2f}\n"

            # SHAP explanations (per-row feature impact)
            shap_summary = []
            try:
                import shap
                explainer = shap.TreeExplainer(model)
                shap_vals = explainer.shap_values(X.head(20))
                for si in range(min(5, len(shap_vals))):
                    row_shap = {col.replace("_encoded", ""): round(float(shap_vals[si][j]), 4) for j, col in enumerate(feature_cols)}
                    shap_summary.append(row_shap)
                if shap_summary:
                    result += f"\nSHAP (per-row explanations available for top {len(shap_summary)} rows)\n"
            except Exception:
                pass

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
                    "cross_validation": cv_data,
                    "shap_values": shap_summary,
                    "hyperparameters": {"n_estimators": 100, "max_depth": 5, "random_state": 42},
                },
                accuracy={"r2": round(r2, 4), "rmse": round(rmse, 4), "mae": round(mae, 4),
                          "cv_mean": cv_data.get("cv_mean"), "cv_std": cv_data.get("cv_std"),
                          "best_params": cv_data.get("best_params"), "preprocessing": prep_info})
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

            # Normal data stats for comparison
            normal_idx = [i for i, p in enumerate(predictions) if p == 1]
            normal_stats = {}
            for c in available_cols:
                normal_vals = df_num.iloc[normal_idx][c]
                normal_stats[c] = {"mean": float(normal_vals.mean()), "std": float(normal_vals.std()), "min": float(normal_vals.min()), "max": float(normal_vals.max())}

            # Full anomaly details with all column values
            anomaly_details = []
            for idx in anomaly_idx[:20]:
                row_data = {c: float(df.iloc[idx][c]) if c in available_cols else str(df.iloc[idx][c]) for c in df.columns[:8] if pd.notna(df.iloc[idx][c])}
                row_data["_row"] = int(idx)
                row_data["_score"] = float(scores[idx])
                row_data["_severity"] = "HIGH" if scores[idx] < -0.1 else "MEDIUM" if scores[idx] < -0.05 else "LOW"
                # Explain WHY this is anomalous
                explanations = []
                for col in available_cols:
                    if col in row_data and col in normal_stats:
                        val = float(row_data[col]) if isinstance(row_data[col], (int, float)) else 0
                        n_mean = normal_stats[col]["mean"]
                        n_std = max(normal_stats[col]["std"], 0.001)
                        z = (val - n_mean) / n_std
                        if abs(z) > 1.5:
                            direction = "above" if z > 0 else "below"
                            explanations.append(f"{col}: {val:,.0f} is {abs(z):.1f}x std {direction} normal ({n_mean:,.0f})")
                row_data["_explanation"] = explanations
                anomaly_details.append(row_data)

            if anomaly_idx:
                result += "\nWHY THESE ARE ANOMALIES:\n"
                for detail in anomaly_details[:5]:
                    if detail.get("_explanation"):
                        result += f"  Row {detail['_row']}: {'; '.join(detail['_explanation'][:3])}\n"

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

            # Create SQL view with anomaly flags (so Analyst can query it)
            try:
                from sqlalchemy import text as _vt
                from sqlalchemy import create_engine as _vce
                from db.url import db_url as _vurl
                _veng = _vce(_vurl)
                try:
                    view_name = f"{table}_anomalies"
                    qualified_view = f'"{_schema}"."{view_name}"' if _schema else f'"{view_name}"'
                    qualified_src = f'"{_schema}"."{table}"' if _schema else f'"{table}"'
                    anomaly_set = ",".join(str(idx) for idx in anomaly_idx)
                    if anomaly_set:
                        with _veng.connect() as _vc:
                            _vc.execute(_vt(f"""
                                CREATE OR REPLACE VIEW {qualified_view} AS
                                SELECT t.*, CASE WHEN rn IN ({anomaly_set}) THEN true ELSE false END AS is_anomaly
                                FROM (SELECT *, ROW_NUMBER() OVER () - 1 AS rn FROM {qualified_src}) t
                            """))
                            _vc.commit()
                        result += f"\n[Created view: {view_name} — query with: SELECT * FROM {view_name} WHERE is_anomaly = true]\n"
                finally:
                    _veng.dispose()
            except Exception:
                pass

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
            raw = training_llm_call(prompt, "ml_prediction")
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


def create_classify_tool(project_slug: str, engine=None, schema: str = None):
    """Create classification tool for agent."""
    from agno.tools import tool

    @tool(name="classify", description="Train a classifier to predict categories. Use when user asks to predict churn, classify risk, which category. Args: table (str), target_column (str)")
    def classify(table: str, target_column: str) -> str:
        try:
            import pandas as pd
            import numpy as np
            from sklearn.ensemble import GradientBoostingClassifier
            from sklearn.model_selection import train_test_split, GridSearchCV, cross_val_score
            from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, confusion_matrix
            from sklearn.preprocessing import LabelEncoder
            from db import get_sql_engine

            eng = engine or get_sql_engine()
            _schema = schema or __import__('re').sub(r"[^a-z0-9_]", "_", project_slug.lower())[:63]
            qualified = f'"{_schema}"."{table}"' if _schema else f'"{table}"'

            df = pd.read_sql(f"SELECT * FROM {qualified} LIMIT 1000", eng)
            if target_column not in df.columns:
                return f"Column '{target_column}' not found in table '{table}'"

            # Encode target first (before preprocessing removes it)
            le = LabelEncoder()
            df['_target'] = le.fit_transform(df[target_column].astype(str))
            classes = list(le.classes_)

            # Shared preprocessing: impute, temporal features, encode
            X, _, feature_cols, prep_info = _preprocess_df(df, target_column='_target')

            if not feature_cols:
                return "Not enough features for classification."

            y = df.loc[X.index, '_target']
            if len(X) < 10:
                return "Need at least 10 rows for classification."

            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y if len(classes) > 1 and min(y.value_counts()) >= 2 else None)

            # Hyperparameter tuning
            param_grid = {'n_estimators': [50, 100, 200], 'max_depth': [3, 4, 6], 'learning_rate': [0.05, 0.1]}
            n_cv = min(5, max(2, len(X_train) // 10))
            grid = GridSearchCV(GradientBoostingClassifier(random_state=42), param_grid, cv=n_cv, scoring='f1_weighted', n_jobs=-1, refit=True)
            grid.fit(X_train, y_train)
            clf = grid.best_estimator_

            y_pred = clf.predict(X_test)
            acc = accuracy_score(y_test, y_pred)
            f1 = f1_score(y_test, y_pred, average='weighted', zero_division=0)
            prec = precision_score(y_test, y_pred, average='weighted', zero_division=0)
            rec = recall_score(y_test, y_pred, average='weighted', zero_division=0)
            cm = confusion_matrix(y_test, y_pred).tolist()

            # Cross-validation
            cv_scores = cross_val_score(clf, X, y, cv=n_cv, scoring='f1_weighted')

            # Feature importance
            importances = clf.feature_importances_
            total = sum(importances) or 1
            features_ranked = sorted(zip(feature_cols, importances), key=lambda x: x[1], reverse=True)

            # Class distribution
            class_dist = [{"class": classes[int(c)], "count": int((y == c).sum())} for c in sorted(y.unique())]

            result = f"[ML:CLASSIFY|algorithm=GradientBoosting|accuracy={acc:.2f}|f1={f1:.2f}|classes={len(classes)}|data={len(X)} rows]\n"
            result += f"CLASSIFICATION (GradientBoosting, tuned: {grid.best_params_}):\n"
            result += f"Target: {target_column} ({len(classes)} classes)\n"
            result += f"Data: {len(X)} rows, {len(feature_cols)} features"
            if prep_info.get("temporal_features"):
                result += f" (+{len(prep_info['temporal_features'])} temporal)"
            result += f"\n\nMETRICS:\n  Accuracy: {acc:.1%}\n  F1 Score: {f1:.1%}\n  Precision: {prec:.1%}\n  Recall: {rec:.1%}\n"
            result += f"  CV F1 ({n_cv}-fold): {cv_scores.mean():.1%} \u00b1 {cv_scores.std():.1%}\n\n"
            result += "CLASS DISTRIBUTION:\n"
            for cd in class_dist:
                result += f"  {cd['class']}: {cd['count']} rows\n"
            result += "\nTOP PREDICTORS:\n"
            for fname, imp in features_ranked[:8]:
                pct = imp / total * 100
                result += f"  {fname.replace('_enc', '')}: {pct:.1f}%\n"

            _save_experiment(project_slug, "classification", f"{table}_{target_column}", "GradientBoosting", "on-demand",
                input_summary={"table": table, "target": target_column, "rows": len(X), "features": len(feature_cols)},
                result_data={"classes": class_dist, "factors": [{"name": f.replace("_enc",""), "importance": round(i/total*100,1)} for f, i in features_ranked[:10]],
                             "confusion_matrix": cm, "class_names": classes},
                accuracy={"accuracy": round(acc, 4), "f1": round(f1, 4), "precision": round(prec, 4), "recall": round(rec, 4),
                          "cv_f1_mean": round(float(cv_scores.mean()), 4), "cv_f1_std": round(float(cv_scores.std()), 4),
                          "best_params": grid.best_params_, "preprocessing": prep_info})

            return result
        except Exception as e:
            return f"Classification failed: {e}"
    return classify


def create_cluster_tool(project_slug: str, engine=None, schema: str = None):
    """Create clustering tool for agent."""
    from agno.tools import tool

    @tool(name="cluster", description="Segment data into groups using K-Means clustering. Use when user asks to segment, group, cluster, categorize. Args: table (str), n_clusters (int, default 0 for auto)")
    def cluster(table: str, n_clusters: int = 0) -> str:
        try:
            import pandas as pd
            import numpy as np
            from sklearn.cluster import KMeans
            from sklearn.preprocessing import StandardScaler
            from sklearn.metrics import silhouette_score, calinski_harabasz_score
            from db import get_sql_engine

            eng = engine or get_sql_engine()
            _schema = schema or __import__('re').sub(r"[^a-z0-9_]", "_", project_slug.lower())[:63]
            qualified = f'"{_schema}"."{table}"' if _schema else f'"{table}"'

            df = pd.read_sql(f"SELECT * FROM {qualified} LIMIT 1000", eng)

            # Shared preprocessing: impute missing values
            X, _, feature_cols, prep_info = _preprocess_df(df)
            numeric_cols = [c for c in feature_cols if c in df.select_dtypes(include=['number']).columns or c.startswith('_')]
            if len(numeric_cols) < 2:
                return "Need at least 2 numeric columns for clustering."

            df_num = X[numeric_cols]
            if len(df_num) < 10:
                return "Need at least 10 rows for clustering."

            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(df_num)

            # Auto-select k
            if n_clusters <= 0:
                best_k, best_score = 2, -1
                for k in range(2, min(9, len(df_num) // 3)):
                    km = KMeans(n_clusters=k, random_state=42, n_init=10)
                    labels = km.fit_predict(X_scaled)
                    score = silhouette_score(X_scaled, labels)
                    if score > best_score:
                        best_k, best_score = k, score
                n_clusters = best_k

            km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            labels = km.fit_predict(X_scaled)
            sil = silhouette_score(X_scaled, labels)

            # Cluster profiles
            df_num['_cluster'] = labels
            profiles = []
            for c in range(n_clusters):
                mask = df_num['_cluster'] == c
                size = int(mask.sum())
                means = {col: round(float(df_num.loc[mask, col].mean()), 2) for col in numeric_cols[:6]}
                profiles.append({"cluster": c, "size": size, "pct": round(size/len(df_num)*100, 1), "means": means})

            # Scatter data (first 2 cols)
            scatter = {
                "x_col": numeric_cols[0], "y_col": numeric_cols[1],
                "points": [[float(row[numeric_cols[0]]), float(row[numeric_cols[1]]), int(row['_cluster'])] for _, row in df_num.head(200).iterrows()]
            }

            result = f"[ML:CLUSTER|algorithm=K-Means|clusters={n_clusters}|silhouette={sil:.2f}|data={len(df_num)} rows]\n"
            result += f"CLUSTERING (K-Means, {n_clusters} segments, silhouette: {sil:.2f}):\n"
            result += f"Data: {len(df_num)} rows, {len(numeric_cols)} features\n\n"
            result += "SEGMENTS:\n"
            for p in profiles:
                result += f"\n  Cluster {p['cluster']} ({p['size']} rows, {p['pct']}%):\n"
                for col, val in list(p['means'].items())[:4]:
                    result += f"    {col}: {val}\n"

            _save_experiment(project_slug, "clustering", f"{table}_clusters", "K-Means", "on-demand",
                input_summary={"table": table, "rows": len(df_num), "features": len(numeric_cols), "columns": numeric_cols[:6]},
                result_data={"n_clusters": n_clusters, "silhouette": round(sil, 4), "profiles": profiles, "scatter": scatter,
                             "calinski_harabasz": round(float(calinski_harabasz_score(X_scaled, labels)), 2)},
                accuracy={"silhouette": round(sil, 4), "calinski_harabasz": round(float(calinski_harabasz_score(X_scaled, labels)), 2),
                          "preprocessing": prep_info})

            return result
        except Exception as e:
            return f"Clustering failed: {e}"
    return cluster


def create_decompose_tool(project_slug: str, engine=None, schema: str = None):
    """Create time series decomposition tool."""
    from agno.tools import tool

    @tool(name="decompose", description="Decompose time series into trend + seasonal + residual components. Use when user asks about trend, seasonality, pattern, decompose. Args: table (str), date_column (str), value_column (str)")
    def decompose(table: str, date_column: str, value_column: str) -> str:
        try:
            import pandas as pd
            from statsmodels.tsa.seasonal import seasonal_decompose
            from db import get_sql_engine

            eng = engine or get_sql_engine()
            _schema = schema or __import__('re').sub(r"[^a-z0-9_]", "_", project_slug.lower())[:63]
            qualified = f'"{_schema}"."{table}"' if _schema else f'"{table}"'

            df = pd.read_sql(f'SELECT "{date_column}", "{value_column}" FROM {qualified} ORDER BY "{date_column}"', eng)
            df[date_column] = pd.to_datetime(df[date_column], errors='coerce')
            df = df.dropna().set_index(date_column)

            if len(df) < 8:
                return "Need at least 8 data points for decomposition."

            period = min(12, len(df) // 2)
            decomp = seasonal_decompose(df[value_column], model='additive', period=period)

            trend_vals = decomp.trend.dropna().tolist()
            seasonal_vals = decomp.seasonal.dropna().tolist()
            resid_vals = decomp.resid.dropna().tolist()

            # Trend direction
            if len(trend_vals) >= 2:
                trend_dir = "increasing" if trend_vals[-1] > trend_vals[0] else "decreasing" if trend_vals[-1] < trend_vals[0] else "flat"
                trend_change = ((trend_vals[-1] - trend_vals[0]) / abs(trend_vals[0]) * 100) if trend_vals[0] != 0 else 0
            else:
                trend_dir, trend_change = "unknown", 0

            # Seasonal strength
            seasonal_strength = max(seasonal_vals) - min(seasonal_vals) if seasonal_vals else 0

            result = f"[ML:DECOMPOSE|algorithm=Seasonal Decompose|trend={trend_dir}|period={period}|data={len(df)} rows]\n"
            result += f"TIME SERIES DECOMPOSITION:\n"
            result += f"Data: {len(df)} points, period={period}\n\n"
            result += f"TREND: {trend_dir} ({trend_change:+.1f}%)\n"
            result += f"SEASONAL STRENGTH: {seasonal_strength:,.0f}\n"
            result += f"RESIDUAL STD: {pd.Series(resid_vals).std():,.0f}\n"

            _save_experiment(project_slug, "decomposition", f"{table}_{value_column}", "SeasonalDecompose", "on-demand",
                input_summary={"table": table, "date_col": date_column, "value_col": value_column, "rows": len(df), "period": period},
                result_data={
                    "trend": trend_vals[:50], "seasonal": seasonal_vals[:50], "residual": resid_vals[:50],
                    "trend_direction": trend_dir, "trend_change_pct": round(trend_change, 1),
                    "seasonal_strength": round(seasonal_strength, 2),
                    "dates": [str(d)[:10] for d in decomp.trend.dropna().index[:50]],
                },
                accuracy={"trend": trend_dir, "period": period})

            return result
        except ImportError:
            return "statsmodels not installed."
        except Exception as e:
            return f"Decomposition failed: {e}"
    return decompose
