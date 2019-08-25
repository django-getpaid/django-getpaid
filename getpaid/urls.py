from django.conf.urls import include, url

from . import views
from .registry import registry

app_name = "getpaid"

urlpatterns = [
    url(
        r"^new/(?P<currency>[A-Z]{3})/$",
        views.CreatePaymentView.as_view(),
        name="create-payment",
    ),
    url(
        r"^success/(?P<pk>[0-9a-f-]+)/$",
        views.SuccessView.as_view(),
        name="payment-success",
    ),
    url(
        r"^failure/(?P<pk>[0-9a-f-]+)/$",
        views.FailureView.as_view(),
        name="payment-failure",
    ),
    url(
        r"^callback/(?P<pk>[0-9a-f-]+)/$",
        views.CallbackView.as_view(),
        name="callback-detail",
    ),
    url(r"^backends/", include(registry.urls)),
]
