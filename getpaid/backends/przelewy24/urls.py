from django.conf.urls import url
from django.views.decorators.csrf import csrf_exempt
from getpaid.backends.przelewy24.views import OnlineView, SuccessView,\
    FailureView

urlpatterns = [
    url(r'^online/$',
        csrf_exempt(OnlineView.as_view()),
        name='online'),
    url(r'^success/(?P<pk>\d+)/',
        csrf_exempt(SuccessView.as_view()),
        name='success'),
    url(r'^failure/(?P<pk>\d+)/',
        csrf_exempt(FailureView.as_view()),
        name='failure'),
]
