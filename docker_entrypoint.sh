#!/bin/bash
export DJANGO_DEBUG="False"

gunicorn -b 0.0.0.0:8000 ligand_service.wsgi --timeout 120 &
pid1=$!
python manage.py run_huey &
pid2=$!

while true; do
    sleep 10m

    echo "Checking for new commits..."
    [ "$(git pull)" = "Already up to date." ] && { echo "No new commits. Waiting again..."; continue; } || echo "Applying changes, restaring the server..."
    micromamba install -f env.yaml -y
    python3 manage.py migrate
    python3 manage.py collectstatic --noinput
    kill "$pid1" "$pid2"
    # time for graceful shutdown
    sleep 1m
    gunicorn -b 0.0.0.0:8000 ligand_service.wsgi --timeout 120 &
    pid1=$!
    python manage.py run_huey &
    pid2=$!
done

