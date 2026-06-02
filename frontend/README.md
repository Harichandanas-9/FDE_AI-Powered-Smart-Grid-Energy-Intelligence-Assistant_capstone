# Frontend — Smart Grid AI Assistant (STEP 9 + 10)

React + Vite + Tailwind + Framer Motion. Glassmorphism UI with per-page accent
colors and a working ETL + Dashboard wired to the FastAPI backend.

## Quick start (Windows / VS Code)

```powershell
# 1. From the project root, open a new terminal (Ctrl + `)
cd frontend

# 2. Install dependencies (~30 s)
npm install

# 3. Make sure the backend is running on :8000 in another terminal:
#    cd ..\backend && uvicorn app.main:app --reload --port 8000

# 4. Run the dev server
npm run dev
```

Open http://localhost:5173/

## What works now

| Page | Status | Backend endpoint(s) it calls |
|---|---|---|
| Dashboard | ✅ live | `/grid-score`, `/heatmap`, `/timeline`, `/recommendations`, `/ingest`+`/embed` (Refresh button) |
| Query Console | ✅ live | `/analyze` (chat-style, shows agent trace + retrieval evidence) |
| **ETL** | ✅ live | `/datasets` (list), `/datasets/upload`, `/datasets/{name}/process`, `/datasets/{name}` (DELETE) |
| Settings | ✅ live | `/health`, `/auth/me` |
| Grid Stability | 📋 placeholder | filled in STEP 11 |
| Failure Analysis | 📋 placeholder | filled in STEP 11 |
| Smart Meter | 📋 placeholder | filled in STEP 11 |
| Telemetry | 📋 placeholder | filled in STEP 11 |
| Recommendations | 📋 placeholder | filled in STEP 11 |
| Agent Flow | 📋 placeholder | filled in STEP 11 |
| Incident Timeline | 📋 placeholder | filled in STEP 11 |
| Heatmap Analytics | 📋 placeholder | filled in STEP 11 |

## Dev tips

- **CORS / proxy:** `vite.config.js` proxies `/api/*` to `http://localhost:8000`,
  so the frontend talks to the backend on the same origin in dev. No CORS errors.
- **Operator field:** in the topbar; persists to `localStorage`. Sent as
  `X-Operator-Name` header for audit logs.
- **JWT:** Settings page has an input to paste a token (only needed if you flip
  `MULTI_TENANCY_ENABLED=true` on the backend).
- **Build:** `npm run build` outputs `dist/` (ready for Render Static Site).

## Theme

Per-page accents are defined in `tailwind.config.js`:

```
accent-dashboard:  bluish green   #5EE6C8
accent-stability:  electric blue  #4DA8FF
accent-failure:    orange/red     #FF7A45
accent-meter:      lavender       #B79CFF
accent-recommend:  green          #6FE38A
accent-telemetry:  cyan           #4DE2F0
accent-etl:        gold-orange    #FFA552
```

The shared glass-card component (`GlassCard.jsx`) accepts an `accent` prop to
paint the top border in the page's theme color.
