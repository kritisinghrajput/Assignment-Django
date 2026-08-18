# Box Selector — AI-Assisted Box Selection System

A Django + DRF service that recommends which shipping box(es) to use for an
order, given each product's dimensions/weight and each box's internal
dimensions, weight capacity, and cost.

## Problem

Given an order (a list of products + quantities), determine which box(es)
from the available inventory should be used to ship it, minimizing cost
while respecting each box's physical and weight limits.

## Approach

True 3D bin-packing is NP-hard, so this uses a **Greedy First-Fit
Decreasing (FFD) heuristic** rather than an optimal solver:

1. Expand the order into individual product units (respecting quantity).
2. Feasibility check: reject the order upfront if any single unit cannot
   physically fit inside *any* box in *any* orientation, or exceeds every
   box's max weight.
3. Sort units largest-volume-first.
4. For each unit, try to place it in an already-opened box with enough
   remaining weight and volume capacity (first fit).
5. If it doesn't fit any open box, open the **cheapest** box type that can
   fit it.
6. Return the box assignment and total cost.

**Trade-off:** this can use more boxes than a truly optimal packer would in
edge cases (e.g. many items of similar volume). It was chosen over an exact
solver for simplicity, speed, and testability within the assignment scope.

**Fit checking:** a product fits a box if, after sorting both the product's
and box's dimensions independently, each product dimension is ≤ the
corresponding sorted box dimension — this checks all 6 axis-aligned
rotations in one comparison.

**Volumetric packing:** remaining box capacity is tracked as volume, used as
a proxy for actual 3D spatial fit. It does not model real geometric
placement (e.g. irregular shapes wasting space) — see Known Limitations.

## Setup

```bash
git clone <repo-url>
cd box_selector
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py seed_data          # optional sample data
python manage.py createsuperuser    # optional, for /admin/
python manage.py runserver
```

## API

### `POST /api/orders/recommend-box/`

Request:
```json
{
  "items": [
    {"product_id": 1, "quantity": 2},
    {"product_id": 3, "quantity": 1}
  ]
}
```

Success (200):
```json
{
  "status": "ok",
  "boxes": [
    {
      "box_name": "Small Box",
      "box_id": 2,
      "items": [{"product_id": 1, "product_name": "Phone", "quantity": 2}],
      "cost": "1.50"
    }
  ],
  "total_cost": "1.50",
  "box_count": 1
}
```

Cannot fulfill (422):
```json
{"error": "Product 'Wardrobe' (id=5) cannot fit inside any available box in any orientation."}
```

Validation error (400): standard DRF field errors.

## Running tests

```bash
python -m pytest boxing/tests/ -v
```

17 tests covering: single/multi-item single-box packing, forced multi-box
splitting, dimensionally-infeasible items, over-weight items, cost
tie-breaking, empty orders, and full API request/response/validation paths.

## Design decisions

| Decision | Why |
|---|---|
| Business logic lives in `boxing/services/box_selector.py`, not views/models | Keeps the algorithm testable in isolation from HTTP/ORM concerns |
| `OrderItem.product` uses `on_delete=PROTECT` | Prevents deleting a product referenced by historical orders |
| Order + OrderItems are created *before* running the packer | Preserves a record of the request even if it can't be fulfilled — see Known Limitations |
| Cost tie-break by `(cost, name)` | Deterministic output; no dependence on DB row order |

## Known limitations

- Volumetric packing is a proxy, not true geometric placement — a heuristic
  trade-off, documented above.
- A `cannot_fulfill` (422) response still leaves an `Order` row in the DB
  with no successful box assignment. This was a deliberate choice for audit
  visibility, but could instead roll back the transaction if that's not
  desired.
- No model-level validators on physical fields (e.g. negative dimensions);
  relies on sane input.
- `SECRET_KEY`, `DEBUG=True`, and `ALLOWED_HOSTS=["*"]` in `settings.py` are
  dev-only configuration, not production-ready.

## Tech stack

Django 5, Django REST Framework, SQLite (dev), pytest / Django TestCase.
