FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RAMP_DB_PATH=/data/ramplab.sqlite3

WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --system --gid 10001 ramplab \
    && useradd --system --uid 10001 --gid 10001 --home-dir /nonexistent ramplab \
    && mkdir -p /data \
    && chown -R 10001:10001 /data

COPY app ./app
COPY frontend ./frontend
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
