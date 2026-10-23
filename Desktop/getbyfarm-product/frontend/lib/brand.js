// One place for brand facts. Colours mirror tailwind.config.js (derived from the logo).
export const BRAND = {
  name: "GetbyFarm",
  tagline: "Taste the freshness",
  colors: { green: "#0C850D", orange: "#FB3C06", forest: "#0B3B1A" },
  // intrinsic pixel sizes, so the browser reserves space before the image loads (no layout shift)
  logos: {
    compact: { src: "/logo.png", w: 420, h: 95 }, // emblem + wordmark
    full: { src: "/logo-full.png", w: 577, h: 141 }, // + "Taste the freshness"
    light: { src: "/logo-light.png", w: 420, h: 95 }, // for dark backgrounds
    fullLight: { src: "/logo-full-light.png", w: 577, h: 141 },
    emblem: { src: "/emblem.png", w: 132, h: 131 },
  },
};
