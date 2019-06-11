from django.conf.urls import url

from . import views

urlpatterns = [
    url(r"^fake_gateway/$", views.DummyAuthorizationView.as_view(), name="gateway")
]
