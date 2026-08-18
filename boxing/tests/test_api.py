"""
API integration tests for POST /api/orders/recommend-box/.

Test scenarios
--------------
1. happy_path              — valid products, expect 200 with box assignment
2. cannot_fulfill_path     — product too large for any box, expect 422
3. missing_items_field     — body without "items" key, expect 400
4. empty_items_list        — "items": [], expect 400
5. invalid_product_id      — non-existent product_id, expect 400
6. zero_quantity           — quantity=0, expect 400
7. order_and_items_created — verify DB rows after a successful call
"""

import json

from django.test import TestCase
from django.urls import reverse

from boxing.models import Box, Order, OrderItem, Product


# URL name declared in boxing/urls.py → included under api/ prefix.
ENDPOINT = "/api/orders/recommend-box/"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_product(
    name: str = "Widget",
    length: float = 10.0,
    width: float = 10.0,
    height: float = 10.0,
    weight: float = 0.5,
) -> Product:
    return Product.objects.create(
        name=name, length=length, width=width, height=height, weight=weight
    )


def make_box(
    name: str = "Standard Box",
    internal_length: float = 30.0,
    internal_width: float = 30.0,
    internal_height: float = 30.0,
    max_weight: float = 10.0,
    cost: float = 2.00,
) -> Box:
    return Box.objects.create(
        name=name,
        internal_length=internal_length,
        internal_width=internal_width,
        internal_height=internal_height,
        max_weight=max_weight,
        cost=cost,
    )


class TestRecommendBoxAPIHappyPath(TestCase):
    def setUp(self) -> None:
        self.product = make_product(name="Phone", length=15, width=8, height=2, weight=0.2)
        self.box = make_box(
            name="Small Box",
            internal_length=20, internal_width=15, internal_height=10,
            max_weight=5, cost=1.50,
        )

    def test_happy_path_returns_200(self) -> None:
        response = self.client.post(
            ENDPOINT,
            data=json.dumps({"items": [{"product_id": self.product.pk, "quantity": 2}]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("boxes", data)
        self.assertIn("total_cost", data)
        self.assertGreater(data["box_count"], 0)

    def test_happy_path_response_structure(self) -> None:
        """Verify every expected key is present in the response."""
        response = self.client.post(
            ENDPOINT,
            data=json.dumps({"items": [{"product_id": self.product.pk, "quantity": 1}]}),
            content_type="application/json",
        )
        data = response.json()
        self.assertEqual(data["status"], "ok")
        box_entry = data["boxes"][0]
        self.assertIn("box_name", box_entry)
        self.assertIn("box_id", box_entry)
        self.assertIn("items", box_entry)
        self.assertIn("cost", box_entry)
        item_entry = box_entry["items"][0]
        self.assertIn("product_id", item_entry)
        self.assertIn("product_name", item_entry)
        self.assertIn("quantity", item_entry)


class TestRecommendBoxAPICannotFulfill(TestCase):
    def setUp(self) -> None:
        # Product too large for the only available box.
        self.giant = make_product(
            name="Giant Crate", length=100, width=100, height=100, weight=1.0
        )
        make_box(
            name="Tiny Box",
            internal_length=20, internal_width=20, internal_height=20,
            max_weight=5, cost=2.00,
        )

    def test_cannot_fulfill_returns_422(self) -> None:
        response = self.client.post(
            ENDPOINT,
            data=json.dumps({"items": [{"product_id": self.giant.pk, "quantity": 1}]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        data = response.json()
        self.assertIn("error", data)
        self.assertIn("Giant Crate", data["error"])


class TestRecommendBoxAPIValidation(TestCase):
    def setUp(self) -> None:
        self.product = make_product()
        make_box()

    def test_missing_items_field_returns_400(self) -> None:
        response = self.client.post(
            ENDPOINT,
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_empty_items_list_returns_400(self) -> None:
        response = self.client.post(
            ENDPOINT,
            data=json.dumps({"items": []}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_product_id_returns_400(self) -> None:
        response = self.client.post(
            ENDPOINT,
            data=json.dumps({"items": [{"product_id": 99999, "quantity": 1}]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_zero_quantity_returns_400(self) -> None:
        response = self.client.post(
            ENDPOINT,
            data=json.dumps({"items": [{"product_id": self.product.pk, "quantity": 0}]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_negative_quantity_returns_400(self) -> None:
        response = self.client.post(
            ENDPOINT,
            data=json.dumps({"items": [{"product_id": self.product.pk, "quantity": -1}]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)


class TestRecommendBoxAPIOrderCreation(TestCase):
    """Verify that a successful request creates the expected DB rows."""

    def test_order_and_items_created(self) -> None:
        product = make_product(name="Mug", length=12, width=12, height=12, weight=0.3)
        make_box(
            internal_length=20, internal_width=20, internal_height=20,
            max_weight=5, cost=1.50,
        )
        orders_before = Order.objects.count()

        response = self.client.post(
            ENDPOINT,
            data=json.dumps({"items": [{"product_id": product.pk, "quantity": 3}]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        # One new Order created.
        self.assertEqual(Order.objects.count(), orders_before + 1)
        # One OrderItem created with quantity=3.
        latest_order = Order.objects.order_by("-created_at").first()
        items = latest_order.items.all()
        self.assertEqual(items.count(), 1)
        self.assertEqual(items.first().quantity, 3)
        self.assertEqual(items.first().product, product)
