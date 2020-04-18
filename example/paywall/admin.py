from django.contrib import admin
from django.contrib.admin import ModelAdmin
from paywall.models import PaymentEntry


@admin.register(PaymentEntry)
class PaymentEntryAdmin(ModelAdmin):
    pass
