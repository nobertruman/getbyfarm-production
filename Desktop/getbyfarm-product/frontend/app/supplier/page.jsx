"use client";

import { useState } from "react";
import { useUser } from "@/components/Session";
import { EmptyState, ErrorNote, Loading, StatBlock, VerifiedStamp } from "@/components/ui";
import {
  advanceAllocation,
  createPrice,
  deletePrice,
  getSupplierDashboard,
  listAllocations,
  listMyPrices,
  listProducts,
  updatePrice,
} from "@/lib/api";
import { kes, qty, shortDate } from "@/lib/format";
import { useAsync } from "@/lib/useAsync";

const NEXT = {
  new: { to: "accepted", label: "Accept order" },
  accepted: { to: "preparing", label: "Start preparing" },
  preparing: { to: "ready", label: "Mark ready" },
  ready: { to: "dispatched", label: "Dispatch" },
  dispatched: { to: "delivered", label: "Mark delivered" },
};
const STATE_LABEL = {
  new: "New",
  accepted: "Accepted",
  preparing: "Preparing",
  ready: "Ready",
  dispatched: "Dispatched",
  delivered: "Delivered",
  cancelled: "Cancelled",
};

const BANNER = {
  pending:
    "Your account is waiting for review by the GetbyFarm team. You can set up your listings now; buyers will see them once you're verified.",
  under_review: "Your account is being reviewed. Buyers will see your listings once you're verified.",
  rejected: "Your application wasn't approved. Please contact GetbyFarm support.",
  suspended: "Your account is suspended and your listings are hidden from buyers. Please contact GetbyFarm support.",
};

function AllocationCard({ a, reload }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const next = NEXT[a.status];
  async function go() {
    if (!next) return;
    setBusy(true);
    setError(null);
    try {
      await advanceAllocation(a.id, next.to);
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update.");
      setBusy(false);
    }
  }
  return (
    <li className="rounded border border-line bg-paper-raised p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="num text-xs text-ink-faint">
            {a.order_number} · {shortDate(a.placed_at)}
          </p>
          <p className="mt-1 font-medium">{a.buyer}</p>
          <p className="text-sm text-ink-soft">
            Deliver to: {a.delivery_address || "address not provided; contact the buyer"}
          </p>
        </div>
        <div className="text-right">
          <span className="rounded-pill bg-paper-dim px-2.5 py-1 text-xs font-medium">
            {STATE_LABEL[a.status] ?? a.status}
          </span>
          <p className="num mt-2 font-medium">{kes(a.subtotal)}</p>
        </div>
      </div>
      <ul className="mt-3 divide-y divide-line border-t border-line text-sm">
        {a.items.map((i, n) => (
          <li key={n} className="flex justify-between py-1.5">
            <span>{i.product_name}</span>
            <span className="num text-ink-soft">
              {qty(i.quantity)} {i.unit} × {kes(i.unit_price)}
            </span>
          </li>
        ))}
      </ul>
      {error && (
        <div className="mt-3">
          <ErrorNote>{error}</ErrorNote>
        </div>
      )}
      {next && (
        <button
          disabled={busy}
          onClick={go}
          className="mt-3 rounded bg-leaf-600 px-4 py-2 text-sm font-medium text-white hover:bg-leaf-700 disabled:opacity-60"
        >
          {busy ? "Updating…" : next.label}
        </button>
      )}
    </li>
  );
}

