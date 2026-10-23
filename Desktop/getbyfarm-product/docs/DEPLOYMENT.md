# Deploying GetbyFarm

One server, four containers, automatic HTTPS. This is the simplest setup that is still safe for a real launch
(tens of businesses, hundreds of orders a day). Section 9 covers growing past it.

```
Internet ──443──▶ Caddy ──┬─ /api/*  /django-admin/*  /static/* ─▶ backend  (Django + gunicorn) ─▶ db (PostgreSQL 16)
                          └─ everything else ────────────────────▶ frontend (Next.js)               ▲
                                                     scheduler (hourly: expire unpaid orders) ──────┘
```

* Only Caddy is exposed (ports 80/443). The database, API and frontend live on a private Docker network.
* The browser talks to **one origin**, so there is no CORS and no API URL baked into the frontend build.
* Caddy gets and renews HTTPS certificates by itself.

---

## 1. What you need

| | |
|---|---|
| A server | Any Linux VPS, **2 vCPU / 4 GB RAM / 40 GB disk** is comfortable. Ubuntu 22.04 or 24.04. Pick a region with good latency to Nairobi. |
| A domain | e.g. `app.yourcompany.co.ke`, with an **A record** (and AAAA if you use IPv6) pointing at the server's IP. Do this first; certificates can't be issued until DNS resolves. |
| Docker | Docker Engine + the Compose plugin. |
| Open ports | 80 and 443 (and 22 for SSH). Nothing else. |

```bash
# on the server (Ubuntu), as a non-root sudo user
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker
sudo ufw allow OpenSSH && sudo ufw allow 80 && sudo ufw allow 443/tcp && sudo ufw allow 443/udp && sudo ufw enable
```

## 2. First deploy

```bash
git clone <your-repo-url> /opt/getbyfarm && cd /opt/getbyfarm
cp .env.production.example .env.production
nano .env.production            # set DOMAIN, ACME_EMAIL, and generate DJANGO_SECRET_KEY + DB_PASSWORD
```

Generate secrets (run each, paste the output into `.env.production`):

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"   # DJANGO_SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(24))"   # DB_PASSWORD
python3 -c "import secrets; print(secrets.token_urlsafe(32))"   # MPESA_CALLBACK_SECRET (later)
```

The app **refuses to start** with a missing/placeholder secret key, no `ALLOWED_HOSTS`, or fake payments switched on
without the explicit acknowledgement flag. That is intentional.

Build and start:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
docker compose --env-file .env.production -f docker-compose.prod.yml ps        # all should become "healthy"
docker compose --env-file .env.production -f docker-compose.prod.yml logs -f backend caddy
```

On first start the backend applies migrations, creates the cache table, and loads the starter product catalogue
(50 common hospitality items, no prices, no fake businesses).

Create your platform-admin login (this is how you verify suppliers, add products, and reconcile payments):

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml exec backend \
  python manage.py createsuperuser --email you@yourcompany.co.ke --full_name "Your Name"
```

### Smoke test (5 minutes)

1. `https://YOUR_DOMAIN/api/health/` returns `{"status": "ok"}`.
2. `https://YOUR_DOMAIN/` shows the landing page with a valid padlock.
3. Register a **supplier** and a **buyer** account at `/register`.
4. Log in as your admin at `/login`; you land on `/admin`. Move the supplier through **Start review → Verify**.
5. Log in as the supplier, add a product listing (price + stock).
6. Log in as the buyer, **Compare & buy**, add to cart, place the order.
7. Payment: see section 5. Until M-Pesa is configured, paying is refused with a clear message. That is correct.

### A staging site with fake payments (optional, never your real site)

On a **separate** server/domain you can let testers "pay" without charging anyone:

```
ALLOW_MOCK_PAYMENTS=true
I_UNDERSTAND_MOCK_PAYMENTS_ARE_FAKE=true
```

and load fictional businesses to click around: `exec backend python manage.py seed_demo_data --i-know-this-is-demo`.
Do **not** do either on the production database.

## 3. Day-to-day operations

