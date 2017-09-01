#!/bin/sh
set -e

if [ "$WORKER" = "True" ]; then
    echo "Running worker, no migrations necessary."
    return
fi

echo "Compressing static files"
python3 manage.py compress --force

echo "Collecting static files"
python3 manage.py collectstatic -i docs -i fonts -i *.md -i *.txt -i *.js -i *.css -i *.scss -i *.less -i *.json -i LICENSE -i *.hbs -i *.html --noinput

echo "Migrating database"
python3 manage.py migrate
