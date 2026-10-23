"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { EmptyState, ErrorNote, Loading } from "@/components/ui";
import { checkoutCart, getOpenCart, removeCartItem } from "@/lib/api";
import { guessEmoji } from "@/lib/emoji";
import { kes, num, qty } from "@/lib/format";
import { useAsync } from "@/lib/useAsync";

export default function CartPage() {
  const router = useRouter();
  const cart = useAsync(getOpenCart);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const c = cart.data;
  const items = c?.items ?? [];

  const bySupplier = items.reduce((acc, i) => ((acc[i.supplier_id] ||= []).push(i), acc), {});
  const total = num(c?.totals.total);

  async function remove(itemId) {
    if (!c) return;
    setError(null);
    try {
      cart.setData(await removeCartItem(c.id, itemId));
      await cart.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not remove item.");
    }
  }

  async function checkout() {
    if (!c) return;
    setBusy(true);
    setError(null);
    try {
      const order = await checkoutCart(c.id);
      router.push(`/buyer/orders?focus=${order.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Checkout failed.");
      setBusy(false);
      cart.reload();
    }
  }

  return (
    <>
      <h1 className="font-display text-display-md font-medium">Your cart</h1>
      {cart.loading && <Loading />}
      {cart.error && (
        <div className="mt-4">
          <ErrorNote>{cart.error}</ErrorNote>
        </div>
      )}
      {!cart.loading && items.length === 0 && (
        <div className="mt-6">
          <EmptyState title="Your cart is empty">
            <Link href="/buyer/compare" className="text-leaf-700 underline">
              Compare suppliers to add something.
            </Link>
          </EmptyState>
        </div>
      )}

      {items.length > 0 && c && (
        <div className="mt-8 grid gap-8 lg:grid-cols-[1fr_340px]">
          <div className="space-y-6">
            {Object.values(bySupplier).map((group) => (
              <div key={group[0].supplier_id} className="overflow-hidden rounded border border-line bg-paper-raised">
                <div className="flex items-center justify-between border-b border-line bg-paper-dim px-4 py-2.5">
                  <p className="text-sm font-medium">{group[0].supplier_name}</p>
                  <p className="num text-xs text-ink-faint">Delivery {kes(group[0].delivery_cost)}</p>
                </div>
                <ul className="divide-y divide-line">
                  {group.map((i) => (
                    <li key={i.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
                      <div className="flex items-center gap-3">
                        <span className="text-xl" aria-hidden>
                          {guessEmoji(i.product_name)}
                        </span>
                        <div>
                          <p className="text-sm font-medium">{i.product_name}</p>
                          <p className="text-xs text-ink-faint">
                            {qty(i.quantity)} {i.unit} × {kes(i.locked_unit_price)}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        <span className="num text-sm font-medium">{kes(i.line_total)}</span>
                        <button onClick={() => remove(i.id)} className="text-xs text-berry-500 hover:underline">
                          Remove
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          <aside className="h-fit rounded border border-line bg-paper-raised p-5">
            <p className="font-display text-lg font-medium">Order summary</p>
            <dl className="mt-4 space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-ink-faint">Subtotal</dt>
                <dd className="num">{kes(c.totals.subtotal)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-ink-faint">
                  Delivery ({Object.keys(bySupplier).length} supplier{Object.keys(bySupplier).length > 1 ? "s" : ""})
                </dt>
                <dd className="num">{kes(c.totals.delivery_total)}</dd>
              </div>
              <div className="flex justify-between border-t border-line pt-2 font-medium">
                <dt>Total</dt>
                <dd className="num">{kes(c.totals.total)}</dd>
              </div>
            </dl>
            {total >= 20000 && (
              <p className="mt-4 rounded bg-ember-100 px-3 py-2 text-xs text-ember-700">
                Orders of KSh 20,000 or more need approval before you can pay. We'll route it to the right approver.
              </p>
            )}
            {error && (
              <div className="mt-4">
                <ErrorNote>{error}</ErrorNote>
              </div>
            )}
            <button
              onClick={checkout}
              disabled={busy}
              className="mt-5 w-full rounded bg-ember-600 py-2.5 text-sm font-medium text-white hover:bg-ember-700 disabled:opacity-60"
            >
              {busy ? "Placing order…" : "Place order"}
            </button>
            <p className="mt-3 text-xs text-ink-faint">
              You pay in the next step. Prices are confirmed against current supplier stock at checkout.
            </p>
          </aside>
        </div>
      )}
    </>
  );
}
