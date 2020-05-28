import logging

from django_fsm import can_proceed

logger = logging.getLogger(__name__)


class PayuCallbackHandler:
    def __init__(self, payment):
        self.payment = payment

    def handle(self, data):
        if "order" in data:
            self._handle_order(data)
        elif "refund" in data:
            self._handle_refund(data)

        self.payment.save()

    def _handle_order(self, data):
        order_data = data.get("order")
        status = order_data.get("status")
        if status == "COMPLETED":
            self._handle_order_completed()
        elif status == "CANCELED":
            self._handle_order_canceled()
        elif status == "WAITING_FOR_CONFIRMATION":
            self._handle_order_waiting_for_confirmation()

    def _handle_refund(self, data):
        refund_data = data.get("refund")
        status = refund_data.get("status")
        if status == "FINALIZED":
            amount = int(refund_data.get("amount")) / 100
            self._handle_refund_finalized(amount)
        elif status == "CANCELED":
            self._handle_order_canceled()

    def _handle_order_completed(self):
        if can_proceed(self.payment.confirm_payment):
            self.payment.confirm_payment()
            if can_proceed(self.payment.mark_as_paid):
                self.payment.mark_as_paid()
        else:
            logger.debug(
                "Cannot confirm payment",
                extra={
                    "payment_id": self.payment.id,
                    "payment_status": self.payment.status,
                },
            )

    def _handle_order_canceled(self):
        if can_proceed(self.payment.fail):
            self.payment.fail()

    def _handle_order_waiting_for_confirmation(self):
        if can_proceed(self.payment.confirm_lock):
            self.payment.confirm_lock()
        else:
            logger.debug(
                "Already locked",
                extra={
                    "payment_id": self.payment.id,
                    "payment_status": self.payment.status,
                },
            )

    def _handle_refund_finalized(self, amount):
        if can_proceed(self.payment.confirm_refund):
            self.payment.confirm_refund(amount)
            if can_proceed(self.payment.mark_as_refunded):
                self.payment.mark_as_refunded()

    def _handle_refund_canceled(self):
        self.payment.cancel_refund()
        if can_proceed(self.payment.mark_as_paid):
            self.payment.mark_as_paid()
