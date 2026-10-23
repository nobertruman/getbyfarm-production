"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { EmptyState, ErrorNote, Loading, StatusPill } from "@/components/ui";
import { OrderTimeline } from "@/components/OrderTimeline";
import {
  approveOrder,
  cancelOrder,
  confirmReceipt,
  getPaymentStatus,
  initiatePayment,
  listInvoices,
  listOrders,
} from "@/lib/api";
import { kes, qty, shortDate } from "@/lib/format";
import { useAsync } from "@/lib/useAsync";

const ROLE_LABEL = { manager: "Manager", procurement: "Procurement", finance: "Finance" };
const ALLOC_LABEL = {
  new: "Waiting for supplier",
  accepted: "Accepted",
  preparing: "Preparing",
  ready: "Ready",
  dispatched: "On the way",
  delivered: "Delivered",
  cancelled: "Cancelled",
};

/** M-Pesa payment: sends the STK prompt, then polls until Safaricom confirms (or rejects) it. */
function PayPanel({ order, onDone }) {
  const [phone, setPhone] = useState("");
  const [state, setState] = useState("idle");
  const [message, setMessage] = useState(null);
  const timer = useRef(null);
  useEffect(
    () => () => {
      if (timer.current) clearInterval(timer.current);
    },
    [],
  );

  async function pay(e) {
    e.preventDefault();
    setState("starting");
    setMessage(null);
    try {
      const res = await initiatePayment(order.id, phone);
      if (res.payment.status === "success") return onDone();
      setState("waiting");
      setMessage(res.message);
      let tries = 0;
      timer.current = setInterval(async () => {
        tries += 1;
        try {
          const p = await getPaymentStatus(order.id);
          if (p.status === "success") {
            clearInterval(timer.current);
            onDone();
          } else if (p.status === "failed") {
            clearInterval(timer.current);
            setState("failed");
            setMessage(p.result_description || "The payment was not completed.");
          }
        } catch {
          /* transient: keep polling */
        }
        if (tries >= 40) {
          clearInterval(timer.current);
          setState("failed");
          setMessage(
            "We didn't get a confirmation yet. If M-Pesa charged you, this page will update shortly. Refresh to check.",
          );
        }
      }, 3000);
    } catch (err) {
      setState("failed");
      setMessage(err instanceof Error ? err.message : "Could not start the payment.");
    }
  }

  return (
    <form onSubmit={pay} className="rounded border border-ember-500/40 bg-ember-50 p-4">
      <p className="font-medium">Pay {kes(order.total_amount)} with M-Pesa</p>
      <p className="mt-1 text-sm text-ink-soft">
        Enter the Safaricom number to charge. You'll get a prompt on that phone to enter your M-Pesa PIN.
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <label htmlFor={`phone-${order.id}`} className="sr-only">
          M-Pesa phone number
        </label>
        <input
          id={`phone-${order.id}`}
          type="tel"
          required
          placeholder="0712 345 678"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          disabled={state === "waiting" || state === "starting"}
          className="num w-48 rounded border border-line bg-paper px-3 py-2"
        />
        <button
          disabled={state === "waiting" || state === "starting"}
          className="rounded bg-ember-600 px-5 py-2 text-sm font-medium text-white hover:bg-ember-700 disabled:opacity-60"
        >
          {state === "starting" ? "Sending…" : state === "waiting" ? "Waiting for PIN…" : "Pay with M-Pesa"}
        </button>
      </div>
      {state === "waiting" && (
        <p className="mt-3 text-sm text-leaf-700" role="status">
          {message || "Check your phone and enter your M-Pesa PIN."}
        </p>
      )}
      {state === "failed" && message && (
        <div className="mt-3">
          <ErrorNote>{message}</ErrorNote>
        </div>
      )}
    </form>
  );
}

