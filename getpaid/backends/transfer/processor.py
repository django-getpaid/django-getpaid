""""
Settings:
    message_template_name
"""
import logging

from django.conf import settings
from django.template.loader import render_to_string

from getpaid.processor import BaseProcessor

logger = logging.getLogger(__name__)


class PaymentProcessor(BaseProcessor):
    slug = settings.GETPAID_TRANSFER_SLUG
    display_name = "Transfer bankowy"
    accepted_currencies = [
        "PLN",
    ]
    default_message_template = "transfer/transfer_payment_message.html"

    def prepare_transaction(self, request=None, view=None, **kwargs):
        message_template_name = self.get_setting(
            "message_template_name", default=self.default_message_template
        )
        message = render_to_string(
            message_template_name,
            context={"order": self.payment.order, "payment": self.payment},
        )
        self.payment.message = message
        self.payment.confirm_prepared()
        self.payment.save()
