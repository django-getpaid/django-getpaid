from django.conf.urls import patterns, url
from django.views.decorators.csrf import csrf_exempt
from getpaid.backends.przelewy24.views import OnlineView, SuccessView, FailureView

urlpatterns = patterns('',
    url(r'^online/$', csrf_exempt(OnlineView.as_view()), name='getpaid-przelewy24-online'),
    url(r'^success/(?P<pk>\d+)/', csrf_exempt(SuccessView.as_view()), name='getpaid-przelewy24-success'),
    url(r'^failure/(?P<pk>\d+)/', csrf_exempt(FailureView.as_view()), name='getpaid-przelewy24-failure'),

)
