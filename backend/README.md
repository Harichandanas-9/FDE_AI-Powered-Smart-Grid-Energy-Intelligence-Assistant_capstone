# Backend — Smart Grid AI Assistant (STEP 2)

FastAPI scaffold. Boots cleanly with `/health` and OpenAPI docs.

> Canonical project spec: `../AI-Powered Smart Grid Energy Intelligence Assistant requirements.txt`
> (also copied into `../requirements/requirement.txt` for reference)

---

## Quick start (Windows PowerShell + VS Code)

```powershell
# 0. Open the project folder in VS Code, then open a terminal (Ctrl + `)
cd backend

# 1. Create venv — Python 3.11 preferred (matches Render). Falls back gracefully.
py -3.11 -m venv venv          # preferred
# OR (works on Python 3.10–3.13):
python -m venv venv

# 2. Activate
venv\Scripts\activate

# 3. Install (upgrade pip first; required for newer wheels)
python -m pip install --upgrade pip
pip install -r requirements.txt

# 4. Configure env
copy .env.example .env

# 5. Run
uvicorn app.main:app --reload --port 8000
```

> **If you see `ModuleNotFoundError: No module named 'pydantic_settings'`**,
> step 3 didn't complete successfully. Check its output for an earlier failure
> (often a wheel build error). Re-run `pip install -r requirements.txt` and
> confirm it ends with `Successfully installed ...` for every package.

## ML / RAG stack — install at STEP 3, not now

```powershell
pip install -r requirements-ml.txt
```

This installs numpy, scipy, pandas, chromadb, sentence-transformers, langchain,
deepeval, etc. ~2–4 minutes on first install; large download.

## Quick start (macOS/Linux)

```bash
cd backend
python3.11 -m venv venv     # or: python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

## Smoke test (no server needed)

From project root:

```powershell
cd backend
venv\Scripts\activate
python ..\scripts\smoke_test_backend.py
```

Expected last line: `[smoke] OK ✓`

## Verify in browser

| URL | Expected |
|---|---|
| http://localhost:8000/             | service banner JSON |
| http://localhost:8000/api/v1/health | `{"status":"ok",...}` |
| http://localhost:8000/docs         | Swagger UI |
| http://localhost:8000/redoc        | ReDoc UI |

## Layout (STEP 2)

```
backend/
├── requirements.txt        # core (install now)
├── requirements-ml.txt     # ML/RAG (install at STEP 3)
├── runtime.txt             # Python version pin for Render
├── .env.example
├── pytest.ini
└── app/
    ├── main.py             # FastAPI factory
    ├── core/
    │   ├── config.py       # pydantic Settings
    │   ├── logging.py      # JSON logger
    │   └── lifespan.py     # async startup/shutdown
    ├── api/
    │   └── routes_health.py
    ├── models/
    │   └── schemas.py
    ├── data/      ⏳ STEP 3
    ├── rag/       ⏳ STEP 4–6
    ├── agents/    ⏳ STEP 7
    ├── services/  ⏳ STEP 8
    ├── evaluation/⏳ STEP 14
    └── utils/
```

Empty packages (`data/`, `rag/`, `agents/`, `services/`, `evaluation/`, `utils/`)
have `__init__.py` files only — populated in the steps shown above.
