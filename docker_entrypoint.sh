#!/bin/bash
export DJANGO_DEBUG="False"

gunicorn -b 0.0.0.0:8000 ligand_service.wsgi --timeout 120 &
python manage.py run_huey

wait
