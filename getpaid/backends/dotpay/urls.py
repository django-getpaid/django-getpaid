from django.conf.urls import patterns, url
from django.views.decorators.csrf import csrf_exempt
from getpaid.backends.dotpay.views import ReturnView
from getpaid.backends.dotpay.views import OnlineView

urlpatterns = patterns('',
    url(r'^online/$', csrf_exempt(OnlineView.as_view()), name='getpaid-dotpay-online'),
    url(r'^return/(?P<pk>\d+)/$', csrf_exempt(ReturnView.as_view()), name='getpaid-dotpay-return'),

)
