#!/bin/sh
set -e

pg_createcluster 9.5 tesselo --D /pgdata

psql -U postgres -d postgres -h localhost -c 'CREATE DATABASE IF NOT EXISTS tesselo;'

if [ "$1" = "test" ]; then
    PYTHONPATH=$PYTHONPATH:/code python3 /code/manage.py test $2
else
    service postgresql start
    service rabbitmq-server start
    service redis-server start

    #/etc/init.d/celeryd start

    psql -U postgres -d postgres -h localhost -c 'show data_directory;'
    
    python3 /code/manage.py check

    PYTHONPATH=$PYTHONPATH:/code python3 /code/manage.py migrate

    PYTHONPATH=$PYTHONPATH:/code python3 /code/manage.py runserver 0.0.0.0:8000
fi
