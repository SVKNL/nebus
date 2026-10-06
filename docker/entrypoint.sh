#!/bin/sh
# Единая точка входа: накатываем миграции, затем стартуем нужный процесс.
set -e

role="${1:-api}"

echo "Applying Alembic migrations..."
alembic upgrade head

if [ "$role" = "api" ]; then
  echo "Starting API (uvicorn)..."
  exec uvicorn app.main:app --host 0.0.0.0 --port 8000
fi

if [ "$role" = "consumer" ]; then
  echo "Starting payment consumer (FastStream)..."
  exec faststream run app.consumer.main:app
fi

echo "Unknown role: $role (expected api or consumer)" >&2
exit 1
