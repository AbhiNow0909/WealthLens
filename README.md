# WealthLens

A personal investment portfolio tracker that ingests NSDL / CAMS / KFintech **CAS**
(Consolidated Account Statement) PDFs and provides institutional-grade analytics,
AI-powered recommendations, and exportable reports.

- **Parse** mutual fund holdings and transactions from a CAS PDF
- **Fetch** real-time and historical NAVs (MFApi + AMFI) and a Nifty 50 benchmark
- **Compute** XIRR, trailing & rolling returns, Alpha, Beta, Sharpe, Sortino, Max Drawdown
- **Analyse** with a LangGraph multi-agent workflow powered by Gemini
- **Export** Excel / Word / PowerPoint reports

---

## Tech stack

| Layer | Stack |
|---|---|
| Backend | FastAPI · LangGraph · pandas/numpy/scipy · APScheduler · casparser |
| Frontend | Next.js 16 (App Router) · TypeScript · Tailwind v4 · Recharts |
| Data | Supabase (Postgres + Auth + Storage) |
| LLM | Google Gemini (via Google AI Studio) |

---

## Prerequisites

- Python 3.11+
- Node.js 20+
- A Supabase project
- A Google AI Studio API key

---

## 1. Supabase setup

1. Create a Supabase project.
2. In the **SQL editor**, run the schema in `CLAUDE.md` §5 (tables + RLS policies).
3. Create two **private** Storage buckets:
   - `cas-pdfs` — uploaded statements (deleted after parsing)
   - `reports` — generated Excel/Word/PPT files (served via signed URLs)
4. Note your **Project URL**, **anon key**, **service-role key**, and **JWT secret**
   (Settings → API).

> The backend uses the service-role key and bypasses Storage RLS, so no Storage
> policies are needed. Keep both buckets private.

---

## 2. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate           # Windows
# source .venv/bin/activate      # macOS/Linux
pip install -r requirements.txt

cp .env.example .env             # then fill in your values
uvicorn main:app --reload        # http://localhost:8000
```

`.env` keys (see `backend/.env.example`):

| Key | Notes |
|---|---|
| `SUPABASE_URL` | Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Service-role key (server-only, never exposed) |
| `SUPABASE_JWT_SECRET` | Used to validate user JWTs |
| `GOOGLE_AI_STUDIO_API_KEY` | Gemini key |
| `GEMINI_MODEL` | Optional; defaults to `gemini-1.5-pro` (e.g. `gemini-3.1-flash-lite`) |
| `FRONTEND_URL` | Frontend origin for CORS (prod) |
| `RISK_FREE_RATE` | Sharpe/Sortino risk-free rate (default `0.065`) |

Health checks: `GET /health` (liveness) and `GET /health/deep` (Supabase + Gemini).

Run tests:

```bash
.venv\Scripts\python.exe -m pytest tests/ -q
```

---

## 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local       # then fill in your values
npm run dev                      # http://localhost:3000
```

`.env.local` keys (see `frontend/.env.example`):

| Key | Notes |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | anon key (safe for the browser) |
| `NEXT_PUBLIC_API_URL` | Backend base URL (e.g. `http://localhost:8000`) |

---

## 4. Using the app

1. Sign up / log in.
2. Upload a CAS PDF (password = the one used to open it — usually your PAN).
   - For accurate **XIRR**, upload a **Detailed** CAS spanning inception-to-today
     (camsonline.com → CAS → Detailed). A short periodic statement lacks the full
     transaction history XIRR needs.
3. Click **Refresh prices** to populate NAV history and the benchmark.
4. Explore the dashboard, fund detail pages, the Compare page, and the AI Assistant.
5. Export a report (Excel / Word / PowerPoint) from the Assistant page.

---

## 5. Deployment

### Backend → Railway (or Render)

- Root directory: `backend/`
- Start command is provided by `Procfile`: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Set all `backend/.env` variables in the host's environment settings.
- Set `FRONTEND_URL` to your deployed frontend origin (for CORS).

### Frontend → Vercel

- Root directory: `frontend/`
- Framework preset: Next.js (auto-detected).
- Set `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, and
  `NEXT_PUBLIC_API_URL` (your deployed backend URL) in Vercel env settings.

After deploy, smoke-test: sign in → upload CAS → refresh prices → view analytics →
run an assistant query → export a report.

---

## Project layout

```
backend/        FastAPI app, LangGraph agents, analytics, services, scheduler
frontend/       Next.js app (App Router), components, lib
CLAUDE.md       Full architecture & implementation spec
```

The daily NAV sync runs automatically at 23:00 IST via APScheduler while the
backend is running; **Refresh prices** triggers the same sync on demand.
