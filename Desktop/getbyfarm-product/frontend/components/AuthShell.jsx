import Link from "next/link";
import { Logo } from "./Logo";
import { TriBar } from "./Brand";
import { BRAND } from "@/lib/brand";

const POINTS = [
  "Compare verified suppliers side by side",
  "Pay with an M-Pesa prompt on your phone",
  "Track every delivery to your door",
];

/** Two-panel layout for login/register: a deep-green brand panel (md+) beside the form. */
export function AuthShell({ title, children, footer }) {
  return (
    <div className="grid min-h-screen md:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      <aside
        className="relative hidden overflow-hidden bg-leaf-900 p-10 text-paper md:flex md:flex-col md:justify-between"
        // Green glows only: orange light on deep green mixes to muddy brown, so orange stays as crisp accents.
        style={{
          backgroundImage:
            "radial-gradient(520px circle at 85% 8%, rgba(22,163,23,0.30), transparent 60%), radial-gradient(480px circle at 0% 100%, rgba(22,163,23,0.22), transparent 60%)",
        }}
      >
        <Link href="/" aria-label="GetbyFarm home" className="inline-block">
          <Logo variant="full-light" height={78} />
        </Link>
        <div>
          <p className="font-script text-4xl leading-tight text-ember-300">{BRAND.tagline}.</p>
          <h2 className="mt-3 max-w-sm font-display text-3xl font-medium leading-tight">
            Wholesale sourcing for kitchens that care what's on the plate.
          </h2>
          <ul className="mt-8 space-y-3">
            {POINTS.map((p) => (
              <li key={p} className="flex items-start gap-3 text-paper/85">
                <span className="mt-1 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-ember-500 text-xs font-bold text-white" aria-hidden>
                  ✓
                </span>
                {p}
              </li>
            ))}
          </ul>
        </div>
        <p className="text-sm text-paper/60">Nairobi, Kenya.</p>
        <div className="absolute inset-x-0 bottom-0"><TriBar className="h-1.5" /></div>
      </aside>

      <main className="flex items-center justify-center bg-paper px-6 py-12">
        <div className="w-full max-w-md">
          <Link href="/" aria-label="GetbyFarm home" className="mb-8 inline-block md:hidden">
            <Logo height={40} />
          </Link>
          <h1 className="font-display text-3xl font-medium">{title}</h1>
          {children}
          <p className="mt-6 text-sm text-ink-soft">{footer}</p>
        </div>
      </main>
    </div>
  );
}