function ListingRow({ p, reload }) {
  const [f, setF] = useState({
    unit_price: p.unit_price,
    stock_quantity: p.stock_quantity,
    minimum_order_quantity: p.minimum_order_quantity,
    delivery_cost_flat: p.delivery_cost_flat,
  });
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);
  const dirty = Object.keys(f).some((k) => Number(f[k]) !== Number(p[k]));
  const cell = "num w-24 rounded border border-line bg-paper px-2 py-1.5 text-right";
  const set = (k) => (e) => {
    setSaved(false);
    setF({ ...f, [k]: e.target.value });
  };
  async function save() {
    setError(null);
    try {
      await updatePrice(p.id, f);
      setSaved(true);
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save.");
    }
  }
  async function remove() {
    if (!confirm(`Stop selling ${p.product_name}? Existing orders are not affected.`)) return;
    try {
      await deletePrice(p.id);
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not remove.");
    }
  }
  return (
    <tr className="align-top">
      <td className="px-3 py-3">
        <p className="font-medium">{p.product_name}</p>
        <p className="text-xs text-ink-faint">per {p.unit}</p>
        {error && <p className="mt-1 max-w-[16rem] text-xs text-berry-500">{error}</p>}
      </td>
      <td className="px-2 py-3">
        <input
          aria-label="Price"
          value={f.unit_price}
          onChange={set("unit_price")}
          className={cell}
          inputMode="decimal"
        />
      </td>
      <td className="px-2 py-3">
        <input
          aria-label="Stock"
          value={f.stock_quantity}
          onChange={set("stock_quantity")}
          className={cell}
          inputMode="decimal"
        />
      </td>
      <td className="px-2 py-3">
        <input
          aria-label="Minimum order"
          value={f.minimum_order_quantity}
          onChange={set("minimum_order_quantity")}
          className={cell}
          inputMode="decimal"
        />
      </td>
      <td className="px-2 py-3">
        <input
          aria-label="Delivery cost"
          value={f.delivery_cost_flat}
          onChange={set("delivery_cost_flat")}
          className={cell}
          inputMode="decimal"
        />
      </td>
      <td className="whitespace-nowrap px-3 py-3 text-right">
        <button
          disabled={!dirty}
          onClick={save}
          className="rounded bg-leaf-600 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40"
        >
          {saved ? "Saved ✓" : "Save"}
        </button>
        <button onClick={remove} className="ml-3 text-xs text-berry-500 hover:underline">
          Remove
        </button>
      </td>
    </tr>
  );
}

function AddListing({ existing, onAdded }) {
  const catalogue = useAsync(async () => (await listProducts()).results);
  const [f, setF] = useState({
    product: "",
    unit_price: "",
    stock_quantity: "",
    minimum_order_quantity: "1",
    delivery_cost_flat: "0",
    lead_time_days: "1",
  });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const options = (catalogue.data ?? []).filter((p) => !existing.includes(p.id));
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const box = "mt-1 w-full rounded border border-line bg-paper px-3 py-2";

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await createPrice(f);
      setF({ ...f, product: "", unit_price: "", stock_quantity: "" });
      onAdded();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add listing.");
    }
    setBusy(false);
  }
  return (
    <form onSubmit={submit} className="rounded border border-line bg-paper-raised p-4">
      <p className="font-medium">Add a product to sell</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        <div className="sm:col-span-3">
          <label className="text-sm text-ink-soft" htmlFor="prod">
            Product
          </label>
          <select id="prod" required value={f.product} onChange={set("product")} className={box}>
            <option value="">Choose from the catalogue…</option>
            {options.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} (per {p.default_unit})
              </option>
            ))}
          </select>
          <p className="mt-1 text-xs text-ink-faint">
            Can't find it? Ask GetbyFarm support to add it to the catalogue.
          </p>
        </div>
        <div>
          <label className="text-sm text-ink-soft" htmlFor="pr">
            Price (KSh)
          </label>
          <input
            id="pr"
            required
            inputMode="decimal"
            value={f.unit_price}
            onChange={set("unit_price")}
            className={box}
          />
        </div>
        <div>
          <label className="text-sm text-ink-soft" htmlFor="st">
            Stock
          </label>
          <input
            id="st"
            required
            inputMode="decimal"
            value={f.stock_quantity}
            onChange={set("stock_quantity")}
            className={box}
          />
        </div>
        <div>
          <label className="text-sm text-ink-soft" htmlFor="mo">
            Minimum order
          </label>
          <input
            id="mo"
            required
            inputMode="decimal"
            value={f.minimum_order_quantity}
            onChange={set("minimum_order_quantity")}
            className={box}
          />
        </div>
        <div>
          <label className="text-sm text-ink-soft" htmlFor="dc">
            Delivery fee (KSh)
          </label>
          <input
            id="dc"
            required
            inputMode="decimal"
            value={f.delivery_cost_flat}
            onChange={set("delivery_cost_flat")}
            className={box}
          />
        </div>
        <div>
          <label className="text-sm text-ink-soft" htmlFor="lt">
            Lead time (days)
          </label>
          <input
            id="lt"
            required
            inputMode="decimal"
            value={f.lead_time_days}
            onChange={set("lead_time_days")}
            className={box}
          />
        </div>
      </div>
      {error && (
        <div className="mt-3">
          <ErrorNote>{error}</ErrorNote>
        </div>
      )}
      <button
        disabled={busy || !f.product}
        className="mt-4 rounded bg-ink px-4 py-2 text-sm font-medium text-white hover:bg-leaf-700 disabled:opacity-50"
      >
        {busy ? "Adding…" : "Add listing"}
      </button>
    </form>
  );
}

