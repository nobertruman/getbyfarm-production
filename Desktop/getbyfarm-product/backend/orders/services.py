"""
Order lifecycle business logic. Views stay thin; everything that must be atomic or consistent lives here.
"""
import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from pricing.models import SupplierPrice
from .models import Order, OrderAllocation, OrderItem, PurchaseApproval

logger = logging.getLogger(__name__)


class OrderError(Exception):
    """A business-rule violation whose message is safe to show to the user."""


# ---------------------------------------------------------------- approvals
# Platform-wide default bands (spec §21). Per-organisation configuration is Phase 2.
def required_approvals(total: Decimal) -> list[str]:
    if total < Decimal("20000"):
        return []
    if total < Decimal("100000"):
        return ["manager", "procurement"]
    return ["manager", "procurement", "finance"]


# Which role codes may sign off each approval step. The business owner ('enterprise_admin')
# can approve every step so a one-person business is never blocked by its own approval chain.
APPROVER_ROLES = {
    "manager": {"buyer_manager", "enterprise_admin"},
    "procurement": {"procurement_manager", "enterprise_admin"},
    "finance": {"finance_manager", "enterprise_admin"},
}


def user_can_approve(user, approver_role: str) -> bool:
    allowed = APPROVER_ROLES.get(approver_role, set())
    return user.roles.filter(code__in=allowed).exists()


# ---------------------------------------------------------------- checkout
@transaction.atomic
def create_order_from_cart(cart, placed_by) -> Order:
    items = list(cart.items.select_related("supplier_price").order_by("supplier_price_id"))
    if not items:
        raise OrderError("Your cart is empty.")

    # Lock the price/stock rows (consistent order => no deadlocks) so two buyers can't oversell the same stock.
    locked = {
        p.id: p
        for p in SupplierPrice.objects.select_for_update(of=("self",))
        .select_related("supplier", "product")
        .filter(id__in=[i.supplier_price_id for i in items])
        .order_by("id")
    }

    subtotal = Decimal("0")
    delivery_by_supplier: dict = {}
    for ci in items:
        sp = locked[ci.supplier_price_id]
        name = f"{sp.product.name} from {sp.supplier.business_name}"
        if not sp.is_active or sp.supplier.verification_status != "verified":
            raise OrderError(f"{name} is no longer available. Remove it from your cart.")
        if sp.unit_price != ci.locked_unit_price:
            raise OrderError(
                f"The price of {name} changed from KSh {ci.locked_unit_price:,.2f} to KSh {sp.unit_price:,.2f}. "
                "Please re-add it to your cart to confirm the new price."
            )
        if sp.stock_quantity < ci.quantity:
            raise OrderError(f"Only {sp.stock_quantity:g} of {name} left in stock.")
        subtotal += ci.locked_unit_price * ci.quantity
        delivery_by_supplier[sp.supplier_id] = sp.delivery_cost_flat

    delivery_fee = sum(delivery_by_supplier.values(), Decimal("0"))
    order = Order.objects.create(
        branch=cart.branch,
        order_number=Order.generate_order_number(),
        status="draft",
        subtotal=subtotal,
        delivery_fee=delivery_fee,
        # VAT treatment of food items varies (zero-rated/exempt/standard); computing it is configured
        # per product/country in a later phase rather than guessed here. Invoices carry what the order carries.
        tax_amount=Decimal("0"),
        total_amount=subtotal + delivery_fee,
        placed_by=placed_by,
    )

    allocations: dict = {}
    for ci in items:
        sp = locked[ci.supplier_price_id]
        OrderItem.objects.create(
            order=order, product=sp.product, supplier=sp.supplier,
            quantity=ci.quantity, unit_price=ci.locked_unit_price, line_total=ci.line_total,
        )
        alloc = allocations.get(sp.supplier_id)
        if alloc is None:
            alloc = allocations[sp.supplier_id] = OrderAllocation.objects.create(
                order=order, supplier=sp.supplier, subtotal=Decimal("0")
            )
        alloc.subtotal += ci.line_total
        sp.stock_quantity -= ci.quantity
        sp.save(update_fields=["stock_quantity", "updated_at"])
    for alloc in allocations.values():
        alloc.save(update_fields=["subtotal"])

    for role in required_approvals(order.total_amount):
        PurchaseApproval.objects.create(order=order, approver_role=role, threshold_amount=order.total_amount)
    if not order.approvals.exists():
        order.transition_to("submitted")
    return order


