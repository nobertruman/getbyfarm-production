"""Lets other apps serialize an Order without importing views (avoids circular imports)."""


def serialize_order(order, request=None):
    from .views import OrderSerializer
    return OrderSerializer(order, context={"request": request}).data
