"""
Box selection service — Greedy First-Fit Decreasing (FFD) heuristic.

DISCLAIMER
----------
This is a *heuristic* algorithm, not an optimal 3D bin-packing solver.
True 3D bin-packing is NP-hard; the greedy FFD approach used here trades
optimality for simplicity and speed.  In practice it gives reasonable results
for typical e-commerce parcel sizes, but may use more boxes than strictly
necessary in pathological cases (e.g., many items of similar volume competing
for the same box).

Algorithm overview
------------------
1. Expand order items into individual product units.
2. Check that every unit can physically fit in *at least one* box
   (in any of its six axial rotations).  Abort early if not.
3. Sort units by descending volume (largest first) — FFD ordering.
4. For each unit, scan already-opened boxes for the first one that has
   enough remaining weight and volume capacity.  If found, place there.
5. If no open box can accept the unit, open the *cheapest* box type that
   can fit this unit (ties broken by name for determinism).
6. Return a structured result with box assignments and total cost.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from boxing.models import Box, Order, Product


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class _Unit:
    """A single physical product instance expanded from an OrderItem."""

    product: "Product"
    # Pre-computed volume for sorting; kept as Decimal for precision.
    volume: Decimal


@dataclass
class _OpenBox:
    """Tracks an opened shipping box instance during packing."""

    box: "Box"
    # Remaining weight capacity (kg).
    remaining_weight: Decimal
    # Remaining internal volume (cm³).  We use volumetric packing as a proxy
    # for spatial packing.  True 3D placement is not modelled.
    remaining_volume: Decimal
    # Units placed in this box so far.
    units: list[_Unit] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def _product_volume(product: "Product") -> Decimal:
    """Return the product's volume in cm³."""
    return Decimal(product.length) * Decimal(product.width) * Decimal(product.height)


def _box_volume(box: "Box") -> Decimal:
    """Return the box's internal volume in cm³."""
    return (
        Decimal(box.internal_length)
        * Decimal(box.internal_width)
        * Decimal(box.internal_height)
    )


def _fits_in_box(product: "Product", box: "Box") -> bool:
    """
    Return True if the product can fit inside the box in *any* axial rotation.

    We enumerate all 6 permutations of (l, w, h) and check whether the
    product's sorted dimensions fit inside the box's sorted dimensions.
    Sorting both sides means we only need one comparison per permutation.

    Note: this is a necessary-but-not-sufficient condition for true 3D
    placement when a box already contains other items.  For the feasibility
    pre-check (step 2) it is used against an empty box.
    """
    prod_dims = sorted([
        Decimal(product.length),
        Decimal(product.width),
        Decimal(product.height),
    ])
    box_dims = sorted([
        Decimal(box.internal_length),
        Decimal(box.internal_width),
        Decimal(box.internal_height),
    ])
    # After sorting, prod_dims[i] <= box_dims[i] for all i is sufficient.
    return all(p <= b for p, b in zip(prod_dims, box_dims))


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------

