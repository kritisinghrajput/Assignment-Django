"""Views for the boxing app."""

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from boxing.models import Order, OrderItem, Product
from boxing.serializers import RecommendBoxInputSerializer
from boxing.services.box_selector import recommend_boxes


class RecommendBoxView(APIView):
    """
    POST /api/orders/recommend-box/

    Creates an Order + OrderItems for the given product list, runs the
    greedy FFD box-selection heuristic, and returns the box assignment.

    Request body::

        {
            "items": [
                {"product_id": 1, "quantity": 3},
                {"product_id": 2, "quantity": 1}
            ]
        }

    Responses:
        200 OK  — box assignment result (status "ok")
        400 Bad Request — invalid/missing fields
        422 Unprocessable Entity — valid request but items cannot be packed
    """

    def post(self, request: Request) -> Response:
        serializer = RecommendBoxInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated_items = serializer.validated_data["items"]

        # Create the order and its line items atomically within a transaction.
        # We deliberately do NOT wrap this in try/except for DB errors here;
        # those surface naturally as 500s, which is intentional for server faults.
        from django.db import transaction

        with transaction.atomic():
            order = Order.objects.create()
            for item_data in validated_items:
                OrderItem.objects.create(
                    order=order,
                    product_id=item_data["product_id"],
                    quantity=item_data["quantity"],
                )

        result = recommend_boxes(order)

        if result["status"] == "cannot_fulfill":
            return Response(
                {"error": result["reason"]},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        return Response(result, status=status.HTTP_200_OK)
