from django.conf.urls import patterns, url
from django.views.decorators.csrf import csrf_exempt
from getpaid.backends.pagseguro.views import NotificationsView

urlpatterns = patterns('',
    url(r'^notifications/$', csrf_exempt(NotificationsView.as_view()), name='getpaid-pagseguro-notifications'),
)
