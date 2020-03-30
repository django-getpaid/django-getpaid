from django.contrib import admin
from django.urls import include, path, re_path
from orders.views import HomeView, OrderView

app_name = "getpaid_example"

urlpatterns = [
    path("admin/", admin.site.urls),
    re_path(r"^$", HomeView.as_view(), name="home"),
    path("order/<int:pk>/", OrderView.as_view(), name="order_detail"),
    path("payments/", include("getpaid.urls")),
    path("paywall/", include("paywall.urls")),
]
