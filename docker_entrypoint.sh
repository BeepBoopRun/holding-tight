#!/bin/bash

python manage.py migrate

gunicorn -b 0.0.0.0:8000 ligand_service.wsgi &
python manage.py run_huey

wait
