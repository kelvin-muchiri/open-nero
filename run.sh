#!/bin/sh

python manage.py migrate
gunicorn nero.wsgi:application --bind 0.0.0.0:8000  --workers 3
