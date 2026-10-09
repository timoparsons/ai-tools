---
name: pricebuddy-mcp
description: Use when the user asks about tracked prices, deals, price drops or history, or wants to add, change or check products and stores in PriceBuddy (the self-hosted price tracker) through the pricebuddy MCP server.
---

# pricebuddy-mcp

Reach this server through bifrost-gateway (see local-environment): `listToolFiles`, then `readToolFile` on `servers/pricebuddy.pyi`, then `executeToolCode`. Read the stub once per session.

**Setup (verified 2026-10-07).** Official pricebuddy-cli v1.0.0 `pricebuddy-mcp`, native streamable HTTP. Container `pricebuddy-mcp` in `/opt/docker-compose.yml` on the n8n LXC (10.1.1.31), built from `/opt/pricebuddy-mcp/Dockerfile`, which also ships the companion `pricebuddy` CLI the analysis tools shell out to. Bifrost client `pricebuddy` at `http://10.1.1.31:7777/mcp`, no auth on that port (LAN only). It talks to PriceBuddy internally at `http://pricebuddy/api` with a full-access token from `PRICEBUDDY_API_TOKEN` in `/opt/.env`. The web UI is `pricebuddy.timparsons.nz` (LAN http, public https via Cloudflare). Prices are in NZD unless a store is mislabelled (see Data quirks).

## Calling convention

- Product, store or tag IDs for the analysis tools go in `args` as a string: `pricebuddy.insights(args="11", agent=True)`.
- Never put flags in `args`; the server refuses them (`flag-like argument ... not allowed`).
- Parameters with hyphens (`dry-run`, `data-source`, `max-pages`) cannot be Starlark keywords. Pass them by dict unpacking: `pricebuddy.products_pause(args="12", agent=True, **{"dry-run": True})`. Verified: the dry run is honoured.
- Pass `agent=True` on analysis tools for compact JSON. `select="points.date,points.price"` trims fields.
- Typed endpoint tools take plain keywords: `products_detail(id="11")`, `meta_extract(url=...)`.

## Use the live tools, not the local mirror

`sync` only ever fetches the first 25 records per resource (the CLI expects cursor paging, the API pages with `?page=`), whatever `full` or `max-pages` say. So `sql`, `search`, `analytics` and anything with `data-source local` see an incomplete catalogue. `products_pagination` and `stores_pagination` also return page 1 only and have no page parameter.

- Whole watch list (id, title, current price, target met): `watch(agent=True)`. It reads live and covers every product.
- One product with every store, price, availability and daily history: `products_detail(id=...)`.
- Price drops: `drops(days=7, agent=True)`. Moves since a window: `since(args="7d", agent=True)`.
- Lowest ever, overall and per store: `lowest(args="ID", agent=True)`.
- Deal score, buy or wait verdict, stats: `insights(args="ID", agent=True)`. `lowConfidence: true` means too little history to trust the verdict; say so.
- Daily series: `history(args="ID", agent=True, select="points.date,points.price")`.
- On sale against a target: `deals(agent=True)`. It is empty when no product has `notify_price` or `notify_percent` set, which was true of every product on 2026-10-07.

## Data quirks

- Availability is not considered by `lowest` or the product's `current_price`. A discontinued or out-of-stock listing can be reported as the cheapest (PS5: Amazon AU discontinued at 1091.69). Check `availability` in `price_cache` before calling something the best price.
- Store currency labels: Jbhifi.co.nz and Bits4bots.co.nz were set to USD on 2026-10-07 although they are NZ stores. Treat their prices as NZD and mention the label if it matters.
- Product titles are scraped page titles and can be long or include the store name.

## Writes

The typed write tools act immediately and have no dry run: `products_create`, `products_update`, `products_delete`, `stores_create`, `stores_update`, `stores_delete`, `tags_*`, `product_sources_*`, `import`. State the change and get a go-ahead first. Deletes remove the product and its price history permanently.

- Before tracking a new URL, preview it with `meta_extract(url=...)` and show the scraped title and price.
- `products_update` requires `title` and `image` even for a one-field change. Read them from `products_detail` first and send them back unchanged.
- Targets: `notify_price` (absolute) or `notify_percent` on `products_update`.
- Pause, resume, check interval and back-in-stock toggles (`products_pause`, `products_resume`, `products_set_interval`, `products_notify_in_stock`) take `args="ID"` and support `**{"dry-run": True}`. Allowed intervals in seconds: 300, 600, 900, 1800, 3600, 7200, 14400, 21600, 43200, 86400.
- Never call `pricebuddy_auth_login` or `pricebuddy_auth_logout`; logout would revoke the token the container uses.

## Maintenance

All through ansible on host `n8n`, in `/opt`. The compose file loads cleanly as of 2026-10-07 (PriceStalker moved to `docker-compose-removed.yml`).

- Restart: `docker compose restart pricebuddy-mcp`.
- New token: the user edits `PRICEBUDDY_API_TOKEN` in `/opt/.env` (never through the model), then `docker compose up -d --no-deps pricebuddy-mcp`.
- Upgrade the CLI: bump `PB_CLI_VERSION` in the Dockerfile (and the image tag in compose), then `docker compose build pricebuddy-mcp` and `up -d --no-deps pricebuddy-mcp`. Re-test the tools after an upgrade; the sync paging bug may be fixed.
- Recreating the container can drop Bifrost's session. If calls fail, `bifrost_reconnect_mcp_client(client="pricebuddy")`, dry run then confirm.
- Health check from the host: `docker exec pricebuddy-mcp pricebuddy doctor --agent`.
- The local mirror lives in volume `pricebuddy_mcp_home` (`/home/mcp/.local/share/pricebuddy/data.db`).
