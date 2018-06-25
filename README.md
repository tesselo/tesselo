Tesselo
=======

Copyright (c) 2017 Daniel Wiesmann

Docker
------
The Tesselo docker image is a python 3.6 based image that is stripped down and
resembles the AWS Lambda environment. The worker docker instance is more heavy
and contains libraries that are not used for the web app (such as scipy,
sen2cor, etc).


Zappa create superuser
----------------------

    zappa invoke dev "printf \"from django.contrib.auth.models import User; User.objects.create_superuser('daniel2', 'daniel2@tesselo.com', 'adminpass')\" | python manage.py shell" --raw

or alternatively

    zappa invoke dev "from django.contrib.auth.models import User; User.objects.create_superuser('daniel2', 'daniel2@tesselo.com', 'adminpass')" --raw
