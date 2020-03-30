from django.urls import path

from .views import DummyCallbackView

urlpatterns = [path("dummy_callback/", DummyCallbackView.as_view(), name="dummy")]
