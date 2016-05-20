from django.conf.urls import url
from django.views.decorators.csrf import csrf_exempt
from getpaid.backends.dotpay.views import ReturnView
from getpaid.backends.dotpay.views import OnlineView

urlpatterns = [
    url(r'^online/$',
        csrf_exempt(OnlineView.as_view()),
        name='online'),
    url(r'^return/(?P<pk>\d+)/$',
        csrf_exempt(ReturnView.as_view()),
        name='return'),
]
