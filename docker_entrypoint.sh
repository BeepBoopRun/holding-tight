#!/bin/bash
export DJANGO_DEBUG="False"
python manage.py migrate

gunicorn -b 0.0.0.0:8000 ligand_service.wsgi --timeout 90 &
python manage.py run_huey

wait
