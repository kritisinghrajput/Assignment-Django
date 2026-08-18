"""DRF serializers for the boxing app."""

from rest_framework import serializers

from boxing.models import Order, OrderItem, Product


class OrderItemInputSerializer(serializers.Serializer):
    """Validates a single line item in the recommend-box request body."""

    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1)

    def validate_product_id(self, value: int) -> int:
        """Ensure the referenced product exists."""
        if not Product.objects.filter(pk=value).exists():
            raise serializers.ValidationError(f"Product with id={value} does not exist.")
        return value


class RecommendBoxInputSerializer(serializers.Serializer):
    """
    Top-level request serializer.

    Accepts a list of {product_id, quantity} pairs and validates that:
    - The list is non-empty.
    - Each product_id refers to an existing Product.
    - All quantities are positive integers.
    """

    items = OrderItemInputSerializer(many=True)

    def validate_items(self, value: list) -> list:
        if not value:
            raise serializers.ValidationError("At least one item is required.")
        return value
