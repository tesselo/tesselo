#!/bin/sh
set -e

chown -R mrdjango /tesselo_media

service rabbitmq-server start
service redis-server start

if [ "$DEBUG" = "True" ]; then
    service postgresql start
fi

/etc/init.d/celeryd start

if [ "$1" = "test" ]; then
    PYTHONPATH=$PYTHONPATH:/code python3 /code/manage.py test $2
elif [ "$DEBUG" = "True" ]; then
    su -m mrdjango -c "DEBUG=True python3 manage.py migrate"
    #su -m mrdjango -c "DEBUG=True python3 manage.py collectstatic -i node_modules --noinput"
    #su -m mrdjango -c "DEBUG=True python3 manage.py compress --force"
    su -m mrdjango -c "DEBUG=True python3 manage.py runserver 0.0.0.0:8000"
else
    gunicorn -w 3 -b 0.0.0.0 -u mrdjango tesselo.wsgi
fi
