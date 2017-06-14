#!/bin/sh
set -e

service rabbitmq-server start
service redis-server start

# If it does not exist, create pg cluster.
if [ "$DEBUG" = "True" ] && [ ! -f /pgdata/PG_VERSION ]; then
    echo "\nNo database cluster detected, creating a new one in /pgdata."
    pg_createcluster 9.5 tesselo --D /pgdata
fi

# Start database server using the above cluster.
if [ "$DEBUG" = "True" ]; then
    chown -R postgres /pgdata
    chmod -R 700 /pgdata
    service postgresql start
    sleep 2
fi

# Check if tesselo database exists, if not create it and a new superuser.
if [ "$DEBUG" = "True" ] && [ ! $(psql -U postgres -d postgres -h localhost -lqt | cut -d \| -f 1 | grep tesselo) ]; then
    echo "\nTesselo DB not detected, creating new database."
    psql -U postgres -d postgres -h localhost -c "CREATE DATABASE tesselo;"
    su -m mrdjango -c "DEBUG=True python3 manage.py migrate"
    echo "\nCreating superuser."
    python3 manage.py shell -c "from django.contrib.auth.models import User; User.objects.create_superuser('tesselo', 'admin@tesselo.com', 'pass');"
fi

# Start the celery worker in this instance.
if [ "$DEBUG" = "True" ]; then
    /etc/init.d/celeryd start
fi

if [ "$1" = "test" ]; then
    # Run the tests if requested.
    PYTHONPATH=$PYTHONPATH:/code python3 /code/manage.py test $2
elif [ "$DEBUG" = "True" ]; then
    # Run the django development server.
    chown -R mrdjango /tesselo_media
    su -m mrdjango -c "DEBUG=True python3 manage.py migrate"
    su -m mrdjango -c "DEBUG=True python3 manage.py runserver 0.0.0.0:8000"
elif ["$WORKER" = "True"]; then
    # Run django as a celery worker.
    su -m mrdjango -c "celery worker -A tesselo -l info --concurrency=1"
else
    # Run gunicorn in production.
    gunicorn -w 3 -b 0.0.0.0 -u mrdjango tesselo.wsgi
fi