```bash
alias gbf='docker compose --env-file .env.production -f docker-compose.prod.yml'

gbf logs -f --tail=100 backend         # application logs
gbf ps                                  # health of every service
gbf exec backend python manage.py shell # Django shell, if ever needed
```

**Deploy an update**

```bash
cd /opt/getbyfarm && git pull
gbf up -d --build          # rebuilds changed images; migrations run automatically on backend start
```

Migrations run when the backend starts, so a brief (seconds) interruption during an update is expected. Take a backup
first (below) before any release that changes the database.

**Backups** (the only copy of your data is the `pgdata` Docker volume until you do this)

```bash
./scripts/backup.sh                                              # writes backups/getbyfarm-<timestamp>.sql.gz
crontab -e   # add:  30 2 * * * cd /opt/getbyfarm && ./scripts/backup.sh >> backups/backup.log 2>&1
```

Also copy `backups/` **off the server** (object storage, another machine, or provider snapshots). A backup on the
same disk does not survive losing the server. **Test a restore** on a scratch server before you need it:
`./scripts/restore.sh backups/<file>.sql.gz`.

**Monitoring.** Point any uptime monitor (UptimeRobot, Better Stack, …) at `https://YOUR_DOMAIN/api/health/`; it returns
503 if the database is unreachable. Watch `docker compose logs backend` for lines containing `PAYMENT AMOUNT MISMATCH`
or `refund/reconcile manually`; those mean money needs a human.

**Rotating secrets.** Change the value in `.env.production`, then `gbf up -d`. Changing `DJANGO_SECRET_KEY` logs
everyone out (JWTs are signed with it). Never rotate `DB_PASSWORD` in the file alone; change it inside Postgres too.

## 4. Admin tasks you'll actually do

| Task | Where |
|---|---|
| Verify / reject / suspend a supplier | `https://YOUR_DOMAIN/admin` |
| Add products or categories to the catalogue | `https://YOUR_DOMAIN/django-admin/` → Catalog |
| Enable another country | Django admin → Organizations → Countries |
| Look at a payment, find unreconciled money | Django admin → Payments (read-only ledger) |
| Refund / dispute / cancel a paid order | **Manual** for now: refund in the M-Pesa portal, then note it. There is no in-app refund flow yet. |

Optionally restrict `/django-admin/` to your office/VPN by setting `ADMIN_ALLOWED_IPS="1.2.3.4/32 10.0.0.0/8"`.

## 5. Going live with M-Pesa (checklist)

The Daraja client follows Safaricom's documented STK Push format, but **it has not been run against Safaricom** from
this repository. Treat the following as mandatory, in order:

1. Create a Daraja developer account; create an app; get the **sandbox** consumer key/secret and the sandbox shortcode + passkey.
2. Set in `.env.production`: `MPESA_ENABLED=true`, `MPESA_ENV=sandbox`, the four credentials, and a random `MPESA_CALLBACK_SECRET`.
   The callback URL Safaricom will call is built for you: `https://YOUR_DOMAIN/api/payments/mpesa-callback/<secret>/`.
3. `gbf up -d`, then place a small order and pay with a **sandbox test number**. Confirm: you get a prompt/response;
   the order turns **Paid · confirmed**; an invoice appears; the Payments ledger shows `success` with a receipt number.
4. Test the unhappy paths in sandbox: cancel the prompt, enter a wrong PIN, let it time out. The order must stay
   "Awaiting payment" and the buyer must be able to retry.
5. Apply for **Daraja go-live** (production shortcode/passkey) following Safaricom's process. Production credentials and
   shortcode type (Paybill vs Till) are issued by them. Till: set `MPESA_TRANSACTION_TYPE=CustomerBuyGoodsOnline`
   and `MPESA_PARTY_B=<till number>`.
6. Set `MPESA_ENV=production` + production credentials. Run **one real payment of a small amount** end to end and
   reconcile it against your M-Pesa statement.
7. Lock the callback to Safaricom: take the callback source IP ranges from **Safaricom's current official Daraja
   documentation** (do not copy them from a blog), put them (space-separated CIDRs) in `MPESA_ALLOWED_IPS`, `gbf up -d`,
   and confirm a real callback still arrives. (A wrong list will block real payments, so verify after changing it.)
