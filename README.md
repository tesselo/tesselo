Tesselo
=======

Copyright (c) 2021 Space Mosaic Lda

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

Casperjs install on ubuntu
--------------------------
```
sudo npm install -g phantomjs@2.1.1 --unsafe-perm
sudo npm install casperjs
```

Zappa envents disabled
----------------------
Zappa can not handle the sentinel topic subscriptions because the events are
not owned by Tesselo, which raises permissions errors on boto3.

The following events are currently active, but not anymore managed by Zappa
until the events are put back into the config file.
```json
"keep_warm": true,
"events": [
  {
    "function": "apps.sentinel.tasks.push_scheduled_composite_builds",
    "expression": "cron(0 12 ? * MON-SUN *)"
  },
  {
    "function": "apps.sentinel.tasks.process_sentinel_sns_message",
    "event_source": {
      "arn": "arn:aws:sns:eu-west-1:214830741341:NewSentinel2Product",
      "events": [
        "sns:Publish"
      ]
    }
  },
  {
    "function": "apps.sentinel_1.tasks.process_sentinel_sns_message",
    "event_source": {
      "arn": "arn:aws:sns:eu-central-1:214830741341:SentinelS1L1C",
      "events": [
        "sns:Publish"
      ]
    }
  }
]
```

Docker setup
------------
Location of docker files: `/etc/docker/daemon.json`
