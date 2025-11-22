#!/bin/bash

DJANGO_USER_UID=$(id -u mambauser 2>/dev/null || echo 0)
SECRET_FILES="/run/secrets/db_password /run/secrets/django_key"
echo "Checking and fixing secret permissions for Django user UID: $DJANGO_USER_UID"

for FILE in $SECRET_FILES; do
    if [ -f "$FILE" ]; then
        chown $DJANGO_USER_UID:0 "$FILE"
        chmod 0400 "$FILE"
    fi
done
