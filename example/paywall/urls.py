from django.urls import path

from . import views

app_name = "paywall"

urlpatterns = [
    path("fake_gateway/", views.authorization_view, name="gateway"),
]
