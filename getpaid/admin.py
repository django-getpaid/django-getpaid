from django.contrib import admin

from . import models


# Payment model is used here directly so that this PaymentAdmin does not show
# if Payment is swapped.
@admin.register(models.Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order_id",
        "amount_required",
        "currency",
        "status",
        "backend",
        "created_on",
        "last_payment_on",
        "amount_paid",
    )
    search_fields = ("id", "order_id")
    date_hierarchy = "created_on"
