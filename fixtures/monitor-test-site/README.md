# Monitor test site (static fixture)

Six HTML pages plus `robots.txt` and `sitemap.xml` for exercising llms-gen crawls and monitor webhooks on your machine.

## Serve locally (default port **8765**)

```bash
cd fixtures/monitor-test-site
python3 -m http.server 8765
```

Use **`http://127.0.0.1:8765/`** as the root URL in llms-gen. The committed `sitemap.xml` and `robots.txt` use that host for local runs; **do not** hand-edit them for production—see GitHub Pages below.

## Deploy (GitHub Pages)

The workflow **Deploy monitor test site (GitHub Pages)** (`.github/workflows/monitor-test-site-pages.yml`) copies this folder, rewrites `sitemap.xml`, `robots.txt`, and the localhost URL in `index.html` to match your project site, then publishes the artifact.

1. In the GitHub repo: **Settings → Pages → Build and deployment**, set **Source** to **GitHub Actions** (not “Deploy from a branch”).
2. Push to **`main`** (or run the workflow manually via **Actions → Deploy monitor test site → Run workflow**).
3. After the job finishes, the site is at **`https://<owner>.github.io/<repo>/`** (GitHub shows the exact URL on the workflow run and in **Settings → Pages**). Use that URL as the monitor **root** on Render or anywhere the crawler must reach the public internet.
4. Nav links are **relative** so they work under the `/repo/` path. To trigger a webhook hash change from the deployed fixture: edit `changelog.html` (e.g. `MONITOR_TEST_VERSION_1` → `MONITOR_TEST_VERSION_2`), commit, push, wait for the Pages workflow to complete, then **`POST /api/monitored-sites/{id}/refresh`** on your app.

## Pages

| File | Role |
|------|------|
| `index.html` | Home + nav |
| `about.html` | About |
| `docs.html` | Docs-style copy |
| `blog.html` | Blog-style article |
| `pricing.html` | Product/pricing list |
| `changelog.html` | **Edit this** between refreshes to change crawl output |

## Trigger a webhook hash change

1. Register a monitor for your fixture root URL (local `http://127.0.0.1:8765/` or your GitHub Pages URL) with your webhook URL (e.g. Zapier Catch Hook).
2. Run one monitor-linked crawl (generate with monitor, or `POST /api/monitored-sites` + `POST .../refresh`) — **no webhook** on the first successful baseline.
3. In `changelog.html`, change `MONITOR_TEST_VERSION_1` to `MONITOR_TEST_VERSION_2` (or any visible text).
4. Call `POST /api/monitored-sites/{id}/refresh` again and wait for completion — if the new `llms.txt` hash differs, your webhook should receive `llms_txt.changed`.
