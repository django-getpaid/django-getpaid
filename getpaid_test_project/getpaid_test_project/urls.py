from django.conf.urls import patterns, include, url
from django.views.generic.edit import CreateView
from getpaid_test_project.orders.forms import OrderForm
from getpaid_test_project.orders.models import Order
from getpaid_test_project.orders.views import OrderView

urlpatterns = patterns('getpaid_test_project',
    url(r'^$', CreateView.as_view(model=Order, template_name='home.html', form_class=OrderForm), name='home'),
    url(r'^order/(?P<pk>\d+)/$', OrderView.as_view(), name='order_detail'),


     url(r'', include('getpaid.urls')),


)
