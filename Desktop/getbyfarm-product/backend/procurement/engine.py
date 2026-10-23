"""
GetbyFarm Smart Procurement Engine
==================================

Framework-agnostic core logic for recommending the *best overall* supplier
for a requested product/quantity — not simply the cheapest.

Kept independent of Django so it can be:
  - called from the DRF API (procurement/views.py)
  - called from a Celery job (nightly re-scoring, reorder suggestions)
  - reused later by a WhatsApp bot or mobile app without duplicating logic

Status: [Implemented] — pure logic + unit tests. Not yet wired to a live
Postgres dataset (that happens in views.py, which reads real SupplierPrice
rows and converts them into `SupplierOffer` objects before calling this).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SupplierOffer:
    """One supplier's offer for a requested product+quantity."""
    supplier_id: str
    supplier_name: str
    unit_price: float                 # KES per unit
    delivery_cost: float               # flat delivery fee for this order, KES
    reliability_score: float           # 0-100 (historical fulfillment rate)
    quality_rating: float              # 0-5 stars
    lead_time_days: float              # days until delivery
    available_stock: float             # units the supplier currently has
    minimum_order_quantity: float = 0

    def is_eligible(self, requested_quantity: float) -> tuple[bool, Optional[str]]:
        if self.available_stock < requested_quantity:
            return False, f"Insufficient stock ({self.available_stock} < {requested_quantity})"
        if requested_quantity < self.minimum_order_quantity:
            return False, (
                f"Requested quantity ({requested_quantity}) below supplier's "
                f"minimum order quantity ({self.minimum_order_quantity})"
            )
        return True, None


@dataclass(frozen=True)
class EngineWeights:
    """Configurable per-organization scoring weights. Must sum to 1.0."""
    price: float = 0.40
    delivery: float = 0.20
    reliability: float = 0.25
    quality: float = 0.10
    lead_time: float = 0.05

    def __post_init__(self):
        total = self.price + self.delivery + self.reliability + self.quality + self.lead_time
        if not (0.99 <= total <= 1.01):
            raise ValueError(f"EngineWeights must sum to 1.0, got {total}")


@dataclass
class ScoredOffer:
    offer: SupplierOffer
    total_landed_cost: float
    score: float                       # lower is better
    component_breakdown: dict = field(default_factory=dict)
    explanation: str = ""


@dataclass
class RecommendationResult:
    requested_quantity: float
    recommended: Optional[ScoredOffer]
    ranked_candidates: list[ScoredOffer]
    excluded: list[tuple[SupplierOffer, str]]   # (offer, reason) for ineligible offers


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def _normalize(value: float, lo: float, hi: float) -> float:
    """Scale value into [0, 1] where 0 = best (lowest), 1 = worst (highest).
    Guards against a zero-width range (all offers identical on this metric)."""
    if hi <= lo:
        return 0.0
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


# ---------------------------------------------------------------------------
# Core engine
# ---------------------------------------------------------------------------

