from decimal import Decimal

from django.http import HttpResponseBadRequest
from getpaid_core.backends.dummy import DummyProcessor
from getpaid_core.enums import BackendMethod, PaymentEvent
from getpaid_core.types import (
    ChargeResult,
    PaymentUpdate,
    RefundResult,
    TransactionResult,
)

from getpaid.post_forms import PaymentHiddenInputsPostForm
from getpaid.processor import BaseProcessor


class PaymentProcessor(BaseProcessor, DummyProcessor):
    slug = 'dummy'
    display_name = 'Dummy'
    accepted_currencies = ['PLN', 'EUR', 'USD', 'GBP', 'CHF', 'CZK']
    post_form_class = PaymentHiddenInputsPostForm
    post_template_name = 'getpaid_dummy/payment_post_form.html'
    sandbox_url = 'https://dummy.example.com'
    production_url = 'https://dummy.example.com'

    def get_paywall_method(self):
        return self.get_setting('paywall_method', 'REST')

    async def prepare_transaction(self, **kwargs) -> TransactionResult:
        method = BackendMethod(self.get_paywall_method())
        if method is BackendMethod.POST:
            return TransactionResult(
                method=method,
                redirect_url='https://dummy.example.com/form',
                form_data={
                    'payment_id': str(self.payment.id),
                    'amount': f'{self.payment.amount_required:.2f}',
                    'currency': self.payment.currency,
                },
            )
        return TransactionResult(
            method=method,
            redirect_url=f'https://dummy.example.com/pay/{self.payment.id}',
        )

    async def handle_callback(self, data, headers, **kwargs):
        if 'event' in data:
            return await DummyProcessor.handle_callback(
                self, data, headers, **kwargs
            )

        new_status = data.get('new_status')
        if not new_status:
            return HttpResponseBadRequest(b'Missing new_status')

        if new_status == 'paid':
            return await DummyProcessor.handle_callback(
                self,
                {
                    'event': 'payment_confirmed',
                    'paid_amount': str(self.payment.amount_required),
                },
                headers,
                **kwargs,
            )
        if new_status == 'pre-auth':
            return await DummyProcessor.handle_callback(
                self,
                {
                    'event': 'payment_locked',
                    'locked_amount': str(self.payment.amount_required),
                },
                headers,
                **kwargs,
            )
        if new_status == 'failed':
            return await DummyProcessor.handle_callback(
                self,
                {'event': 'payment_failed'},
                headers,
                **kwargs,
            )
        if new_status == 'refund_started':
            return PaymentUpdate(payment_event=PaymentEvent.REFUND_REQUESTED)
        if new_status == 'refunded':
            return PaymentUpdate(
                payment_event=PaymentEvent.REFUND_CONFIRMED,
                refunded_amount=self.payment.amount_paid,
            )
        return HttpResponseBadRequest(
            f'Unhandled status: {new_status}'.encode()
        )

    def handle_paywall_callback(self, request, **kwargs):
        from getpaid.runtime import handle_callback_request

        return handle_callback_request(self.payment, request, **kwargs)

    async def fetch_payment_status(self, **kwargs):
        confirmation_status = self.get_setting('confirmation_status', 'paid')
        confirmation_event = {
            'paid': 'payment_confirmed',
            'pre_auth': 'payment_locked',
            'failed': 'payment_failed',
        }.get(confirmation_status, 'payment_confirmed')
        self.config['confirmation_event'] = confirmation_event
        return await DummyProcessor.fetch_payment_status(self, **kwargs)

    async def charge(self, amount=None, **kwargs) -> ChargeResult:
        return await DummyProcessor.charge(self, amount=amount, **kwargs)

    async def release_lock(self, **kwargs):
        return await DummyProcessor.release_lock(self, **kwargs)

    async def start_refund(self, amount=None, **kwargs) -> RefundResult:
        refund_amount = (
            amount if amount is not None else self.payment.amount_paid
        )
        return RefundResult(
            amount=Decimal(str(refund_amount)),
            provider_data={'refund_id': f'dummy-refund-{self.payment.id}'},
        )

    async def cancel_refund(self, **kwargs):
        return True
