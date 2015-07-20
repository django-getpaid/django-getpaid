from django.conf.urls import patterns, url
from django.views.decorators.csrf import csrf_exempt
from getpaid.backends.epaydk.views import CallbackView, AcceptView, CancelView

urlpatterns = patterns('',
    url(r'^online/(?P<secret_path>[a-zA-Z0-9]{32,96})/$',
        csrf_exempt(CallbackView.as_view()),
        name='getpaid-epaydk-online'),
    url(r'^online/$',
        csrf_exempt(CallbackView.as_view()),
        name='getpaid-epaydk-online'),
    url(r'^success/',
        csrf_exempt(AcceptView.as_view()),
        name='getpaid-epaydk-success'),
    url(r'^failure/',
        csrf_exempt(CancelView.as_view()),
        name='getpaid-epaydk-failure'),

)