export default function SupplierDashboard() {
  const user = useUser();
  const stats = useAsync(getSupplierDashboard);
  const queue = useAsync(async () => (await listAllocations()).results);
  const prices = useAsync(async () => (await listMyPrices()).results);
  const status = user.supplier?.verification_status ?? "pending";
  const open = (queue.data ?? []).filter((a) => !["delivered", "cancelled"].includes(a.status));
  const done = (queue.data ?? []).filter((a) => ["delivered", "cancelled"].includes(a.status));
  const reloadAll = () => {
    queue.reload();
    stats.reload();
  };

  return (
    <>
      <div className="flex items-center gap-3">
        {status === "verified" && <VerifiedStamp size="md" />}
        <div>
          <p className="text-sm text-ink-faint">Supplier</p>
          <h1 className="font-display text-display-md font-medium">{user.supplier?.business_name}</h1>
        </div>
      </div>
      {status !== "verified" && (
        <p className="mt-6 rounded bg-ember-100 px-4 py-3 text-sm text-ember-700">{BANNER[status]}</p>
      )}

      <div className="mt-8 grid gap-4 rounded border border-line bg-paper-raised p-6 sm:grid-cols-4">
        <StatBlock label="Revenue (30 days)" value={kes(stats.data?.revenue_30d)} tone="positive" />
        <StatBlock label="Paid orders (30 days)" value={String(stats.data?.orders_30d ?? 0)} />
        <StatBlock label="Open orders" value={String(stats.data?.open_orders ?? 0)} />
        <StatBlock
          label="Fulfilment rate"
          value={stats.data?.fulfillment_rate_pct == null ? "—" : `${stats.data.fulfillment_rate_pct}%`}
          sublabel={stats.data?.fulfillment_rate_pct == null ? "After your first delivery" : undefined}
        />
      </div>

      <section className="mt-10">
        <h2 className="font-display text-lg font-medium">Orders to fulfil</h2>
        <p className="mt-1 text-sm text-ink-faint">Orders appear here once the buyer has paid.</p>
        {queue.loading && <Loading />}
        {queue.error && (
          <div className="mt-3">
            <ErrorNote>{queue.error}</ErrorNote>
          </div>
        )}
        {!queue.loading && open.length === 0 && (
          <div className="mt-3">
            <EmptyState title="No open orders right now" />
          </div>
        )}
        <ul className="mt-3 space-y-3">
          {open.map((a) => (
            <AllocationCard key={a.id} a={a} reload={reloadAll} />
          ))}
        </ul>
        {done.length > 0 && (
          <details className="mt-4">
            <summary className="cursor-pointer text-sm text-ink-soft">Completed orders ({done.length})</summary>
            <ul className="mt-3 space-y-3">
              {done.map((a) => (
                <AllocationCard key={a.id} a={a} reload={reloadAll} />
              ))}
            </ul>
          </details>
        )}
      </section>

      <section className="mt-12">
        <h2 className="font-display text-lg font-medium">Your products</h2>
        {prices.error && (
          <div className="mt-3">
            <ErrorNote>{prices.error}</ErrorNote>
          </div>
        )}
        {prices.loading && <Loading />}
        {(prices.data ?? []).length > 0 && (
          <div className="mt-3 overflow-x-auto rounded border border-line bg-paper-raised">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-ink-faint">
                  <th className="px-3 py-3 font-normal">Product</th>
                  <th className="px-2 py-3 text-right font-normal">Price (KSh)</th>
                  <th className="px-2 py-3 text-right font-normal">Stock</th>
                  <th className="px-2 py-3 text-right font-normal">Min. order</th>
                  <th className="px-2 py-3 text-right font-normal">Delivery (KSh)</th>
                  <th />
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {prices.data.map((p) => (
                  <ListingRow key={`${p.id}-${p.updated_at ?? ""}`} p={p} reload={prices.reload} />
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="mt-4">
          <AddListing existing={(prices.data ?? []).map((p) => p.product)} onAdded={prices.reload} />
        </div>
      </section>
    </>
  );
}
