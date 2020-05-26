from rest_framework import serializers

from getpaid.rest_framework.serializers import PaymentCreateSerializer


class PaymentCreator:
    def __init__(self, order_instance, raw_payment_data):
        self.order_instance = order_instance
        self.raw_payment_data = raw_payment_data

    def create(self):
        payment_serializer_kwargs = {
            "data": self.raw_payment_data,
            "initial": {"order": self.order_instance,},
        }
        payment_serializer = PaymentCreateSerializer(**payment_serializer_kwargs)
        # Re-raise serializer error with correct nesting
        try:
            payment_serializer.is_valid(raise_exception=True)
        except serializers.ValidationError as e:
            serializer_error = serializers.as_serializer_error(e)
            raise serializers.ValidationError({"payment": serializer_error})
        payment = payment_serializer.save()
        return payment
