from django.conf.urls import url
from getpaid.backends.paymill.views import PaymillView

urlpatterns = [
    url(r'^payment/authorization/(?P<pk>[0-9]+)/$',
        PaymillView.as_view(),
        name='authorization'),
]
