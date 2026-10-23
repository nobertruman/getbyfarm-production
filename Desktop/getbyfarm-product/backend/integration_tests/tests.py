"""
End-to-end API tests: real HTTP-style requests through DRF with real JWT auth, covering both the happy
path and the security properties we promised (no cross-tenant access, no payment spoofing, no approval bypass).

    DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test integration_tests -v2
"""
import json
from decimal import Decimal
from unittest import mock

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import Role, User
from catalog.models import Category, Product
from invoices.models import Invoice
from orders.models import Order, PurchaseApproval
from organizations.models import Branch, Country, Organization
from payments.models import Payment
from payments.mpesa_adapter import MpesaDarajaAdapter, PaymentError, normalize_msisdn
from pricing.models import SupplierPrice
from suppliers.models import SupplierOrganization, SupplierUser

PW = "a-Strong-Passw0rd!"
SECRET = "cb-secret-for-tests"
MPESA_ON = {"ENABLED": True, "ENV": "sandbox", "CONSUMER_KEY": "k", "CONSUMER_SECRET": "s", "SHORTCODE": "174379",
            "PASSKEY": "pk", "CALLBACK_BASE_URL": "https://example.test", "CALLBACK_SECRET": SECRET,
            "TRANSACTION_TYPE": "CustomerPayBillOnline", "TILL_OR_SHORTCODE": ""}


def api(email=None, password=PW):
    client = APIClient()
    if email:
        res = client.post("/api/auth/login/", {"email": email, "password": password}, format="json")
        assert res.status_code == 200, res.content
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.json()['access']}")
    return client


class Base(TestCase):
    def setUp(self):
        self.ke = Country.objects.get(code="KE")  # seeded by migration
        self.cat = Category.objects.create(name="Fresh Produce", slug="fresh-produce")
        self.tomato = Product.objects.create(category=self.cat, name="Tomatoes", default_unit="kg")
        self.onion = Product.objects.create(category=self.cat, name="Onions", default_unit="kg")

        self.org = Organization.objects.create(name="Savannah Bites", country=self.ke)
        self.branch = Branch.objects.create(organization=self.org, name="CBD", address="Kenyatta Ave")
        self.owner = self._user("owner@buyer.test", org=self.org, branch=self.branch, role="enterprise_admin")
        self.clerk = self._user("clerk@buyer.test", org=self.org, branch=self.branch, role="buyer_user")

        self.org2 = Organization.objects.create(name="Other Cafe", country=self.ke)
        self.branch2 = Branch.objects.create(organization=self.org2, name="Westlands")
        self.other_buyer = self._user("other@buyer.test", org=self.org2, branch=self.branch2, role="enterprise_admin")

        self.sup_a = self._supplier("Kilimo Fresh", "a@supplier.test", 94, 4.6)
        self.sup_b = self._supplier("Wakulima Direct", "b@supplier.test", 78, 3.9)
        self.price_a = self._price(self.sup_a[0], self.tomato, 90, delivery=300)
        self.price_b = self._price(self.sup_b[0], self.tomato, 85, delivery=550)

        self.staff = User.objects.create_user(email="ops@getbyfarm.test", password=PW, full_name="Ops", is_staff=True)

    # -- builders
    def _user(self, email, org=None, branch=None, role=None):
        u = User.objects.create_user(email=email, password=PW, full_name=email.split("@")[0], organization=org, branch=branch)
        if role:
            u.roles.add(Role.objects.get(code=role))
        return u

    def _supplier(self, name, email, rel, qual, status="verified"):
        s = SupplierOrganization.objects.create(business_name=name, country=self.ke, verification_status=status,
                                                reliability_score=rel, quality_rating=qual)
        u = self._user(email, role="supplier_admin")
        SupplierUser.objects.create(user=u, supplier=s)
        return s, u

    def _price(self, supplier, product, price, stock=500, delivery=0, moq=1):
        return SupplierPrice.objects.create(supplier=supplier, product=product, unit_price=Decimal(price),
                                            stock_quantity=Decimal(stock), minimum_order_quantity=Decimal(moq),
                                            delivery_cost_flat=Decimal(delivery), lead_time_days=Decimal(1))

    def _cart_order(self, client, price, qty):
        r = client.post("/api/carts/add-item/", {"supplier_price_id": str(price.id), "quantity": qty}, format="json")
        assert r.status_code == 201, r.content
        r = client.post(f"/api/carts/{r.json()['id']}/checkout/")
        assert r.status_code == 201, r.content
        return r.json()


