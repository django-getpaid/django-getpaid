import swapper
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from getpaid.validators import run_getpaid_validators

Order = swapper.load_model("getpaid", "Order")
Payment = swapper.load_model("getpaid", "Payment")


class PaymentCreateSerializer(serializers.ModelSerializer):
    """
    Used to validate payment.
    Extracts `amount_required` & `description` from order.
    """

    class Meta:
        model = Payment
        fields = ["order", "amount_required", "description", "currency", "backend"]
        read_only_fields = ["amount_required", "description"]

    def __init__(self, *args, **kwargs):
        from getpaid.registry import registry

        super().__init__(*args, **kwargs)
        self._order = self.initial.get("order")
        currency = getattr(self._order, "currency", None) or self.initial_data.get("currency")
        backends = registry.get_choices(currency)
        self.fields["backend"] = serializers.ChoiceField(choices=backends)
        self.fields["order"] = serializers.HiddenField(default=self._order)
        self.fields["currency"] = serializers.HiddenField(default=currency)

    def validate(self, attrs):
        validated_data = super().validate(attrs)
        self._validate_order(validated_data)
        return run_getpaid_validators(validated_data)

    def _validate_order(self, validated_data):
        if hasattr(validated_data["order"], "is_ready_for_payment"):
            if not validated_data["order"].is_ready_for_payment():
                raise serializers.ValidationError(_("Order is not ready for payment."))

    def create(self, validated_data):
        validated_data["amount_required"] = self._order.get_total_amount()
        validated_data["description"] = self._order.get_description()[:256]
        return super().create(validated_data)


class PaymentDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = "__all__"
