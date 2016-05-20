from django.conf.urls import url, include
from getpaid.views import NewPaymentView, FallbackView
from getpaid.utils import import_backend_modules


app_name = 'getpaid'
namespace = app_name

includes_list = []
for backend_name, urls in import_backend_modules('urls').items():
    backend_url_regex = r'^%s/' % backend_name
    backend_namespace = backend_name.split('.')[-1]
    backend_url = url(
        backend_url_regex,
        include(urls, app_name=app_name, namespace=backend_namespace)
    )
    includes_list.append(backend_url)


urlpatterns = [
    url(
        r'^new/payment/(?P<currency>[A-Z]{3})/$',
        NewPaymentView.as_view(),
        name='new-payment'
    ),
    url(
        r'^payment/success/(?P<pk>\d+)/$',
        FallbackView.as_view(success=True),
        name='success-fallback'
    ),
    url(
        r'^payment/failure/(?P<pk>\d+)$',
        FallbackView.as_view(success=False),
        name='failure-fallback'
    ),
] + includes_list
