from django.urls import include, path, register_converter

from . import views
from .converters import CurrencyConverter
from .registry import registry

register_converter(CurrencyConverter, "currency")

app_name = "getpaid"

urlpatterns = [
    path(
        "new/<currency:currency>/",
        views.CreatePaymentView.as_view(),
        name="create-payment",
    ),
    path("success/<uuid:pk>/", views.SuccessView.as_view(), name="payment-success",),
    path("failure/<uuid:pk>/", views.FailureView.as_view(), name="payment-failure",),
    path("callback/<uuid:pk>/", views.CallbackView.as_view(), name="callback-detail",),
    path("backends/", include(registry.urls)),
]
