from django.urls import path
from rest_framework.routers import DefaultRouter

from getpaid.rest_framework.views import CallbackDetailView, PaymentDetailViewSet

app_name = "getpaid_rest_framework"

router = DefaultRouter()
router.register("", PaymentDetailViewSet)

urlpatterns = [
    path("callback/<uuid:pk>/", CallbackDetailView.as_view(), name="callback")
]
urlpatterns += router.urls