@override_settings(ALLOW_MOCK_PAYMENTS=True)
class HappyPathTests(Base):
    def test_full_lifecycle_buyer_pays_supplier_fulfils_buyer_confirms(self):
        buyer, supplier = api("owner@buyer.test"), api("a@supplier.test")

        # 1. /me tells the frontend which surface to show
        self.assertEqual(buyer.get("/api/auth/me/").json()["role"], "buyer")
        self.assertEqual(supplier.get("/api/auth/me/").json()["role"], "supplier")
        self.assertEqual(api("ops@getbyfarm.test").get("/api/auth/me/").json()["role"], "admin")

        # 2. engine recommends, buyer carts + checks out (KSh 90*20 + 300 = 2,100: no approval needed)
        rec = buyer.post("/api/procurement/recommend/", {"product_id": str(self.tomato.id), "quantity": 20}, format="json").json()
        self.assertIsNotNone(rec["recommended"]["supplier_price_id"])
        self.assertIn("reliability_score", rec["recommended"])
        order = self._cart_order(buyer, self.price_a, 20)
        self.assertEqual(order["status"], "submitted")
        self.assertEqual(Decimal(order["total_amount"]), Decimal("2100.00"))
        self.price_a.refresh_from_db()
        self.assertEqual(self.price_a.stock_quantity, Decimal("480"))

        # 3. supplier can't touch it until it's paid
        alloc_id = order["allocations"][0]["id"]
        self.assertEqual(supplier.get("/api/orders/allocations/").json()["count"], 0)
        self.assertEqual(supplier.post(f"/api/orders/allocations/{alloc_id}/advance/", {"status": "accepted"}, format="json").status_code, 404)

        # 4. pay (mock adapter, staging mode) -> confirmed + invoice + notification
        r = buyer.post("/api/payments/initiate/", {"order_id": order["id"], "phone_number": "0712345678"}, format="json")
        self.assertEqual(r.status_code, 202, r.content)
        o = Order.objects.get(pk=order["id"])
        self.assertEqual(o.status, "confirmed")
        self.assertEqual(Invoice.objects.get(order=o).payment_status, "paid")

        # 5. supplier now sees ONLY its own slice, then fulfils it step by step
        queue = supplier.get("/api/orders/allocations/").json()["results"]
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["items"][0]["product_name"], "Tomatoes")
        for step, expected_order_status in [("accepted", "processing"), ("preparing", "processing"),
                                            ("ready", "ready_for_dispatch"), ("dispatched", "in_transit"),
                                            ("delivered", "delivered")]:
            r = supplier.post(f"/api/orders/allocations/{alloc_id}/advance/", {"status": step}, format="json")
            self.assertEqual(r.status_code, 200, r.content)
            self.assertEqual(Order.objects.get(pk=order["id"]).status, expected_order_status)

        # 6. buyer sees a real delivery record, then confirms receipt
        deliveries = buyer.get("/api/deliveries/").json()["results"]
        self.assertEqual(deliveries[0]["status"], "delivered")
        r = buyer.post(f"/api/orders/{order['id']}/confirm-receipt/")
        self.assertEqual(r.json()["status"], "completed")

        # 7. dashboards reflect it
        self.assertEqual(Decimal(str(buyer.get("/api/analytics/buyer-dashboard/").json()["monthly_spend"])), Decimal("2100.00"))
        self.assertEqual(Decimal(str(supplier.get("/api/analytics/supplier-dashboard/").json()["revenue_30d"])), Decimal("1800.00"))

    def test_registration_creates_working_buyer_and_pending_supplier(self):
        anon = api()
        r = anon.post("/api/auth/register/", {"account_type": "buyer", "email": "new@cafe.test", "password": PW,
                                              "full_name": "New Owner", "business_name": "New Cafe"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        me = api("new@cafe.test").get("/api/auth/me/").json()
        self.assertEqual(me["role"], "buyer")
        self.assertEqual(me["roles"], ["enterprise_admin"])
        self.assertEqual(me["branch"]["name"], "Main branch")

        r = anon.post("/api/auth/register/", {"account_type": "supplier", "email": "new@farm.test", "password": PW,
                                              "full_name": "Farmer", "business_name": "New Farm"}, format="json")
        self.assertEqual(r.status_code, 201)
        me = api("new@farm.test").get("/api/auth/me/").json()
        self.assertEqual(me["supplier"]["verification_status"], "pending")
        # a pending supplier is invisible to buyers and can't be bought from
        self.assertEqual(api("owner@buyer.test").get("/api/suppliers/directory/").json()["count"], 2)

    def test_registration_rejects_weak_password_and_duplicate_email(self):
        anon = api()
        body = {"account_type": "buyer", "email": "x@cafe.test", "password": "12345678", "full_name": "X", "business_name": "X"}
        self.assertEqual(anon.post("/api/auth/register/", body, format="json").status_code, 400)
        body["email"] = "owner@buyer.test"
        body["password"] = PW
        self.assertEqual(anon.post("/api/auth/register/", body, format="json").status_code, 400)

    def test_logout_revokes_refresh_token(self):
        c = APIClient()
        tokens = c.post("/api/auth/login/", {"email": "owner@buyer.test", "password": PW}, format="json").json()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(c.post("/api/auth/logout/", {"refresh": tokens["refresh"]}, format="json").status_code, 204)
        self.assertEqual(APIClient().post("/api/auth/refresh/", {"refresh": tokens["refresh"]}, format="json").status_code, 401)

    def test_cancel_restores_stock_and_blocks_paid_orders(self):
        buyer = api("owner@buyer.test")
        order = self._cart_order(buyer, self.price_a, 10)
        self.price_a.refresh_from_db()
        self.assertEqual(self.price_a.stock_quantity, Decimal("490"))
        self.assertEqual(buyer.post(f"/api/orders/{order['id']}/cancel/").json()["status"], "cancelled")
        self.price_a.refresh_from_db()
        self.assertEqual(self.price_a.stock_quantity, Decimal("500"))

        paid = self._cart_order(buyer, self.price_a, 10)
        buyer.post("/api/payments/initiate/", {"order_id": paid["id"], "phone_number": "0712345678"}, format="json")
        self.assertEqual(buyer.post(f"/api/orders/{paid['id']}/cancel/").status_code, 400)


class ExpiryTests(Base):
    def test_stale_unpaid_orders_expire_and_release_stock_but_paid_ones_survive(self):
        from datetime import timedelta
        from django.core.management import call_command
        from django.utils import timezone

        buyer = api("owner@buyer.test")
        stale = self._cart_order(buyer, self.price_a, 10)
        fresh = self._cart_order(buyer, self.price_a, 5)
        paying = self._cart_order(buyer, self.price_a, 7)
        Payment.objects.create(order_id=paying["id"], amount=Decimal("1"), status="pending")
        old = timezone.now() - timedelta(hours=30)
        Order.objects.filter(pk__in=[stale["id"], paying["id"]]).update(created_at=old)

        self.price_a.refresh_from_db()
        self.assertEqual(self.price_a.stock_quantity, Decimal("478"))  # 500 - 10 - 5 - 7
        call_command("expire_unpaid_orders", "--hours", "24", verbosity=0)

        self.assertEqual(Order.objects.get(pk=stale["id"]).status, "cancelled")
        self.assertEqual(Order.objects.get(pk=fresh["id"]).status, "submitted")   # too recent
        self.assertEqual(Order.objects.get(pk=paying["id"]).status, "submitted")  # payment in flight: untouched
        self.price_a.refresh_from_db()
        self.assertEqual(self.price_a.stock_quantity, Decimal("488"))  # the stale order's 10 came back


class SecurityTests(Base):
    def test_unauthenticated_requests_are_rejected(self):
        anon = api()
        for url in ["/api/orders/", "/api/carts/", "/api/catalog/products/", "/api/analytics/buyer-dashboard/", "/api/auth/me/"]:
            self.assertEqual(anon.get(url).status_code, 401, url)

    def test_health_is_public_and_leaks_nothing(self):
        r = api().get("/api/health/")
        self.assertEqual((r.status_code, r.json()), (200, {"status": "ok"}))

    def test_buyer_cannot_create_or_edit_supplier_prices(self):
        buyer = api("owner@buyer.test")
        r = buyer.post("/api/pricing/supplier-prices/", {"supplier": str(self.sup_a[0].id), "product": str(self.onion.id),
                                                          "unit_price": "1", "stock_quantity": "9", "minimum_order_quantity": "1"}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(buyer.patch(f"/api/pricing/supplier-prices/{self.price_a.id}/", {"unit_price": "1"}, format="json").status_code, 403)

    def test_supplier_cannot_write_to_another_suppliers_listing_or_spoof_owner(self):
        a = api("a@supplier.test")
        self.assertEqual(a.patch(f"/api/pricing/supplier-prices/{self.price_b.id}/", {"unit_price": "1"}, format="json").status_code, 404)
        r = a.post("/api/pricing/supplier-prices/", {"supplier": str(self.sup_b[0].id), "product": str(self.onion.id),
                                                      "unit_price": "50", "stock_quantity": "9", "minimum_order_quantity": "1"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["supplier"], str(self.sup_a[0].id))  # forced to own supplier, body ignored

    def test_supplier_input_validation(self):
        a = api("a@supplier.test")
        base = {"product": str(self.onion.id), "stock_quantity": "9", "minimum_order_quantity": "1"}
        self.assertEqual(a.post("/api/pricing/supplier-prices/", {**base, "unit_price": "-5"}, format="json").status_code, 400)
        self.assertEqual(a.post("/api/pricing/supplier-prices/", {**base, "unit_price": "0"}, format="json").status_code, 400)

    def test_buyer_dashboard_cannot_read_other_branch(self):
        o = Order.objects.create(branch=self.branch2, order_number="X-1", status="confirmed", total_amount=Decimal("999999"),
                                 subtotal=Decimal("999999"), placed_by=self.other_buyer)
        mine = api("owner@buyer.test").get(f"/api/analytics/buyer-dashboard/?branch_id={self.branch2.id}").json()
        self.assertEqual(Decimal(str(mine["monthly_spend"])), Decimal("0"))
        self.assertEqual(api("owner@buyer.test").get(f"/api/orders/{o.id}/").status_code, 404)

    def test_buyer_cannot_view_supplier_analytics_or_admin_overview(self):
        buyer = api("owner@buyer.test")
        self.assertEqual(buyer.get("/api/analytics/supplier-dashboard/").status_code, 403)
        self.assertEqual(buyer.get("/api/analytics/admin-overview/").status_code, 403)
        self.assertEqual(buyer.get("/api/suppliers/admin/").status_code, 403)

    def test_cannot_create_branch_in_another_org_or_change_tier(self):
        c = api("owner@buyer.test")
        r = c.post("/api/organizations/branches/", {"organization": str(self.org2.id), "name": "Sneaky"}, format="json")
        self.assertEqual(r.status_code, 400)
        r = c.patch(f"/api/organizations/orgs/{self.org.id}/", {"subscription_tier": "enterprise"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.org.refresh_from_db()
        self.assertEqual(self.org.subscription_tier, "starter")  # silently ignored: read-only field
        # a non-owner clerk can't add branches at all
        self.assertEqual(api("clerk@buyer.test").post("/api/organizations/branches/", {"name": "B"}, format="json").status_code, 403)

    def test_unverified_supplier_cannot_be_bought_from(self):
        pending, _ = self._supplier("Pending Farm", "p@supplier.test", 0, 0, status="pending")
        price = self._price(pending, self.onion, 10)
        r = api("owner@buyer.test").post("/api/carts/add-item/", {"supplier_price_id": str(price.id), "quantity": 1}, format="json")
        self.assertEqual(r.status_code, 404)

    def test_supplier_and_staff_accounts_have_no_cart(self):
        self.assertEqual(api("a@supplier.test").post("/api/carts/add-item/", {"supplier_price_id": str(self.price_a.id), "quantity": 1}, format="json").status_code, 403)

    def test_stock_and_moq_enforced_at_cart_and_checkout(self):
        buyer = api("owner@buyer.test")
        r = buyer.post("/api/carts/add-item/", {"supplier_price_id": str(self.price_a.id), "quantity": 99999}, format="json")
        self.assertEqual(r.status_code, 400)
        moq = self._price(self.sup_a[0], self.onion, 50, moq=10)
        r = buyer.post("/api/carts/add-item/", {"supplier_price_id": str(moq.id), "quantity": 2}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_checkout_rejects_stale_price_and_sold_out_stock(self):
        buyer = api("owner@buyer.test")
        cart = buyer.post("/api/carts/add-item/", {"supplier_price_id": str(self.price_a.id), "quantity": 20}, format="json").json()
        self.price_a.unit_price = Decimal("120")
        self.price_a.save()
        r = buyer.post(f"/api/carts/{cart['id']}/checkout/")
        self.assertEqual(r.status_code, 409)
        self.assertIn("price", r.json()["detail"].lower())
        self.price_a.unit_price = Decimal("90")
        self.price_a.stock_quantity = Decimal("5")
        self.price_a.save()
        r = buyer.post(f"/api/carts/{cart['id']}/checkout/")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(Order.objects.count(), 0)  # nothing half-created

    def test_another_buyer_cannot_see_or_pay_my_order(self):
        order = self._cart_order(api("owner@buyer.test"), self.price_a, 5)
        other = api("other@buyer.test")
        self.assertEqual(other.get(f"/api/orders/{order['id']}/").status_code, 404)
        self.assertEqual(other.post("/api/payments/initiate/", {"order_id": order["id"], "phone_number": "0712345678"}, format="json").status_code, 404)
        self.assertEqual(other.post(f"/api/orders/{order['id']}/cancel/").status_code, 404)

    def test_suppliers_cannot_use_buyer_order_endpoint(self):
        order = self._cart_order(api("owner@buyer.test"), self.price_a, 5)
        self.assertEqual(api("a@supplier.test").get(f"/api/orders/{order['id']}/").status_code, 404)


class ApprovalTests(Base):
    def _big_order(self):
        # 300 * 90 + 300 = 27,300 -> needs manager + procurement
        return self._cart_order(api("clerk@buyer.test"), self.price_a, 300)

    def test_order_waits_for_approval_and_cannot_be_submitted_or_paid_early(self):
        order = self._big_order()
        self.assertEqual(order["status"], "draft")
        self.assertEqual({a["approver_role"] for a in order["approvals"]}, {"manager", "procurement"})
        clerk = api("clerk@buyer.test")
        self.assertEqual(clerk.post(f"/api/orders/{order['id']}/submit/").status_code, 400)  # bypass blocked
        r = clerk.post("/api/payments/initiate/", {"order_id": order["id"], "phone_number": "0712345678"}, format="json")
        self.assertEqual(r.status_code, 409)

    @override_settings(ALLOW_MOCK_PAYMENTS=True)
    def test_requester_cannot_self_approve_but_owner_can(self):
        order = self._big_order()
        approvals = order["approvals"]
        clerk, owner = api("clerk@buyer.test"), api("owner@buyer.test")
        self.assertFalse(any(a["can_decide"] for a in clerk.get(f"/api/orders/{order['id']}/").json()["approvals"]))
        r = clerk.post(f"/api/orders/{order['id']}/approve/", {"approval_id": approvals[0]["id"]}, format="json")
        self.assertEqual(r.status_code, 403)

        for a in approvals:
            r = owner.post(f"/api/orders/{order['id']}/approve/", {"approval_id": a["id"]}, format="json")
            self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["status"], "submitted")
        pay = owner.post("/api/payments/initiate/", {"order_id": order["id"], "phone_number": "0712345678"}, format="json")
        self.assertEqual(pay.status_code, 202)

    def test_dedicated_role_can_approve_only_its_step(self):
        mgr = self._user("mgr@buyer.test", org=self.org, branch=self.branch, role="buyer_manager")
        order = self._big_order()
        by_role = {a["approver_role"]: a["id"] for a in order["approvals"]}
        c = api("mgr@buyer.test")
        self.assertEqual(c.post(f"/api/orders/{order['id']}/approve/", {"approval_id": by_role["procurement"]}, format="json").status_code, 403)
        self.assertEqual(c.post(f"/api/orders/{order['id']}/approve/", {"approval_id": by_role["manager"]}, format="json").status_code, 200)


class PaymentSecurityTests(Base):
    def _submitted(self):
        return self._cart_order(api("owner@buyer.test"), self.price_a, 20)

    def test_payments_are_refused_when_not_configured_and_mock_not_allowed(self):
        order = self._submitted()
        r = api("owner@buyer.test").post("/api/payments/initiate/", {"order_id": order["id"], "phone_number": "0712345678"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Payment.objects.count(), 0)
        self.assertEqual(Order.objects.get(pk=order["id"]).status, "submitted")  # NOT marked paid

    def test_invalid_phone_number_rejected(self):
        order = self._submitted()
        with override_settings(ALLOW_MOCK_PAYMENTS=True):
            r = api("owner@buyer.test").post("/api/payments/initiate/", {"order_id": order["id"], "phone_number": "12345"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_msisdn_normalisation(self):
        for raw in ["0712345678", "+254712345678", "254712345678", "712345678", "0712 345 678", "0112345678"]:
            self.assertRegex(normalize_msisdn(raw), r"^254[17]\d{8}$")
        with self.assertRaises(PaymentError):
            normalize_msisdn("0612345678")

    @override_settings(MPESA_CONFIG=MPESA_ON)
    def test_daraja_flow_end_to_end_with_signed_path_callback(self):
        order = self._submitted()
        oauth = mock.Mock(status_code=200, **{"json.return_value": {"access_token": "tok"}, "raise_for_status.return_value": None})
        push = mock.Mock(status_code=200, **{"json.return_value": {
            "MerchantRequestID": "m-1", "CheckoutRequestID": "ws_CO_123", "ResponseCode": "0", "CustomerMessage": "Enter PIN"}})
        with mock.patch("payments.mpesa_adapter.requests.get", return_value=oauth), \
             mock.patch("payments.mpesa_adapter.requests.post", return_value=push) as post:
            r = api("owner@buyer.test").post("/api/payments/initiate/", {"order_id": order["id"], "phone_number": "0712345678"}, format="json")
        self.assertEqual(r.status_code, 202, r.content)
        sent = post.call_args.kwargs["json"]
        self.assertEqual(sent["PartyA"], "254712345678")
        self.assertEqual(sent["Amount"], 2100)
        self.assertLessEqual(len(sent["AccountReference"]), 12)
        self.assertEqual(sent["CallBackURL"], f"https://example.test/api/payments/mpesa-callback/{SECRET}/")
        self.assertEqual(Order.objects.get(pk=order["id"]).status, "submitted")  # NOT paid until Safaricom confirms

        def cb(code=0, amount=2100.0):
            body = {"Body": {"stkCallback": {"MerchantRequestID": "m-1", "CheckoutRequestID": "ws_CO_123",
                    "ResultCode": code, "ResultDesc": "x"}}}
            if code == 0:
                body["Body"]["stkCallback"]["CallbackMetadata"] = {"Item": [
                    {"Name": "Amount", "Value": amount}, {"Name": "MpesaReceiptNumber", "Value": "NLJ7RT61SV"}]}
            return body

        anon = api()
        url = f"/api/payments/mpesa-callback/{SECRET}/"
        # wrong secret: 404, nothing changes (an attacker can't mark orders paid)
        self.assertEqual(anon.post("/api/payments/mpesa-callback/guess/", cb(), format="json").status_code, 404)
        self.assertEqual(Order.objects.get(pk=order["id"]).status, "submitted")
        # wrong amount: leaves it pending for manual reconciliation
        anon.post(url, cb(amount=1.0), format="json")
        self.assertEqual(Payment.objects.get().status, "pending")
        self.assertEqual(Order.objects.get(pk=order["id"]).status, "submitted")
        # right secret + matching amount: settles
        self.assertEqual(anon.post(url, cb(), format="json").status_code, 200)
        self.assertEqual(Order.objects.get(pk=order["id"]).status, "confirmed")
        self.assertEqual(Payment.objects.get().provider_reference, "NLJ7RT61SV")
        self.assertEqual(Invoice.objects.get().payment_status, "paid")
        # replayed callback is a no-op
        anon.post(url, cb(), format="json")
        self.assertEqual(Invoice.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 1)

    @override_settings(MPESA_CONFIG=MPESA_ON)
    def test_cancelled_by_user_on_phone_marks_failed_and_allows_retry(self):
        order = self._submitted()
        Payment.objects.create(order_id=order["id"], amount=Decimal("2100"), provider_reference="ws_CO_9")
        body = {"Body": {"stkCallback": {"MerchantRequestID": "m", "CheckoutRequestID": "ws_CO_9", "ResultCode": 1032, "ResultDesc": "Request cancelled by user"}}}
        api().post(f"/api/payments/mpesa-callback/{SECRET}/", body, format="json")
        self.assertEqual(Payment.objects.get().status, "failed")
        self.assertEqual(Order.objects.get(pk=order["id"]).status, "submitted")
        Payment.objects.create(order_id=order["id"], amount=Decimal("2100"))  # constraint allows a new attempt after a failure

    @override_settings(MPESA_CONFIG=MPESA_ON)
    def test_only_one_live_payment_per_order(self):
        order = self._submitted()
        Payment.objects.create(order_id=order["id"], amount=Decimal("2100"), status="pending")
        r = api("owner@buyer.test").post("/api/payments/initiate/", {"order_id": order["id"], "phone_number": "0712345678"}, format="json")
        self.assertEqual(r.status_code, 409)

    def test_callback_disabled_when_no_secret_configured(self):
        self.assertEqual(api().post("/api/payments/mpesa-callback//", {}, format="json").status_code, 404)
        self.assertEqual(api().post("/api/payments/mpesa-callback/anything/", {}, format="json").status_code, 404)

    def test_mock_adapter_cannot_be_reached_in_production_mode(self):
        from payments.mpesa_adapter import get_payment_adapter
        from django.conf import settings
        with override_settings(DEBUG=False, ALLOW_MOCK_PAYMENTS=False):
            with self.assertRaises(PaymentError):
                get_payment_adapter(settings)

    def test_daraja_adapter_refuses_incomplete_config(self):
        with self.assertRaises(PaymentError):
            MpesaDarajaAdapter({"ENABLED": True, "CONSUMER_KEY": "k"})


class SupplierVerificationTests(Base):
    def test_admin_workflow_and_state_machine(self):
        pending, _ = self._supplier("New Farm", "n@supplier.test", 0, 0, status="pending")
        admin = api("ops@getbyfarm.test")
        base = f"/api/suppliers/admin/{pending.id}"
        self.assertEqual(admin.post(f"{base}/verify/").status_code, 400)  # can't skip review
        self.assertEqual(admin.post(f"{base}/review/").json()["verification_status"], "under_review")
        r = admin.post(f"{base}/verify/").json()
        self.assertEqual(r["verification_status"], "verified")
        self.assertGreater(float(r["reliability_score"]), 0)  # neutral prior so new suppliers aren't ranked last forever
        # bare PATCH can't force a status or score
        admin.patch(f"{base}/", {"verification_status": "pending", "reliability_score": "100"}, format="json")
        pending.refresh_from_db()
        self.assertEqual(pending.verification_status, "verified")
        self.assertLess(float(pending.reliability_score), 100)
        self.assertEqual(admin.post(f"{base}/suspend/").json()["verification_status"], "suspended")

    def test_admin_overview_numbers(self):
        data = api("ops@getbyfarm.test").get("/api/analytics/admin-overview/").json()
        self.assertEqual(data["active_suppliers"], 2)
        self.assertEqual(data["buyers"], 2)


import threading
import unittest

from django.db import connection, connections
from django.test import TransactionTestCase


@unittest.skipUnless(connection.vendor == "postgresql", "row-level locking needs PostgreSQL")
class OversellRaceTests(TransactionTestCase):
    """Two buyers check out the last stock at the same instant: exactly one must win, never both."""

    def test_concurrent_checkouts_cannot_oversell(self):
        from carts.models import Cart, CartItem
        from orders.services import OrderError, create_order_from_cart

        ke = Country.objects.get(code="KE")
        product = Product.objects.create(category=Category.objects.create(name="C", slug="c"), name="Rice", default_unit="kg")
        sup = SupplierOrganization.objects.create(business_name="S", country=ke, verification_status="verified")
        price = SupplierPrice.objects.create(supplier=sup, product=product, unit_price=Decimal("100"),
                                             stock_quantity=Decimal("10"), minimum_order_quantity=Decimal("1"))
        carts = []
        for n in range(2):
            org = Organization.objects.create(name=f"Org{n}", country=ke)
            br = Branch.objects.create(organization=org, name="B")
            u = User.objects.create_user(email=f"u{n}@race.test", password=PW, full_name="U", organization=org, branch=br)
            cart = Cart.objects.create(branch=br)
            CartItem.objects.create(cart=cart, supplier_price=price, quantity=Decimal("8"), locked_unit_price=Decimal("100"))
            carts.append((cart, u))

        barrier, results = threading.Barrier(2), []

        def checkout(cart, user):
            try:
                barrier.wait()
                create_order_from_cart(cart, user)
                results.append("ok")
            except OrderError:
                results.append("sold_out")
            finally:
                connections.close_all()

        threads = [threading.Thread(target=checkout, args=c) for c in carts]
        [t.start() for t in threads]
        [t.join() for t in threads]

        self.assertEqual(sorted(results), ["ok", "sold_out"])
        price.refresh_from_db()
        self.assertEqual(price.stock_quantity, Decimal("2"))
        self.assertEqual(Order.objects.count(), 1)
