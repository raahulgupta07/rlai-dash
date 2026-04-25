FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir sqlalchemy psycopg[binary] pandas scikit-learn lightgbm statsforecast
COPY ml_worker/main.py /app/main.py
CMD ["python", "main.py"]
