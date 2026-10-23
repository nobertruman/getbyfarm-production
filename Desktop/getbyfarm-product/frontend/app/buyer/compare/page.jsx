"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { EmptyState, ErrorNote, Loading, VerifiedStamp } from "@/components/ui";
import { addCartItem, listProducts, recommend } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import { guessEmoji } from "@/lib/emoji";
import { kes, num } from "@/lib/format";
import { useAsync } from "@/lib/useAsync";

// Engine weights (backend/procurement/engine.py EngineWeights defaults), used only to draw the "fit" bars.
const FACTORS = [
  ["price", "Price", 0.4],
  ["delivery", "Delivery", 0.2],
  ["reliability", "Reliability", 0.25],
  ["quality", "Quality", 0.1],
  ["lead_time", "Speed", 0.05],
];

export default function ComparePage() {
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [productId, setProductId] = useState(null);
  const [quantity, setQuantity] = useState(10);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  const products = useAsync(async () => (await listProducts(debounced)).results, [debounced]);
  const list = products.data ?? [];
  const product = list.find((p) => p.id === productId) ?? null;

  const offers = useAsync(async () => {
    if (!productId || quantity <= 0) return null;
    try {
      return await recommend(productId, quantity);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) return "none";
      throw e;
    }
  }, [productId, quantity]);

  const [added, setAdded] = useState(null);
  const [addError, setAddError] = useState(null);

  async function add(o) {
    if (!o.supplier_price_id) return;
    setAddError(null);
    try {
      await addCartItem(o.supplier_price_id, quantity, o.explanation);
      setAdded(o.supplier_id);
      setTimeout(() => setAdded(null), 2500);
    } catch (e) {
      setAddError(e instanceof Error ? e.message : "Could not add to cart.");
    }
  }

  const rec = offers.data && offers.data !== "none" ? offers.data : null;

  return (
    <>
      <h1 className="font-display text-display-md font-medium">Compare & buy</h1>
      <p className="mt-2 max-w-prose text-ink-soft">
        Choose a product and quantity. We rank every verified supplier on landed cost, reliability, quality and lead
        time, and show our reasoning.
      </p>

      <div className="mt-8 grid gap-8 lg:grid-cols-[300px_1fr]">
        <aside>
          <label htmlFor="search" className="text-sm text-ink-soft">
            Find a product
          </label>
          <input
            id="search"
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="e.g. tomatoes, rice, oil"
            className="mt-1 w-full rounded border border-line bg-paper-raised px-3 py-2.5"
          />
          <div className="mt-3 max-h-[28rem] overflow-y-auto rounded border border-line bg-paper-raised">
            {products.loading && <Loading />}
            {products.error && (
              <div className="p-3">
                <ErrorNote>{products.error}</ErrorNote>
              </div>
            )}
            {!products.loading && list.length === 0 && !products.error && (
              <p className="p-4 text-sm text-ink-faint">No products match “{search}”.</p>
            )}
            <ul className="divide-y divide-line">
              {list.map((p) => (
                <li key={p.id}>
                  <button
                    onClick={() => setProductId(p.id)}
                    aria-pressed={p.id === productId}
                    className={`flex w-full items-center gap-3 px-4 py-3 text-left text-sm ${p.id === productId ? "bg-leaf-600 text-white" : "hover:bg-paper-dim"}`}
                  >
                    <span className="text-lg" aria-hidden>
                      {guessEmoji(p.name)}
                    </span>
                    <span>
                      <span className="block font-medium">{p.name}</span>
                      <span className={`block text-xs ${p.id === productId ? "text-white/70" : "text-ink-faint"}`}>
                        {p.category_name} · per {p.default_unit}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </aside>

        <section aria-live="polite">
          {!product ? (
            <EmptyState title="Pick a product to compare suppliers" />
          ) : (
            <>
              <div className="flex flex-wrap items-end justify-between gap-4 border-b border-line pb-4">
                <p className="font-display text-xl font-medium">
                  {guessEmoji(product.name)} {product.name}
                </p>
                <div>
                  <label htmlFor="qty" className="text-sm text-ink-soft">
                    Quantity ({product.default_unit})
                  </label>
                  <input
                    id="qty"
                    type="number"
                    min={1}
                    step="any"
                    value={quantity}
                    onChange={(e) => setQuantity(Number(e.target.value) || 0)}
                    className="num ml-2 w-24 rounded border border-line bg-paper-raised px-3 py-2"
                  />
                </div>
              </div>

              {offers.loading && <Loading label="Scoring supplier offers…" />}
              {offers.error && (
                <div className="mt-4">
                  <ErrorNote>{offers.error}</ErrorNote>
                </div>
              )}
              {addError && (
                <div className="mt-4">
                  <ErrorNote>{addError}</ErrorNote>
                </div>
              )}
              {offers.data === "none" && (
                <div className="mt-6">
                  <EmptyState title="No supplier lists this product yet">
                    Check back soon, or try a similar product.
                  </EmptyState>
                </div>
              )}
              {rec && rec.ranked_candidates.length === 0 && (
                <div className="mt-6">
                  <EmptyState title="No supplier can fill this quantity">Try a smaller quantity.</EmptyState>
                </div>
              )}

              {rec && rec.ranked_candidates.length > 0 && (
                <ul className="mt-6 space-y-4">
                  {rec.ranked_candidates.map((o, i) => (
                    <li
                      key={o.supplier_id}
                      className={`rounded border p-5 ${i === 0 ? "border-leaf-600 bg-leaf-50" : "border-line bg-paper-raised"}`}
                    >
                      <div className="flex flex-wrap items-start justify-between gap-4">
                        <div className="flex items-start gap-3">
                          <span className="num mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-line bg-paper text-xs text-ink-faint">
                            {i + 1}
                          </span>
                          <div>
                            <p className="flex flex-wrap items-center gap-1.5 font-medium">
                              {o.supplier_name}
                              <VerifiedStamp />
                              {i === 0 && (
                                <span className="rounded-pill bg-ember-100 px-2 py-0.5 text-xs font-medium text-ember-700">
                                  Best overall
                                </span>
                              )}
                            </p>
                            <p className="mt-1 max-w-prose text-sm text-ink-soft">{o.explanation}</p>
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="num font-display text-lg font-medium">{kes(o.total_landed_cost)}</p>
                          <p className="text-xs text-ink-faint">
                            {kes(o.unit_price)}/{product.default_unit} + {kes(o.delivery_cost)} delivery
                          </p>
                          <button
                            onClick={() => add(o)}
                            disabled={!o.supplier_price_id}
                            className={`mt-3 rounded px-4 py-2 text-sm font-medium ${i === 0 ? "bg-ember-600 text-white hover:bg-ember-700" : "border border-ink hover:bg-paper-dim"}`}
                          >
                            {added === o.supplier_id ? "Added to cart ✓" : "Add to cart"}
                          </button>
                        </div>
                      </div>
                      <div className="mt-4 grid grid-cols-5 gap-3 border-t border-line pt-4">
                        {FACTORS.map(([key, label, weight]) => {
                          const fit = Math.max(0, Math.min(100, (1 - num(o.component_breakdown[key]) / weight) * 100));
                          return (
                            <div key={key}>
                              <p className="text-[11px] text-ink-faint">{label}</p>
                              <div
                                className="mt-1 h-1.5 overflow-hidden rounded-pill bg-paper-dim"
                                role="img"
                                aria-label={`${label}: ${Math.round(fit)} out of 100`}
                              >
                                <div className="h-full rounded-pill bg-leaf-600" style={{ width: `${fit}%` }} />
                              </div>
                            </div>
                          );
                        })}
                      </div>
                      <p className="mt-3 text-xs text-ink-faint">
                        {num(o.reliability_score)}% reliability · {num(o.quality_rating)}/5 quality ·{" "}
                        {num(o.lead_time_days)} day lead time · longer bar = better fit
                      </p>
                    </li>
                  ))}
                </ul>
              )}
              {rec && rec.excluded.length > 0 && (
                <div className="mt-6 rounded border border-line p-4 text-sm text-ink-soft">
                  <p className="font-medium">Not available for this quantity</p>
                  <ul className="mt-1 list-disc pl-5">
                    {rec.excluded.map((e) => (
                      <li key={e.supplier_id}>
                        {e.supplier_name}: {e.reason}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <p className="mt-6">
                <Link href="/buyer/cart" className="text-sm text-leaf-700 underline">
                  Go to cart
                </Link>
              </p>
            </>
          )}
        </section>
      </div>
    </>
  );
}
