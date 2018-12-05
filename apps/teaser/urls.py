from django.conf.urls import url
from teaser.views import teasercontact

urlpatterns = (
    url(r'^contact-process$', teasercontact, name='teasercontact'),
)