function OrderCard({ order, invoice, open, onToggle, reload }) {
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const act = async (fn) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "That didn't work.");
    }
    setBusy(false);
  };
  const pending = order.approvals.filter((a) => a.status === "pending");

  return (
    <div id={order.id}>
      <button
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full flex-wrap items-center justify-between gap-3 px-4 py-4 text-left hover:bg-paper-dim sm:px-5"
      >
        <span className="flex flex-wrap items-center gap-x-4 gap-y-1">
          <span className="num text-sm text-ink-faint">{order.order_number}</span>
          <span className="text-xs text-ink-faint">{shortDate(order.created_at)}</span>
        </span>
        <span className="flex items-center gap-4">
          <span className="num text-sm font-medium">{kes(order.total_amount)}</span>
          <StatusPill status={order.status} />
        </span>
      </button>

      {open && (
        <div className="space-y-6 border-t border-line bg-paper px-4 py-6 sm:px-5">
          <OrderTimeline status={order.status} />
          {error && <ErrorNote>{error}</ErrorNote>}

          {order.status === "draft" && (
            <div className="rounded border border-ember-300 bg-ember-100 p-4 text-sm">
              <p className="font-medium text-ember-700">This order needs approval before it can be paid.</p>
              <ul className="mt-3 space-y-2">
                {order.approvals.map((a) => (
                  <li key={a.id} className="flex flex-wrap items-center justify-between gap-2">
                    <span>
                      {ROLE_LABEL[a.approver_role] ?? a.approver_role} approval ·{" "}
                      <span className={a.status === "approved" ? "text-leaf-700" : ""}>{a.status}</span>
                    </span>
                    {a.can_decide && (
                      <button
                        disabled={busy}
                        onClick={() => act(() => approveOrder(order.id, a.id))}
                        className="rounded bg-leaf-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-leaf-700"
                      >
                        Approve
                      </button>
                    )}
                  </li>
                ))}
              </ul>
              {pending.length > 0 && !pending.some((a) => a.can_decide) && (
                <p className="mt-3 text-xs text-ember-700">
                  Ask someone with the right role in your business to approve.
                </p>
              )}
            </div>
          )}

          {order.status === "submitted" && <PayPanel order={order} onDone={reload} />}

          <div className="overflow-x-auto rounded border border-line bg-paper-raised">
            <table className="w-full min-w-[520px] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-ink-faint">
                  <th className="px-4 py-2.5 font-normal">Item</th>
                  <th className="px-4 py-2.5 font-normal">Supplier</th>
                  <th className="px-4 py-2.5 text-right font-normal">Qty</th>
                  <th className="px-4 py-2.5 text-right font-normal">Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {order.items.map((i) => (
                  <tr key={i.id}>
                    <td className="px-4 py-2.5">{i.product_name}</td>
                    <td className="px-4 py-2.5 text-ink-soft">{i.supplier_name}</td>
                    <td className="num px-4 py-2.5 text-right">
                      {qty(i.quantity)} {i.unit}
                    </td>
                    <td className="num px-4 py-2.5 text-right">{kes(i.line_total)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t border-line text-sm">
                <tr>
                  <td colSpan={3} className="px-4 py-2 text-right text-ink-faint">
                    Delivery
                  </td>
                  <td className="num px-4 py-2 text-right">{kes(order.delivery_fee)}</td>
                </tr>
                <tr>
                  <td colSpan={3} className="px-4 py-2 text-right font-medium">
                    Total
                  </td>
                  <td className="num px-4 py-2 text-right font-medium">{kes(order.total_amount)}</td>
                </tr>
              </tfoot>
            </table>
          </div>

          {!["draft", "submitted", "cancelled"].includes(order.status) && (
            <ul className="grid gap-2 sm:grid-cols-2">
              {order.allocations.map((a) => (
                <li
                  key={a.id}
                  className="flex items-center justify-between rounded border border-line bg-paper-raised px-4 py-2.5 text-sm"
                >
                  <span>{a.supplier_name}</span>
                  <span className="text-ink-soft">{ALLOC_LABEL[a.status] ?? a.status}</span>
                </li>
              ))}
            </ul>
          )}

          <div className="flex flex-wrap items-center gap-3">
            {order.status === "delivered" && (
              <button
                disabled={busy}
                onClick={() => act(() => confirmReceipt(order.id))}
                className="rounded bg-leaf-600 px-4 py-2 text-sm font-medium text-white hover:bg-leaf-700"
              >
                I've received this order
              </button>
            )}
            {(order.status === "draft" || order.status === "submitted") && (
              <button
                disabled={busy}
                onClick={() =>
                  confirm("Cancel this order? Reserved stock is released.") && act(() => cancelOrder(order.id))
                }
                className="rounded border border-line px-4 py-2 text-sm text-berry-500 hover:bg-berry-100"
              >
                Cancel order
              </button>
            )}
            {invoice && (
              <span className="num text-sm text-ink-soft">
                Invoice {invoice.invoice_number} · {invoice.payment_status}
              </span>
            )}
            {!["draft", "submitted", "cancelled"].includes(order.status) && !invoice && (
              <span className="text-sm text-ink-faint">Invoice is being prepared.</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function OrdersList() {
  const params = useSearchParams();
  const orders = useAsync(async () => (await listOrders()).results);
  const invoices = useAsync(async () => (await listInvoices()).results);
  const [openId, setOpenId] = useState(params.get("focus"));
  const list = orders.data ?? [];

  const reload = () => {
    orders.reload();
    invoices.reload();
  };
  return (
    <>
      <h1 className="font-display text-display-md font-medium">Orders</h1>
      <p className="mt-2 text-ink-soft">Every purchase, from approval to delivery.</p>
      {orders.loading && <Loading />}
      {orders.error && (
        <div className="mt-4">
          <ErrorNote>{orders.error}</ErrorNote>
        </div>
      )}
      {!orders.loading && list.length === 0 && !orders.error && (
        <div className="mt-6">
          <EmptyState title="No orders yet">
            <Link href="/buyer/compare" className="text-leaf-700 underline">
              Place your first order.
            </Link>
          </EmptyState>
        </div>
      )}
      {list.length > 0 && (
        <div className="mt-8 divide-y divide-line rounded border border-line bg-paper-raised">
          {list.map((o) => (
            <OrderCard
              key={o.id}
              order={o}
              invoice={invoices.data?.find((i) => i.order === o.id)}
              open={openId === o.id}
              onToggle={() => setOpenId(openId === o.id ? null : o.id)}
              reload={reload}
            />
          ))}
        </div>
      )}
    </>
  );
}

export default function OrdersPage() {
  return (
    <Suspense fallback={<Loading />}>
      <OrdersList />
    </Suspense>
  );
}
