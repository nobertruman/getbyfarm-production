import { STATUS_LABEL } from "@/lib/status";
import { Logo } from "./Logo";

export function StatBlock({ label, value, sublabel, tone = "default" }) {
  const color = tone === "positive" ? "text-leaf-700" : tone === "warning" ? "text-ember-700" : "text-ink";
  return (
    <div className="border-b border-line py-4 first:pt-0 last:border-b-0 sm:border-b-0 sm:border-r sm:px-6 sm:py-0 sm:first:pl-0 sm:last:border-r-0">
      <p className="text-sm text-ink-faint">{label}</p>
      <p className={`num mt-1 font-display text-2xl font-medium ${color}`}>{value}</p>
      {sublabel && <p className="mt-1 text-xs text-ink-faint">{sublabel}</p>}
    </div>
  );
}

/** Verified-supplier mark (only rendered for suppliers an admin has verified): a green ring with a check. */
export function VerifiedStamp({ size = "sm" }) {
  const px = size === "sm" ? 18 : 28;
  return (
    <svg width={px} height={px} viewBox="0 0 24 24" role="img" aria-label="Verified supplier" className="shrink-0">
      <title>Verified supplier</title>
      <circle cx="12" cy="12" r="10.5" fill="#EBF7EA" stroke="#0C850D" strokeWidth="2" />
      <path d="M7 12.5l3.2 3.2L17 8.8" fill="none" stroke="#0C850D" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// Order status colours follow one rule: grey-blue = waiting on someone else, orange = needs YOUR action,
// green = moving / done, berry = cancelled.
const TONE = {
  draft: "bg-steel-100 text-steel-600",
  submitted: "bg-ember-100 text-ember-700",
  confirmed: "bg-leaf-100 text-leaf-800",
  processing: "bg-leaf-100 text-leaf-800",
  ready_for_dispatch: "bg-leaf-100 text-leaf-800",
  in_transit: "bg-leaf-100 text-leaf-800 ring-1 ring-leaf-300",
  delivered: "bg-leaf-100 text-leaf-800 ring-1 ring-leaf-300",
  completed: "bg-leaf-600 text-white",
  cancelled: "bg-berry-100 text-berry-700",
};
export const StatusPill = ({ status }) => (
  <span className={`inline-block whitespace-nowrap rounded-pill px-2.5 py-1 text-xs font-medium ${TONE[status]}`}>
    {STATUS_LABEL[status]}
  </span>
);

export const ErrorNote = ({ children }) => (
  <p role="alert" className="flex gap-2 rounded border border-berry-500/30 bg-berry-100 px-3 py-2 text-sm text-berry-700">
    <span aria-hidden className="font-bold">!</span>
    <span>{children}</span>
  </p>
);

export const Loading = ({ label = "Loading…" }) => (
  <p className="flex items-center gap-2 py-6 text-sm text-ink-faint" role="status">
    <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-leaf-600 border-t-transparent" aria-hidden />
    {label}
  </p>
);

export const EmptyState = ({ title, children }) => (
  <div className="rounded border border-dashed border-leaf-300 bg-paper-raised p-8 text-center">
    <Logo variant="emblem" height={40} className="mx-auto opacity-90" />
    <p className="mt-3 font-medium">{title}</p>
    {children && <div className="mt-2 text-sm text-ink-soft">{children}</div>}
  </div>
);
