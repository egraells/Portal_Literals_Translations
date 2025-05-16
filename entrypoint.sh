#!/usr/bin/env bash

set -euo pipefail

echo "🚀  Starting application using entrypoint.sh at $(date)" | tee -a /app/ai_translator_backend.log

# Start scheduler
nohup python /app/aitranslator_batch_process/scheduler_ai.py >> /app/ai_translator_backend.log 2>&1 &

# Collect static files 
python manage.py collectstatic --noinput

# Run any pending DB migrations
python manage.py migrate --noinput

# Start Gunicorn based on environment
if [ "$IS_DEVELOPMENT_ENV" = "TRUE" ]; then
  echo "🚀  We are in DEVELOPMENT environment" | tee -a /app/ai_translator_backend.log
  # For debugging use --wait-for-client
  # exec python -m debugpy --listen 0.0.0.0:5678 --wait-for-client -m uvicorn xliff_project.asgi:application --host 0.0.0.0 --port 8000 --reload --reload-dir /app --reload-include "*.html"
  # For non-debugging
  exec python -m debugpy --listen 0.0.0.0:5678 -m uvicorn xliff_project.asgi:application \
    --host 0.0.0.0 --port 8000 --reload --reload-dir /app --reload-include "*.html"
  
  #exec uvicorn xliff_project.asgi:application --host 0.0.0.0 --port 8000 --reload
  #exec python -m gunicorn --reload --log-level debug --bind 0.0.0.0:8000 --workers 1 xliff_project.wsgi:application
else
  echo "🚀  We are in a PRODuction environment" | tee -a /app/ai_translator_backend.log
  exec python -m gunicorn --bind 0.0.0.0:8000 --workers 3 xliff_project.wsgi:application
fi
