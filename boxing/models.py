"""Models for the boxing app.

Three core domain objects:
- Product: an item that can be shipped
- Box: a container used for shipping
- Order / OrderItem: customer order with line items
"""

from django.core.validators import MinValueValidator
from django.db import models


class Product(models.Model):
    """A shippable product with physical dimensions and weight."""

    name = models.CharField(max_length=255)
    length = models.DecimalField(max_digits=10, decimal_places=2, help_text="cm", validators=[MinValueValidator(0)])
    width = models.DecimalField(max_digits=10, decimal_places=2, help_text="cm", validators=[MinValueValidator(0)])
    height = models.DecimalField(max_digits=10, decimal_places=2, help_text="cm", validators=[MinValueValidator(0)])
    weight = models.DecimalField(max_digits=10, decimal_places=3, help_text="kg", validators=[MinValueValidator(0)])

    def __str__(self) -> str:
        return self.name


class Box(models.Model):
    """A shipping box with internal dimensions, weight limit, and per-unit cost."""

    name = models.CharField(max_length=255)
    internal_length = models.DecimalField(max_digits=10, decimal_places=2, help_text="cm", validators=[MinValueValidator(0)])
    internal_width = models.DecimalField(max_digits=10, decimal_places=2, help_text="cm", validators=[MinValueValidator(0)])
    internal_height = models.DecimalField(max_digits=10, decimal_places=2, help_text="cm", validators=[MinValueValidator(0)])
    max_weight = models.DecimalField(max_digits=10, decimal_places=3, help_text="kg", validators=[MinValueValidator(0)])
    cost = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])

    def __str__(self) -> str:
        return self.name


class Order(models.Model):
    """A customer order, timestamped at creation."""

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Order #{self.pk}"


class OrderItem(models.Model):
    """A line item in an order: which product and how many."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    quantity = models.PositiveIntegerField()

    def __str__(self) -> str:
        return f"{self.quantity}× {self.product.name}"
