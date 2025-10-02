#!/bin/bash
export DJANGO_DEBUG="False"

./wait-for-it.sh db:5432
python manage.py migrate --no-input
python manage.py tailwind install --no-input
python manage.py tailwind build --no-input
python manage.py collectstatic --no-input 
gunicorn -b 0.0.0.0:8080 ligand_service.wsgi --timeout 120
