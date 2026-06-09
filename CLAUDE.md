# CLAUDE.md — NSDL Portfolio Tracker

> This file is the single source of truth for Claude Code. Read it fully before writing any code,
> creating any file, or running any command. Every architectural decision, naming convention, and
> workflow rule here was deliberate. Follow it exactly.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Tech Stack](#2-tech-stack)
3. [Architecture](#3-architecture)
4. [Project Structure](#4-project-structure)
5. [Database Schema](#5-database-schema)
6. [LangGraph Agent Design](#6-langgraph-agent-design)
7. [API Design](#7-api-design)
8. [Frontend Design Principles](#8-frontend-design-principles)
9. [Skills to Use](#9-skills-to-use)
10. [Guiding Principles](#10-guiding-principles)
11. [Implementation Steps & Git Workflow](#11-implementation-steps--git-workflow)
12. [Environment Variables](#12-environment-variables)
13. [Current Status](#13-current-status)

---

## 1. Project Overview

A personal investment portfolio tracker that ingests NSDL CAS (Consolidated Account Statement) PDF
files and provides deep analytics, AI-powered recommendations, and exportable reports — similar to
Kuvera.in but with significantly richer analytics and a multi-agent AI backbone.

### Core capabilities

- Parse NSDL CAS PDF statements and extract all mutual fund holdings and transaction history
- Fetch real-time and historical NAV data from AMFI / MFApi
- Compute institutional-grade metrics: XIRR, trailing returns (1W/1M/3M/6M/1Y/3Y/5Y), rolling
  returns, Alpha, Beta, Sharpe ratio, Sortino ratio, Max Drawdown, Expense Ratio
- Multi-agent AI workflow powered by Gemini 1.5 Pro via Google AI Studio
- Natural-language chat interface for portfolio queries and report generation
- Export to Excel, Word (.docx), and PowerPoint (.pptx)
- Trailing returns comparison table across all portfolio funds side by side
- Fund detail pages with full metrics and risk comparison across funds
- Multi-user support with Supabase Auth and Row Level Security

### Target user

An Indian retail investor who holds mutual funds through multiple AMCs, uploads their CAS monthly,
and wants institutional-level analysis without paying for a wealth manager.

---

## 2. Tech Stack

### Backend
| Layer | Choice | Reason |
|---|---|---|
| Language | Python 3.11+ | Best ecosystem for financial math and LLM tooling |
| Web framework | FastAPI | Async support, auto-generated OpenAPI docs |
| Agent framework | LangGraph | Stateful multi-agent graphs with conditional routing |
| LLM | Gemini 1.5 Pro (Google AI Studio) | 1M token context, generous free tier |
| PDF parsing | pdfplumber | Reliable text and table extraction from NSDL PDFs |
| Financial math | pandas, numpy, scipy | XIRR, rolling returns, regression for Alpha/Beta |
| Scheduling | APScheduler | Daily NAV sync job running inside FastAPI |
| Auth validation | python-jose | Validate Supabase JWTs in FastAPI middleware |
| HTTP client | httpx | Async HTTP calls to external APIs |
| Export — Excel | openpyxl | .xlsx generation with charts |
| Export — Word | python-docx | .docx generation |
| Export — PPT | python-pptx | .pptx generation |

### Frontend
| Layer | Choice |
|---|---|
| Framework | Next.js 14 (App Router) |
| Language | TypeScript |
| Styling | Tailwind CSS |
| Charts | Recharts |
| Data fetching | React Query (TanStack Query) |
| Auth client | Supabase JS client (@supabase/ssr) |
| Forms | React Hook Form + Zod |
| File upload | react-dropzone |

### Data / Infrastructure
| Layer | Choice |
|---|---|
| Database | Supabase (PostgreSQL) |
| Auth | Supabase Auth (email/password + Google OAuth) |
| File storage | Supabase Storage (CAS PDFs) |
| Row-level security | Enabled on all tables |
| NAV data | MFApi.in (primary), AMFI website (fallback) |
| Benchmark data | yfinance (Nifty 50 TRI, Sensex) |
| Deployment | Vercel (frontend), Railway or Render (backend) |

---

## 3. Architecture

### Three-layer system

```
┌─────────────────────────────────────────────────┐
│              FRONTEND (Next.js)                  │
│  Dashboard · Fund Detail · AI Chat · Auth        │
│  Recharts · Tailwind · React Query · Supabase JS │
└─────────────────┬───────────────────────────────┘
                  │  REST + WebSocket
┌─────────────────▼───────────────────────────────┐
│           BACKEND (FastAPI + LangGraph)           │
│  /auth  /portfolio  /analytics  /agent/run        │
│                                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │           LangGraph Agent Graph              │ │
│  │  intent_classifier → [conditional routing]  │ │
│  │  → cas_parser | data_fetcher | analytics    │ │
│  │  → recommender | export                     │ │
│  │  → state_update → quality_check             │ │
│  │  → synthesizer → supabase_write → END       │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  APScheduler: daily NAV sync at 11:00 PM IST      │
└─────────────────┬───────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────┐
│                DATA LAYER                         │
│  Supabase PostgreSQL · Supabase Auth              │
│  Supabase Storage (PDFs)                          │
│  Google AI Studio (Gemini 1.5 Pro)               │
│  MFApi.in · AMFI · yfinance                      │
└─────────────────────────────────────────────────┘
```

### Multi-agent graph (LangGraph)

Gemini is called in exactly three nodes:

1. **intent_classifier** — lightweight call to parse user prompt into a structured intent enum
2. **recommender** — heavy call with full metrics dict as context; produces investment narrative
3. **quality_check** — validation call to verify output coherence before returning to user

All other nodes (cas_parser, data_fetcher, analytics, export, synthesizer) are pure Python — no LLM.

### LangGraph state object

```python
class PortfolioState(TypedDict):
    user_id: str
    user_prompt: str
    intent: str                   # set by intent_classifier
    cas_data: dict                # set by cas_parser
    nav_data: dict                # set by data_fetcher
    metrics: dict                 # set by analytics
    recommendation: str           # set by recommender
    export_path: str | None       # set by export
    quality_check_passed: bool    # set by quality_check
    retry_count: int              # incremented on quality fail
    final_response: dict          # set by synthesizer
    error: str | None
```

### Routing logic

```python
INTENT_ROUTES = {
    "new_cas_upload":      "cas_parser",
    "refresh_data":        "data_fetcher",
    "get_analytics":       "analytics",
    "get_recommendation":  "recommender",
    "export_report":       "export",
}
MAX_RETRIES = 1
```

---

## 4. Project Structure

```
portfolio-tracker/
├── CLAUDE.md                        ← this file
├── .env.example
├── .gitignore
│
├── backend/
│   ├── main.py                      ← FastAPI app, CORS, lifespan
│   ├── requirements.txt
│   ├── .env
│   │
│   ├── routers/
│   │   ├── auth.py                  ← /auth/me, /auth/validate
│   │   ├── portfolio.py             ← /portfolio/upload, /portfolio/list
│   │   ├── analytics.py             ← /analytics/{fund_id}, /analytics/compare
│   │   └── agent.py                 ← /agent/run (POST), /agent/stream (WS)
│   │
│   ├── agents/
│   │   ├── graph.py                 ← LangGraph graph definition and compilation
│   │   ├── state.py                 ← PortfolioState TypedDict
│   │   └── nodes/
│   │       ├── intent_classifier.py ← Gemini call #1
│   │       ├── cas_parser.py        ← pdfplumber extraction
│   │       ├── data_fetcher.py      ← MFApi + yfinance
│   │       ├── analytics.py         ← pandas/scipy metrics
│   │       ├── recommender.py       ← Gemini call #2
│   │       ├── export.py            ← openpyxl / python-docx / python-pptx
│   │       ├── quality_check.py     ← Gemini call #3
│   │       └── synthesizer.py       ← assembles final_response
│   │
│   ├── services/
│   │   ├── supabase_client.py       ← supabase-py init, typed query helpers
│   │   ├── gemini_client.py         ← Google AI Studio client wrapper
│   │   ├── nav_fetcher.py           ← MFApi + AMFI fetch logic
│   │   └── auth_middleware.py       ← JWT validation via python-jose
│   │
│   └── scheduler/
│       └── daily_sync.py            ← APScheduler job: NAV sync + metrics recompute
│
└── frontend/
    ├── package.json
    ├── tsconfig.json
    ├── tailwind.config.ts
    ├── next.config.ts
    │
    ├── app/
    │   ├── layout.tsx               ← root layout, fonts, providers
    │   ├── page.tsx                 ← landing / redirect to dashboard
    │   ├── (auth)/
    │   │   ├── login/page.tsx
    │   │   └── signup/page.tsx
    │   ├── dashboard/
    │   │   └── page.tsx             ← portfolio overview, total value, XIRR, pie chart
    │   ├── fund/
    │   │   └── [id]/page.tsx        ← fund detail: metrics, rolling returns, trailing table
    │   ├── compare/
    │   │   └── page.tsx             ← risk metrics comparison across funds
    │   └── assistant/
    │       └── page.tsx             ← AI chat + export UI
    │
    ├── components/
    │   ├── ui/                      ← reusable primitives (Button, Card, Badge, Table)
    │   ├── charts/
    │   │   ├── PortfolioPieChart.tsx
    │   │   ├── RollingReturnsChart.tsx
    │   │   ├── TrailingReturnsTable.tsx
    │   │   └── RiskRadarChart.tsx
    │   ├── portfolio/
    │   │   ├── FundCard.tsx
    │   │   ├── MetricBadge.tsx
    │   │   └── CASUploadDropzone.tsx
    │   └── assistant/
    │       ├── ChatPanel.tsx
    │       └── ExportButton.tsx
    │
    └── lib/
        ├── supabase.ts              ← browser + server Supabase clients
        ├── api.ts                   ← typed fetch helpers for FastAPI
        └── formatters.ts            ← currency, percentage, date formatters
```

---

## 5. Database Schema

All tables must have `user_id uuid references auth.users(id)` and Row Level Security enabled.
Create all tables and RLS policies in the Supabase dashboard SQL editor before running the backend.

```sql
-- Users profile (extends Supabase auth.users)
create table public.profiles (
  id uuid references auth.users(id) primary key,
  full_name text,
  pan_last4 text,
  created_at timestamptz default now()
);

-- CAS upload log
create table public.cas_uploads (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) not null,
  storage_path text not null,        -- Supabase Storage path
  statement_date date,
  parsed_at timestamptz,
  status text default 'pending',     -- pending | parsed | failed
  created_at timestamptz default now()
);

-- Fund holdings (one row per fund per user)
create table public.holdings (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) not null,
  isin text not null,
  scheme_name text not null,
  amfi_code text,
  folio_number text,
  units_held numeric(18,4),
  average_nav numeric(12,4),
  current_nav numeric(12,4),
  current_value numeric(18,2),
  invested_value numeric(18,2),
  last_updated timestamptz,
  unique(user_id, isin)
);

-- Full transaction history
create table public.transactions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) not null,
  isin text not null,
  folio_number text,
  transaction_date date not null,
  transaction_type text not null,    -- purchase | redemption | switch_in | switch_out | dividend
  amount numeric(18,2),
  units numeric(18,4),
  nav numeric(12,4),
  created_at timestamptz default now()
);

-- Historical NAV (fetched from MFApi, one row per fund per date)
create table public.nav_history (
  id uuid primary key default gen_random_uuid(),
  isin text not null,
  amfi_code text,
  nav_date date not null,
  nav numeric(12,4) not null,
  unique(isin, nav_date)
);
-- Note: nav_history is NOT user-scoped. It is shared across all users.
-- RLS: allow read for authenticated users, no write from client.

-- Benchmark index data (Nifty 50 TRI, Sensex)
create table public.benchmark_history (
  id uuid primary key default gen_random_uuid(),
  index_name text not null,          -- 'nifty50_tri' | 'sensex'
  price_date date not null,
  close_price numeric(12,4) not null,
  unique(index_name, price_date)
);

-- Computed metrics cache (refreshed nightly by scheduler)
create table public.fund_metrics (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) not null,
  isin text not null,
  xirr numeric(8,4),
  trailing_1w numeric(8,4),
  trailing_1m numeric(8,4),
  trailing_3m numeric(8,4),
  trailing_6m numeric(8,4),
  trailing_1y numeric(8,4),
  trailing_3y numeric(8,4),
  trailing_5y numeric(8,4),
  alpha numeric(8,4),
  beta numeric(8,4),
  sharpe_ratio numeric(8,4),
  sortino_ratio numeric(8,4),
  max_drawdown numeric(8,4),
  expense_ratio numeric(6,4),
  computed_at timestamptz default now(),
  unique(user_id, isin)
);

-- AI-generated reports / recommendations
create table public.reports (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) not null,
  prompt text not null,
  intent text not null,
  response_text text,
  export_path text,                  -- Supabase Storage path if exported
  created_at timestamptz default now()
);

-- RLS policies (apply to all user-scoped tables)
-- Example for holdings:
alter table public.holdings enable row level security;
create policy "Users can only access own holdings"
  on public.holdings for all
  using (auth.uid() = user_id);
-- Repeat for: cas_uploads, transactions, fund_metrics, reports, profiles
```

---

## 6. LangGraph Agent Design

### Full graph implementation pattern

```python
# backend/agents/graph.py
from langgraph.graph import StateGraph, END
from agents.state import PortfolioState
from agents.nodes import (
    intent_classifier, cas_parser, data_fetcher,
    analytics, recommender, export,
    quality_check, synthesizer, supabase_write
)

def route_by_intent(state: PortfolioState) -> str:
    routes = {
        "new_cas_upload":      "cas_parser",
        "refresh_data":        "data_fetcher",
        "get_analytics":       "analytics",
        "get_recommendation":  "recommender",
        "export_report":       "export",
    }
    return routes.get(state["intent"], END)

def route_quality_check(state: PortfolioState) -> str:
    if state["quality_check_passed"]:
        return "synthesizer"
    if state["retry_count"] >= 1:
        return "synthesizer"      # surface best-effort after one retry
    return "state_update"         # retry

def build_graph() -> StateGraph:
    g = StateGraph(PortfolioState)

    g.add_node("intent_classifier", intent_classifier.run)
    g.add_node("cas_parser",        cas_parser.run)
    g.add_node("data_fetcher",      data_fetcher.run)
    g.add_node("analytics",         analytics.run)
    g.add_node("recommender",       recommender.run)
    g.add_node("export",            export.run)
    g.add_node("state_update",      lambda s: s)   # passthrough; nodes update state directly
    g.add_node("quality_check",     quality_check.run)
    g.add_node("synthesizer",       synthesizer.run)
    g.add_node("supabase_write",    supabase_write.run)

    g.set_entry_point("intent_classifier")
    g.add_conditional_edges("intent_classifier", route_by_intent)

    for node in ["cas_parser", "data_fetcher", "analytics", "recommender", "export"]:
        g.add_edge(node, "state_update")

    g.add_edge("state_update", "quality_check")
    g.add_conditional_edges("quality_check", route_quality_check)
    g.add_edge("synthesizer", "supabase_write")
    g.add_edge("supabase_write", END)

    return g.compile()

portfolio_graph = build_graph()
```

### Gemini client wrapper

```python
# backend/services/gemini_client.py
import google.generativeai as genai
from functools import lru_cache
import os

@lru_cache(maxsize=1)
def get_gemini_model():
    genai.configure(api_key=os.environ["GOOGLE_AI_STUDIO_API_KEY"])
    return genai.GenerativeModel("gemini-1.5-pro")

async def call_gemini(prompt: str, system: str = "") -> str:
    model = get_gemini_model()
    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    response = await model.generate_content_async(full_prompt)
    return response.text
```

### Analytics node — key formulas

```python
# backend/agents/nodes/analytics.py
import numpy as np
from scipy.optimize import brentq
import pandas as pd

def compute_xirr(transactions: list[dict], current_value: float) -> float:
    """XIRR using scipy brentq. transactions = [{date, amount}] where
    purchases are negative, redemptions positive. current_value is positive."""
    cashflows = [(t["date"], -t["amount"]) for t in transactions]
    cashflows.append((date.today(), current_value))
    # ... brentq implementation on NPV function

def compute_trailing_return(nav_history: pd.Series, days: int) -> float:
    """Point-to-point CAGR over trailing N days."""
    end_nav = nav_history.iloc[-1]
    start_nav = nav_history.iloc[-days] if len(nav_history) > days else nav_history.iloc[0]
    years = days / 365
    return (end_nav / start_nav) ** (1 / years) - 1

def compute_alpha_beta(fund_returns: pd.Series, benchmark_returns: pd.Series) -> tuple:
    """OLS regression of fund returns on benchmark returns."""
    from scipy.stats import linregress
    slope, intercept, *_ = linregress(benchmark_returns, fund_returns)
    return intercept * 252, slope   # annualised alpha, beta

def compute_sharpe(returns: pd.Series, risk_free_rate: float = 0.065) -> float:
    excess = returns - risk_free_rate / 252
    return (excess.mean() / excess.std()) * np.sqrt(252)

def compute_sortino(returns: pd.Series, risk_free_rate: float = 0.065) -> float:
    excess = returns - risk_free_rate / 252
    downside = excess[excess < 0].std()
    return (excess.mean() / downside) * np.sqrt(252) if downside > 0 else np.nan

def compute_max_drawdown(nav_series: pd.Series) -> float:
    roll_max = nav_series.cummax()
    drawdown = nav_series / roll_max - 1
    return drawdown.min()
```

---

## 7. API Design

All routes require `Authorization: Bearer <supabase_jwt>` header except `/health`.

### Backend routes

```
GET  /health                          → {status: "ok"}

POST /portfolio/upload                → upload CAS PDF, trigger cas_parser agent
     body: multipart/form-data (file)
     response: {upload_id, status}

GET  /portfolio/holdings              → list all holdings with current value
GET  /portfolio/summary               → total value, XIRR, gain/loss, allocation

GET  /analytics/{isin}               → full metrics for one fund
GET  /analytics/compare              → risk metrics for all portfolio funds
     query: ?isins=isin1,isin2,...

GET  /analytics/trailing-returns     → trailing returns table for all funds
     response: [{isin, name, 1w, 1m, 3m, 6m, 1y, 3y, 5y}]

POST /agent/run                       → run LangGraph graph, return final_response
     body: {prompt: string}
     response: {response_text, export_url?, report_id}

WS   /agent/stream                    → streaming version of /agent/run
```

### Frontend API conventions

- All API calls go through `lib/api.ts` which attaches the Supabase JWT automatically
- Use React Query for all GET requests with sensible stale times:
  - Holdings/summary: 5 minutes
  - Metrics: 1 hour (refreshed nightly anyway)
  - NAV history: 24 hours
- Mutations (upload, agent run) use React Query's `useMutation`

---

## 8. Frontend Design Principles

**Before writing any frontend code, read `/mnt/skills/public/frontend-design/SKILL.md`.**

### Visual identity

This is a financial intelligence tool for a sophisticated Indian investor. The design language should
feel precise, data-dense, and trustworthy — closer to a Bloomberg terminal than a consumer app.

- **Color palette:**
  - Background: `#0F1117` (near-black, not pure black)
  - Surface: `#1A1D27`
  - Border: `#2A2D3A`
  - Primary accent: `#4F8EF7` (cool blue — trust, data)
  - Positive / gain: `#22C55E` (green)
  - Negative / loss: `#EF4444` (red)
  - Warning: `#F59E0B` (amber)
  - Text primary: `#F1F5F9`
  - Text secondary: `#94A3B8`

- **Typography:** Use Inter for UI text (data tables, labels, numbers). Use a monospace font
  (`JetBrains Mono` or `Fira Code`) for all numeric values — this ensures decimal alignment in
  tables and gives the interface a terminal-adjacent precision.

- **Trailing returns table:** Color-code every cell relative to the category average — green if
  above, red if below. Use `tabular-nums` for all number cells.

- **Charts:** Dark background, grid lines at 20% opacity, no chart borders. Recharts with custom
  tooltip styles that match the dark theme.

- **Signature element:** A subtle animated sparkline on each fund card that shows 12-month NAV
  movement — no axes, no labels, just the curve. This is the one motion element in the UI.

### Component rules

- No default Tailwind component libraries (no shadcn, no DaisyUI). Build primitives from scratch
  in `components/ui/`.
- Every number on screen must use `formatters.ts` — never inline `toFixed()` calls.
- All monetary values display in Indian number format with ₹ symbol (e.g., ₹12,34,567).
- Percentages always show 2 decimal places with a + or − prefix.
- Loading states use skeleton screens, never spinners on the main content area.
- Empty states are actionable — they tell the user exactly what to do next.

---

## 9. Skills to Use

Claude Code must read the relevant skill file before implementing that feature.
Skill files live at `/mnt/skills/public/<name>/SKILL.md`.

| Feature | Skill file to read first |
|---|---|
| Any frontend UI, layout, visual design | `frontend-design/SKILL.md` |
| Excel export (.xlsx) | `xlsx/SKILL.md` |
| Word export (.docx) | `docx/SKILL.md` |
| PowerPoint export (.pptx) | `pptx/SKILL.md` |
| Reading/parsing uploaded PDF files | `pdf-reading/SKILL.md` |
| Creating PDF reports | `pdf/SKILL.md` |

Do not attempt any of these features without reading the skill first. The skills encode
environment-specific constraints and available libraries that override general knowledge.

---

## 10. Guiding Principles

### Code quality
- Python: type hints on every function signature. Use `pydantic` models for all FastAPI request/response bodies.
- TypeScript: no `any`. All API responses have typed interfaces in `lib/api.ts`.
- No business logic in route handlers — handlers call services, services call agents.
- Every agent node is a pure function: `(state: PortfolioState) -> PortfolioState`. No side effects except the `supabase_write` node.

### Security
- Never log or store raw CAS PDFs longer than needed. Delete from Supabase Storage after parsing.
- Never expose Supabase service role key to the frontend. Only the anon key.
- All FastAPI routes validate the Supabase JWT in `auth_middleware.py` before touching any data.
- RLS is the last line of defense — never rely solely on application-level auth checks.

### Financial accuracy
- XIRR must use the actual transaction dates and amounts from the CAS — never approximate.
- Trailing returns are CAGR (not simple returns) for periods over 1 year.
- Risk-free rate for Sharpe/Sortino: use the current 91-day Indian T-bill rate (hardcode to 6.5% initially, make it configurable later).
- Benchmark for Alpha/Beta: Nifty 50 TRI (Total Return Index), not price index.

### Error handling
- If the CAS parser fails on a page, log the error and continue — partial data is better than no data.
- If MFApi is down, fall back to AMFI's direct NAV text file.
- If Gemini returns an error, the quality_check node sets `quality_check_passed = False` and
  the synthesizer returns a best-effort response from the analytics node output alone.
- Never surface raw Python tracebacks to the frontend. Map all errors to user-readable messages.

### Testing
- Each analytics function in `agents/nodes/analytics.py` must have a unit test with known inputs
  and expected outputs (test against a manually calculated XIRR, Sharpe, etc.).
- CAS parser tests use sample PDF fixtures stored in `backend/tests/fixtures/`.
- Integration tests for the full LangGraph graph use a mocked Gemini client.

---

## 11. Implementation Steps & Git Workflow

### Git conventions

- Branch naming: `step/<N>-<short-description>` (e.g., `step/1-project-scaffold`)
- Commit message format: `[Step N] Short description of what was done`
- After completing each step: run any relevant tests, then commit and push to the branch.
- Merge to `main` only after each step is fully working end-to-end.
- Never commit `.env` files. Always commit `.env.example` with placeholder values.

---

### Step 1 — Project scaffold & environment
**Branch:** `step/1-project-scaffold`

- [ ] Create `portfolio-tracker/` root directory
- [ ] Create `backend/` with `main.py`, `requirements.txt`, `.env.example`
- [ ] Create `frontend/` with `npx create-next-app@latest` (TypeScript, Tailwind, App Router)
- [ ] Set up `.gitignore` (Python venv, node_modules, .env, __pycache__, .next)
- [ ] Install backend deps: `fastapi uvicorn pdfplumber pandas numpy scipy langgraph google-generativeai supabase python-jose httpx openpyxl python-docx python-pptx apscheduler pydantic`
- [ ] Install frontend deps: `@supabase/ssr @supabase/supabase-js @tanstack/react-query recharts react-dropzone react-hook-form zod`
- [ ] Create `backend/main.py` with FastAPI app, CORS configured for localhost:3000, `/health` route
- [ ] Create `frontend/lib/supabase.ts` with browser and server Supabase client setup
- [ ] Verify: `uvicorn main:app --reload` starts, `npm run dev` starts, `/health` returns 200
- [ ] **Commit:** `[Step 1] Project scaffold — FastAPI + Next.js + Supabase client setup`

---

### Step 2 — Supabase database schema & auth
**Branch:** `step/2-supabase-schema-auth`

- [ ] Run all CREATE TABLE statements from Section 5 in Supabase SQL editor
- [ ] Enable RLS and create policies for all user-scoped tables
- [ ] Create Supabase Storage bucket: `cas-pdfs` (private)
- [ ] Implement `backend/services/supabase_client.py` — init supabase-py with service role key
- [ ] Implement `backend/services/auth_middleware.py` — FastAPI dependency that validates JWT
- [ ] Implement `backend/routers/auth.py` — `GET /auth/me` returns user profile
- [ ] Implement `frontend/app/(auth)/login/page.tsx` and `signup/page.tsx`
- [ ] Implement `frontend/middleware.ts` — redirect unauthenticated users to /login
- [ ] Test: sign up, log in, verify JWT validation works in FastAPI
- [ ] **Commit:** `[Step 2] Supabase schema, RLS, auth flow — login/signup working`

---

### Step 3 — CAS PDF parser & upload
**Branch:** `step/3-cas-parser-upload`

- [ ] **Read `pdf-reading/SKILL.md` before writing any parsing code**
- [ ] Implement `backend/agents/nodes/cas_parser.py` using pdfplumber
  - Extract fund names, ISIN/AMFI codes, folio numbers
  - Extract all transactions (date, type, amount, units, NAV)
  - Extract current units held per fund
  - Handle multi-page PDFs and varying AMC formatting
- [ ] Write unit tests with at least one sample CAS PDF fixture
- [ ] Implement `backend/routers/portfolio.py` — `POST /portfolio/upload`
  - Receive PDF, upload to Supabase Storage
  - Trigger cas_parser, write results to `holdings` and `transactions` tables
- [ ] Implement `frontend/components/portfolio/CASUploadDropzone.tsx`
  - Read `frontend-design/SKILL.md` before styling
  - Drag-and-drop or click-to-upload, progress indicator, success/error states
- [ ] Test: upload a real CAS PDF, verify holdings and transactions appear in Supabase
- [ ] **Commit:** `[Step 3] CAS parser + upload flow — holdings and transactions stored`

---

### Step 4 — NAV data pipeline & daily sync
**Branch:** `step/4-nav-data-pipeline`

- [ ] Implement `backend/services/nav_fetcher.py`
  - Fetch all NAV history for an ISIN from MFApi.in
  - Fallback: parse AMFI NAV text file
  - Fetch Nifty 50 TRI from yfinance
- [ ] Implement `backend/agents/nodes/data_fetcher.py` — fetches and stores nav_history and benchmark_history rows
- [ ] Implement `backend/scheduler/daily_sync.py`
  - APScheduler job at 11:00 PM IST
  - For each unique ISIN across all users, fetch latest NAV
  - Trigger metrics recompute for all affected users
- [ ] Register scheduler in `backend/main.py` lifespan
- [ ] Test: manually trigger sync, verify nav_history rows appear
- [ ] **Commit:** `[Step 4] NAV fetcher + daily sync scheduler — nav_history populating`

---

### Step 5 — Analytics engine
**Branch:** `step/5-analytics-engine`

- [ ] Implement all formulas in `backend/agents/nodes/analytics.py`:
  - XIRR (brentq on NPV function using actual transaction dates)
  - Trailing returns: 1W, 1M, 3M, 6M, 1Y, 3Y, 5Y (CAGR where period > 1Y)
  - Rolling returns (1Y rolling window)
  - Alpha and Beta (OLS regression against Nifty 50 TRI)
  - Sharpe ratio (annualised, risk-free = 6.5%)
  - Sortino ratio (annualised, downside deviation only)
  - Max drawdown
  - Expense ratio (fetch from AMFI scheme metadata)
- [ ] Write unit tests for every formula with known inputs
- [ ] Store computed metrics in `fund_metrics` table
- [ ] Implement `backend/routers/analytics.py`:
  - `GET /analytics/{isin}` — full metrics for one fund
  - `GET /analytics/compare` — side-by-side for all portfolio funds
  - `GET /analytics/trailing-returns` — full trailing table
- [ ] Test: run analytics for a fund, verify numbers against manual calculation
- [ ] **Commit:** `[Step 5] Analytics engine — XIRR, Sharpe, Alpha/Beta, trailing returns`

---

### Step 6 — LangGraph agent graph
**Branch:** `step/6-langgraph-agent-graph`

- [ ] Implement `backend/services/gemini_client.py`
- [ ] Implement `backend/agents/state.py` — `PortfolioState` TypedDict
- [ ] Implement all agent nodes:
  - `intent_classifier.py` — Gemini call, returns structured intent
  - `recommender.py` — Gemini call with metrics context
  - `quality_check.py` — Gemini validation call
  - `synthesizer.py` — assembles `final_response` from state
  - `supabase_write.py` — persists report to `reports` table
- [ ] Implement `backend/agents/graph.py` — full graph with conditional routing
- [ ] Implement `backend/routers/agent.py` — `POST /agent/run`
- [ ] Write integration test with mocked Gemini client
- [ ] Test: send a prompt via POST /agent/run, verify full graph execution
- [ ] **Commit:** `[Step 6] LangGraph multi-agent graph — intent→route→analyze→recommend`

---

### Step 7 — Portfolio dashboard (frontend)
**Branch:** `step/7-portfolio-dashboard`

- [ ] **Read `frontend-design/SKILL.md` before writing any component**
- [ ] Implement `frontend/lib/api.ts` — typed fetch helpers with JWT attachment
- [ ] Implement `frontend/lib/formatters.ts` — Indian currency format, % format, date format
- [ ] Implement `frontend/components/ui/` — Card, Button, Badge, Table, Skeleton primitives
- [ ] Implement `frontend/app/dashboard/page.tsx`:
  - Total portfolio value, total invested, total gain/loss with %
  - Overall XIRR
  - Asset allocation pie chart (Recharts)
  - Fund cards list with mini sparkline (12-month NAV curve, no axes)
  - CAS upload dropzone if no holdings yet
- [ ] Apply dark theme from Section 8, monospace for all numbers
- [ ] Test: dashboard renders with real data, charts display correctly
- [ ] **Commit:** `[Step 7] Portfolio dashboard — overview, pie chart, fund cards, sparklines`

---

### Step 8 — Fund detail page & trailing returns table
**Branch:** `step/8-fund-detail-trailing-returns`

- [ ] **Read `frontend-design/SKILL.md` before writing any component**
- [ ] Implement `frontend/app/fund/[id]/page.tsx`:
  - Fund name, AMC, category, ISIN
  - Current value, invested value, gain/loss, XIRR
  - Metrics grid: Alpha, Beta, Sharpe, Sortino, Max Drawdown, Expense Ratio
  - Rolling returns chart (Recharts area chart, 5-year window)
  - Trailing returns table for this fund (1W/1M/3M/6M/1Y/3Y/5Y)
- [ ] Implement `frontend/components/charts/TrailingReturnsTable.tsx`
  - All portfolio funds side by side
  - Color-code cells: green if positive, red if negative
  - Monospace numbers, sortable columns
- [ ] Implement `frontend/components/charts/RollingReturnsChart.tsx`
- [ ] Test: click a fund card from dashboard, verify all metrics and charts load
- [ ] **Commit:** `[Step 8] Fund detail page — metrics, rolling chart, trailing returns table`

---

### Step 9 — Risk comparison page
**Branch:** `step/9-risk-comparison`

- [ ] **Read `frontend-design/SKILL.md` before writing any component**
- [ ] Implement `frontend/app/compare/page.tsx`
  - Multi-select funds from portfolio
  - Side-by-side risk metrics table: Alpha, Beta, Sharpe, Sortino, Max Drawdown, Expense Ratio
  - Radar chart (Recharts) overlaying risk profiles of selected funds
  - Color-code each fund consistently across table and chart
- [ ] Implement `frontend/components/charts/RiskRadarChart.tsx`
- [ ] Test: select 3 funds, verify radar chart and table render correctly
- [ ] **Commit:** `[Step 9] Risk comparison page — radar chart + side-by-side metrics table`

---

### Step 10 — AI assistant & export
**Branch:** `step/10-ai-assistant-export`

- [ ] **Read `xlsx/SKILL.md`, `docx/SKILL.md`, `pptx/SKILL.md` before building export nodes**
- [ ] Flesh out `backend/agents/nodes/export.py`:
  - Excel: portfolio summary sheet + per-fund metrics sheet + trailing returns sheet with charts
  - Word: narrative report with metrics tables and Gemini-generated analysis sections
  - PowerPoint: executive summary deck — one slide per fund, summary slide, recommendation slide
- [ ] Store exported files in Supabase Storage, return signed URL
- [ ] Implement `frontend/app/assistant/page.tsx`:
  - Chat input with message history
  - Renders Gemini recommendation text with markdown formatting
  - Export buttons (Excel / Word / PPT) that appear when the response includes an export
  - Download via signed Supabase Storage URL
- [ ] Implement `frontend/components/assistant/ChatPanel.tsx`
- [ ] Implement `frontend/components/assistant/ExportButton.tsx`
- [ ] Test: prompt "generate an Excel report of my portfolio", verify file downloads
- [ ] **Commit:** `[Step 10] AI assistant chat + Excel/Word/PPT export pipeline`

---

### Step 11 — Polish, error handling & deployment
**Branch:** `step/11-polish-deploy`

- [ ] Add global error boundary in Next.js layout
- [ ] Add loading skeletons to all data-fetching pages
- [ ] Add empty states with clear CTAs on all pages
- [ ] Ensure all monetary and percentage values use `formatters.ts` consistently
- [ ] Implement rate limiting on `/agent/run` (max 10 requests per user per hour)
- [ ] Add backend health check that verifies Supabase and Gemini connectivity
- [ ] Write `README.md` with local setup instructions
- [ ] Deploy backend to Railway (set all env vars)
- [ ] Deploy frontend to Vercel (set all env vars)
- [ ] Run end-to-end smoke test on production URLs
- [ ] **Commit:** `[Step 11] Production polish — error handling, empty states, deployed`

---

## 12. Environment Variables

### Backend (`backend/.env`)
```
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret

# Google AI Studio
GOOGLE_AI_STUDIO_API_KEY=your-google-ai-studio-key

# App
FRONTEND_URL=http://localhost:3000
ENVIRONMENT=development
RISK_FREE_RATE=0.065
```

### Frontend (`frontend/.env.local`)
```
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### `backend/.env.example` and `frontend/.env.example`
Always keep these up to date with placeholder values. Commit them. Never commit the real `.env`.

---

## 13. Current Status

**Project phase:** Planning complete, implementation not yet started.

**Decisions made and locked:**
- Tech stack finalized (FastAPI, Next.js, Supabase, LangGraph, Gemini 1.5 Pro)
- Multi-agent architecture with 5 sub-agents + orchestration nodes
- LangGraph state object structure defined
- Database schema designed with RLS
- 11-step implementation plan with git commit points

**Next immediate action:**
Start with Step 1 — create the project scaffold, get FastAPI and Next.js both running locally,
and verify the `/health` endpoint before doing anything else.

**Not yet decided (decide when you reach that step):**
- Exact NSDL CAS PDF format edge cases — discover during Step 3
- Whether to use WebSockets or polling for the AI assistant chat — decide in Step 10
- Production hosting: Railway vs Render for the backend — decide in Step 11

---

*Last updated: based on full architecture conversation. Update this file whenever a significant
architectural decision is made during implementation.*