8. Keep `ALLOW_MOCK_PAYMENTS=false`.

How callbacks are protected: unguessable secret in the URL, the checkout ID must match a payment *we* created and that is
still pending, the amount must match exactly, processing is idempotent (replays do nothing), and an optional IP allowlist.
Daraja does not sign callbacks, so these layers are the defence; keep the secret private.

Amounts: M-Pesa moves whole shillings, so a payment is **rounded up** to the next shilling (never short for the supplier).

## 6. Security summary

Built in: HTTPS + HSTS; security headers and a CSP; passwords validated and hashed (PBKDF2); short-lived access tokens
with rotating, server-revocable refresh tokens; login/signup/payment rate limits keyed on the real client IP (shared
across workers); tenant isolation on buyer and supplier data (covered by tests); role-checked approvals; staff-only supplier verification via an enforced
state machine; no sensitive supplier fields exposed to buyers; database never exposed; non-root containers; secrets only
from the environment (the app won't boot with weak ones); read-only audit-style admin for orders/payments/invoices.

Known trade-offs to be aware of:

* **Tokens are stored in `localStorage`.** An XSS bug could steal them. Mitigated by short lifetimes, rotation and a CSP,
  but the stronger design is an httpOnly cookie. Worth doing as a follow-up.
* **CSP allows `'unsafe-inline'`** because Next.js hydration and Django admin need it today; nonce-based CSP is a follow-up.
* **No account lockout/2FA/email verification/password reset yet** (see section 8).
* **Keep dependencies patched.** At release time `pip-audit` reports no known vulnerabilities for the backend and `npm audit --omit=dev`
  reports none for the frontend runtime (this required Django 5.2 LTS and Next.js 16: the older Django 5.0 and the whole Next 14
  line had open advisories). Re-run both regularly (CI is a good place) and rebuild images to pick up fixes. One dev-only
  advisory remains (`braces` via Tailwind v3, build-time CSS tooling that never ships in the runtime image).

## 7. If you use a managed platform instead of a VPS

The two Dockerfiles run anywhere (Render, Railway, Fly.io, Cloud Run, ECS…):

* **Backend**: set `DATABASE_URL` (add `DB_SSL_REQUIRE=true` for managed Postgres), `DJANGO_SECRET_KEY`,
  `DJANGO_ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, and the `MPESA_*` variables. Set `NUM_PROXIES` to the number of proxy
  hops in front of Django (platform load balancers are usually 1; wrong values break rate limiting).
  Run the hourly `python manage.py expire_unpaid_orders` as a scheduled job.
* **Frontend**: build with `NEXT_PUBLIC_API_URL=https://api.yourdomain` and set the backend's
  `CORS_ALLOWED_ORIGINS=https://yourdomain`. (Same-origin hosting, as in this guide, avoids all of this.)
* If you run **more than one backend instance**, set `REDIS_URL` so rate limits are shared.

## 7a. Render (step by step) and troubleshooting

**Backend (Web Service → Docker):** set *Root Directory* to `backend`; leave *Docker Command* **blank** (the image already
knows how to start). Render supplies `PORT` and `WEB_CONCURRENCY`; the image honours both. Set *Health Check Path* to `/api/health/`.
Create a Render PostgreSQL database and set these environment variables on the service:

| Variable | Value |
|---|---|
| `DJANGO_SECRET_KEY` | a long random string (50+ chars) |
| `DATABASE_URL` | the database's **Internal** connection string from Render |
| `CORS_ALLOWED_ORIGINS` | `https://<your-frontend>.onrender.com` (comma-separate extra origins) |
| `NUM_PROXIES` | start with `1`; see note below |
| `MPESA_*`, `ALLOW_MOCK_PAYMENTS` | as in `.env.production.example` |

`DJANGO_ALLOWED_HOSTS` is optional on Render: the service's own `*.onrender.com` name (Render's `RENDER_EXTERNAL_HOSTNAME`)
is allowed automatically, which is also what Render's health check uses. For a custom domain add it to `DJANGO_ALLOWED_HOSTS`.
Housekeeping: add a Render **Cron Job** (same image, command `python manage.py expire_unpaid_orders --hours 24`, hourly).

