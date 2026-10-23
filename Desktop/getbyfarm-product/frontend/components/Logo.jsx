import { BRAND } from "@/lib/brand";

const VARIANTS = { compact: "compact", full: "full", light: "light", "full-light": "fullLight", emblem: "emblem" };

/**
 * The GetbyFarm logo.
 *  variant: "compact" (emblem + wordmark, default), "full" (+ tagline), "light"/"full-light" (for dark backgrounds),
 *           "emblem" (circle only).
 *  height:  rendered height in px; width follows the image's proportions.
 */
export function Logo({ variant = "compact", height = 40, className = "" }) {
  const logo = BRAND.logos[VARIANTS[variant]];
  const width = Math.round((logo.w / logo.h) * height);
  return (
    // Plain <img>: small static asset, no optimiser needed. width/height attributes prevent layout shift.
    <img src={logo.src} alt={BRAND.name} width={width} height={height} className={className} style={{ height, width }} />
  );
}
