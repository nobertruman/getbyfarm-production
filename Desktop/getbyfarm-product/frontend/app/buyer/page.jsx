"use client";

import Link from "next/link";
import { useUser } from "@/components/Session";
import { EmptyState, ErrorNote, Loading, StatBlock, StatusPill } from "@/components/ui";
import { getBuyerDashboard, listOrders } from "@/lib/api";
import { kes, shortDate } from "@/lib/format";
import { useAsync } from "@/lib/useAsync";

export default function BuyerDashboard() {
  const user = useUser();
  const stats = useAsync(getBuyerDashboard);
  const orders = useAsync(async () => (await listOrders()).results);
  const list = orders.data ?? [];
  const attention = list.filter((o) => o.status === "draft" || o.status === "submitted" || o.status === "delivered");

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm text-ink-faint">
            {user.organization?.name} · {user.branch?.name}
          </p>
          <h1 className="mt-1 font-display text-display-md font-medium">Hello, {user.full_name.split(" ")[0]}.</h1>
        </div>
        <Link
          href="/buyer/compare"
          className="rounded bg-ember-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-ember-700"
        >
          Create purchase
        </Link>
      </div>

      {stats.error && (
        <div className="mt-6">
          <ErrorNote>{stats.error}</ErrorNote>
        </div>
      )}
      <div className="mt-8 grid gap-4 rounded border border-line bg-paper-raised p-6 sm:grid-cols-4">
        <StatBlock label="Spend this month" value={kes(stats.data?.monthly_spend)} />
        <StatBlock label="Orders this month" value={String(stats.data?.orders_this_month ?? 0)} />
        <StatBlock
          label="In progress"
          value={String((stats.data?.in_progress ?? 0) + (stats.data?.orders_in_transit ?? 0))}
          sublabel={stats.data?.orders_in_transit ? `${stats.data.orders_in_transit} in transit` : undefined}
        />
        <StatBlock
          label="Supplier reliability"
          tone="positive"
          value={stats.data?.supplier_performance_pct == null ? "—" : `${stats.data.supplier_performance_pct}%`}
          sublabel={
            stats.data?.supplier_performance_pct == null ? "After your first order" : "Average of your suppliers"
          }
        />
      </div>

      {orders.loading && <Loading />}
      {orders.error && (
        <div className="mt-6">
          <ErrorNote>{orders.error}</ErrorNote>
        </div>
      )}

      {attention.length > 0 && (
        <section className="mt-10">
          <h2 className="font-display text-lg font-medium">Needs your attention</h2>
          <ul className="mt-3 divide-y divide-line rounded border border-line bg-paper-raised">
            {attention.map((o) => (
              <li key={o.id}>
                <Link
                  href={`/buyer/orders?focus=${o.id}`}
                  className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 hover:bg-paper-dim"
                >
                  <span>
                    <span className="num text-sm">{o.order_number}</span>
                    <span className="ml-3 text-sm text-ink-soft">
                      {o.status === "draft"
                        ? "Waiting for approval"
                        : o.status === "submitted"
                          ? "Ready to pay"
                          : "Delivered, confirm receipt"}
                    </span>
                  </span>
                  <span className="num text-sm font-medium">{kes(o.total_amount)}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="mt-10">
        <div className="flex items-baseline justify-between">
          <h2 className="font-display text-lg font-medium">Recent orders</h2>
          {list.length > 0 && (
            <Link href="/buyer/orders" className="text-sm text-leaf-700 hover:underline">
              View all
            </Link>
          )}
        </div>
        {!orders.loading && list.length === 0 ? (
          <div className="mt-3">
            <EmptyState title="No orders yet">
              <Link href="/buyer/compare" className="text-leaf-700 underline">
                Compare suppliers and place your first order.
              </Link>
            </EmptyState>
          </div>
        ) : (
          <div className="mt-3 overflow-x-auto rounded border border-line bg-paper-raised">
            <table className="w-full min-w-[560px] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-ink-faint">
                  <th className="px-4 py-3 font-normal">Order</th>
                  <th className="px-4 py-3 font-normal">Placed</th>
                  <th className="px-4 py-3 font-normal">Total</th>
                  <th className="px-4 py-3 font-normal">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {list.slice(0, 5).map((o) => (
                  <tr key={o.id}>
                    <td className="px-4 py-3">
                      <Link href={`/buyer/orders?focus=${o.id}`} className="num text-leaf-700 hover:underline">
                        {o.order_number}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-ink-soft">{shortDate(o.created_at)}</td>
                    <td className="num px-4 py-3">{kes(o.total_amount)}</td>
                    <td className="px-4 py-3">
                      <StatusPill status={o.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
