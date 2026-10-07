#!/bin/sh
# Роли: migrate (один раз), api, consumer. Миграции не гоняются в рабочих процессах.
set -e

role="${1:-api}"

if [ "$role" = "migrate" ]; then
  echo "Applying Alembic migrations..."
  exec alembic upgrade head
fi

if [ "$role" = "api" ]; then
  echo "Starting API (uvicorn)..."
  exec uvicorn app.main:app --host 0.0.0.0 --port 8000
fi

if [ "$role" = "consumer" ]; then
  echo "Starting payment consumer (FastStream)..."
  exec faststream run app.workers.consumer:app
fi

echo "Unknown role: $role (expected migrate, api or consumer)" >&2
exit 1
