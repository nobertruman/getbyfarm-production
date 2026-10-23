/**
 * Frontend <-> backend contract test.
 * Runs the REAL lib/auth.ts + lib/api.ts (the same code the browser runs) against a live API,
 * walking the complete journey. Needs a backend reachable at NEXT_PUBLIC_API_URL with
 * ALLOW_MOCK_PAYMENTS on (staging) and E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD for a staff user.
 *
 *   NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 npx tsx e2e/contract.ts
 */
const store = new Map();
globalThis.window = {
  localStorage: {
    getItem: (k) => store.get(k) ?? null,
    setItem: (k, v) => void store.set(k, v),
    removeItem: (k) => void store.delete(k),
  },
  location: { assign: (u) => console.log("   (redirect →", u + ")") },
};

import * as api from "../lib/api";
import { login, logout, getRefreshToken } from "../lib/auth";
import { ApiError } from "../lib/api-client";
import { num } from "../lib/format";

let passed = 0;
function ok(cond, label) {
  if (!cond) {
    console.error(`  ✗ ${label}`);
    process.exitCode = 1;
    throw new Error(`FAILED: ${label}`);
  }
  passed++;
  console.log(`  ✓ ${label}`);
}
const rnd = Math.random().toString(36).slice(2, 8);
const PW = "Contract-Test-Pw-9!";
const buyerEmail = `buyer-${rnd}@e2e.test`,
  supEmail = `supplier-${rnd}@e2e.test`;

