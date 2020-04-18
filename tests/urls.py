from django.urls import include, path
from orders.views import OrderView

urlpatterns = [
    path("order/<int:pk>/", OrderView.as_view(), name="order_detail"),
    path("payments/", include("getpaid.urls")),
    path("paywall/", include("paywall.urls")),
]
