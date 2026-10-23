/** @type {import('tailwindcss').Config} */
// Palette is derived from the GetbyFarm logo: leaf green #0C850D and orange-red #FB3C06.
// Contrast notes (WCAG): white on leaf-600 4.8:1; white on ember-600 5.0:1; ember-700 text on paper 6.0:1.
// The pure logo orange (ember-500) is only 3.5:1 on light backgrounds, so it is used for large graphics and
// accents, never for small text.
module.exports = {
  content: ["./app/**/*.{js,jsx}", "./components/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: "#12281A", soft: "#33503B", faint: "#566F5C" },
        paper: { DEFAULT: "#F8FAF3", raised: "#FFFFFF", dim: "#EDF2E6" },
        // brand green (the "GET" and "FARM")
        leaf: { 50: "#EBF7EA", 100: "#D0EDCE", 300: "#7CCB78", 500: "#16A317", 600: "#0C850D", 700: "#0A6E0B", 800: "#085A09", 900: "#0B3B1A" },
        // brand orange-red (the "BY" and the emblem)
        ember: { 50: "#FFF1EC", 100: "#FFE1D6", 300: "#FF8A66", 500: "#FB3C06", 600: "#D13500", 700: "#B52D00", 900: "#7A1F00" },
        // errors and destructive actions only: deliberately a different hue from the brand orange
        berry: { 100: "#FBE6EA", 500: "#A51C3A", 700: "#8C1631" },
        steel: { 100: "#E2EAEC", 400: "#7C99A3", 600: "#45637A" },
        line: "#DCE5D3",
      },
      fontFamily: {
        display: ["Space Grotesk", "system-ui", "sans-serif"],
        body: ["IBM Plex Sans", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "monospace"],
        script: ["Caveat", "cursive"], // echoes the hand-lettered "Taste the freshness" tagline
      },
      fontSize: {
        "display-xl": ["4.5rem", { lineHeight: "1.02", letterSpacing: "-0.02em" }],
        "display-lg": ["3.25rem", { lineHeight: "1.05", letterSpacing: "-0.015em" }],
        "display-md": ["2.25rem", { lineHeight: "1.1", letterSpacing: "-0.01em" }],
      },
      borderRadius: { sm: "4px", DEFAULT: "6px", lg: "10px", pill: "999px" },
      keyframes: {
        riseIn: { "0%": { opacity: "0", transform: "translateY(10px)" }, "100%": { opacity: "1", transform: "translateY(0)" } },
      },
      animation: { riseIn: "riseIn 0.6s cubic-bezier(0.2, 0.8, 0.2, 1) both" },
    },
  },
  plugins: [],
};
