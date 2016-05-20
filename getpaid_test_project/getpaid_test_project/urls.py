from django.conf.urls import include, url
from getpaid_test_project.orders.views import OrderView, HomeView
from django.contrib import admin


admin.autodiscover()

app_name = 'getpaid_test_project'
urlpatterns = [
    url(r'^admin/', include(admin.site.urls)),

    url(r'^$', HomeView.as_view(), name='home'),
    url(r'^order/(?P<pk>\d+)/$', OrderView.as_view(), name='order_detail'),
    url(r'', include('getpaid.urls', app_name='getpaid', namespace='getpaid')),

]
