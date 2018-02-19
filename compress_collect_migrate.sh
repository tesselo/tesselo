#!/bin/sh
set -e

echo Rebuilding rpm database...
rpm --rebuilddb
echo Installing npm...
yum install -y --enablerepo=epel npm
echo installing Requirejs...
npm install -g requirejs
echo Installing frontend deps...
npm install --prefix frontend frontend
echo Building frontend js...
r.js -o frontend/js/build.js
echo Compressing staticfiles...
python manage.py compress --force
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
