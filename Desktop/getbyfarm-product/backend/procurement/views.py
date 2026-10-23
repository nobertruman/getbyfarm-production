"""
API layer for the Smart Procurement Engine.
[Implemented] — converts real SupplierPrice rows into the engine's SupplierOffer
contract, calls the pure-logic engine, and returns a fully explained recommendation.
"""
from rest_framework import serializers, permissions
from decimal import Decimal
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from pricing.models import SupplierPrice
from .engine import SupplierOffer, EngineWeights, recommend_supplier, optimize_cart, LineRequest


class RecommendRequestSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    # Optional per-request weight overrides (e.g. a buyer who prioritizes speed)
    weight_price = serializers.FloatField(required=False)
    weight_delivery = serializers.FloatField(required=False)
    weight_reliability = serializers.FloatField(required=False)
    weight_quality = serializers.FloatField(required=False)
    weight_lead_time = serializers.FloatField(required=False)


class CartOptimizeRequestSerializer(serializers.Serializer):
    class LineSerializer(serializers.Serializer):
        product_id = serializers.UUIDField()
        quantity = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))

    lines = LineSerializer(many=True)


def _load_offers_for_product(product_id):
    """Returns (offers, price_id_by_supplier) — the engine only needs the scoring
    fields, but the frontend needs the SupplierPrice id back to add the chosen
    offer to a cart, so we track that mapping alongside it rather than growing
    the engine's SupplierOffer contract with a field the scoring logic never uses."""
    prices = SupplierPrice.objects.filter(
        product_id=product_id,
        is_active=True,
        supplier__verification_status="verified",
        supplier__deleted_at__isnull=True,
    ).select_related("supplier")

    offers = []
    price_id_by_supplier = {}
    for p in prices:
        offers.append(SupplierOffer(
            supplier_id=str(p.supplier_id),
            supplier_name=p.supplier.business_name,
            unit_price=float(p.unit_price),
            delivery_cost=float(p.delivery_cost_flat),
            reliability_score=float(p.supplier.reliability_score),
            quality_rating=float(p.supplier.quality_rating),
            lead_time_days=float(p.lead_time_days),
            available_stock=float(p.stock_quantity),
            minimum_order_quantity=float(p.minimum_order_quantity),
        ))
        price_id_by_supplier[str(p.supplier_id)] = str(p.id)
    return offers, price_id_by_supplier


def _weights_from_request(data) -> EngineWeights:
    kwargs = {}
    mapping = {
        "weight_price": "price", "weight_delivery": "delivery",
        "weight_reliability": "reliability", "weight_quality": "quality",
        "weight_lead_time": "lead_time",
    }
    for req_key, field_name in mapping.items():
        if data.get(req_key) is not None:
            kwargs[field_name] = data[req_key]
    return EngineWeights(**kwargs) if kwargs else EngineWeights()


def _serialize_result(result, price_id_by_supplier: dict) -> dict:
    def offer_dict(scored):
        return {
            "supplier_id": scored.offer.supplier_id,
            "supplier_price_id": price_id_by_supplier.get(scored.offer.supplier_id),
            "supplier_name": scored.offer.supplier_name,
            "unit_price": scored.offer.unit_price,
            "delivery_cost": scored.offer.delivery_cost,
            "reliability_score": scored.offer.reliability_score,
            "quality_rating": scored.offer.quality_rating,
            "lead_time_days": scored.offer.lead_time_days,
            "available_stock": scored.offer.available_stock,
            "total_landed_cost": scored.total_landed_cost,
            "score": scored.score,
            "component_breakdown": scored.component_breakdown,
            "explanation": scored.explanation,
        }

    return {
        "requested_quantity": result.requested_quantity,
        "recommended": offer_dict(result.recommended) if result.recommended else None,
        "ranked_candidates": [offer_dict(s) for s in result.ranked_candidates],
        "excluded": [
            {"supplier_id": o.supplier_id, "supplier_name": o.supplier_name, "reason": reason}
            for o, reason in result.excluded
        ],
    }


class RecommendSupplierView(APIView):
    """POST /api/procurement/recommend/ — single product/quantity recommendation."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = RecommendRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        offers, price_id_by_supplier = _load_offers_for_product(data["product_id"])
        if not offers:
            return Response(
                {"detail": "No verified supplier currently lists this product."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            weights = _weights_from_request(data)
        except ValueError as exc:  # weights must sum to 1.0
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        result = recommend_supplier(offers, float(data["quantity"]), weights)
        return Response(_serialize_result(result, price_id_by_supplier))


class OptimizeCartView(APIView):
    """POST /api/procurement/optimize-cart/ — multi-line shopping list -> best split across suppliers."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CartOptimizeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lines_data = serializer.validated_data["lines"]

        line_requests = []
        price_id_maps = {}
        for line in lines_data:
            offers, price_id_by_supplier = _load_offers_for_product(line["product_id"])
            product_id_str = str(line["product_id"])
            price_id_maps[product_id_str] = price_id_by_supplier
            line_requests.append(LineRequest(
                product_id=product_id_str,
                product_name=product_id_str,  # resolved to a real name client-side / could join Product
                quantity=float(line["quantity"]),
                offers=offers,
            ))

        cart = optimize_cart(line_requests)
        return Response({
            "total_estimated_cost": cart.total_estimated_cost,
            "suppliers_used": list(cart.suppliers_used),
            "lines": {
                product_id: _serialize_result(result, price_id_maps.get(product_id, {}))
                for product_id, result in cart.line_results.items()
            },
        })
