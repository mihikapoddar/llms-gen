# Monitor test site (static fixture)

Six HTML pages plus `robots.txt` and `sitemap.xml` for exercising llms-gen crawls and monitor webhooks on your machine.

## Serve locally (default port **8765**)

```bash
cd fixtures/monitor-test-site
python3 -m http.server 8765
```

Use **`http://127.0.0.1:8765/`** as the root URL in llms-gen (match the host in `sitemap.xml` and `robots.txt`). If you use another port, update every `8765` in those two files to match.

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

1. Register a monitor for `http://127.0.0.1:8765/` with your webhook URL (e.g. webhook.site).
2. Run one monitor-linked crawl (generate with monitor, or `POST /api/monitored-sites` + `POST .../refresh`) — **no webhook** on the first successful baseline.
3. In `changelog.html`, change `MONITOR_TEST_VERSION_1` to `MONITOR_TEST_VERSION_2` (or any visible text).
4. Call `POST /api/monitored-sites/{id}/refresh` again and wait for completion — if the new `llms.txt` hash differs, your webhook should receive `llms_txt.changed`.
