#!/usr/bin/env bash

# This file is a shell script used to run some tasks for the app to run in the container

python manage.py collectstatic --noinput
# Collect all static files (CSS, JavaScript, images, etc.) from various apps into a single directory (usually specified in the STATIC_ROOT setting).
# In non development environment the tatic files are served by a web server (like Nginx) not by Django itself. 
# This command ensures all static assets are in one place for efficient serving.
# Flag --noinput: runs without prompting the user for input

python manage.py migrate --noinput
# Database: The migrate command ensures the database schema is up-to-date.
# This command applies database migrations in Django based on the changes in our Django models.
# When deploying a new version of the application, the database schema might need to be updated to match the code. 
# This command ensures the database is in sync with the latest code.

python -m gunicorn --bind 0.0.0.0:8000 --workers 3 xliff_project.wsgi:application
# This command starts the Gunicorn application server to serve your Django application.
# Params:
# --bind 0.0.0.0:8000: Specifies that Gunicorn should listen on all network interfaces (0.0.0.0) and port 8000.
# --workers 3: Specifies the number of worker processes Gunicorn should use to handle requests. This is typically set based on the number of CPU cores available.
# xliff_project.wsgi:application: Points to the WSGI application object that appears on wsgi.py.
# The wsgi.py file is the entry point for serving your Django application.
