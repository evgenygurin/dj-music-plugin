---
name: panel
description: Open the DJ Music monitoring panel (Next.js dashboard at http://localhost:3000)
argument-hint: (none)
allowed-tools: ["Bash"]
---

# Open DJ Music Panel

Start the backend + panel if not running, then open the dashboard in the default browser.

## Steps

1. Ensure the backend REST API (port 8000) and Next.js panel (port 3000) are running. Start them if not:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/start-services.sh"
```

2. Wait briefly for the panel to boot:

```bash
for i in 1 2 3 4 5; do
  curl -sf -o /dev/null http://localhost:3000 && break
  sleep 1
done
```

3. Open the dashboard in the browser:

```bash
open http://localhost:3000
```

4. Report the panel URLs to the user:

- **Dashboard**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **Swagger docs**: http://localhost:8000/docs
- **Logs**: `/tmp/dj-music-panel.log`, `/tmp/dj-music-backend.log`

## Troubleshooting

If port 3000 is already used by another app, tail the log:

```bash
tail -30 /tmp/dj-music-panel.log
```

If panel `node_modules` is missing, install deps first:

```bash
cd "${CLAUDE_PLUGIN_ROOT}/panel" && bun install
```
