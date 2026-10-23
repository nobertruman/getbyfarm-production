export function num(v) {
  if (v === null || v === undefined) return 0;
  const n = typeof v === "number" ? v : parseFloat(v);
  return Number.isFinite(n) ? n : 0;
}
export const kes = (v) => `KSh ${num(v).toLocaleString("en-KE", { maximumFractionDigits: 2 })}`;
export const qty = (v) => num(v).toLocaleString("en-KE", { maximumFractionDigits: 2 });
export const shortDate = (iso) =>
  new Date(iso).toLocaleDateString("en-KE", { day: "numeric", month: "short", year: "numeric" });
