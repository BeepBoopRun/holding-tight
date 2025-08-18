#!/bin/bash

python manage.py runserver 0.0.0.0:8000 &
python manage.py run_huey

wait