from django.urls import path, include, re_path

from . import views
from .registry import registry

app_name = 'getpaid'

urlpatterns = [
    re_path(r'^new/(?P<currency>[A-Z]{3})/$', views.CreatePaymentView.as_view(), name='create-payment'),
    path('success/<uuid:pk>/', views.SuccessView.as_view(), name='payment-success'),
    path('failure/<uuid:pk>/', views.FailureView.as_view(), name='payment-failure'),
    path('callback/<uuid:pk>/', views.CallbackView.as_view(), name='callback-detail'),
    path('backends/', include(registry.urls)),
]
