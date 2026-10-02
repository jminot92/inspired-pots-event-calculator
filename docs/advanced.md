# Inspired Pots Event Quoting

A local Streamlit application for remote pottery-painting events and out-of-hours private studio hire. It separates customer quotes, protected internal economics and salesperson commission.

## Open the app on this computer

Run `run.ps1` in this folder, then open **http://127.0.0.1:8501**. The launcher uses a project virtual environment if one exists, otherwise the Codex bundled Python and the dependencies installed in `../.codex_tmp/quote-deps` for this build.

```powershell
Set-Location 'C:\Users\jackm\Documents\Inspired Pots\inspired_pots_quote_app'
.\run.ps1
```

If PowerShell blocks scripts, run `powershell -ExecutionPolicy Bypass -File .\run.ps1` for this invocation. Do not change the machine's global policy.

## Portable Python setup

Python 3.12 or newer:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address=127.0.0.1
```

Start Streamlit **from this folder** so it picks up `.streamlit/config.toml` and secrets. The local launcher binds only to `127.0.0.1`. Local setup mode gives trusted users of this computer administrator access. Local mode is blocked when the configured server address is not loopback.

## First-use workflow

1. Open Settings and review package safeguards, staffing, commission and booking minimums.
2. Configure Shopify and Google Routes credentials if available. Without Maps, enter and confirm a manually checked **return** journey; without Shopify, labelled package safeguards apply.
3. Sync Shopify in Products & Packages. All new variants are **ineligible and unclassified**. Assign pieces deliberately; use batch assignment for packages and speciality upgrades.
4. Create a quote, enter the customer, guest count, location and package. Set either the ex-VAT per-person price or total; the other updates automatically.
5. Review the protected minimum and staff commission. Save, then Generate Customer Quote for PDF, a printable HTML page and copyable email text.
6. Reopen in Saved Quotes, update booking status and track commission. Only admins can mark earned commission Paid.

No emails are sent and no payments are processed. Quote numbers are assigned on save. Duplicate starts a fresh draft without deposits, payments or inherited price approval.

## Shopify is indicative

The Shopify catalogue is **not a verified source of truth**. It may contain outdated or placeholder prices. The app explicitly states this in the editor, catalogue and settings.

Package protected pottery value defaults to the **higher of** the configured inc-VAT safeguard and the highest retail value of the active, eligible, manually assigned variants. Initial safeguards are Keepsakes £10, Everyday £15 and Favourites £25 inc VAT. These are configurable commercial assumptions, not confirmed inventory prices. A reviewed admin override in **ex VAT per painter** replaces the default value.

Low prices (£1 or less), inventory requiring checking and syncs older than 30 days receive catalogue review flags. Shopify never infers classifications from prices, and sync never changes manual eligibility, package, upgrade amount or notes. Deleted/missing variants are deactivated after a complete successful sync. Pottery choice availability must still be confirmed with the customer.

Speciality upgrades apply to all painters in this MVP. Their protected increment is the larger of the manually assigned ex-VAT upgrade and the extra ex-VAT retail value. The selling price remains the salesperson's explicitly entered price.

## Credentials and integrations

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`, or set the same names as environment variables. Real secrets files are gitignored. Environment values take precedence.

| Variable | Purpose |
| --- | --- |
| `SHOPIFY_SHOP` | `your-store.myshopify.com` hostname, without protocol |
| `SHOPIFY_ACCESS_TOKEN` | Admin API token with product/inventory read access |
| `SHOPIFY_API_VERSION` | Versioned Admin GraphQL API; validated against `2026-07` |
| `GOOGLE_MAPS_API_KEY` | Google key with Routes API and billing enabled |
| `AUTH_MODE` | `local` (default, loopback only) or `password` |
| `BOOTSTRAP_ADMIN_EMAIL` | Email for the first admin when the database is empty |
| `BOOTSTRAP_ADMIN_NAME` | Display name for the first admin |
| `BOOTSTRAP_ADMIN_PASSWORD` | Required in password mode when creating the first account; 12+ characters |
| `DATABASE_URL` | Optional SQLAlchemy URL; default SQLite under `data/quotes.sqlite3` |

Shopify sync fetches all variant pages before making local changes. HTTP errors are sanitized so tokens are not printed. Google Routes queries the outward and return journeys separately, and stores the result source. Journey estimates are traffic-unaware; verify timing for the event. Changing the location or manually editing route values requires travel confirmation again.

