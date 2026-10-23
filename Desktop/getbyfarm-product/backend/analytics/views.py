"""
Analytics is computed live from transactional tables (no second source of truth to drift).
Fine at MVP scale; move to materialised views / a warehouse once volume grows.
"""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, Sum
from django.utils import timezone
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Product
from orders.models import Order, OrderAllocation, OrderItem
from organizations.models import Organization
from payments.models import Payment
from suppliers.models import SupplierOrganization

PAID_STATES = ["confirmed", "processing", "ready_for_dispatch", "in_transit", "delivered", "completed"]


class BuyerDashboardView(APIView):
    """A buyer only ever sees their OWN branch. (Platform staff may pass ?branch_id=.)"""

    def get(self, request):
        user = request.user
        branch_id = request.query_params.get("branch_id") if user.is_staff else user.branch_id
        if not branch_id:
            return Response({"detail": "No branch associated with this account."}, status=400)

        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        orders = Order.objects.filter(branch_id=branch_id)
        spend = orders.filter(created_at__gte=month_start, status__in=PAID_STATES).aggregate(t=Sum("total_amount"))["t"] or Decimal("0")
        reliability = (SupplierOrganization.objects.filter(order_allocations__order__branch_id=branch_id)
                       .distinct().aggregate(a=Avg("reliability_score"))["a"])
        return Response({
            "monthly_spend": spend,
            "orders_this_month": orders.filter(created_at__gte=month_start).exclude(status="cancelled").count(),
            "awaiting_approval": orders.filter(status="draft").count(),
            "awaiting_payment": orders.filter(status="submitted").count(),
            "in_progress": orders.filter(status__in=["confirmed", "processing", "ready_for_dispatch"]).count(),
            "orders_in_transit": orders.filter(status="in_transit").count(),
            "supplier_performance_pct": round(float(reliability), 1) if reliability is not None else None,
        })


class SupplierDashboardView(APIView):
    """GET /api/analytics/supplier-dashboard/ — the signed-in supplier's own numbers."""

    def get(self, request):
        su = getattr(request.user, "supplieruser", None)
        if su is None:
            return Response({"detail": "Supplier accounts only."}, status=403)
        since = timezone.now() - timedelta(days=30)
        allocs = OrderAllocation.objects.filter(supplier_id=su.supplier_id).exclude(order__status__in=["draft", "submitted", "cancelled"])
        recent = allocs.filter(order__created_at__gte=since)
        done = allocs.filter(status="delivered").count()
        total_closed = allocs.filter(status__in=["delivered", "cancelled"]).count()
        s = su.supplier
        return Response({
            "business_name": s.business_name,
            "verification_status": s.verification_status,
            "revenue_30d": recent.aggregate(t=Sum("subtotal"))["t"] or Decimal("0"),
            "orders_30d": recent.count(),
            "open_orders": allocs.exclude(status__in=["delivered", "cancelled"]).count(),
            "fulfillment_rate_pct": round(100 * done / total_closed, 1) if total_closed else None,
            "reliability_score": s.reliability_score,
            "quality_rating": s.quality_rating,
            "top_products": list(OrderItem.objects.filter(supplier_id=s.id, order__status__in=PAID_STATES)
                                 .values("product__name").annotate(qty=Sum("quantity"), revenue=Sum("line_total"))
                                 .order_by("-revenue")[:5]),
        })


class AdminOverviewView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        since = timezone.now() - timedelta(days=30)
        gmv = Order.objects.filter(created_at__gte=since, status__in=PAID_STATES).aggregate(t=Sum("total_amount"))["t"] or Decimal("0")
        return Response({
            "gmv_last_30_days": gmv,
            "total_orders": Order.objects.count(),
            "buyers": Organization.objects.filter(deleted_at__isnull=True).count(),
            "active_suppliers": SupplierOrganization.objects.filter(verification_status="verified").count(),
            "pending_supplier_verifications": SupplierOrganization.objects.filter(verification_status__in=["pending", "under_review"]).count(),
            "active_products": Product.objects.filter(is_active=True, deleted_at__isnull=True).count(),
            "failed_payments_30d": Payment.objects.filter(status="failed", created_at__gte=since).count(),
            "orders_by_status": dict(Order.objects.values_list("status").annotate(c=Count("id")).order_by()),
        })
