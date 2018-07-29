from django.urls import path

from . import views

urlpatterns = [
    path('authorize', views.DummyAuthorizationView.as_view(), name='authorize'),

]
