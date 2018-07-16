from django.conf.urls import url

from .views import ConfirmationWebhook


urlpatterns = [
    url(r'^confirm/$', ConfirmationWebhook.as_view(), name='confirm'),
]
