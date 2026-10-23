/*
 * API SHAPES (reference). This codebase is plain JavaScript, so these are documentation, not enforced types.
 * They mirror the Django serializers exactly. DRF sends DecimalField values (prices, totals, quantities) as
 * STRINGS, e.g. "1800.00": convert with num() / kes() from lib/format.js before arithmetic or display.
 *
 * Role = "buyer" | "supplier" | "admin"
 * OrderStatus = "draft" | "submitted" | "confirmed" | "processing" | "ready_for_dispatch" | "in_transit"
 *             | "delivered" | "completed" | "cancelled"
 *
 * export type Role = "buyer" | "supplier" | "admin";
 * export type Me = {
 *   id: string; email: string; full_name: string; role: Role; roles: string[];
 *   organization: { id: string; name: string } | null;
 *   branch: { id: string; name: string } | null;
 *   supplier: { id: string; business_name: string; verification_status: string } | null;
 * };
 * export type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };
 * export type Product = { id: string; name: string; category_name: string; default_unit: string; description: string };
 * export type Offer = {
 *   supplier_id: string; supplier_price_id: string | null; supplier_name: string;
 *   unit_price: number; delivery_cost: number; total_landed_cost: number;
 *   reliability_score: number; quality_rating: number; lead_time_days: number; available_stock: number;
 *   score: number; component_breakdown: Record<string, number>; explanation: string;
 * };
 * export type Recommendation = {
 *   requested_quantity: number; recommended: Offer | null; ranked_candidates: Offer[];
 *   excluded: { supplier_id: string; supplier_name: string; reason: string }[];
 * };
 * export type CartItem = {
 *   id: string; supplier_price: string; supplier_id: string; product_name: string; unit: string; supplier_name: string;
 *   quantity: string; locked_unit_price: string; delivery_cost: string; recommendation_reason: string; line_total: string;
 * };
 * export type Cart = { id: string; items: CartItem[]; totals: { subtotal: string; delivery_total: string; total: string } };
 * export type Approval = { id: string; approver_role: string; status: string; can_decide: boolean };
 * export type Order = {
 *   id: string; order_number: string; branch_name: string; status: OrderStatus;
 *   subtotal: string; delivery_fee: string; tax_amount: string; total_amount: string; created_at: string;
 *   items: { id: string; product_name: string; unit: string; supplier_name: string; quantity: string; unit_price: string; line_total: string }[];
 *   allocations: { id: string; supplier_name: string; status: string; subtotal: string }[];
 *   approvals: Approval[];
 * };
 * export type Invoice = { id: string; order: string; order_number: string; invoice_number: string; total_amount: string; payment_status: string; issued_at: string };
 * export type Payment = { id: string; status: "pending" | "success" | "failed" | "refunded"; result_description: string; amount: string };
 * export type BuyerDashboard = {
 *   monthly_spend: string; orders_this_month: number; awaiting_approval: number; awaiting_payment: number;
 *   in_progress: number; orders_in_transit: number; supplier_performance_pct: number | null;
 * };
 * export type SupplierDashboard = {
 *   business_name: string; verification_status: string; revenue_30d: string; orders_30d: number; open_orders: number;
 *   fulfillment_rate_pct: number | null; reliability_score: string; quality_rating: string;
 *   top_products: { product__name: string; qty: string; revenue: string }[];
 * };
 * export type Allocation = {
 *   id: string; order_number: string; order_status: string; placed_at: string; status: string; subtotal: string;
 *   buyer: string; delivery_address: string;
 *   items: { product_name: string; unit: string; quantity: string; unit_price: string; line_total: string }[];
 * };
 * export type SupplierPrice = {
 *   id: string; product: string; product_name: string; unit: string; category_name: string; unit_price: string;
 *   stock_quantity: string; minimum_order_quantity: string; delivery_cost_flat: string; lead_time_days: string; is_active: boolean; updated_at?: string;
 * };
 * export type AdminOverview = {
 *   gmv_last_30_days: string; total_orders: number; buyers: number; active_suppliers: number;
 *   pending_supplier_verifications: number; active_products: number; failed_payments_30d: number;
 *   orders_by_status: Record<string, number>;
 * };
 * export type AdminSupplier = {
 *   id: string; business_name: string; operating_location: string; kra_pin: string; registration_number: string;
 *   verification_status: "pending" | "under_review" | "verified" | "suspended" | "rejected";
 *   reliability_score: string; quality_rating: string; created_at: string;
 * };
 */

