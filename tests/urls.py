from django.conf.urls import include, url

urlpatterns = [url(r"^payments/", include("getpaid.urls", namespace="getpaid"))]
