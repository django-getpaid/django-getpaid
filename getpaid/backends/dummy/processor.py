"""Dummy payment backend for development and testing.

Self-contained processor simulating payment flows without external
HTTP calls. Supports REST/POST/GET initiation and PUSH/PULL confirmation.

Settings (via GETPAID_BACKEND_SETTINGS['getpaid.backends.dummy']):
    paywall_method: 'REST' | 'POST' | 'GET' (default: 'REST')
    confirmation_method: 'PUSH' | 'PULL' (default: 'PUSH')
"""

import json
import logging
from decimal import Decimal

from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
)
from django.template.response import TemplateResponse
from getpaid_core.fsm import create_payment_machine
from transitions.core import MachineError

from getpaid.post_forms import PaymentHiddenInputsPostForm
from getpaid.processor import BaseProcessor
from getpaid.types import PaymentStatus as ps

logger = logging.getLogger(__name__)


def _can_trigger(payment, trigger_name):
    """Check if a trigger can proceed without actually firing it."""
    trigger = getattr(payment, trigger_name, None)
    if trigger is None:
        return False
    try:
        return payment.may_trigger(trigger_name)
    except (AttributeError, MachineError):
        # If machine not attached or method unavailable
        return False


class PaymentProcessor(BaseProcessor):
    slug = 'dummy'
    display_name = 'Dummy'
    accepted_currencies = ['PLN', 'EUR']
    ok_statuses = [200]
    method = 'REST'
    confirmation_method = 'PUSH'
    post_form_class = PaymentHiddenInputsPostForm
    post_template_name = 'getpaid_dummy/payment_post_form.html'

    def get_paywall_method(self):
        return self.get_setting('paywall_method', self.method)

    def get_confirmation_method(self):
        return self.get_setting(
            'confirmation_method', self.confirmation_method
        ).upper()

    def prepare_transaction(self, request=None, view=None, **kwargs):
        """Simulate payment preparation. No external HTTP calls."""
        method = self.get_paywall_method()

        # Ensure FSM is attached
        create_payment_machine(self.payment)
        self.payment.confirm_prepared()  # ty: ignore[possibly-missing-attribute]
        self.payment.save()  # ty: ignore[possibly-missing-attribute]

        if method == 'POST':
            params = {
                'amount': str(self.payment.amount_required),
                'currency': self.payment.currency,
                'description': self.payment.description,
            }
            form = self.get_form(params)
            return TemplateResponse(
                request=request,
                template=self.get_template_names(view=view),
                context={'form': form, 'paywall_url': '#dummy'},
            )

        redirect_url = self.get_our_baseurl(request)
        return HttpResponseRedirect(redirect_url)

    def handle_paywall_callback(self, request, **kwargs):
        """Handle a simulated callback with JSON body."""
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return HttpResponseBadRequest('Invalid JSON')

        new_status = data.get('new_status')
        if new_status is None:
            return HttpResponseBadRequest('Missing new_status')

        create_payment_machine(self.payment)

        if new_status == ps.FAILED:
            self.payment.fail()  # ty: ignore[possibly-missing-attribute]
        elif new_status == ps.PRE_AUTH:
            self.payment.confirm_lock()  # ty: ignore[possibly-missing-attribute]
        elif new_status == ps.PAID:
            if _can_trigger(self.payment, 'confirm_lock'):
                self.payment.confirm_lock()  # ty: ignore[possibly-missing-attribute]
            if _can_trigger(self.payment, 'confirm_payment'):
                self.payment.confirm_payment()  # ty: ignore[possibly-missing-attribute]
            if _can_trigger(self.payment, 'mark_as_paid'):
                try:
                    self.payment.mark_as_paid()  # ty: ignore[possibly-missing-attribute]
                except MachineError:
                    logger.debug(
                        'Cannot mark as paid (guard failed).',
                        extra={
                            'payment_id': self.payment.id,
                        },
                    )
        else:
            return HttpResponseBadRequest(f'Unhandled status: {new_status}')

        self.payment.save()  # ty: ignore[possibly-missing-attribute]
        return HttpResponse('OK')

    def fetch_payment_status(self, **kwargs):
        """Simulate fetching status from external provider."""
        status = self.payment.status
        simulated = self.get_setting('confirmation_status', 'paid')

        if status in (
            ps.PAID,
            ps.FAILED,
            ps.REFUNDED,
            ps.REFUND_STARTED,
        ):
            return {}

        if status == ps.NEW:
            return {}

        if simulated == 'failed':
            return {'callback': 'fail'}
        if simulated == 'pre_auth':
            return {'callback': 'confirm_lock'}
        return {
            'callback': 'confirm_payment',
            'amount': self.payment.amount_required,
        }

    def charge(self, amount=None, **kwargs):
        """Simulate charging a pre-authorized amount."""
        if amount is None:
            amount = self.payment.amount_locked
        return {
            'amount_charged': Decimal(str(amount)),
            'success': True,
        }

    def release_lock(self, **kwargs):
        """Simulate releasing a locked amount."""
        return Decimal(str(self.payment.amount_locked))

    def start_refund(self, amount=None, **kwargs):
        """Simulate starting a refund."""
        if amount is None:
            amount = self.payment.amount_paid
        return Decimal(str(amount))

    def cancel_refund(self, **kwargs):
        """Simulate cancelling a refund."""
        return True
