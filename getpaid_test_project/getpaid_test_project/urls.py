from django.conf.urls import patterns, include, url
from getpaid_test_project.orders.views import OrderView, HomeView
from django.contrib import admin

admin.autodiscover()

urlpatterns = patterns('getpaid_test_project',
    url(r'^$', HomeView.as_view(), name='home'),
    url(r'^order/(?P<pk>\d+)/$', OrderView.as_view(), name='order_detail'),


    url(r'', include('getpaid.urls')),

    (r'^admin/', include(admin.site.urls)),
)
