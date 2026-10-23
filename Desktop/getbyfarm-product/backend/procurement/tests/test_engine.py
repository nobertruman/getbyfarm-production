"""
Unit tests for procurement/engine.py.
Run with: python -m pytest backend/procurement/tests/test_engine.py -v
(or plain: python -m unittest discover)
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from procurement.engine import (
    SupplierOffer,
    EngineWeights,
    LineRequest,
    recommend_supplier,
    optimize_cart,
)


class TestEligibility(unittest.TestCase):
    def test_excludes_insufficient_stock(self):
        offers = [
            SupplierOffer("s1", "Supplier A", unit_price=100, delivery_cost=500,
                           reliability_score=90, quality_rating=4.5, lead_time_days=1,
                           available_stock=5),
        ]
        result = recommend_supplier(offers, requested_quantity=10)
        self.assertIsNone(result.recommended)
        self.assertEqual(len(result.excluded), 1)
        self.assertIn("Insufficient stock", result.excluded[0][1])

    def test_excludes_below_minimum_order_quantity(self):
        offers = [
            SupplierOffer("s1", "Supplier A", unit_price=100, delivery_cost=500,
                           reliability_score=90, quality_rating=4.5, lead_time_days=1,
                           available_stock=100, minimum_order_quantity=50),
        ]
        result = recommend_supplier(offers, requested_quantity=10)
        self.assertIsNone(result.recommended)
        self.assertIn("minimum order quantity", result.excluded[0][1])


class TestRecommendationLogic(unittest.TestCase):
    def test_does_not_always_pick_cheapest_spec_example(self):
        """
        From the product spec:
        Supplier A: cost 40,000, delivery 2,000, reliability 94%
        Supplier B: cost 38,500, delivery 4,000, reliability 78%
        Expect Supplier A can be recommended despite higher price.
        """
        supplier_a = SupplierOffer(
            "A", "Supplier A", unit_price=40000, delivery_cost=2000,
            reliability_score=94, quality_rating=4.5, lead_time_days=1,
            available_stock=1000,
        )
        supplier_b = SupplierOffer(
            "B", "Supplier B", unit_price=38500, delivery_cost=4000,
            reliability_score=78, quality_rating=3.5, lead_time_days=2,
            available_stock=1000,
        )
        result = recommend_supplier([supplier_a, supplier_b], requested_quantity=1)
        self.assertEqual(result.recommended.offer.supplier_id, "A")
        # Note: at qty=1, A's landed cost (42,000) is *also* cheaper than B's (42,500),
        # since B's higher delivery fee outweighs its lower unit price. A wins on both
        # price and reliability here. The engine still records the full breakdown so a
        # buyer can see reliability/quality contributed, not just price.
        self.assertIn("reliability 94%", result.recommended.explanation)

    def test_prefers_reliability_over_lower_price_at_larger_quantity(self):
        """At higher volume, B's lower unit price makes it cheaper overall; confirm the
        engine can still favor A on reliability/quality when weights are tilted that way."""
        supplier_a = SupplierOffer(
            "A", "Supplier A", unit_price=40000, delivery_cost=2000,
            reliability_score=94, quality_rating=4.5, lead_time_days=1,
            available_stock=1000,
        )
        supplier_b = SupplierOffer(
            "B", "Supplier B", unit_price=38500, delivery_cost=4000,
            reliability_score=78, quality_rating=3.5, lead_time_days=2,
            available_stock=1000,
        )
        # Quantity large enough that B is materially cheaper on landed cost alone.
        cheap_first = recommend_supplier([supplier_a, supplier_b], requested_quantity=10)
        self.assertEqual(cheap_first.recommended.offer.supplier_id, "B")

        reliability_weighted = EngineWeights(price=0.10, delivery=0.05, reliability=0.65,
                                              quality=0.15, lead_time=0.05)
        reliability_first = recommend_supplier(
            [supplier_a, supplier_b], requested_quantity=10, weights=reliability_weighted
        )
        self.assertEqual(reliability_first.recommended.offer.supplier_id, "A")
        self.assertIn("Chosen over", reliability_first.recommended.explanation)

    def test_picks_cheapest_when_all_else_equal(self):
        a = SupplierOffer("A", "Supplier A", unit_price=100, delivery_cost=0,
                           reliability_score=90, quality_rating=4, lead_time_days=1,
                           available_stock=100)
        b = SupplierOffer("B", "Supplier B", unit_price=90, delivery_cost=0,
                           reliability_score=90, quality_rating=4, lead_time_days=1,
                           available_stock=100)
        result = recommend_supplier([a, b], requested_quantity=1)
        self.assertEqual(result.recommended.offer.supplier_id, "B")

    def test_weights_must_sum_to_one(self):
        with self.assertRaises(ValueError):
            EngineWeights(price=0.9, delivery=0.9, reliability=0, quality=0, lead_time=0)

    def test_ranked_candidates_sorted_ascending_score(self):
        a = SupplierOffer("A", "A", 100, 0, 90, 4, 1, 100)
        b = SupplierOffer("B", "B", 90, 0, 50, 2, 5, 100)
        c = SupplierOffer("C", "C", 95, 0, 80, 3, 2, 100)
        result = recommend_supplier([a, b, c], requested_quantity=1)
        scores = [s.score for s in result.ranked_candidates]
        self.assertEqual(scores, sorted(scores))


class TestCartOptimization(unittest.TestCase):
    def test_optimize_cart_splits_across_suppliers(self):
        rice_offers = [
            SupplierOffer("s1", "Rice Co", 150, 300, 92, 4.2, 1, 500),
            SupplierOffer("s2", "Grain Ltd", 145, 800, 60, 3.0, 3, 500),
        ]
        tomato_offers = [
            SupplierOffer("s3", "Fresh Farms", 90, 200, 95, 4.8, 1, 300),
        ]
        cart = optimize_cart([
            LineRequest("rice", "Rice 50kg", quantity=10, offers=rice_offers),
            LineRequest("tomatoes", "Tomatoes", quantity=20, offers=tomato_offers),
        ])
        self.assertEqual(len(cart.line_results), 2)
        self.assertGreater(cart.total_estimated_cost, 0)
        self.assertIn("s3", cart.suppliers_used)

    def test_no_eligible_supplier_reflected_in_summary(self):
        cart = optimize_cart([
            LineRequest("eggs", "Eggs", quantity=1000, offers=[
                SupplierOffer("s1", "Small Supplier", 10, 5, 80, 4, 1, available_stock=5),
            ]),
        ])
        self.assertIsNone(cart.line_results["eggs"].recommended)
        self.assertIn("NO ELIGIBLE SUPPLIER", cart.summary())


if __name__ == "__main__":
    unittest.main()
