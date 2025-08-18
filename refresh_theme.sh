#!/bin/bash

python manage.py tailwind build
python manage.py collectstatic
