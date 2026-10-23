import js from "@eslint/js";
import globals from "globals";
import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";

// Plain-JS safety net (replaces TypeScript's compile-time checks): catches undefined variables, unused imports,
// misused React hooks and Next.js pitfalls before they reach users.
export default defineConfig([
  js.configs.recommended,
  ...nextVitals,
  globalIgnores([".next/**", "node_modules/**"]),
  {
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
    rules: {
      "no-unused-vars": ["error", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
      "react/no-unescaped-entities": "off",
      "@next/next/no-img-element": "off", // the logo is a small static asset; <img> is intentional
    },
  },
]);
