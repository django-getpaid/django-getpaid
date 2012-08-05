from django.conf.urls import patterns, url
from django.views.decorators.csrf import csrf_exempt
from getpaid.backends.transferuj.views import OnlineView, SuccessView, FailureView

urlpatterns = patterns('',
    url(r'^online/$', csrf_exempt(OnlineView.as_view()), name='getpaid-transferuj-online'),
    url(r'^success/(?P<pk>\d+)/$', csrf_exempt(SuccessView.as_view()), name='getpaid-transferuj-success'),
    url(r'^failure/(?P<pk>\d+)/$', csrf_exempt(FailureView.as_view()), name='getpaid-transferuj-failure'),

)
