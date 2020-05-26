# Create your views here.
from django import http
from django.db import transaction
from django.views import View
from django.views.generic import CreateView
from django.views.generic.detail import DetailView
from rest_framework import mixins, permissions, viewsets

from getpaid.forms import PaymentMethodForm
from getpaid.rest_framework.payment_creator import PaymentCreator

from .forms import OrderForm
from .models import Order
from .serializers import OrderSerializer


class HomeView(CreateView):
    model = Order
    template_name = "home.html"
    form_class = OrderForm

    def get_context_data(self, **kwargs):
        context = super(HomeView, self).get_context_data(**kwargs)
        context["orders"] = Order.objects.all()
        return context


class OrderView(DetailView):
    model = Order

    def get_context_data(self, **kwargs):
        context = super(OrderView, self).get_context_data(**kwargs)
        context["payment_form"] = PaymentMethodForm(
            initial={"order": self.object, "currency": self.object.currency}
        )
        return context


class OrderRestViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = OrderSerializer
    queryset = Order.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    @transaction.atomic()
    def perform_create(self, serializer):
        super().perform_create(serializer)
        self.create_payment(serializer.instance)

    def create_payment(self, order):
        payment_data = self.request.data.get("payment", {})
        return PaymentCreator(order, payment_data)


class PostGetter(View):
    def post(self, request, *args, **kwargs):
        return http.HttpResponse("OK")
