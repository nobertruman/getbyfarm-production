import Link from "next/link";
import { Logo } from "@/components/Logo";
import { BrandWord, TriBar } from "@/components/Brand";
import { VerifiedStamp } from "@/components/ui";
import { BRAND } from "@/lib/brand";

// Illustrative figures for the hero demo only (labelled as an example on the page).
const EXAMPLE = [
  { name: "Supplier A", note: "94% reliability · 1 day lead time", total: 3980, best: true },
  { name: "Supplier B", note: "88% reliability · 1 day lead time", total: 3960, best: false },
  { name: "Supplier C", note: "78% reliability · 2 day lead time", total: 3950, best: false },
];

const CATEGORIES = ["Fresh produce", "Meat & protein", "Dry foods", "Beverages", "Kitchen supplies", "Cleaning", "Packaging"];

// Accent cycle mirrors the wordmark: green, orange, green, orange…
const ACCENT = [
  { bar: "bg-leaf-600", num: "bg-leaf-600 text-white" },
  { bar: "bg-ember-500", num: "bg-ember-600 text-white" },
  { bar: "bg-leaf-600", num: "bg-leaf-600 text-white" },
  { bar: "bg-ember-500", num: "bg-ember-600 text-white" },
];

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-paper">
      <header className="sticky top-0 z-20 bg-paper-raised/95 backdrop-blur">
        <TriBar className="h-1" />
        <div className="border-b border-line">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
            <Link href="/" aria-label="GetbyFarm home">
              <Logo height={40} />
            </Link>
            <nav className="hidden items-center gap-7 text-sm text-ink-soft md:flex" aria-label="Sections">
              <a href="#how-it-works" className="hover:text-leaf-700">How it works</a>
              <a href="#categories" className="hover:text-leaf-700">Categories</a>
              <a href="#suppliers" className="hover:text-leaf-700">For suppliers</a>
            </nav>
            <div className="flex items-center gap-3">
              <Link href="/login" className="text-sm font-medium text-leaf-700 hover:underline">Log in</Link>
              <Link href="/register" className="rounded bg-ember-600 px-4 py-2 text-sm font-medium text-white hover:bg-ember-700">
                Start buying
              </Link>
            </div>
          </div>
        </div>
      </header>

      {/* ---------------------------------------------------------------- hero */}
      <section
        className="relative overflow-hidden"
        style={{
          backgroundImage:
            "radial-gradient(640px circle at 92% 4%, rgba(251,60,6,0.13), transparent 62%), radial-gradient(560px circle at 0% 100%, rgba(12,133,13,0.14), transparent 60%)",
        }}
      >
        <div className="mx-auto grid max-w-6xl gap-12 px-4 py-16 sm:px-6 md:grid-cols-2 md:items-center md:py-24">
          <div className="animate-riseIn">
            <p className="font-script text-3xl text-ember-700">{BRAND.tagline}.</p>
            <h1 className="mt-2 font-display text-display-lg font-medium text-ink md:text-display-xl">
              Smarter sourcing starts with <BrandWord />.
            </h1>
            <p className="mt-6 max-w-prose text-lg text-ink-soft">
              Buy wholesale food and hospitality supplies at better prices. Compare verified suppliers, pay with M-Pesa, and keep
              every branch stocked, from one procurement desk built for Kenyan restaurants, hotels and caterers.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-4">
              <Link href="/register?type=buyer" className="rounded bg-ember-600 px-6 py-3 font-medium text-white shadow-[0_6px_0_0_#7A1F00] transition hover:translate-y-[2px] hover:bg-ember-700 hover:shadow-[0_4px_0_0_#7A1F00]">
                Start buying
              </Link>
              <Link href="/register?type=supplier" className="rounded border-2 border-leaf-600 px-6 py-3 font-medium text-leaf-700 hover:bg-leaf-50">
                Become a supplier
              </Link>
            </div>
            <ul className="mt-8 flex flex-wrap gap-2 text-sm" aria-label="How it works in four words">
              {["Compare", "Buy", "Save", "Track"].map((w, i) => (
                <li key={w} className={`rounded-pill px-3 py-1 font-medium ${i % 2 ? "bg-ember-100 text-ember-700" : "bg-leaf-100 text-leaf-800"}`}>
                  {w}
                </li>
              ))}
            </ul>
          </div>

          <div className="animate-riseIn overflow-hidden rounded-lg border border-line bg-paper-raised shadow-[0_20px_50px_-24px_rgba(11,59,26,0.45)]" aria-label="Example supplier comparison">
            <TriBar className="h-1.5" />
            <div className="p-5">
              <div className="flex items-center justify-between border-b border-line pb-3">
                <div>
                  <p className="text-xs text-ink-faint">Example comparison, illustrative figures</p>
                  <p className="font-display text-lg font-medium">Tomatoes, 40 kg</p>
                </div>
                <span className="rounded-pill bg-ember-600 px-3 py-1 text-xs font-medium text-white">Best overall</span>
              </div>
              <ul className="mt-4 space-y-2">
                {EXAMPLE.map((o, i) => (
                  <li
                    key={o.name}
                    className={`flex items-center justify-between rounded border-l-4 px-3 py-2.5 ${o.best ? "border-leaf-600 bg-leaf-50" : "border-transparent"}`}
                  >
                    <div className="flex items-center gap-3">
                      <span className={`num flex h-6 w-6 items-center justify-center rounded-full text-xs ${o.best ? "bg-leaf-600 text-white" : "border border-line text-ink-faint"}`}>
                        {i + 1}
                      </span>
                      <div>
                        <p className="flex items-center gap-1.5 text-sm font-medium">{o.name}<VerifiedStamp /></p>
                        <p className="text-xs text-ink-faint">{o.note}</p>
                      </div>
                    </div>
                    <p className="num text-sm font-medium">KSh {o.total.toLocaleString()}</p>
                  </li>
                ))}
              </ul>
              <p className="mt-4 border-t border-line pt-3 text-xs text-ink-faint">
                Supplier A is recommended even though it costs a little more: it delivers on time far more often. GetbyFarm weighs
                reliability, delivery cost, quality and lead time, not just price, and shows you why.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* -------------------------------------------------------- how it works */}
      <section id="how-it-works" className="border-y border-line bg-paper-raised">
        <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
          <h2 className="max-w-md font-display text-display-md font-medium">From shopping list to delivered stock, in four steps.</h2>
          <div className="mt-10 grid gap-8 md:grid-cols-4">
            {[
              ["Compare", "See every verified supplier's price, delivery cost and track record side by side."],
              ["Order", "Add the recommended supplier, or pick another. One cart can span several suppliers."],
              ["Pay", "Larger orders go through your approval chain. Pay with an M-Pesa prompt on your phone."],
              ["Track", "Follow each supplier from accepted to dispatched to delivered, and get your invoice."],
            ].map(([t, b], i) => (
              <div key={t}>
                <div className={`h-1 w-full ${ACCENT[i].bar}`} />
                <span className={`num mt-4 flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium ${ACCENT[i].num}`}>{i + 1}</span>
                <p className="mt-3 font-display text-lg font-medium">{t}</p>
                <p className="mt-2 text-sm text-ink-soft">{b}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ----------------------------------------------------------- categories */}
      <section id="categories" className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
        <h2 className="font-display text-display-md font-medium">Everything the kitchen and bar need.</h2>
        <ul className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {CATEGORIES.map((c, i) => (
            <li key={c} className={`rounded border border-line border-t-4 bg-paper-raised p-5 text-sm font-medium ${i % 3 === 1 ? "border-t-ember-500" : "border-t-leaf-600"}`}>
              {c}
            </li>
          ))}
          <li className="rounded border border-dashed border-leaf-300 p-5 text-sm text-ink-faint">More added as suppliers join</li>
        </ul>
      </section>

      {/* ------------------------------------------------- never just cheapest */}
      <section className="relative overflow-hidden bg-leaf-900 text-paper" style={{ backgroundImage: "radial-gradient(520px circle at 95% 0%, rgba(22,163,23,0.30), transparent 60%)" }}>
        <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
          <h2 className="max-w-lg font-display text-display-md font-medium">It never just picks the <span className="text-ember-300">cheapest</span> supplier.</h2>
          <p className="mt-4 max-w-prose text-paper/75">
            The cheapest quote isn't the cheapest purchase if it arrives late or short. Our procurement engine ranks suppliers on the real
            landed cost, plus reliability, quality and lead time, and every recommendation comes with its reasoning, so you stay in control.
          </p>
          <div className="mt-10 grid gap-6 md:grid-cols-3">
            {[
              ["Transparent ranking", "See the score breakdown for each supplier. Override the recommendation any time."],
              ["Approvals that fit your business", "Orders above KSh 20,000 route to the right approver before anyone is charged."],
              ["Every branch, one place", "Orders, invoices and spend, kept per branch under one business account."],
            ].map(([t, b]) => (
              <div key={t} className="rounded border border-paper/15 border-t-4 border-t-ember-500 bg-paper/5 p-6">
                <p className="font-display font-medium">{t}</p>
                <p className="mt-2 text-sm text-paper/75">{b}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------- group buying */}
      <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
        <div className="rounded-lg border border-ember-500/30 bg-ember-50 p-6 md:flex md:items-center md:justify-between md:gap-8">
          <div>
            <p className="inline-block rounded-pill bg-ember-600 px-3 py-1 text-xs font-medium text-white">Coming soon</p>
            <h2 className="mt-3 font-display text-2xl font-medium">Group buying</h2>
            <p className="mt-2 max-w-prose text-ink-soft">
              Pool demand with other businesses to unlock bulk prices. We're building this next; today, each order is priced at the supplier's listed rate.
            </p>
          </div>
          <p className="mt-4 font-script text-3xl text-ember-700 md:mt-0">Better together.</p>
        </div>
      </section>

      {/* ------------------------------------------------------------ suppliers */}
      <section id="suppliers" className="border-y border-line bg-leaf-50">
        <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 md:grid md:grid-cols-2 md:items-center md:gap-10">
          <div>
            <h2 className="font-display text-display-md font-medium">Built for suppliers too.</h2>
            <p className="mt-4 max-w-prose text-ink-soft">
              List your products, set your prices and stock, and receive paid orders from restaurants and hotels, with the buyer's delivery
              address and a clear queue to accept, prepare and dispatch. New suppliers are verified by our team before going live.
            </p>
            <Link href="/register?type=supplier" className="mt-6 inline-block rounded bg-leaf-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-leaf-700">
              Become a supplier
            </Link>
          </div>
        </div>
      </section>

      {/* --------------------------------------------------------------- CTA band */}
      <section className="bg-ember-500">
        <div className="mx-auto max-w-6xl px-4 py-14 text-center text-white sm:px-6">
          <h2 className="font-display text-display-md font-semibold">Ready to stock smarter this week?</h2>
          <div className="mt-6 flex flex-wrap justify-center gap-4">
            <Link href="/register?type=buyer" className="rounded bg-white px-6 py-3 font-medium text-ember-700 hover:bg-ember-50">Start buying</Link>
            <Link href="/register?type=supplier" className="rounded border-2 border-white px-6 py-3 font-medium text-white hover:bg-ember-600">Become a supplier</Link>
          </div>
        </div>
      </section>

      {/* ----------------------------------------------------------------- footer */}
      <footer className="bg-leaf-900 text-paper">
        <TriBar className="h-1.5" />
        <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-10 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <div>
            <Logo variant="light" height={40} />
            <p className="mt-2 font-script text-2xl text-ember-300">{BRAND.tagline}.</p>
          </div>
          <p className="text-sm text-paper/65">Nairobi, Kenya.</p>
        </div>
      </footer>
    </main>
  );
}
