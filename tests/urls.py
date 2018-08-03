from django.conf.urls import url, include

urlpatterns = [
    url(r'^payments/', include('getpaid.urls', namespace='getpaid')),
]
