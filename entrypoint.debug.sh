#!/usr/bin/env bash
python manage.py collectstatic --noinput
python manage.py migrate --noinput

# start Gunicorn under debugpy
python -m debugpy --listen 0.0.0.0:5678 --wait-for-client -m gunicorn --bind 0.0.0.0:8000 --workers 3 xliff_project.wsgi:application
