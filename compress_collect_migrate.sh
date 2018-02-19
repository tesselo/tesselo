#!/bin/sh
set -e

rpm --rebuilddb
yum install -y --enablerepo=epel npm
npm install -g requirejs
npm install --prefix frontend frontend
r.js -o frontend/js/build.js
python manage.py compress --force
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
    -i LICENSE
python manage.py migrate
