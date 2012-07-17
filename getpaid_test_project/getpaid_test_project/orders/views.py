# Create your views here.
from django.views.generic.detail import DetailView
from getpaid.forms import PaymentMethodForm
from getpaid_test_project.orders.models import Order

class OrderView(DetailView):
    model=Order

    def get_context_data(self, **kwargs):
        context = super(OrderView, self).get_context_data(**kwargs)
        context['payment_form'] = PaymentMethodForm(self.object.currency, initial={'order': self.object})
        return context

