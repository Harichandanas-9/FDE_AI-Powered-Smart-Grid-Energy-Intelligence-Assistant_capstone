# Deployment — Render

This project ships with a complete `render.yaml`. One commit + a few clicks
and you get a live backend, frontend, and persistent Chroma vector store.

## Prerequisites

1. A GitHub repo containing this project.
2. A free Render account ( https://render.com ).
3. (Optional) An OpenAI or Anthropic API key for the LLM. The system works
   without one (template fallback), but the headline answer quality is much
   better with a real LLM.

## Step-by-step

1. **Push to GitHub.**
   ```powershell
   cd C:\Users\harichandana.p.PRODAPT\Documents\capstone\AFDE_AI-Powered-Smart-Grid-Energy-Intelligence-Assistant_capstone
   git add .
   git commit -m "capstone: complete build"
   git push origin main
   ```

2. **Render dashboard → New → Blueprint.** Connect your GitHub account,
   pick the repo, and accept the detected `render.yaml`. Render queues
   three resources:
   - Web service `smart-grid-backend`
   - Static site `smart-grid-frontend`
   - Persistent disk `chroma-disk` (1 GB)

3. **Set secrets** (Backend → Environment → Add Environment Variable):

   | Key | Value |
   |---|---|
   | `OPENAI_API_KEY` *(or ANTHROPIC_API_KEY)* | your real key |
   | `JWT_SECRET` | a 32+ char random string |
   | `CORS_ORIGINS` | the frontend URL Render assigned, e.g. `https://smart-grid-frontend.onrender.com` |

   Click **Save** and trigger a manual deploy if not auto-triggered.

4. **Wait for the first deploy.** Build takes ~6–8 minutes because the ML stack
   (torch, chromadb, sentence-transformers) is heavy. Subsequent deploys cache.

5. **Open the backend healthcheck.** Visit
   `https://smart-grid-backend.onrender.com/api/v1/health` → should return
   `{"status":"ok", ...}` once the Render banner shows "Live".

6. **Open the frontend.** Visit `https://smart-grid-frontend.onrender.com`.
   You'll see the dashboard with the gauge at "no data yet".

7. **First-run ETL.** Open the **ETL** tab in the frontend:
   - Drag-drop `smart_grid_stability_augmented.csv` into the upload zone
   - Click **Run ETL** on the row — the backend ingests + embeds it
   - Repeat for `household_power_consumption.csv` and
     `electric_power_consumption.csv` if you have them
   - Refresh the Dashboard tab — the gauge now shows a real score

## How the persistent disk works

Render's `chroma-disk` mounts at `/var/data/chroma`. We point both
`CHROMA_PERSIST_DIR` and `DATA_DIR` underneath it, so:

- Embeddings survive restarts and redeploys
- Uploaded CSVs survive restarts and redeploys
- A redeploy of the **code** does not require re-running ETL

If you ever need a clean slate, delete the disk in the Render dashboard.

## Cold start

The free tier sleeps after 15 minutes of inactivity. First request after
sleep takes ~30 s (FastAPI boot + Chroma load + sentence-transformers
model load). For a demo, hit `/api/v1/health` a minute before the panel
starts to warm the service.

## Going to paid tier

For a real organization, upgrade the backend to **Starter** ($7/mo):
- No sleep / no cold start
- 0.5 vCPU + 512 MB RAM (room for the ML stack)
- Custom domain + automatic SSL

Frontend stays free (static sites have no sleep).

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Build fails on `chromadb` install | Python version mismatch | Confirm `PYTHON_VERSION=3.11.10` is set |
| `/api/v1/health` returns "degraded" | LLM env vars missing | Set `OPENAI_API_KEY` *or* set `LLM_PROVIDER=template` (no LLM) |
| Frontend cannot reach backend | CORS / wrong URL | Verify `VITE_API_URL` in frontend env matches the backend service URL |
| Dashboard is empty after deploy | No data ingested yet | Run ETL once via the ETL tab |
| 401 on `/incidents` | Multi-tenancy on without token | Either set `MULTI_TENANCY_ENABLED=false` or paste a JWT in Settings |

## Local production build (sanity-check before deploy)

```powershell
# Backend — same install Render runs
cd backend
pip install -r requirements.txt
pip install -r requirements-ml.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Frontend — same build Render runs
cd ..\frontend
npm ci
npm run build
npm run preview      # serves dist/ on http://localhost:4173
```

If both work locally, Render will work.
