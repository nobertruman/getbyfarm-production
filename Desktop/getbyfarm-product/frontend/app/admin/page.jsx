"use client";

import { useState } from "react";
import { ErrorNote, Loading, StatBlock } from "@/components/ui";
import { getAdminOverview, listAdminSuppliers, supplierAction } from "@/lib/api";
import { kes, shortDate } from "@/lib/format";
import { STATUS_LABEL } from "@/lib/status";
import { useAsync } from "@/lib/useAsync";

const TABS = [
  ["pending", "New"],
  ["under_review", "In review"],
  ["verified", "Verified"],
  ["suspended", "Suspended"],
];
const ACTIONS = {
  pending: [
    { action: "review", label: "Start review", tone: "bg-ink text-white hover:bg-leaf-700" },
    { action: "reject", label: "Reject", tone: "border border-line text-berry-500 hover:bg-berry-100" },
  ],
  under_review: [
    { action: "verify", label: "Verify supplier", tone: "bg-leaf-600 text-white hover:bg-leaf-700" },
    { action: "reject", label: "Reject", tone: "border border-line text-berry-500 hover:bg-berry-100" },
  ],
  verified: [{ action: "suspend", label: "Suspend", tone: "border border-line text-berry-500 hover:bg-berry-100" }],
  suspended: [{ action: "verify", label: "Reinstate", tone: "bg-leaf-600 text-white hover:bg-leaf-700" }],
};

function SupplierRow({ s, tab, reload }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  async function run(action) {
    if (
      (action === "reject" || action === "suspend") &&
      !confirm(`${action === "reject" ? "Reject" : "Suspend"} ${s.business_name}?`)
    )
      return;
    setBusy(true);
    setError(null);
    try {
      await supplierAction(s.id, action);
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed.");
      setBusy(false);
    }
  }
  return (
    <li className="flex flex-wrap items-center justify-between gap-3 p-4">
      <div>
        <p className="font-medium">{s.business_name}</p>
        <p className="text-sm text-ink-soft">
          {s.operating_location || "No location given"} · applied {shortDate(s.created_at)}
        </p>
        {(s.kra_pin || s.registration_number) && (
          <p className="text-xs text-ink-faint">
            KRA PIN {s.kra_pin || "—"} · Reg. {s.registration_number || "—"}
          </p>
        )}
        {error && <p className="mt-1 text-xs text-berry-500">{error}</p>}
      </div>
      <div className="flex gap-2">
        {ACTIONS[tab]?.map((a) => (
          <button
            key={a.action}
            disabled={busy}
            onClick={() => run(a.action)}
            className={`rounded px-3 py-1.5 text-xs font-medium disabled:opacity-60 ${a.tone}`}
          >
            {a.label}
          </button>
        ))}
      </div>
    </li>
  );
}

export default function AdminDashboard() {
  const overview = useAsync(getAdminOverview);
  const [tab, setTab] = useState("pending");
  const suppliers = useAsync(async () => (await listAdminSuppliers(tab)).results, [tab]);
  const byStatus = Object.entries(overview.data?.orders_by_status ?? {});
  const max = Math.max(1, ...byStatus.map(([, v]) => v));
  const reload = () => {
    suppliers.reload();
    overview.reload();
  };

  return (
    <>
      <h1 className="font-display text-display-md font-medium">Platform overview</h1>
      {overview.error && (
        <div className="mt-4">
          <ErrorNote>{overview.error}</ErrorNote>
        </div>
      )}
      <div className="mt-8 grid gap-4 rounded border border-line bg-paper-raised p-6 sm:grid-cols-4">
        <StatBlock label="Sales volume (30 days)" value={kes(overview.data?.gmv_last_30_days)} tone="positive" />
        <StatBlock label="Total orders" value={String(overview.data?.total_orders ?? 0)} />
        <StatBlock
          label="Buyers / verified suppliers"
          value={`${overview.data?.buyers ?? 0} / ${overview.data?.active_suppliers ?? 0}`}
        />
        <StatBlock
          label="Failed payments (30 days)"
          value={String(overview.data?.failed_payments_30d ?? 0)}
          tone={overview.data?.failed_payments_30d ? "warning" : "default"}
        />
      </div>

      <div className="mt-10 grid gap-8 lg:grid-cols-[1fr_380px]">
        <section>
          <h2 className="font-display text-lg font-medium">Supplier verification</h2>
          <div className="mt-3 flex flex-wrap gap-1" role="tablist">
            {TABS.map(([t, label]) => (
              <button
                key={t}
                role="tab"
                aria-selected={tab === t}
                onClick={() => setTab(t)}
                className={`rounded-pill px-3 py-1.5 text-sm ${tab === t ? "bg-ink text-white" : "text-ink-soft hover:bg-paper-dim"}`}
              >
                {label}
              </button>
            ))}
          </div>
          {suppliers.loading && <Loading />}
          {suppliers.error && (
            <div className="mt-3">
              <ErrorNote>{suppliers.error}</ErrorNote>
            </div>
          )}
          {!suppliers.loading && (suppliers.data ?? []).length === 0 && (
            <p className="mt-4 rounded border border-line bg-paper-raised p-6 text-sm text-ink-faint">
              Nobody here right now.
            </p>
          )}
          <ul className="mt-3 divide-y divide-line rounded border border-line bg-paper-raised empty:hidden">
            {(suppliers.data ?? []).map((s) => (
              <SupplierRow key={s.id} s={s} tab={tab} reload={reload} />
            ))}
          </ul>
          <p className="mt-3 text-xs text-ink-faint">
            Verification is a manual review of the business's details and documents. Newly verified suppliers start with
            a neutral reliability rating until they build a delivery history.
          </p>
        </section>

        <aside>
          <h2 className="font-display text-lg font-medium">Orders by status</h2>
          <div className="mt-3 space-y-3 rounded border border-line bg-paper-raised p-5">
            {byStatus.length === 0 && <p className="text-sm text-ink-faint">No orders yet.</p>}
            {byStatus.map(([s, n]) => (
              <div key={s} className="flex items-center gap-3">
                <span className="w-36 shrink-0 text-sm text-ink-faint">{STATUS_LABEL[s] ?? s}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-pill bg-paper-dim">
                  <div className="h-full rounded-pill bg-leaf-600" style={{ width: `${(n / max) * 100}%` }} />
                </div>
                <span className="num w-8 text-right text-sm">{n}</span>
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs text-ink-faint">
            Refunds, disputes and catalogue changes are handled in the{" "}
            <a href="/django-admin/" className="underline">
              Django admin console
            </a>
            .
          </p>
        </aside>
      </div>
    </>
  );
}
