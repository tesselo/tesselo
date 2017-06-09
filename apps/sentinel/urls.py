from __future__ import unicode_literals

from django.conf.urls import url
from sentinel.views import CloudView

urlpatterns = [
    url(
        r'^clouds/(?P<stile>[^/]+)/(?P<z>[0-9]+)/(?P<x>[0-9]+)/(?P<y>[0-9]+).(?P<frmt>png|jpg)$',
        CloudView.as_view(),
        name='clouds'
    ),
]
