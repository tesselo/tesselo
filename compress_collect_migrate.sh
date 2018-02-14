#!/bin/sh
set -e

if [ "$WORKER" = "True" ]; then
    echo "Running worker, no migrations necessary."
    return
fi

echo "Compressing static files"
python3.6 manage.py compress --force

echo "Collecting static files"
python3.6 manage.py collectstatic --noinput\
    -i tesselo\
    -i docs\
    -i fonts\
    -i *.md\
    -i *.txt\
    -i *.scss\
    -i *.less\
    -i *.json\
    -i *.hbs\
    -i *.html\
    -i package.json\
    -i bootswatch\
    -i LICENSE.md\
    -i LICENSE

echo "Migrating database"
python3.6 manage.py migrate
