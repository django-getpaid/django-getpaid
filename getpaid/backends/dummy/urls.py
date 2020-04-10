from django.urls import path

from .views import callback

urlpatterns = [
    path("callback/<uuid:pk>/", callback, name="callback"),
]
