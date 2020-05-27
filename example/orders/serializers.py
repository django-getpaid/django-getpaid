import swapper
from rest_framework import serializers

Order = swapper.load_model("getpaid", "Order")


class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ("id", "name", "total", "currency", "status")
        read_only_fields = ["payments"]
