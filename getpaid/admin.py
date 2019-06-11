from django.contrib import admin

from . import models


@admin.register(models.Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order_id",
        "amount",
        "currency",
        "status",
        "backend",
        "created_on",
        "paid_on",
        "amount_paid",
    )
    search_fields = ("id", "order_id")
    date_hierarchy = "created_on"
