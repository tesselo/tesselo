#!/bin/sh
set -e

service rabbitmq-server start
service redis-server start

if [ "$DEBUG" = "True" ] && [ ! -f /pgdata/PG_VERSION ]; then
    echo "\nNo database cluster detected, creating a new one in /pgdata."
    pg_createcluster 9.5 tesselo --D /pgdata
fi

if [ "$DEBUG" = "True" ]; then
    service postgresql start
fi

sleep 1

if [ "$DEBUG" = "True" ] && [ ! $(psql -U postgres -d postgres -h localhost -lqt | cut -d \| -f 1 | grep tesselo) ]; then
    echo "\nTesselo DB not detected, creating new database."
    psql -U postgres -d postgres -h localhost -c "CREATE DATABASE tesselo;"
    su -m mrdjango -c "DEBUG=True python3 manage.py migrate"
    echo "\nCreating superuser."
    python3 manage.py shell -c "from django.contrib.auth.models import User; User.objects.create_superuser('tesselo', 'admin@tesselo.com', 'pass');"
fi

/etc/init.d/celeryd start

if [ "$1" = "test" ]; then
    PYTHONPATH=$PYTHONPATH:/code python3 /code/manage.py test $2
elif [ "$DEBUG" = "True" ]; then
    chown -R mrdjango /tesselo_media
    su -m mrdjango -c "DEBUG=True python3 manage.py migrate"
    su -m mrdjango -c "DEBUG=True python3 manage.py runserver 0.0.0.0:8000"
else
    gunicorn -w 3 -b 0.0.0.0 -u mrdjango tesselo.wsgi
fi
