from django.conf.urls import patterns, url, include
from getpaid.views import NewPaymentView, FallbackView
from getpaid.utils import import_backend_modules

includes_list = []
for backend_name, urls in import_backend_modules('urls').items():
    includes_list.append(url(r'^%s/' % backend_name, include(urls)))

urlpatterns = patterns('',
    url(r'^new/payment/(?P<currency>[A-Z]{3})/$', NewPaymentView.as_view(), name='getpaid-new-payment'),
    url(r'^payment/success/(?P<pk>\d+)/$', FallbackView.as_view(success=True), name='getpaid-success-fallback'),
    url(r'^payment/failure/(?P<pk>\d+)$', FallbackView.as_view(success=False), name='getpaid-failure-fallback'),
    *includes_list

)
