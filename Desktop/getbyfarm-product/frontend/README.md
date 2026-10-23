# GetbyFarm frontend

Next.js 16 (App Router) · React 19 · **plain JavaScript (JSX)** · Tailwind. Talks only to the real API: no demo data, no mock fallbacks.

```bash
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000 for local dev
npm install && npm run dev
npm run lint && npm run build      # lint is the safety net that TypeScript used to provide
```

**Production:** leave `NEXT_PUBLIC_API_URL` empty. The browser then calls `/api/...` on the same domain that served the
page (the reverse proxy routes it), so there is no CORS and no URL baked into the build. Fonts are self-hosted (no
third-party requests).

## Pages

| Route | Who | What |
|---|---|---|
| `/` | public | Landing page (the hero comparison is labelled as an illustrative example) |
| `/login`, `/register` | public | Auth on a branded two-panel layout; buyers or suppliers can self-register |
| `/buyer` | buyer | Dashboard: spend, orders needing attention, recent orders |
| `/buyer/compare` | buyer | Search catalogue, quantity, ranked suppliers with score breakdown, add to cart |
| `/buyer/cart` | buyer | Multi-supplier cart, checkout |
| `/buyer/orders` | buyer | Approvals, pay with M-Pesa (polls for result), cancel, confirm receipt, invoice |
| `/supplier` | supplier | Fulfilment queue, listings (add/edit/remove), stats, verification banner |
| `/admin` | GetbyFarm staff | Platform stats, supplier verification queue |

`app/{buyer,supplier,admin}/layout.jsx` use `RoleLayout` (`components/Session.jsx`) to require login **and** the right role.
These guards are for UX; the API enforces every permission server-side.

## Code layout

`lib/`: `config.js` · `auth.js` (JWT, single-flight refresh with rotation, logout revocation) · `api-client.js` (fetch wrapper,
readable DRF errors, 401 refresh-retry) · `api.js` (endpoint functions; the top of the file documents every response shape,
and DRF sends decimals as strings, so use `format.js`) · `useAsync.js` · `status.js` · `brand.js`.
`components/`: `Logo`, `Brand` (TriBar, BrandWord), `AuthShell`, `AppNav`, `Session`, `ui`, `OrderTimeline`.

Because there is no compiler checking field names any more, `npm run lint` (ESLint: undefined variables, unused imports,
React-hooks rules) runs in CI, and `e2e/contract.js` exercises the real `lib/` code against a live API through the whole journey
(sign-up → supplier verification → compare → cart → approval → pay → fulfil → receipt → token rotation). `tsx` is used only as a
runner so Node can import our ES-module source; no TypeScript is involved.

## Brand and design

The logo is `public/logo*.png`, cut from the supplied artwork on a transparent background, in five variants:
`logo.png` (emblem + wordmark: headers), `logo-full.png` (+ tagline), `logo-light.png` / `logo-full-light.png` (for dark
backgrounds: the green letters turn off-white, the orange "BY" stays), `emblem.png`. `app/icon.png` / `apple-icon.png` are the
favicon. Use `<Logo variant="compact|full|light|full-light|emblem" height={px} />` (`components/Logo.jsx`); pixel sizes live in `lib/brand.js`.

Colours come from the logo (`tailwind.config.js`): **leaf** green `#0C850D` (the "GET" and "FARM"), **ember** orange `#FB3C06`
(the "BY" and emblem), deep forest `#0B3B1A` for dark sections, and **berry** red reserved for errors so they can't be confused
with the brand orange. Rules of thumb that keep it accessible (WCAG AA):
the pure logo orange is only 3.5:1 on light backgrounds, so it is used for large graphics and accents; buttons and small orange
text use `ember-600/700` (≥ 5:1); text on dark sections uses `paper`/`ember-300`. Orange light on deep green mixes to muddy brown, so dark sections get green glows and orange stays as crisp accents (bars, checks, script tagline). One primary action per page is orange; green is
for structure, confirmation and navigation. The green–orange–green motif of the wordmark repeats as `TriBar` dividers and in the
`BrandWord` headline. The script font (Caveat) echoes the hand-lettered tagline and is used sparingly.
To swap the artwork, replace the PNGs in `public/` (keep the file names) and adjust the sizes in `lib/brand.js`.
