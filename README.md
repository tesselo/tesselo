Tesselo
=======

Docker image
------------

The tesselo docker image can be used for local development. 

To build the image, run

    docker build -t tesselo .

To start a container locally

    docker run --rm --env DEBUG=True -it -v /path/to/local/tesselo/clone:/code -v /path/to/local/pgdata/dir:/pgdata -v /path/to/local/media/dir:/tesselo_media tesselo

Three volumes should be provided:

* Postgres cluster volume, i.e. the location of the database files on the local filesystem. Mapped to :/pgdata
* The local clone of the tesselo repository. Mapped to :/code
* A media folder to store media files (mainly rasterfiles and tiles). Mapped to :/tesselo_media

The docker image will create a new pgcluster in the local pgdata directory if
it does not exist. It will also create a database and a superuser with
username "tesselo" and password "pass".

The image contains the postgres, redis and rabbitmq servers. Django is
configured to use these local servers when running in dev mode.

Docker container ip
-------------------
Do access the runserver, you need to find the local IP of the container its running on. To get the ip,
run `docker ps` and then use the container ID to run `docker inspect containerid`, then the IP is prompted
as part of the metadata. You can then access the container on port 8000. For example http://172.17.0.2:8000/.

Also you can drop into the container running `docker exec -it CONTAINERID python3 manage.py shell`.

Run the test suite
------------------
To run the test suite, simply specify an argument for the run script like so

    docker run --rm --env DEBUG=True -v /path/to/local/tesselo/clone:/code -v /path/to/local/pgdata/dir:/pgdata tesselo /code/run.sh test
