"""
ML Worker — polls dash_ml_jobs, trains heavy models in isolation.
Runs in separate container so chat is never blocked.
"""

import os, sys, json, time, pickle, re, logging, signal

MAX_ROWS = 100_000       # Cap rows loaded per table
JOB_TIMEOUT_SEC = 300    # 5 min max per job

logging.basicConfig(level=logging.INFO, format="%(asctime)s [ML-WORKER] %(message)s")
logger = logging.getLogger("ml_worker")

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    logger.error("DATABASE_URL not set")
    sys.exit(1)


def init_jobs_table():
    from sqlalchemy import text, create_engine
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.dash_ml_jobs (
                id SERIAL PRIMARY KEY,
                project_slug TEXT NOT NULL,
                table_name TEXT NOT NULL,
                job_type TEXT NOT NULL,
                config JSONB DEFAULT '{}',
                status TEXT DEFAULT 'pending',
                result JSONB,
                error TEXT,
                model_id INTEGER,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                started_at TIMESTAMPTZ,
                completed_at TIMESTAMPTZ
            )
        """))
        conn.commit()
    engine.dispose()


def pick_job():
    from sqlalchemy import text, create_engine
    engine = create_engine(DATABASE_URL)
    job = None
    with engine.connect() as conn:
        row = conn.execute(text(
            "UPDATE public.dash_ml_jobs SET status='running', started_at=NOW() "
            "WHERE id=(SELECT id FROM public.dash_ml_jobs WHERE status='pending' "
            "ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED) RETURNING *"
        )).fetchone()
        if row:
            job = {"id": row[0], "project_slug": row[1], "table_name": row[2],
                   "job_type": row[3], "config": row[4] if isinstance(row[4], dict) else json.loads(row[4] or "{}")}
        conn.commit()
    engine.dispose()
    return job


def complete_job(job_id, result=None, error=None, model_id=None):
    from sqlalchemy import text, create_engine
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        if error:
            conn.execute(text("UPDATE public.dash_ml_jobs SET status='failed', error=:e, completed_at=NOW() WHERE id=:id"),
                         {"id": job_id, "e": str(error)[:500]})
        else:
            conn.execute(text("UPDATE public.dash_ml_jobs SET status='done', result=:r, model_id=:m, completed_at=NOW() WHERE id=:id"),
                         {"id": job_id, "r": json.dumps(result or {}), "m": model_id})
        conn.commit()
    engine.dispose()


def train_model(job):
    import pandas as pd
    from sqlalchemy import create_engine
    engine = create_engine(DATABASE_URL)
    schema = re.sub(r"[^a-z0-9_]", "_", job["project_slug"].lower())[:63]
    qualified = f'"{schema}"."{job["table_name"]}"'
    df = pd.read_sql(f"SELECT * FROM {qualified} LIMIT {MAX_ROWS}", engine)
    engine.dispose()
    logger.info(f"Loaded {len(df)} rows from {qualified} (cap={MAX_ROWS})")

    if job["job_type"] == "forecast":
        from statsforecast import StatsForecast
        from statsforecast.models import AutoARIMA, AutoETS
        cfg = job["config"]
        date_col, value_col = cfg.get("date_column", ""), cfg.get("value_column", "")
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df_sf = df[[date_col, value_col]].dropna().sort_values(date_col).rename(columns={date_col: "ds", value_col: "y"})
        df_sf["unique_id"] = "1"
        sf = StatsForecast(models=[AutoARIMA(season_length=min(12, len(df_sf)//2) or 1)], freq="MS", fallback_model=AutoETS(season_length=1))
        sf.fit(df_sf)
        return {"model_bytes": pickle.dumps(sf), "algorithm": "statsforecast/AutoARIMA", "model_type": "forecast", "target": value_col, "rows": len(df_sf)}

    elif job["job_type"] == "anomaly":
        from sklearn.ensemble import IsolationForest
        numeric_cols = [c for c in df.select_dtypes(include=["number"]).columns if c.lower() not in ("id", "index")]
        df_num = df[numeric_cols].dropna()
        iso = IsolationForest(contamination=0.1, random_state=42, n_estimators=100)
        iso.fit(df_num)
        return {"model_bytes": pickle.dumps({"model": iso, "columns": list(numeric_cols)}), "algorithm": "sklearn/IsolationForest", "model_type": "anomaly", "target": None, "rows": len(df_num)}

    return {"error": f"Unknown job type: {job['job_type']}"}


def save_model_from_result(job, result):
    if not result.get("model_bytes"):
        return None
    from sqlalchemy import text, create_engine
    engine = create_engine(DATABASE_URL)
    slug, name = job["project_slug"], f"{job['table_name']}_{result['model_type']}"
    with engine.connect() as conn:
        conn.execute(text("UPDATE public.dash_ml_models SET status='archived' WHERE project_slug=:s AND name=:n AND status='active'"), {"s": slug, "n": name})
        ver = conn.execute(text("SELECT COALESCE(MAX(version),0)+1 FROM public.dash_ml_models WHERE project_slug=:s AND name=:n"), {"s": slug, "n": name}).scalar()
        row = conn.execute(text(
            "INSERT INTO public.dash_ml_models (project_slug,name,model_type,algorithm,target_column,row_count,model_bytes,status,version) "
            "VALUES (:s,:n,:t,:a,:tgt,:rows,:m,'active',:v) RETURNING id"
        ), {"s": slug, "n": name, "t": result["model_type"], "a": result["algorithm"],
            "tgt": result.get("target"), "rows": result.get("rows", 0), "m": result["model_bytes"], "v": ver}).fetchone()
        conn.commit()
    engine.dispose()
    return row[0] if row else None


class JobTimeout(Exception):
    pass

def _timeout_handler(signum, frame):
    raise JobTimeout(f"Job exceeded {JOB_TIMEOUT_SEC}s timeout")


def main():
    logger.info("ML Worker starting...")
    init_jobs_table()
    logger.info("Polling for jobs...")
    while True:
        job = pick_job()
        if not job:
            time.sleep(5)
            continue
        logger.info(f"Job #{job['id']}: {job['job_type']} on {job['table_name']}")
        try:
            # Set timeout alarm
            signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(JOB_TIMEOUT_SEC)
            result = train_model(job)
            signal.alarm(0)  # Cancel alarm on success
            if result.get("error"):
                complete_job(job["id"], error=result["error"])
            else:
                model_id = save_model_from_result(job, result)
                result.pop("model_bytes", None)
                complete_job(job["id"], result=result, model_id=model_id)
                logger.info(f"Job #{job['id']} done. Model: {model_id}")
        except JobTimeout as e:
            signal.alarm(0)
            complete_job(job["id"], error=str(e))
            logger.error(f"Job #{job['id']} timed out after {JOB_TIMEOUT_SEC}s")
        except Exception as e:
            signal.alarm(0)
            complete_job(job["id"], error=str(e))
            logger.error(f"Job #{job['id']} error: {e}")

if __name__ == "__main__":
    main()
