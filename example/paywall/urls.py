from django.urls import path

from . import views

app_name = "paywall"

urlpatterns = [
    path("fake_gateway/", views.authorization_view, name="gateway"),
    path("fake_gateway_api/<uuid:pk>/", views.get_status, name="get_status"),
    path("fake_gateway_api/", views.rest_register_payment, name="api_register"),
    path("fake_gateway_api/operate/", views.rest_operation, name="api_operate"),
]
