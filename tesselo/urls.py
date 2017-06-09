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
from rest_framework.documentation import include_docs_urls

from django.conf.urls import include, url
from django.contrib import admin
from django.views.generic.base import TemplateView
from tesselo.apiurls import router

urlpatterns = [
    url(r'^docs/', include_docs_urls(title='Tesselo API Docs')),
    url(r'^api/', include(router.urls)),
    url(r'^admin/', admin.site.urls),
    url(r'^sentinel/', include('sentinel.urls')),
    url(r'^', include('django.contrib.auth.urls')),
    url(r'^$', TemplateView.as_view(template_name='index.html')),
]
