from django.urls import include, path

from . import views
from .registry import registry

app_name = "getpaid"

urlpatterns = [
    path("new/", views.new_payment, name="create-payment"),
    path("success/<uuid:pk>/", views.success, name="payment-success",),
    path("failure/<uuid:pk>/", views.failure, name="payment-failure",),
    path("callback/<uuid:pk>/", views.callback, name="callback",),
    path("", include(registry.urls)),
]
