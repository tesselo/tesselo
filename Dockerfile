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

# Adjust PostgreSQL configuration so that remote connections to the
# database are possible.
RUN echo "host all  all  localhost trust" > /etc/postgresql/9.5/main/pg_hba.conf

# And add ``listen_addresses`` to ``/etc/postgresql/9.3/main/postgresql.conf``
RUN echo "listen_addresses='*'" >> /etc/postgresql/9.5/main/postgresql.conf

# Change data directory for postgres service.
RUN sed -i 's/\/var\/lib\/postgresql\/9.5\/main/\/pgdata/g' /etc/postgresql/9.5/main/postgresql.conf

# Add VOLUMEs to allow backup of config, logs and databases
VOLUME  ["/etc/postgresql", "/var/log/postgresql", "/var/lib/postgresql"]

# Create an unprivileged user for running Django.
RUN adduser --disabled-password --gecos '' mrdjango

# Create local staticfiles dir, allow django to access it (used by compressor).
RUN mkdir /staticfiles
RUN chown -R mrdjango /staticfiles

# Create local mediafiles dir, allow django to access it (used for testing).
RUN mkdir /tesselo_media
RUN chown -R mrdjango /tesselo_media

# Set workdir
WORKDIR /code

# Set port
EXPOSE 8000

# Set the startup script as default command.
CMD /code/run.sh

# Add requirements.txt separately to be able to cache the pip install.
ADD requirements.txt /code/requirements.txt
RUN pip3 install -r /code/requirements.txt

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