References: [Shopify productVariants](https://shopify.dev/docs/api/admin-graphql/2026-07/queries/productVariants), [Google computeRoutes](https://developers.google.com/maps/documentation/routes/reference/rest/v2/TopLevel/computeRoutes), [Streamlit app testing](https://docs.streamlit.io/develop/api-reference/app-testing).

## Accounts and roles

In Settings, create Staff or Admin accounts and set/reset passwords. Passwords use salted PBKDF2-SHA256 with 600,000 iterations. Staff can only see, edit and export quotes assigned to them and their associated commissions. Staff see the protected minimum and staff commission; the detailed cost breakdown is admin-only. Staff cannot change global settings, product assignments, commission rules or pricing overrides. Active account status is rechecked on each rerun; quote mutations reload the account.

Before sharing or deploying, set a password for the initial local admin using Settings, then set `AUTH_MODE="password"` and restart. Bootstrap credentials do not overwrite an existing account. Password mode does not present a role/user switcher. Basic login includes session-level retry throttling; hosted production should replace it with managed authentication/SSO, global throttling and session revocation.

## Commercial rules and rounding

- All maths uses `Decimal`, with money stored as decimal strings (never SQLite floating-point values). Widget floats are converted to decimal strings at the input boundary.
- The extended cost is rounded **once after multiplying**. This avoids rounding £5/1.20 to £4.17 before multiplication. Components, totals, VAT, deposits and commissions round to two decimal places using `ROUND_HALF_UP`.
- Remote floor = protected pottery retail + consumables + paid base labour + additional travel labour + mileage/fuel + optional costs. Remote commission = `max(0, ex-VAT sale - floor) × commission rate`.
- Private staffing always applies outside opening hours. Package pricing protects pottery, consumables and staffing. Fee + pottery-on-day excludes future pottery sales from this quote. Both apply `max(calculated costs, minimum booking charge)`.
- The default private minimum **£250 is ex VAT**. The suggested private attendee fee **£10 is inc VAT**. These interpretations are clearly labelled and editable.
- Private business commission is fixed £25 by default, or one configured tier scheme. It becomes earned only when Won and deposit paid. Consumer private commission defaults to zero; consumer remote uses the shared engine in this MVP.
- Deposits default to 20% of the quoted inc-VAT amount. Remote deposits are also shown; these are booking records, not payments.
- Below-floor quotes can be saved as Draft/Lost/Cancelled but cannot be Sent/Won or exported to the customer without an admin approval. The admin must provide a reason; user, timestamp and economic fingerprint are recorded in the audit log. Changing economic terms invalidates approval.
- A £1 ex-VAT amber band above the floor is configurable. Above that, positive remote commission produces a green indicator. Private bookings show the protected-economics state separately from their fixed commission.
- Lost/Cancelled quotes have no earned or potential commission. Paid commission locks economic terms, salesperson and booking status. Admins may reopen Paid as Earned, which is audited, before correcting a booking.

Quotes store commercial settings, pottery choice/value snapshots, original creator, updated timestamps and versions. Reopening uses the saved assumptions. Explicitly refreshing pricing, changing the package or changing the upgrade uses current settings/catalogue. Status changes alone preserve the snapshot. An optimistic version check prevents two sessions silently overwriting each other.

## Customer outputs

PDF, printable HTML and email use one explicit allowlist of customer information. They exclude internal notes, costs, protected floors, margins and commission. Remote travel is included in the quoted amount. Private fee mode explicitly says attendees buy pottery separately. The printable HTML has a Print quote action. The email has Copy Email and a selectable/copyable fallback if clipboard permissions prevent copying.

The PDF uses a typographic Inspired Pots wordmark and a muted green/cream palette. No official logo was supplied; an official brand asset can be added later. The private studio's address is fixed to Inspired Pots, Hexham, NE46 1BH.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

For the Codex bundled runtime on this computer:

```powershell
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -c "import sys;sys.path.insert(0,r'C:\Users\jackm\Documents\Inspired Pots\.codex_tmp\quote-deps');import pytest;raise SystemExit(pytest.main(['-q']))"
```

Tests cover the supplied £516.83 floor / £21.59 commission example, rounding, fuel, private floors, commission tier boundaries, VAT exclusion, both-direction routing, Shopify pagination/classification preservation, server-side underquote rules, override invalidation, role checks, frozen pricing, concurrent edits, paid-commission locks, customer export privacy and Streamlit page/price interactions. API tests use mocked responses; live integrations require credentials and were not exercised during the build.

## Persistence and hosting

Tables: users, quotes, quote_costs, products, settings, commissions and audit_log. JSON quote payloads/snapshots keep the MVP extensible. SQLite foreign keys, WAL and a busy timeout are enabled. Back up `data/quotes.sqlite3` with SQLite's backup API; don't copy a live database without its WAL state.

For a hosted build, use password mode (preferably replace basic auth with OIDC), server-managed secrets, HTTPS and a durable database. Streamlit Community Cloud's local filesystem is not guaranteed durable; use a managed SQL database via `DATABASE_URL` for real quote persistence. This initial schema has no migrations yet; add migrations before changing tables in an environment containing real quotes.

## Structure

`app.py` owns navigation/authentication; `pages/` owns the four screens; `components/` owns summary/export presentation; `services/pricing.py` contains pure commercial maths; `services/quotes.py` enforces mutation/export policies; `services/database.py` owns ORM setup and catalogue/settings writes; integration clients, customer exports and PDF rendering live in separate service modules; `models/entities.py` defines the schema.
