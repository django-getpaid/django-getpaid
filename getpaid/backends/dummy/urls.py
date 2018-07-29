from django.urls import path

from . import views

urlpatterns = [
    path('fake_gateway', views.DummyAuthorizationView.as_view(), name='gateway'),

]
