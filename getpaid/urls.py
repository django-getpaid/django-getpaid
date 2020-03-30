from django.urls import include, path

from . import views
from .registry import registry

app_name = "getpaid"

urlpatterns = [
    path("new/", views.CreatePaymentView.as_view(), name="create-payment",),
    # universal success/failure endpoints for some archaic paywalls
    path("success/<uuid:pk>/", views.SuccessView.as_view(), name="payment-success",),
    path("failure/<uuid:pk>/", views.FailureView.as_view(), name="payment-failure",),
    # universal callback endpoint for asynchronous payment status updates sent by paywall
    path("callback/<uuid:pk>/", views.CallbackView.as_view(), name="callback-detail",),
    # each plugin can also have their own endpoints
    path("backends/", include(registry.urls)),
]
