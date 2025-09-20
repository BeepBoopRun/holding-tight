#!/bin/bash
export DJANGO_DEBUG="False"

./wait-for-it.sh db:5432
micromamba run python manage.py migrate
gunicorn -b 0.0.0.0:8000 ligand_service.wsgi --timeout 120
