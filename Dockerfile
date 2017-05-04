FROM ubuntu:xenial

# Connect to ubuntugis and update packages.
RUN apt-get update
RUN apt-get install -y software-properties-common
RUN add-apt-repository -y ppa:ubuntugis/ubuntugis-unstable
RUN apt-get update
RUN apt-get upgrade -y

# Install Utilities
RUN apt-get install -y\
    curl\
    git\
    vim\
    build-essential\
    python3-setuptools\
    python3-dev\
    python3-pip\
    python3-software-properties\
    libxml2-dev\
    libxslt1-dev\
    npm

# DB & GIS
RUN apt-get install -y postgresql-server-dev-9.5 postgis gdal-bin libgeos-3.5.0 redis-server rabbitmq-server

# Create npm symlink to be able to call from command line directly.
RUN ln -s /usr/bin/nodejs /usr/bin/node

# Install r.js and less compilers.
RUN npm install -g requirejs less

RUN pip3 install ipython ipdb\
    psycopg2==2.6.1\
    boto==2.45.0\
    redis==2.10.5\
    gunicorn==19.6.0\
    python-memcached==1.58\
    coreapi==2.3.0\
    requests==2.13.0\
    boto3==1.4.4\
    coreapi==2.3.0\
    Pillow==4.1.0\
    numpy==1.12.1\
    djangorestframework==3.6.2\
    djangorestframework-gis==0.11\
    drf-extensions==0.3.1\
    django-storages==1.5.2\
    django-compressor==2.1\
    django-extensions==1.7.4\
    django-cleanup==0.4.2\
    django-filter==1.0.1\
    django-crispy-forms==1.6.1\
    django-storage-swift==1.2.16\
    django-guardian==1.4.8

# Install python dependencies.
RUN pip3 install https://github.com/celery/celery/archive/master.tar.gz
RUN pip3 install https://github.com/geodesign/django/archive/geodesign_v6.4.tar.gz
RUN pip3 install https://github.com/geodesign/django-raster/archive/raster_file_field.tar.gz
RUN pip3 install --no-deps https://github.com/geodesign/django-raster-aggregation/archive/0.1.1.tar.gz

# Adjust PostgreSQL configuration so that remote connections to the
# database are possible.
RUN echo "host all  all  localhost trust" > /etc/postgresql/9.5/main/pg_hba.conf

# And add ``listen_addresses`` to ``/etc/postgresql/9.3/main/postgresql.conf``
RUN echo "listen_addresses='*'" >> /etc/postgresql/9.5/main/postgresql.conf

# Change data directory for postgres service.
RUN sed -i 's/\/var\/lib\/postgresql\/9.5\/main/\/pgdata/g' /etc/postgresql/9.5/main/postgresql.conf

# Add VOLUMEs to allow backup of config, logs and databases
VOLUME  ["/etc/postgresql", "/var/log/postgresql", "/var/lib/postgresql"]

# Create local staticfiles dir.
RUN mkdir /staticfiles

# Create an unprivileged user for running Django.
RUN adduser --disabled-password --gecos '' mrdjango

# Create local staticfiles dir, allow django to access it.
RUN chown -R mrdjango /staticfiles

# Set workdir
WORKDIR /code

# Set port
EXPOSE 8000

# Set the startup script as default command.
CMD /code/run.sh

# Download generic celery daemon start script.
ADD https://raw.githubusercontent.com/celery/celery/3.1/extra/generic-init.d/celeryd /etc/init.d/celeryd
RUN chmod +x /etc/init.d/celeryd

# Add configuration for the celery daemon.
ADD celeryd.conf /etc/default/celeryd
RUN chmod 640 '/etc/default/celeryd'

# Create celery group and user.
RUN groupadd celery
RUN useradd -g celery celery

ADD . /code/

# Install frontend dependencies.
RUN npm install --prefix frontend frontend

# Build frontend.
RUN r.js -o frontend/js/build.js

# Make startup script executable.
RUN chmod +x /code/run.sh
