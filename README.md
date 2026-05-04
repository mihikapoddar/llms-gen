# llms-gen

Web application that crawls a website, extracts titles and descriptions from key pages, and generates an [llms.txt](https://llmstxt.org/) file (Markdown: H1, optional blockquote, H2 sections with `- [title](url): notes` lists, and an `## Optional` section for secondary pages).

## Features

- URL submission with configurable crawl size and timeouts
- Respects `robots.txt` for the configured user-agent
- Discovers URLs via `sitemap.xml` (including nested indexes) and same-origin link crawling (treats `example.com` and `www.example.com` as the same site so redirects and links do not stall the crawl)
- Ranks and buckets pages into **Docs**, **Blog**, **Product**, **Key pages**, and **Optional** (legal, changelog, etc.)
- Collapses repeated meta descriptions (same text on 3+ pages → one note, rest link-only), sanitizes titles like `X | X`, lists substantive pages before demo/funnel URLs, and overflows trimmed funnel pages into **Optional**
- Async job API with live status; download generated `llms.txt`
- **Monitored sites**: register a root URL from the **Generate** form (webhook **required** when monitoring is checked) or via the HTTP API (`webhook_url` optional there if you only poll). A background worker re-crawls on your interval, stores the SHA-256 of the last `llms.txt`, and can POST to your URL when that hash changes (see below). The public web UI **does not list** monitored URLs—use `GET /api/monitored-sites` (with access control) to inspect or clean up rows.
- SQLite by default (set `LLMS_GEN_DATABASE_URL` for PostgreSQL async URL if you wire a driver)

## Requirements

- Python 3.9+

## Quick start (local)

```bash
cd llms
cp .env.example .env
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -U pip setuptools wheel
pip install -e ".[dev]"
uvicorn llms_gen.main:app --reload --host 0.0.0.0 --port 8000
```

The project uses **setuptools** as the build backend so `pip install -e .` works on common pip versions. If editable install still errors, upgrade pip and setuptools as shown above.

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Docker

```bash
docker compose up --build
```

The app listens on port **8000** (`PORT` is set in `docker-compose.yml`). SQLite data persists in the `llms_data` Docker volume. On **Render**, leave **`PORT`** unset in the dashboard so the platform injects it (usually `10000`); the image defaults to `10000` if `PORT` were missing so the health checker and bind port stay aligned.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LLMS_GEN_DATABASE_URL` | `sqlite+aiosqlite:///./llms_gen.db` | SQLAlchemy async URL |
| `LLMS_GEN_CRAWL_USER_AGENT` | `llms-gen/0.1` | User-Agent for fetches |
| `LLMS_GEN_MAX_PAGES_PER_JOB` | `60` | Max HTML pages per crawl |
| `LLMS_GEN_FETCH_TIMEOUT_S` | `20` | Per-request timeout (seconds) |
| `LLMS_GEN_MAX_RESPONSE_BYTES` | `2097152` | Max bytes read per response |
| `LLMS_GEN_MONITOR_ENABLED` | `true` | Background re-crawl scheduler |
| `LLMS_GEN_MONITOR_POLL_INTERVAL_S` | `300` | How often to check due monitors (seconds) |
| `LLMS_GEN_PUBLIC_BASE_URL` | *(empty)* | Public site origin for absolute `artifact_path` in webhook payloads |
| `LLMS_GEN_API_KEY` | *(empty)* | If set, all `/api/*` routes require header `X-LLMS-GEN-API-Key` or `Authorization: Bearer` with this exact value |
| `LLMS_GEN_EXPOSE_OPENAPI` | `true` | Set `false` on public hosts to disable `/docs`, `/redoc`, and `/openapi.json` |

## API

- `POST /api/jobs` — JSON body: `{"url": "example.com"}` or full `https://…` URL; scheme defaults to `https`, host is normalized to lowercase → `{ "id", "status" }`
- `GET /api/jobs/{id}` — job status and `artifact_id` when complete
- `GET /api/artifacts/{id}` — raw `llms.txt` body (`text/markdown`)
- `POST /api/monitored-sites`, `GET /api/monitored-sites`, `GET /api/monitored-sites/:id`, `PATCH /api/monitored-sites/:id`, `DELETE /api/monitored-sites/:id`, `POST /api/monitored-sites/:id/refresh` — see **Monitoring and webhooks**

## Monitoring and webhooks

There is **no login** and **no per-user dashboard**: every monitor row lives in the same database as the rest of the app. Treat this as **single-tenant** (your laptop, your company VPC, or a server you lock down). If you expose the API to the internet, set **`LLMS_GEN_API_KEY`** (and usually **`LLMS_GEN_EXPOSE_OPENAPI=false`**) so anonymous clients cannot crawl, read artifacts, list monitors, or register webhooks—or put the app behind reverse-proxy auth or a private network.

The **Generate** page can register a monitor (checkbox, interval, **webhook URL required** when the box is checked) after a successful crawl—the same as **`POST /api/monitored-sites`**. The form enforces a webhook so you get change notifications without an on-page monitor list. The HTTP API still allows omitting **`webhook_url`** if you only poll **`GET /api/monitored-sites`**. That UI **does not show** monitored URLs; use **`GET /api/monitored-sites`** when you need to list or audit rows.

### How scheduling works

1. **`POST /api/monitored-sites`** creates a row (or use the **Monitor this site** option on the Generate form after a run succeeds). Body fields (JSON):
   - **`url`** (required): root URL or bare domain (normalized like the job API).
   - **`interval_hours`** (optional, default `24`): time between automatic re-crawls.
   - **`max_pages`** (optional): capped by `LLMS_GEN_MAX_PAGES_PER_JOB`.
   - **`webhook_url`** (optional): HTTPS URL we POST to when the **content hash changes** after a monitor crawl (see webhooks below).

   Example:

   ```bash
   curl -sS -X POST "http://127.0.0.1:8000/api/monitored-sites" \
     -H "Content-Type: application/json" \
     -d '{"url":"https://example.com","interval_hours":24,"max_pages":40,"webhook_url":"https://hooks.zapier.com/hooks/catch/…"}'
   ```

2. The app runs a **background loop** (`LLMS_GEN_MONITOR_POLL_INTERVAL_S`, default **300** seconds). When a site’s `interval_seconds` has elapsed since `last_run_at`, it enqueues a crawl job linked to that monitor. Set **`LLMS_GEN_MONITOR_ENABLED=false`** to turn the loop off (you can still use **`POST …/refresh`** or ad-hoc **`POST /api/jobs`**).

3. **`POST /api/monitored-sites/{id}/refresh`** queues a crawl **now** (HTTP **202**), same pipeline as a normal job but results update the monitor’s `last_llms_sha256` / timestamps.

4. **`GET /api/monitored-sites`** or **`GET /api/monitored-sites/{id}`** returns `last_llms_sha256`, `last_run_at`, `content_changed_at`, `last_job_id`, `webhook_url`, etc.—use these from cron, CI, or a script if you prefer polling to webhooks.

5. **`PATCH /api/monitored-sites/{id}`** — send only fields to change, e.g. `{"webhook_url":"https://…","interval_hours":12,"enabled":false}`.

6. **`DELETE /api/monitored-sites/{id}`** removes the monitor.

### Webhook: when it fires and what you receive

- After each **monitor-linked** crawl completes successfully, we store **SHA-256** of the generated `llms.txt`.
- We call your **`webhook_url`** only if there was a **previous** hash and it **differs** from the new one (so **not** on the very first successful crawl for that monitor).
- Delivery is **best-effort** (failures are logged; the crawl still succeeds).

**JSON body** (UTF-8, `Content-Type: application/json`, `User-Agent: llms-gen-webhook/1`):

| Field | Meaning |
|--------|---------|
| `event` | Always `llms_txt.changed` |
| `site_id` | Monitor row UUID |
| `root_url` | Normalized root URL |
| `job_id` | Completed job id (fetch artifact with `GET /api/artifacts/{job_id}`) |
| `sha256` | New file digest |
| `previous_sha256` | Prior digest |
| `content_changed_at` | ISO 8601 timestamp when we detected the change |
| `artifact_path` | If **`LLMS_GEN_PUBLIC_BASE_URL`** is set (e.g. `https://api.example.com`), an absolute URL to the artifact; otherwise a path like `/api/artifacts/{job_id}` |

**Integrations**: point `webhook_url` at **Zapier** / **Make** / **n8n** “Catch Hook” actions, or your own HTTPS endpoint, then chain email, Slack, PagerDuty, etc. There is **no built-in email**; use your provider’s email action from the webhook payload.

### One-off generation without monitors

Use **`POST /api/jobs`** from the UI or curl whenever you only need a single run—no monitor row required.

### Local fixture site (monitor / webhook tests)

A tiny static site lives under **`fixtures/monitor-test-site/`** (six pages + `robots.txt` + `sitemap.xml`). Serve it with `python3 -m http.server 8765` in that directory and crawl **`http://127.0.0.1:8765/`** — see the folder’s **README** for editing `changelog.html` to force a hash change between `POST .../refresh` calls.

**SQLite:** On startup, missing tables are created and legacy DBs get a best-effort `ALTER TABLE` for `jobs.monitored_site_id`. If anything errors, delete `llms_gen.db` and restart.

## Ethics and limits

Only crawl sites you are allowed to automate. The default user-agent identifies the tool; keep rate limits conservative (single-host sequential fetches in the current implementation).

## Development

```bash
pip install -e ".[dev]"
pytest
```
