from django.contrib import admin

from . import models


@admin.register(models.CustomPayment)
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
        'custom',
    )
    search_fields = ('id', 'order_id')
    date_hierarchy = 'created_on'


@admin.register(models.Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'name',
        'total',
        'currency',
        'status',
    )
