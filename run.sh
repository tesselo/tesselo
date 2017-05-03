#!/bin/sh
set -e

#pg_createcluster 9.5 tesselo --D /pgdata

#psql -U postgres -d postgres -h localhost -c 'CREATE DATABASE IF NOT EXISTS tesselo;'

service rabbitmq-server start
service redis-server start

if [ "$DEBUG" = "True" ]; then
    service postgresql start
fi

/etc/init.d/celeryd start

if [ "$1" = "test" ]; then
    PYTHONPATH=$PYTHONPATH:/code python3 /code/manage.py test $2
elif [ "$DEBUG" = "True" ]; then
    service postgresql start

    su -m mrdjango -c "DEBUG=True python3 manage.py migrate"
    su -m mrdjango -c "DEBUG=True python3 manage.py collectstatic --noinput"
    su -m mrdjango -c "DEBUG=True python3 manage.py runserver 0.0.0.0:8000"
else
    su -m mrdjango -c "gunicorn -w 3 -b 0.0.0.0 tesselo.wsgi"
fi
