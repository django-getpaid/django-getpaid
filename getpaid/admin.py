import logging

from django.contrib import admin, messages
from django.db import transaction
from getpaid_core.enums import PaymentStatus

from . import models

logger = logging.getLogger(__name__)


# Payment model is used here directly so that this PaymentAdmin does not show
# if Payment is swapped.
@admin.register(models.Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'order_id',
        'amount_required',
        'currency',
        'status',
        'backend',
        'created_on',
        'last_payment_on',
        'amount_paid',
    )
    search_fields = ('id', 'order_id')
    date_hierarchy = 'created_on'

    actions = ['charge_payment', 'release_lock_action', 'start_refund']

    def _apply_payment_action(
        self,
        request,
        queryset,
        status,
        method_name,
        success_message,
        failure_message,
    ):
        """Run a payment method on each matching payment, row-locked.

        Reports both success and failure counts via admin messages and
        logs every failure with its traceback.
        """
        succeeded = 0
        failed = 0
        for payment in queryset.filter(status=status):
            try:
                with transaction.atomic():
                    locked = (
                        type(payment)
                        ._default_manager.select_for_update()
                        .get(pk=payment.pk)
                    )
                    getattr(locked, method_name)()
                succeeded += 1
            except Exception:
                failed += 1
                logger.exception(
                    'Admin action %r failed for payment %s',
                    method_name,
                    payment.pk,
                )
        if succeeded:
            self.message_user(
                request,
                success_message.format(count=succeeded),
                level=messages.SUCCESS,
            )
        if failed:
            self.message_user(
                request,
                failure_message.format(count=failed),
                level=messages.ERROR,
            )

    @admin.action(description='Charge selected pre-auth payments')
    def charge_payment(self, request, queryset):
        """Charge pre-authorized payments."""
        self._apply_payment_action(
            request,
            queryset,
            status=PaymentStatus.PRE_AUTH,
            method_name='charge',
            success_message='{count} payment(s) charged.',
            failure_message='{count} payment(s) failed to charge.',
        )

    @admin.action(description='Release locks on selected payments')
    def release_lock_action(self, request, queryset):
        """Release locks on pre-authorized payments."""
        self._apply_payment_action(
            request,
            queryset,
            status=PaymentStatus.PRE_AUTH,
            method_name='release_lock',
            success_message='{count} lock(s) released.',
            failure_message='{count} lock(s) failed to release.',
        )

    @admin.action(description='Start refunds for selected paid payments')
    def start_refund(self, request, queryset):
        """Start refunds for paid payments."""
        self._apply_payment_action(
            request,
            queryset,
            status=PaymentStatus.PAID,
            method_name='start_refund',
            success_message='{count} refund(s) started.',
            failure_message='{count} refund(s) failed to start.',
        )