def recommend_supplier(
    offers: list[SupplierOffer],
    requested_quantity: float,
    weights: EngineWeights = EngineWeights(),
) -> RecommendationResult:
    """
    Score all eligible supplier offers for a given quantity and return a
    ranked recommendation. Never picks purely on price — the reasoning is
    always attached so the buyer can see *why*.
    """
    if requested_quantity <= 0:
        raise ValueError("requested_quantity must be positive")

    eligible: list[SupplierOffer] = []
    excluded: list[tuple[SupplierOffer, str]] = []

    for offer in offers:
        ok, reason = offer.is_eligible(requested_quantity)
        if ok:
            eligible.append(offer)
        else:
            excluded.append((offer, reason))

    if not eligible:
        return RecommendationResult(
            requested_quantity=requested_quantity,
            recommended=None,
            ranked_candidates=[],
            excluded=excluded,
        )

    # Compute landed cost per offer (what the buyer actually pays for this quantity)
    landed_costs = {
        o.supplier_id: (o.unit_price * requested_quantity) + o.delivery_cost
        for o in eligible
    }

    price_lo, price_hi = min(landed_costs.values()), max(landed_costs.values())
    delivery_lo = min(o.delivery_cost for o in eligible)
    delivery_hi = max(o.delivery_cost for o in eligible)
    lead_lo = min(o.lead_time_days for o in eligible)
    lead_hi = max(o.lead_time_days for o in eligible)

    scored: list[ScoredOffer] = []
    for offer in eligible:
        landed_cost = landed_costs[offer.supplier_id]

        price_component = _normalize(landed_cost, price_lo, price_hi)
        delivery_component = _normalize(offer.delivery_cost, delivery_lo, delivery_hi)
        reliability_component = 1 - (offer.reliability_score / 100.0)
        quality_component = 1 - (offer.quality_rating / 5.0)
        lead_time_component = _normalize(offer.lead_time_days, lead_lo, lead_hi)

        breakdown = {
            "price": round(price_component * weights.price, 4),
            "delivery": round(delivery_component * weights.delivery, 4),
            "reliability": round(reliability_component * weights.reliability, 4),
            "quality": round(quality_component * weights.quality, 4),
            "lead_time": round(lead_time_component * weights.lead_time, 4),
        }
        total_score = sum(breakdown.values())

        scored.append(ScoredOffer(
            offer=offer,
            total_landed_cost=round(landed_cost, 2),
            score=round(total_score, 4),
            component_breakdown=breakdown,
        ))

    scored.sort(key=lambda s: s.score)

    for rank, s in enumerate(scored):
        s.explanation = _build_explanation(s, rank, scored)

    return RecommendationResult(
        requested_quantity=requested_quantity,
        recommended=scored[0],
        ranked_candidates=scored,
        excluded=excluded,
    )


def _build_explanation(scored: ScoredOffer, rank: int, all_scored: list[ScoredOffer]) -> str:
    o = scored.offer
    parts = [
        f"Landed cost KSh {scored.total_landed_cost:,.2f} "
        f"(unit price KSh {o.unit_price:,.2f} + delivery KSh {o.delivery_cost:,.2f}), "
        f"reliability {o.reliability_score:.0f}%, quality {o.quality_rating:.1f}/5, "
        f"lead time {o.lead_time_days:.1f} day(s)."
    ]
    if rank == 0 and len(all_scored) > 1:
        runner_up = all_scored[1]
        if runner_up.total_landed_cost < scored.total_landed_cost:
            diff = scored.total_landed_cost - runner_up.total_landed_cost
            parts.append(
                f"Chosen over {runner_up.offer.supplier_name} despite costing "
                f"KSh {diff:,.2f} more, because of stronger reliability/quality/lead-time."
            )
        else:
            parts.append(f"Best overall option — also the lowest landed cost.")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Multi-supplier cart optimization (splits a shopping list across suppliers)
# ---------------------------------------------------------------------------

@dataclass
class LineRequest:
    product_id: str
    product_name: str
    quantity: float
    offers: list[SupplierOffer]


@dataclass
class OptimizedCart:
    line_results: dict[str, RecommendationResult]
    total_estimated_cost: float
    suppliers_used: set

    def summary(self) -> str:
        lines = [f"Optimized cart across {len(self.suppliers_used)} supplier(s):"]
        for product_id, result in self.line_results.items():
            if result.recommended:
                lines.append(
                    f"  - {product_id}: {result.recommended.offer.supplier_name} "
                    f"@ KSh {result.recommended.total_landed_cost:,.2f}"
                )
            else:
                lines.append(f"  - {product_id}: NO ELIGIBLE SUPPLIER")
        lines.append(f"Estimated total: KSh {self.total_estimated_cost:,.2f}")
        return "\n".join(lines)


def optimize_cart(
    lines: list[LineRequest],
    weights: EngineWeights = EngineWeights(),
) -> OptimizedCart:
    """Run the recommendation engine per line item and aggregate into one cart-level view."""
    line_results: dict[str, RecommendationResult] = {}
    total = 0.0
    suppliers_used: set = set()

    for line in lines:
        result = recommend_supplier(line.offers, line.quantity, weights)
        line_results[line.product_id] = result
        if result.recommended:
            total += result.recommended.total_landed_cost
            suppliers_used.add(result.recommended.offer.supplier_id)

    return OptimizedCart(
        line_results=line_results,
        total_estimated_cost=round(total, 2),
        suppliers_used=suppliers_used,
    )
