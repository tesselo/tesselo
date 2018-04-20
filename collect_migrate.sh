#!/bin/sh
set -e

echo Collecting staticfiles...
python manage.py collectstatic --noinput \
    -i tesselo \
    -i docs \
    -i fonts \
    -i *.md \
    -i *.txt \
    -i *.scss \
    -i *.less \
    -i *.json \
    -i *.hbs \
    -i *.html \
    -i package.json \
    -i bootswatch \
    -i LICENSE.md \
    -i LICENSE \
    -i zappa_settings.json

echo Migrating database...
python manage.py migrate
