from django.urls import include, path

from . import views
from .registry import registry

app_name = 'getpaid'

urlpatterns = [
    path('new/', views.new_payment, name='create-payment'),
    path(
        'success/<uuid:pk>/',
        views.success,
        name='payment-success',
    ),
    path(
        'failure/<uuid:pk>/',
        views.failure,
        name='payment-failure',
    ),
    path(
        'callback/<uuid:pk>/',
        views.callback,
        name='callback',
    ),
    # Paymentless webhook (single Dashboard URL, no pk — e.g. Stripe). Must
    # come after the <uuid:pk> route so a real payment pk still matches it;
    # a non-uuid slug like 'stripe' falls through to here.
    path(
        'callback/<str:backend>/',
        views.backend_callback,
        name='backend-callback',
    ),
    path('health/', views.health, name='health-check'),
    path('', include(registry.urls)),
]
