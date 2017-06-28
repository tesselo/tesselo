Tesselo
=======

Copyright (c) 2017 Daniel Wiesmann

Docker image
------------

The tesselo docker image can be used for local development. 

To build the image, run

    docker build -t tesselo .

To start a container locally

    docker run --rm -p 80:8000 --env DEBUG=True -it -v /path/to/local/tesselo/clone:/code -v /path/to/local/pgdata/dir:/pgdata -v /path/to/local/media/dir:/tesselo_media tesselo

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

Setting up the ssh keys
-----------------------
The ssh keys are generated through letsencrypt using a utiltiy app (https://github.com/ibmjstart/bluemix-letsencrypt).
Set the url domain name to ``tesselo.com``, and subdomain to ``www``, then run ``python setup-app.py``.
The running of the script will fail when trying ``Making GET request to https://www.tesselo.com``, but
the certificates are generated on the remote machine. To download the certs, use
    
    cf ssh letsencrypt -c 'cat ~/app/conf/live/www.tesselo.com/cert.pem' > cert.pem
    cf ssh letsencrypt -c 'cat ~/app/conf/live/www.tesselo.com/privkey.pem' > privkey.pem
    cf ssh letsencrypt -c 'cat ~/app/conf/live/www.tesselo.com/chain.pem' > chain.pem
    cf ssh letsencrypt -c 'cat ~/app/conf/live/www.tesselo.com/fullchain.pem' > fullchain.pem

Then manually upload them to bluemix, using the cert.pem as main certificate and fullchain.pem as intermediate cert.

Without the intermediate certificate, the page opens successfully in browsers, but the cert chain is not complete. So
requests from curl or python scripts will fail due to failing cert handshakes.