# ---------------------------------------------------------------- approvals / submit
@transaction.atomic
def approve(order: Order, approval: PurchaseApproval, user) -> Order:
    if not user_can_approve(user, approval.approver_role):
        raise OrderError(f"You don't have permission to give {approval.approver_role} approval.")
    approval.status = "approved"
    approval.approver = user
    approval.decided_at = timezone.now()
    approval.save()
    if order.status == "draft" and not order.approvals.filter(status__in=["pending", "rejected"]).exists():
        order.transition_to("submitted")
    return order


def submit(order: Order) -> Order:
    if order.approvals.exclude(status="approved").exists():
        raise OrderError("This order still needs approval before it can be submitted.")
    try:
        order.transition_to("submitted")
    except ValueError as exc:
        raise OrderError(str(exc))
    return order


# ---------------------------------------------------------------- cancellation
@transaction.atomic
def cancel_order(order: Order) -> Order:
    """Only unpaid orders can be cancelled here. Paid orders need a refund, which is a manual/admin
    process until the refund flow ships — we refuse rather than cancel an order the buyer already paid for."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status not in {"draft", "submitted"}:
        raise OrderError("This order can no longer be cancelled online. Contact support.")
    if order.payments.filter(status__in=["pending", "success"]).exists():
        raise OrderError("A payment is in progress or completed for this order. Contact support to cancel it.")

    # Give the reserved stock back (best-effort match on supplier + product).
    for item in order.items.select_related("supplier", "product"):
        sp = (SupplierPrice.objects.select_for_update()
              .filter(supplier=item.supplier, product=item.product).order_by("created_at").first())
        if sp:
            sp.stock_quantity += item.quantity
            sp.save(update_fields=["stock_quantity", "updated_at"])
    order.allocations.update(status="cancelled")
    order.transition_to("cancelled")
    return order


# ---------------------------------------------------------------- fulfilment progress
_FLOW = ["confirmed", "processing", "ready_for_dispatch", "in_transit", "delivered"]


def _advance_order_to(order: Order, target: str) -> None:
    if order.status not in _FLOW:
        return
    while _FLOW.index(order.status) < _FLOW.index(target):
        order.transition_to(_FLOW[_FLOW.index(order.status) + 1])


def sync_order_status(order: Order) -> Order:
    """Derive the buyer-facing order status from what each supplier has done."""
    live = [a.status for a in order.allocations.all() if a.status != "cancelled"]
    if not live:
        return order
    if all(s == "delivered" for s in live):
        target = "delivered"
    elif any(s in {"dispatched", "delivered"} for s in live):
        target = "in_transit"
    elif all(s == "ready" for s in live):
        target = "ready_for_dispatch"
    elif any(s in {"accepted", "preparing", "ready"} for s in live):
        target = "processing"
    else:
        return order
    _advance_order_to(order, target)
    return order


@transaction.atomic
def advance_allocation(allocation: OrderAllocation, new_status: str) -> OrderAllocation:
    order = Order.objects.select_for_update().get(pk=allocation.order_id)
    if order.status not in {"confirmed", "processing", "ready_for_dispatch", "in_transit"}:
        raise OrderError("This order hasn't been paid yet, so it can't be fulfilled.")
    if new_status == "cancelled":
        raise OrderError("To decline an order, contact GetbyFarm support so the buyer can be refunded.")
    try:
        allocation.transition_to(new_status)
    except ValueError as exc:
        raise OrderError(str(exc))

    # Keep a delivery record in step with the supplier's dispatch / delivery.
    if new_status in {"dispatched", "delivered"}:
        from deliveries.models import Delivery
        delivery, _ = Delivery.objects.get_or_create(
            order_allocation=allocation,
            defaults={"delivery_address": order.branch.address or order.branch.name},
        )
        delivery.record_status("dispatched" if new_status == "dispatched" else "delivered",
                               note=f"Supplier marked order {new_status}.")
    sync_order_status(order)
    return allocation


@transaction.atomic
def confirm_receipt(order: Order) -> Order:
    if order.status != "delivered":
        raise OrderError("You can confirm receipt once every supplier has delivered.")
    order.transition_to("completed")
    return order