import { apiFetch } from "./api-client";

// ---- Types: mirror the Django serializers exactly. DRF sends DecimalFields as strings; use num()/kes() to display.

const json = (body) => JSON.stringify(body);
export const rows = (p) => (Array.isArray(p) ? p : p.results);

// ---- Auth
export const register = (body) => apiFetch("/api/auth/register/", { method: "POST", body: json(body) });
export const getMe = () => apiFetch("/api/auth/me/");

// ---- Catalogue & procurement engine
export const listProducts = (search = "") =>
  apiFetch(`/api/catalog/products/?page_size=200${search ? `&search=${encodeURIComponent(search)}` : ""}`);
export const recommend = (productId, quantity) =>
  apiFetch("/api/procurement/recommend/", { method: "POST", body: json({ product_id: productId, quantity }) });

// ---- Cart & orders
export const addCartItem = (supplierPriceId, quantity, reason = "") =>
  apiFetch("/api/carts/add-item/", {
    method: "POST",
    body: json({ supplier_price_id: supplierPriceId, quantity, recommendation_reason: reason }),
  });
export const getOpenCart = async () => rows(await apiFetch("/api/carts/"))[0] ?? null;
export const removeCartItem = (cartId, itemId) =>
  apiFetch(`/api/carts/${cartId}/remove-item/`, { method: "POST", body: json({ item_id: itemId }) });
export const checkoutCart = (cartId) => apiFetch(`/api/carts/${cartId}/checkout/`, { method: "POST" });

export const listOrders = () => apiFetch("/api/orders/?page_size=100");
export const approveOrder = (orderId, approvalId) =>
  apiFetch(`/api/orders/${orderId}/approve/`, { method: "POST", body: json({ approval_id: approvalId }) });
export const cancelOrder = (orderId) => apiFetch(`/api/orders/${orderId}/cancel/`, { method: "POST" });
export const confirmReceipt = (orderId) => apiFetch(`/api/orders/${orderId}/confirm-receipt/`, { method: "POST" });
export const listInvoices = () => apiFetch("/api/invoices/?page_size=100");

// ---- Payments
export const initiatePayment = (orderId, phone) =>
  apiFetch("/api/payments/initiate/", { method: "POST", body: json({ order_id: orderId, phone_number: phone }) });
export const getPaymentStatus = (orderId) => apiFetch(`/api/payments/status/${orderId}/`);

// ---- Dashboards
export const getBuyerDashboard = () => apiFetch("/api/analytics/buyer-dashboard/");
export const getSupplierDashboard = () => apiFetch("/api/analytics/supplier-dashboard/");
export const getAdminOverview = () => apiFetch("/api/analytics/admin-overview/");

// ---- Supplier
export const listAllocations = () => apiFetch("/api/orders/allocations/?page_size=100");
export const advanceAllocation = (id, status) =>
  apiFetch(`/api/orders/allocations/${id}/advance/`, { method: "POST", body: json({ status }) });
export const listMyPrices = () => apiFetch("/api/pricing/supplier-prices/?page_size=200");
export const createPrice = (body) => apiFetch("/api/pricing/supplier-prices/", { method: "POST", body: json(body) });
export const updatePrice = (id, body) =>
  apiFetch(`/api/pricing/supplier-prices/${id}/`, { method: "PATCH", body: json(body) });
export const deletePrice = (id) => apiFetch(`/api/pricing/supplier-prices/${id}/`, { method: "DELETE" });

// ---- Admin
export const listAdminSuppliers = (status) =>
  apiFetch(`/api/suppliers/admin/?page_size=100${status ? `&verification_status=${status}` : ""}`);
export const supplierAction = (id, action) => apiFetch(`/api/suppliers/admin/${id}/${action}/`, { method: "POST" });
