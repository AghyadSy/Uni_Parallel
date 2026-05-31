from rest_framework import serializers

from apps.orders.models import Order, OrderItem


class CheckoutItemInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)


class CheckoutRequestSerializer(serializers.Serializer):
    customer_name = serializers.CharField(max_length=120)
    items = CheckoutItemInputSerializer(many=True)
    simulate_payment_failure = serializers.BooleanField(default=False)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one item is required.")
        return value


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    sku = serializers.CharField(source="product.sku", read_only=True)

    class Meta:
        model = OrderItem
        fields = ["id", "product", "product_name", "sku", "quantity", "unit_price", "total_price"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ["id", "customer_name", "status", "total_amount", "items", "created_at", "updated_at"]