async function main() {
  console.log("\n1. Sign up");
  await api.register({
    account_type: "buyer",
    email: buyerEmail,
    password: PW,
    full_name: "Wanjiru Test",
    business_name: `Cafe ${rnd}`,
    operating_location: "Nairobi",
  });
  await api.register({
    account_type: "supplier",
    email: supEmail,
    password: PW,
    full_name: "Otieno Test",
    business_name: `Farm ${rnd}`,
    operating_location: "Kiambu",
  });
  try {
    await api.register({ account_type: "buyer", email: buyerEmail, password: PW, full_name: "x", business_name: "x" });
    ok(false, "duplicate email rejected");
  } catch (e) {
    ok(
      e instanceof ApiError && /already exists/i.test(e.message),
      `duplicate email gives readable error: "${e.message}"`,
    );
  }
  try {
    await api.register({
      account_type: "buyer",
      email: `w-${rnd}@e2e.test`,
      password: "12345678",
      full_name: "x",
      business_name: "x",
    });
    ok(false, "weak password rejected");
  } catch (e) {
    ok(e instanceof ApiError && e.status === 400, "weak password rejected with 400");
  }

  console.log("\n2. Supplier lists a product (still unverified)");
  await login(supEmail, PW);
  let me = await api.getMe();
  ok(
    me.role === "supplier" && me.supplier?.verification_status === "pending",
    "supplier /me → role=supplier, status=pending",
  );
  const catalogue = (await api.listProducts("Tomatoes")).results;
  ok(catalogue.length >= 1, "catalogue search returns Tomatoes");
  const tomato = catalogue[0];
  const price = await api.createPrice({
    product: tomato.id,
    unit_price: "90.00",
    stock_quantity: "500",
    minimum_order_quantity: "1",
    delivery_cost_flat: "300",
    lead_time_days: "1",
  });
  ok(num(price.unit_price) === 90, "listing created, decimal string parses via num()");
  ok(api.rows(await api.listMyPrices()).length === 1, "supplier sees own listing");
  await logout();

  console.log("\n3. Buyer cannot buy from an unverified supplier");
  await login(buyerEmail, PW);
  me = await api.getMe();
  ok(me.role === "buyer" && me.branch !== null, "buyer /me → role=buyer with a branch");
  try {
    await api.recommend(tomato.id, 10);
    ok(false, "no verified supplier");
  } catch (e) {
    ok(e instanceof ApiError && e.status === 404, "recommend → 404 'no verified supplier' (new supplier is invisible)");
  }
  await logout();

  console.log("\n4. Admin verifies the supplier");
  await login(process.env.E2E_ADMIN_EMAIL, process.env.E2E_ADMIN_PASSWORD);
  ok((await api.getMe()).role === "admin", "staff user routes to admin");
  let queue = api.rows(await api.listAdminSuppliers("pending"));
  const target = queue.find((s) => s.business_name === `Farm ${rnd}`);
  ok(!!target, "new supplier appears in the pending queue");
  try {
    await api.supplierAction(target.id, "verify");
    ok(false, "cannot skip review");
  } catch (e) {
    ok(e instanceof ApiError && e.status === 400, "cannot verify without review (state machine enforced)");
  }
  await api.supplierAction(target.id, "review");
  const verified = await api.supplierAction(target.id, "verify");
  ok(
    verified.verification_status === "verified" && num(verified.reliability_score) > 0,
    "verified with a neutral starting reliability",
  );
  const overview = await api.getAdminOverview();
  ok(overview.active_suppliers >= 1 && typeof overview.orders_by_status === "object", "admin overview loads");
  await logout();

  console.log("\n5. Buyer: compare → cart → checkout (small order)");
  await login(buyerEmail, PW);
  const rec = await api.recommend(tomato.id, 20);
  ok(
    rec.recommended?.supplier_name === `Farm ${rnd}` ||
      rec.ranked_candidates.some((c) => c.supplier_name === `Farm ${rnd}`),
    "engine now ranks the verified supplier",
  );
  const offer = rec.ranked_candidates.find((c) => c.supplier_name === `Farm ${rnd}`);
  ok(
    !!offer.supplier_price_id && typeof offer.reliability_score === "number" && offer.explanation.length > 10,
    "offer carries supplier_price_id, reliability and an explanation",
  );
  let cart = await api.addCartItem(offer.supplier_price_id, 20, offer.explanation);
  ok(cart.items.length === 1 && num(cart.totals.total) === 2100, "cart total = 20×90 + 300 delivery = 2,100");
  cart = await api.getOpenCart();
  ok(
    cart.items[0].product_name.includes("Tomatoes") && cart.items[0].unit === "kg",
    "GET cart returns product name and unit",
  );
  const order = await api.checkoutCart(cart.id);
  ok(
    order.status === "submitted" && order.approvals.length === 0,
    "order under KSh 20,000 skips approval → awaiting payment",
  );
  ok((await api.getOpenCart()) === null, "cart is empty after checkout");

  console.log("\n6. Pay with M-Pesa (staging mock adapter) → invoice");
  try {
    await api.initiatePayment(order.id, "12345");
    ok(false, "bad phone");
  } catch (e) {
    ok(
      e instanceof ApiError && /valid Safaricom number/i.test(e.message),
      `invalid phone → readable error: "${e.message}"`,
    );
  }
  const pay = await api.initiatePayment(order.id, "0712 345 678");
  ok(pay.payment.status === "success", "payment settles");
  ok((await api.getPaymentStatus(order.id)).status === "success", "payment status endpoint agrees");
  const orders = api.rows(await api.listOrders());
  ok(orders[0].status === "confirmed", "order is now confirmed");
  const invoices = api.rows(await api.listInvoices());
  ok(
    invoices.length === 1 && invoices[0].payment_status === "paid" && invoices[0].order === order.id,
    "invoice generated and marked paid",
  );
  try {
    await api.initiatePayment(order.id, "0712345678");
    ok(false, "double pay");
  } catch (e) {
    ok(e instanceof ApiError && e.status === 409, "paying twice is refused (409)");
  }

  console.log("\n7. Buyer places a large order → approval chain");
  cart = await api.addCartItem(offer.supplier_price_id, 300, "bulk");
  const big = await api.checkoutCart(cart.id);
  ok(big.status === "draft" && big.approvals.length === 2, "KSh 27,300 order needs manager + procurement approval");
  ok(
    big.approvals.every((a) => a.can_decide),
    "business owner (enterprise_admin) can decide every step",
  );
  let latest = big;
  for (const a of big.approvals) latest = await api.approveOrder(big.id, a.id);
  ok(latest.status === "submitted", "after both approvals the order is ready to pay");
  const cancelled = await api.cancelOrder(big.id);
  ok(cancelled.status === "cancelled", "unpaid order can be cancelled (stock released)");
  await logout();

  console.log("\n8. Supplier fulfils the paid order");
  await login(supEmail, PW);
  const stats0 = await api.getSupplierDashboard();
  ok(
    num(stats0.revenue_30d) === 1800 && stats0.open_orders === 1,
    "supplier dashboard: KSh 1,800 revenue, 1 open order",
  );
  const queue2 = api.rows(await api.listAllocations());
  ok(
    queue2.length === 1 && queue2[0].items.length === 1 && queue2[0].buyer.includes(`Cafe ${rnd}`),
    "supplier sees only its own slice, with buyer name",
  );
  for (const step of ["accepted", "preparing", "ready", "dispatched", "delivered"]) {
    const a = await api.advanceAllocation(queue2[0].id, step);
    ok(a.status === step, `advance → ${step}`);
  }
  try {
    await api.advanceAllocation(queue2[0].id, "accepted");
    ok(false, "backwards");
  } catch (e) {
    ok(e instanceof ApiError && e.status === 400, "cannot move an order backwards");
  }
  await logout();

  console.log("\n9. Buyer confirms receipt");
  await login(buyerEmail, PW);
  const delivered = api.rows(await api.listOrders()).find((o) => o.id === order.id);
  ok(delivered.status === "delivered", "order status derived from supplier progress → delivered");
  ok((await api.confirmReceipt(order.id)).status === "completed", "buyer confirms → completed");
  const dash = await api.getBuyerDashboard();
  ok(num(dash.monthly_spend) === 2100, "buyer dashboard spend = KSh 2,100");

  console.log("\n10. Session handling");
  const before = getRefreshToken();
  const apiMod = await import("../lib/auth");
  const fresh = await apiMod.refreshAccessToken();
  ok(!!fresh && getRefreshToken() !== before, "refresh rotates and stores the NEW refresh token");
  const old = before;
  const replay = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh: old }),
  });
  ok(replay.status === 401, "the previous refresh token is blacklisted (replay → 401)");
  await logout();
  const afterLogout = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh: before }),
  });
  ok(afterLogout.status === 401, "logout revokes the refresh token server-side");

  console.log(`\nAll ${passed} contract checks passed.`);
}
main().catch((e) => {
  console.error("\n" + e.message);
  process.exit(1);
});
