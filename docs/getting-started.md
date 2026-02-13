# Getting Started

```{warning}
**v3.0.0a1 (Alpha)** — This is a pre-release. The API may change before the
stable v3.0 release.
```

## Installation

Install django-getpaid:

```bash
pip install django-getpaid
```

Or with uv:

```bash
uv add django-getpaid
```

Then install a payment backend plugin. Make sure the plugin supports v3 —
v2 plugins are **not** compatible:

```bash
pip install django-getpaid-payu  # if a v3-compatible version is available
```

## Create an Order model

Subclass `AbstractOrder` and implement the required methods:

```python
from django.conf import settings
from django.db import models
from django.urls import reverse
from getpaid.abstracts import AbstractOrder


class Order(AbstractOrder):
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE
    )
    description = models.CharField(max_length=128, default="Order")
    total = models.DecimalField(decimal_places=2, max_digits=8)
    currency = models.CharField(max_length=3, default="PLN")

    def get_total_amount(self):
        return self.total

    def get_buyer_info(self):
        return {"email": self.buyer.email}

    def get_description(self):
        return self.description

    def get_absolute_url(self):
        return reverse("order-detail", kwargs={"pk": self.pk})
```

```{note}
If you already have an Order model, you don't need to subclass `AbstractOrder`
— just implement the same methods.
```

## Create the initial migration

After defining your Order model, create its migration before proceeding:

```bash
./manage.py makemigrations yourapp
```

## Configure settings

```python
# settings.py

INSTALLED_APPS = [
    # ...
    "getpaid",
    "getpaid_payu",  # your chosen plugin
]

GETPAID_ORDER_MODEL = "yourapp.Order"

GETPAID_BACKEND_SETTINGS = {
    "getpaid_payu": {
        "pos_id": 12345,
        "second_key": "91ae651578c5b5aa93f2d38a9be8ce11",
        "oauth_id": 12345,
        "oauth_secret": "12f071174cb7eb79d4aac5bc2f07563f",
    },
}
```

## Add URL configuration

```python
# urls.py
from django.urls import include, path

urlpatterns = [
    # ...
    path("payments/", include("getpaid.urls")),
]
```

## Run migrations

```bash
./manage.py migrate
```

## Create a payment view

```python
from django.views.generic import DetailView
from getpaid.forms import PaymentMethodForm

class OrderView(DetailView):
    model = Order

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["payment_form"] = PaymentMethodForm(
            initial={
                "order": self.object,
                "currency": self.object.currency,
            }
        )
        return context
```

Add the template:

```html
<h2>Choose payment method:</h2>
<form action="{% url 'getpaid:create-payment' %}" method="post">
    {% csrf_token %}
    {{ payment_form.as_p }}
    <input type="submit" value="Checkout">
</form>
```

## Next steps

- {doc}`configuration` — all available settings
- {doc}`customization` — custom Payment model and payment API
- {doc}`plugins` — writing your own payment plugin
- See the [example app](https://github.com/django-getpaid/django-getpaid/tree/master/example)
  for a fully working project.
