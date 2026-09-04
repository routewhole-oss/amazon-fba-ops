# Amazon FBA Ops MCP Server

A local MCP server that lets Claude query your Amazon Selling Partner API (SP-API) account directly, for two things:

- **Profitability** — revenue, Amazon fees, reimbursements, cost-of-goods (COGS), and net margin, grouped by SKU / order / day.
- **Inventory alerts** — FBA stock levels and low-stock warnings based on estimated days-of-supply.

Everything this server does against SP-API is **read-only** (GET requests). The only writes are to a local JSON file you control (`data/sku_costs.json`), which stores your own product costs since Amazon has no concept of COGS.

Not built yet (future phases): Amazon Ads/PPC, keyword research, Slack notifications, scheduled/cron runs, a dashboard UI.

## 1. Get SP-API credentials

You need three values from Amazon: an LWA app ID, an LWA client secret, and a refresh token. No AWS IAM / AWS keys are needed — SP-API dropped that requirement in October 2023.

1. Seller Central → gear icon → **Apps and Services → Develop Apps → Add new app client**. Choose **Private app** (not "Publish for others") — this is for your own seller account only.
2. When prompted for API access/roles, select the roles that cover **Orders**, **Finances**, **Inventory and Order Tracking**, and **Product Listing** (label wording can shift in the Seller Central UI — pick whatever maps to those four areas). Amazon may take a short time to approve the role grant even for a private app.
3. Open the app's detail page and copy the **LWA Client ID** and **LWA Client Secret**.
4. Still under Develop Apps, click **Authorize** on your app (self-authorization — since you're authorizing against the same account that created the app, no OAuth redirect server is needed). Confirm, and copy the **refresh token** shown — it's shown only once; if you lose it, re-run Authorize to get a new one.
5. Find your marketplace (e.g. US, UK, DE, JP) — this determines both the API endpoint region and the encoded `marketplace_id`.

## 2. Configure

```bash
cp .env.example .env
```

Fill in `.env`:

```
LWA_APP_ID=...
LWA_CLIENT_SECRET=...
SP_API_REFRESH_TOKEN=...
SP_API_DEFAULT_MARKETPLACE=US   # match your seller's marketplace
```

`.env` is gitignored — never commit it.

## 3. Install

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

## 4. Sanity-check credentials before wiring into Claude

```bash
PYTHONPATH=src .venv/bin/python3 -c "
from amazon_mcp.orders_service import get_orders
from datetime import datetime, timedelta, timezone
end = datetime.now(timezone.utc)
start = end - timedelta(days=7)
print(get_orders(start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')))
"
```

If this prints an orders list (even an empty one) instead of an error, your credentials work. If it errors, re-check `.env` against step 1 before touching the MCP server itself.

## 5. Set your product costs

Profitability can't be computed without knowing what each SKU costs you to make/source. Use the `set_sku_cost` tool from Claude once the server is registered, or seed `data/sku_costs.json` directly (see `data/sku_costs.example.json` for the shape). SKUs with no configured cost show up in `missing_cogs_skus` in the profitability output rather than silently being treated as free.

## 6. Register with Claude Code

A `.mcp.json` is already checked into this project root. It points at `.venv/bin/python`, so make sure step 3's install happened inside this directory. Claude Code will pick it up automatically when you open this project — restart Claude Code (or run `/mcp` to reload) if it doesn't appear right away.

To also register it in Claude Desktop, add the same entry under `mcpServers` in `~/Library/Application Support/Claude/claude_desktop_config.json`.

## 7. Verify end-to-end

All of these are safe, read-only checks against your real seller account:

- `get_orders` over a known recent window — cross-check the count/total against Seller Central's own Orders report.
- `get_inventory_summary()` — cross-check fulfillable quantities against the FBA inventory dashboard for 2-3 known SKUs.
- `get_catalog_item(asin)` for a known ASIN — confirm title/image match the live listing.
- `calculate_profitability` over a short window — manually reconstruct expected profit for 1-2 orders (revenue from Seller Central, fees from the Payments view, COGS from what you entered) and compare.
- `get_low_stock_alerts` — temporarily lower `days_of_supply_threshold` to confirm it flags a SKU you know is low.

Run the unit tests (mocked, no network) any time after changing code:

```bash
.venv/bin/pip install -e ".[dev]"
PYTHONPATH=src .venv/bin/pytest
```

## Tools

| Tool | Purpose |
|---|---|
| `get_orders(start_date, end_date, order_status?)` | List orders in a date range |
| `get_order_items(order_id)` | Line items for one order |
| `get_financial_events(start_date, end_date)` | Raw fee/refund/reimbursement events |
| `calculate_profitability(start_date, end_date, group_by?)` | Revenue/fees/COGS/net profit, grouped by `sku`\|`order`\|`day` |
| `get_inventory_summary(sku?)` | Current FBA inventory levels |
| `get_low_stock_alerts(days_of_supply_threshold?, lookback_days?)` | SKUs at risk of stocking out |
| `get_catalog_item(asin)` | Product title/image/dimensions |
| `set_sku_cost(sku, cost, effective_date?)` | Record a SKU's cost-of-goods |
| `list_sku_costs()` | List configured SKU costs |

## Known limitations

- Orders and financial events have a ~48-hour lag on Amazon's side — very recent orders won't show up yet.
- `get_low_stock_alerts` and `calculate_profitability` (when grouped by SKU) derive sales velocity/units by calling `get_order_items` once per order in the window, capped at 200 orders (`velocity_sampled` / `truncated` flags tell you if a cap was hit). High-volume sellers will eventually want a Reports-API-based bulk pull instead — not built in this MVP.
- Financial-event field parsing (`finances_service.py`) is based on Amazon's documented Finances v0 schema but has not yet been checked against a live response — if the shapes don't match exactly, cross-check `get_financial_events`'s raw output the first time you run it for real and adjust `_flatten_*` in `finances_service.py` if needed.
