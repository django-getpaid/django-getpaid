from django.conf.urls import url
from getpaid.backends.dummy.views import DummyAuthorizationView

urlpatterns = [
    url(r'^payment/authorization/(?P<pk>[0-9]+)/$',
        DummyAuthorizationView.as_view(),
        name='authorization'),
]
