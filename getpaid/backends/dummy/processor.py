"""
Dummy payment backend for development and testing.

This is a self-contained processor that simulates payment flows without
making any external HTTP calls. It supports all three payment initiation
methods (REST, POST, GET) and both confirmation methods (PUSH, PULL).

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
from django_fsm import can_proceed

from getpaid.post_forms import PaymentHiddenInputsPostForm
from getpaid.processor import BaseProcessor
from getpaid.types import PaymentStatus as ps

logger = logging.getLogger(__name__)


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

    def prepare_transaction(self, request, view=None, **kwargs):
        """
        Simulate payment preparation. No external HTTP calls are made.

        - REST/GET: Confirms prepared, returns redirect to success URL.
        - POST: Confirms prepared, returns a template response with a form.
        """
        method = self.get_paywall_method()
        self.payment.confirm_prepared()
        self.payment.save()

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

        # REST and GET both return a redirect
        redirect_url = self.get_our_baseurl(request)
        return HttpResponseRedirect(redirect_url)

    def handle_paywall_callback(self, request, **kwargs):
        """
        Handle a simulated callback. Expects JSON body with 'new_status'.

        Returns HTTP 200 on success, HTTP 400 on bad input.
        """
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return HttpResponseBadRequest('Invalid JSON')

        new_status = data.get('new_status')
        if new_status is None:
            return HttpResponseBadRequest('Missing new_status')

        if new_status == ps.FAILED:
            self.payment.fail()
        elif new_status == ps.PRE_AUTH:
            self.payment.confirm_lock()
        elif new_status == ps.PAID:
            if can_proceed(self.payment.confirm_lock):
                self.payment.confirm_lock()
            if can_proceed(self.payment.confirm_payment):
                self.payment.confirm_payment()
            if can_proceed(self.payment.mark_as_paid):
                self.payment.mark_as_paid()
        else:
            return HttpResponseBadRequest(f'Unhandled status: {new_status}')

        self.payment.save()
        return HttpResponse('OK')

    def fetch_payment_status(self, **kwargs):
        """
        Simulate fetching payment status from an external provider.

        In PULL mode, this is called to discover what happened with the
        payment. The dummy backend simulates a successful payment flow
        by returning the "next step" callback:

        - PREPARED -> confirm_payment (provider says: "payment received")
        - PRE_AUTH -> confirm_payment (provider says: "charge completed")
        - PARTIAL -> confirm_payment (provider says: "more payment received")
        - Already PAID/FAILED/REFUNDED -> no callback (terminal states)

        The ``confirmation_status`` setting can override the simulated
        outcome: 'paid' (default), 'pre_auth', or 'failed'.
        """
        status = self.payment.status
        simulated = self.get_setting('confirmation_status', 'paid')

        # Terminal states — nothing more to do
        if status in (ps.PAID, ps.FAILED, ps.REFUNDED, ps.REFUND_STARTED):
            return {}

        # NEW — not yet prepared, no callback
        if status == ps.NEW:
            return {}

        # Simulate the provider's response based on configuration
        if simulated == 'failed':
            return {'callback': 'fail'}
        elif simulated == 'pre_auth':
            return {'callback': 'confirm_lock'}
        else:
            # Default: simulate successful payment
            return {
                'callback': 'confirm_payment',
                'amount': self.payment.amount_required,
            }

    def charge(self, amount=None, **kwargs):
        """
        Simulate charging a pre-authorized amount.

        Returns a ChargeResponse dict with the charged amount.
        """
        if amount is None:
            amount = self.payment.amount_locked
        return {
            'amount_charged': Decimal(str(amount)),
            'success': True,
        }

    def release_lock(self, **kwargs):
        """
        Simulate releasing a locked amount.

        Returns the released amount as a Decimal.
        """
        return Decimal(str(self.payment.amount_locked))

    def start_refund(self, amount=None, **kwargs):
        """
        Simulate starting a refund.

        Returns the refund amount as a Decimal.
        """
        if amount is None:
            amount = self.payment.amount_paid
        return Decimal(str(amount))

    def cancel_refund(self, **kwargs):
        """
        Simulate cancelling a refund.

        Returns True (always succeeds in dummy mode).
        """
        return True
