# GetbyFarm

> Smarter sourcing starts with GetbyFarm.

B2B procurement for Kenya's hospitality industry: buyers compare verified wholesale suppliers (ranked on landed cost,
reliability, quality and lead time, with the reasoning shown), order across suppliers, route large orders through an
approval chain, pay with M-Pesa, and track fulfilment to an invoice. Suppliers list stock and prices and work a
fulfilment queue. The GetbyFarm team verifies suppliers and oversees the platform.

**Stack:** Next.js 16 (React 19, plain JavaScript/JSX) + Tailwind · Django 5.2 LTS + DRF · PostgreSQL 16 · Caddy (auto-HTTPS) · Docker Compose.

```
backend/    Django API (accounts, organizations, suppliers, catalog, pricing, procurement engine,
            carts, orders, payments, invoices, deliveries, analytics, notifications) + tests
frontend/   Next.js app (landing, auth, buyer / supplier / admin consoles) + API contract test
deploy/     Caddyfile (reverse proxy, security headers, IP allowlists)
scripts/    backup.sh, restore.sh
docs/       DEPLOYMENT.md (runbook), PRD.md (product + architecture), schema.sql (target schema reference)
```

## Deploy it

**Read [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).** Short version, on a server with Docker and a domain pointing at it:

```bash
cp .env.production.example .env.production      # set DOMAIN, ACME_EMAIL, secrets
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
docker compose --env-file .env.production -f docker-compose.prod.yml exec backend python manage.py createsuperuser
```

## Develop locally

```bash
# API: needs Postgres, or set DATABASE_URL=sqlite:///db.sqlite3 for a quick local run
cd backend && pip install -r requirements.txt && cp .env.example .env
export $(grep -v '^#' .env | xargs) && python manage.py migrate && python manage.py createcachetable && python manage.py seed_catalogue
python manage.py seed_demo_data --i-know-this-is-demo     # fictional businesses (dev/staging only)
python manage.py runserver                                  # :8000

# Frontend
cd frontend && cp .env.local.example .env.local && npm install && npm run dev      # :3000
```

## Verify it

```bash
# Backend: 35 tests (SQLite by default; set TEST_DATABASE_URL=postgresql://... to also run the concurrency race test)
cd backend && DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test integration_tests

# Frontend: lint (the safety net for plain JS) + production build
cd frontend && npm run lint && npm run build

# Frontend <-> backend contract: runs the real browser client code against a live API through the whole journey
cd frontend && NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 E2E_ADMIN_EMAIL=... E2E_ADMIN_PASSWORD=... npm run e2e
```

CI (`.github/workflows/ci.yml`) runs all of the above on every push, on PostgreSQL.

## Status, honestly

**Working and tested:** sign-up (buyer/supplier), role-based consoles, supplier verification workflow, catalogue,
supplier listings, the procurement recommendation engine, multi-supplier cart, race-safe checkout, approval chain with
role checks, M-Pesa STK Push flow + secured callback, invoices, fulfilment → delivery → receipt lifecycle, stale-order
expiry, buyer/supplier/admin dashboards, rate limiting, secure production defaults, backups.

**Not yet verified in a real environment:** live Safaricom Daraja calls (needs your credentials; follow the go-live
checklist) and the Docker image builds (authored without Docker available).

**Not built:** group buying, inventory forecasting, subscriptions/commissions, supplier document upload, ratings and
disputes, refunds, email/SMS/WhatsApp delivery, password reset, 2FA, eTIMS, VAT, courier integrations. Full list and
rationale in [`docs/DEPLOYMENT.md` §8](docs/DEPLOYMENT.md) and [`docs/PRD.md` §10](docs/PRD.md).