def recommend_boxes(order: "Order") -> dict:
    """
    Recommend shipping boxes for the given Order using a greedy FFD heuristic.

    Parameters
    ----------
    order:
        A saved :class:`~boxing.models.Order` instance with related
        ``items`` (OrderItem queryset) and each item's ``product`` prefetched.

    Returns
    -------
    dict with one of two shapes:

    Success::

        {
            "status": "ok",
            "boxes": [
                {
                    "box_name": str,
                    "box_id": int,
                    "items": [{"product_id": int, "product_name": str, "quantity": int}, ...],
                    "cost": str,   # Decimal as string
                },
                ...
            ],
            "total_cost": str,   # Decimal as string
            "box_count": int,
        }

    Failure (unfulfillable)::

        {
            "status": "cannot_fulfill",
            "reason": str,
        }

    Algorithm
    ---------
    Uses a **Greedy First-Fit Decreasing** heuristic:

    1. Expand each OrderItem into *quantity* individual unit objects.
    2. Pre-check: every unit must fit dimensionally in at least one box type.
    3. Sort units by descending volume (FFD ordering).
    4. For each unit, find the first already-opened box with sufficient
       remaining weight AND volume capacity.
    5. If no open box fits, open the cheapest eligible box type.
    6. Aggregate results per opened box.

    This is a heuristic — it does **not** guarantee the globally optimal
    (minimum cost or minimum count) solution.
    """
    from boxing.models import Box  # local import to avoid circular imports at module load

    # ------------------------------------------------------------------
    # Step 1: Expand order items into individual units
    # ------------------------------------------------------------------
    units: list[_Unit] = []
    for item in order.items.select_related("product").all():
        vol = _product_volume(item.product)
        for _ in range(item.quantity):
            units.append(_Unit(product=item.product, volume=vol))

    if not units:
        return {
            "status": "ok",
            "boxes": [],
            "total_cost": "0.00",
            "box_count": 0,
        }

    # ------------------------------------------------------------------
    # Step 2: Load all available box types
    # ------------------------------------------------------------------
    all_boxes: list["Box"] = list(Box.objects.all())

    if not all_boxes:
        return {
            "status": "cannot_fulfill",
            "reason": "No box types are configured in the system.",
        }

    # ------------------------------------------------------------------
    # Step 3: Feasibility pre-check — every unit must fit in >= 1 box
    # ------------------------------------------------------------------
    for unit in units:
        if not any(_fits_in_box(unit.product, box) for box in all_boxes):
            return {
                "status": "cannot_fulfill",
                "reason": (
                    f"Product '{unit.product.name}' (id={unit.product.pk}) cannot fit "
                    f"inside any available box in any orientation."
                ),
            }

    # ------------------------------------------------------------------
    # Step 4: Sort units largest-volume-first (FFD ordering)
    # ------------------------------------------------------------------
    units.sort(key=lambda u: u.volume, reverse=True)

    # ------------------------------------------------------------------
    # Step 5: Greedy packing
    # ------------------------------------------------------------------
    opened: list[_OpenBox] = []

    for unit in units:
        placed = False

        # Try to fit into an already-opened box (first fit).
        for ob in opened:
            weight_ok = Decimal(unit.product.weight) <= ob.remaining_weight
            volume_ok = unit.volume <= ob.remaining_volume
            # Also verify the product physically fits the box dimensions.
            dims_ok = _fits_in_box(unit.product, ob.box)
            if weight_ok and volume_ok and dims_ok:
                ob.units.append(unit)
                ob.remaining_weight -= Decimal(unit.product.weight)
                ob.remaining_volume -= unit.volume
                placed = True
                break

        if placed:
            continue

        # No open box can accept this unit — open a new one.
        # Use two sequential filters so each failure produces a precise error:
        #   1. dim_eligible: boxes where the product physically fits (any rotation).
        #   2. weight_eligible: from those, boxes that can bear the product's weight.
        # Keeping them separate lets us tell the caller *why* nothing fits.
        # Ties in cost are broken alphabetically by name for determinism.

        # Filter 1: dimensional fit only.
        dim_eligible = [
            box for box in all_boxes
            if _fits_in_box(unit.product, box)
            and unit.volume <= _box_volume(box)
        ]
        if not dim_eligible:
            # The feasibility pre-check already caught pure dimension failures,
            # so reaching here means volume overflow is the cause.
            return {
                "status": "cannot_fulfill",
                "reason": (
                    f"Product '{unit.product.name}' (id={unit.product.pk}) cannot fit "
                    f"inside any available box in any orientation."
                ),
            }

        # Filter 2: weight capacity (applied to the dimensionally-eligible set).
        weight_eligible = [
            box for box in dim_eligible
            if Decimal(unit.product.weight) <= Decimal(box.max_weight)
        ]
        if not weight_eligible:
            return {
                "status": "cannot_fulfill",
                "reason": (
                    f"Product '{unit.product.name}' (id={unit.product.pk}) exceeds "
                    f"the maximum weight capacity of every available box."
                ),
            }

        # Sort by cost ASC, then name ASC for determinism on ties.
        best_box = min(weight_eligible, key=lambda b: (Decimal(b.cost), b.name))

        new_ob = _OpenBox(
            box=best_box,
            remaining_weight=Decimal(best_box.max_weight) - Decimal(unit.product.weight),
            remaining_volume=_box_volume(best_box) - unit.volume,
        )
        new_ob.units.append(unit)
        opened.append(new_ob)

    # ------------------------------------------------------------------
    # Step 6: Build response payload
    # ------------------------------------------------------------------
    total_cost = Decimal("0.00")
    boxes_out = []

    for ob in opened:
        box_cost = Decimal(ob.box.cost)
        total_cost += box_cost

        # Aggregate individual units back into {product: count} entries.
        counts: dict[int, dict] = {}
        for u in ob.units:
            pid = u.product.pk
            if pid not in counts:
                counts[pid] = {
                    "product_id": pid,
                    "product_name": u.product.name,
                    "quantity": 0,
                }
            counts[pid]["quantity"] += 1

        boxes_out.append({
            "box_name": ob.box.name,
            "box_id": ob.box.pk,
            "items": list(counts.values()),
            "cost": str(box_cost),
        })

    return {
        "status": "ok",
        "boxes": boxes_out,
        "total_cost": str(total_cost),
        "box_count": len(boxes_out),
    }