**Frontend (Web Service → Docker):** *Root Directory* `frontend`; set `NEXT_PUBLIC_API_URL` to the backend's public
URL (`https://<backend>.onrender.com`). This value is baked into the JavaScript **at build time**, so set it before the build;
if the live site calls `localhost:8000`, the variable didn't reach the build, so check it and redeploy.

`NUM_PROXIES` must equal the number of proxy hops in front of Django, otherwise rate limits key on the wrong address
(too low: every user shares one bucket; too high: clients can spoof their address). It is `1` in the Caddy setup above. On a
platform with extra edge layers it may differ and I have not verified Render's hop count: if legitimate users start getting
"too many requests" errors, raise it by one.

**If a deploy says `Exited with status 128` (or 126/127) and the log shows nothing after "Deploying…"**: the container
died before the app printed anything, i.e. the start command itself could not run. Causes seen in practice: the entrypoint
script lost its executable bit or gained Windows (CRLF) line endings from a zip/Windows git checkout. The Dockerfile now repairs
both at build time and starts the script through `sh`, and `.gitattributes` keeps scripts LF; if your repo already
contains CRLF files, run `git add --renormalize . && git commit`. A healthy start now always logs
`GetbyFarm backend starting (port …)` first, so a log that is still empty points at the platform/image, not the app.

Other first-deploy errors, and what they mean:

| Log line | Cause |
|---|---|
| `ImproperlyConfigured: DJANGO_SECRET_KEY must be set…` / `looks weak` | missing or placeholder secret key |
| `ImproperlyConfigured: DJANGO_ALLOWED_HOSTS must be set` | not on Render and no hosts configured |
| `OperationalError: connection … refused` / `could not translate host name` | wrong `DATABASE_URL` (use the Internal URL) or DB not ready yet |
| health check fails, access log shows `400` | the Host header isn't allowed (custom domain missing from `DJANGO_ALLOWED_HOSTS`) |
| `no open ports detected` | something overrode the start command; clear *Docker Command* |

*What was verified:* the start sequence above was reproduced and tested in a Render-like environment (CRLF + lost
executable bit, `PORT=10000`, `WEB_CONCURRENCY=1`, no `DJANGO_ALLOWED_HOSTS`, `RENDER_EXTERNAL_HOSTNAME` set, `DATABASE_URL`): migrations
ran, the health check passed with the `onrender.com` Host, a foreign Host got 400, and register/login worked. It has not been run on Render itself.

## 8. What is NOT built yet (so you can plan)

Honest list, nothing here is hidden behind a fake screen:

* **Not implemented**: group buying, inventory/stock-out tracking and forecasting, subscriptions/billing, commission
  accounting, supplier document upload (verification is a manual review today), ratings/reviews and dispute handling,
  refunds, email/SMS/WhatsApp sending (in-app notification records are written but no UI shows them), password reset,
  email verification, 2FA, courier-partner integrations, eTIMS e-invoicing, VAT calculation (orders carry KSh 0 tax; invoices
  show what the order carries), multi-branch management UI (the data model supports branches; the signup flow creates one).
* **Reliability/quality scores** are an admin-set starting value (neutral prior on verification); they are not yet
  computed from delivery history, so rankings are only as good as those inputs.
* **Not exercised outside this repository's tests**: the real Safaricom Daraja calls, and building the Docker images
  (Docker wasn't available in the environment where this was authored; the Dockerfiles, compose file and Caddyfile were
  reviewed and the Caddy routing/allowlist behaviour tested with the real Caddy binary). Your first `up --build` is the first
  real image build: expect to read the logs.
* The platform has **not been load tested**. Expect a single 2-vCPU server to handle a modest launch; measure before promising more.

## 9. Growing past one server

In rough order: managed PostgreSQL with automated backups/PITR; `REDIS_URL` for shared rate limits and a future task queue;
object storage (S3-compatible) for supplier documents and product images; a second backend instance behind a load balancer;
a task queue (Celery) for notifications and nightly supplier-score computation; error tracking (Sentry) and metrics.
