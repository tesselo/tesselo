"""tesselo URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/dev/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import include, url
from django.contrib.gis import admin
from rest_framework.documentation import include_docs_urls
from rest_framework.permissions import IsAdminUser
from tesselo.apiurls import apiurlpatterns

urlpatterns = [
    url(r'^docs/', include_docs_urls(title='Tesselo API Docs', public=False, permission_classes=[IsAdminUser])),
    url(r'^accounts/', include('rest_framework.urls', namespace='rest_framework')),
    url(r'^accounts/', include('django.contrib.auth.urls')),
    url(r'^admin/', admin.site.urls),
]

urlpatterns += apiurlpatterns
