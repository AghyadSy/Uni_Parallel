from rest_framework import serializers

from apps.products.models import Product


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "sku",
            "price",
            "stock",
            "is_popular",
            "version",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "version", "created_at", "updated_at"]
