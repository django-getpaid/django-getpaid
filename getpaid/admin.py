from django.contrib import admin

from . import models


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

    def charge_payment(self, request, queryset):
        """Charge pre-authorized payments."""
        charged = 0
        for payment in queryset.filter(status='pre-auth'):
            try:
                payment.charge()
                charged += 1
            except Exception:
                pass
        self.message_user(
            request, f'{charged} payment(s) charged.'
        )

    charge_payment.short_description = 'Charge selected pre-auth payments'

    def release_lock_action(self, request, queryset):
        """Release locks on pre-authorized payments."""
        released = 0
        for payment in queryset.filter(status='pre-auth'):
            try:
                payment.release_lock()
                released += 1
            except Exception:
                pass
        self.message_user(
            request, f'{released} lock(s) released.'
        )

    release_lock_action.short_description = 'Release locks on selected payments'

    def start_refund(self, request, queryset):
        """Start refunds for paid payments."""
        started = 0
        for payment in queryset.filter(status='paid'):
            try:
                payment.start_refund()
                started += 1
            except Exception:
                pass
        self.message_user(
            request, f'{started} refund(s) started.'
        )

    start_refund.short_description = 'Start refunds for selected paid payments'
