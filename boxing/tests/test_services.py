"""
Unit tests for boxing.services.box_selector.recommend_boxes.

Test scenarios
--------------
1. single_item_fits_one_box    — one item, one available box, expect it there
2. multiple_items_one_box      — several small items that all fit in one box
3. items_require_multiple_boxes — items whose total volume demands > 1 box
4. item_too_large_for_any_box  — product larger than every box → cannot_fulfill
5. cost_tie_breaking           — two equally-priced boxes exist; cheapest chosen first,
                                  then alphabetically for determinism
6. empty_order                 — no items → ok with 0 boxes and £0 cost
7. item_too_heavy_for_any_box  — product fits dimensionally but exceeds every
                                  box's max_weight → cannot_fulfill
"""

from decimal import Decimal

from django.test import TestCase

from boxing.models import Box, Order, OrderItem, Product
from boxing.services.box_selector import recommend_boxes


# ---------------------------------------------------------------------------
# Helper factories
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


def make_order(*items: tuple[Product, int]) -> Order:
    """Create an Order with (product, quantity) pairs."""
    order = Order.objects.create()
    for product, qty in items:
        OrderItem.objects.create(order=order, product=product, quantity=qty)
    return order


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestRecommendBoxesSingleItemFits(TestCase):
    """A single unit fits exactly one available box."""

    def test_single_item_fits_one_box(self) -> None:
        product = make_product(name="Mug", length=12, width=12, height=12, weight=0.3)
        box = make_box(
            name="Small Box",
            internal_length=20, internal_width=20, internal_height=20,
            max_weight=5, cost=1.50,
        )
        order = make_order((product, 1))

        result = recommend_boxes(order)

        assert result["status"] == "ok"
        assert result["box_count"] == 1
        assert result["boxes"][0]["box_id"] == box.pk
        assert result["boxes"][0]["items"][0]["product_id"] == product.pk
        assert result["boxes"][0]["items"][0]["quantity"] == 1
        assert Decimal(result["total_cost"]) == Decimal("1.50")


class TestRecommendBoxesMultipleItemsOneBox(TestCase):
    """Several small items that together fit inside a single box."""

    def test_multiple_items_one_box(self) -> None:
        # Three books — each tiny — all placed into one medium box.
        book = make_product(name="Book", length=21, width=15, height=3, weight=0.25)
        box = make_box(
            name="Medium Box",
            internal_length=40, internal_width=30, internal_height=20,
            max_weight=5, cost=2.50,
        )
        # 3 books: total vol = 3 * (21*15*3) = 2835 cm³ << 24000 cm³ box vol
        # total weight = 0.75 kg << 5 kg
        order = make_order((book, 3))

        result = recommend_boxes(order)

        assert result["status"] == "ok"
        assert result["box_count"] == 1
        assert result["boxes"][0]["box_id"] == box.pk
        assert result["boxes"][0]["items"][0]["quantity"] == 3
        assert Decimal(result["total_cost"]) == Decimal("2.50")


class TestRecommendBoxesMultipleBoxesRequired(TestCase):
    """Items that overflow one box and require a second."""

    def test_items_require_multiple_boxes(self) -> None:
        # Each unit is a 10-cm cube (volume = 1000 cm³, weight = 1 kg).
        # The box is 11×11×11 cm (volume = 1331 cm³, max_weight = 5 kg).
        # Sorted product dims [10,10,10] ≤ sorted box dims [11,11,11] → fits.
        # One unit leaves only 331 cm³ remaining — not enough for a second
        # 1000 cm³ unit, so a second box must be opened.
        product = make_product(
            name="Big Cube", length=10, width=10, height=10, weight=1.0
        )
        box = make_box(
            name="Tiny Box",
            internal_length=11, internal_width=11, internal_height=11,
            # internal vol = 1331 cm³ — fits one 10³=1000 cm³ product,
            # second unit overflows (remaining 331 cm³ < 1000 cm³)
            max_weight=5, cost=3.00,
        )
        order = make_order((product, 2))

        result = recommend_boxes(order)

        assert result["status"] == "ok"
        assert result["box_count"] == 2
        assert Decimal(result["total_cost"]) == Decimal("6.00")


class TestRecommendBoxesItemTooLargeForAnyBox(TestCase):
    """A product that cannot fit in any box → cannot_fulfill."""

    def test_item_too_large_for_any_box(self) -> None:
        # Product is a 50 cm cube; no box is large enough.
        giant = make_product(name="Wardrobe", length=50, width=50, height=50, weight=1.0)
        make_box(
            name="Biggest Box",
            internal_length=40, internal_width=40, internal_height=40,
            max_weight=30, cost=5.00,
        )
        order = make_order((giant, 1))

        result = recommend_boxes(order)

        assert result["status"] == "cannot_fulfill"
        assert "Wardrobe" in result["reason"]


class TestRecommendBoxesCostTieBreaking(TestCase):
    """
    Two box types with identical cost — cheapest chosen first, then
    alphabetical name used as tiebreaker for determinism.
    """

    def test_cost_tie_breaking_alphabetical(self) -> None:
        product = make_product(name="Gadget", length=5, width=5, height=5, weight=0.1)
        # Two boxes with same cost; "Alpha Box" < "Zeta Box" alphabetically.
        alpha = make_box(
            name="Alpha Box",
            internal_length=20, internal_width=20, internal_height=20,
            max_weight=5, cost=2.00,
        )
        zeta = make_box(
            name="Zeta Box",
            internal_length=20, internal_width=20, internal_height=20,
            max_weight=5, cost=2.00,
        )
        order = make_order((product, 1))

        result = recommend_boxes(order)

        assert result["status"] == "ok"
        # "Alpha Box" should win the tiebreak.
        assert result["boxes"][0]["box_id"] == alpha.pk

    def test_cheaper_box_wins_over_larger_expensive_box(self) -> None:
        product = make_product(name="Gadget", length=5, width=5, height=5, weight=0.1)
        cheap = make_box(
            name="Cheap Small",
            internal_length=20, internal_width=20, internal_height=20,
            max_weight=5, cost=1.00,
        )
        expensive = make_box(
            name="Expensive Large",
            internal_length=40, internal_width=40, internal_height=40,
            max_weight=10, cost=5.00,
        )
        order = make_order((product, 1))

        result = recommend_boxes(order)

        assert result["status"] == "ok"
        assert result["boxes"][0]["box_id"] == cheap.pk


class TestRecommendBoxesEmptyOrder(TestCase):
    """An order with no items returns ok with zero boxes and zero cost."""

    def test_empty_order(self) -> None:
        order = Order.objects.create()  # no OrderItems

        result = recommend_boxes(order)

        assert result["status"] == "ok"
        assert result["box_count"] == 0
        assert result["boxes"] == []
        assert Decimal(result["total_cost"]) == Decimal("0.00")


class TestRecommendBoxesItemTooHeavy(TestCase):
    """
    Product fits dimensionally but exceeds every box's max_weight.
    """

    def test_item_too_heavy_for_any_box(self) -> None:
        heavy = make_product(
            name="Lead Block", length=5, width=5, height=5, weight=50.0
        )
        # Box is big enough dimensionally but max_weight is tiny.
        make_box(
            name="Featherweight Box",
            internal_length=30, internal_width=30, internal_height=30,
            max_weight=1.0, cost=2.00,
        )
        order = make_order((heavy, 1))

        result = recommend_boxes(order)

        assert result["status"] == "cannot_fulfill"
        assert "Lead Block" in result["reason"]
