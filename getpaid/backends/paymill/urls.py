from django.conf.urls import patterns, url
from getpaid.backends.paymill.views import PaymillView

urlpatterns = patterns('',
    url(r'^payment/authorization/(?P<pk>[0-9]+)/$', PaymillView.as_view(), name='getpaid-paymill-authorization'),
)
