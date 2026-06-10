import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
load_dotenv()  # must be before any os.environ reads

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import auth, portfolio, analytics, agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialise scheduler
    from scheduler.daily_sync import start_scheduler
    start_scheduler()
    yield
    # Shutdown: nothing needed yet


app = FastAPI(
    title="WealthLens API",
    version="0.1.0",
    lifespan=lifespan,
)

# Allowed origins: localhost for dev + the deployed frontend (FRONTEND_URL).
_origins = {"http://localhost:3000"}
_frontend_url = os.environ.get("FRONTEND_URL", "").strip().rstrip("/")
if _frontend_url:
    _origins.add(_frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])
app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
app.include_router(agent.router, prefix="/agent", tags=["agent"])


@app.get("/health")
async def health():
    """Liveness — fast, no external calls."""
    return {"status": "ok"}


@app.get("/health/deep")
async def health_deep():
    """Readiness — verifies Supabase and Gemini connectivity."""
    result = {"status": "ok", "supabase": "unknown", "gemini": "unknown"}

    # Supabase: a trivial query
    try:
        from services.supabase_client import get_supabase
        get_supabase().table("holdings").select("id").limit(1).execute()
        result["supabase"] = "ok"
    except Exception as exc:
        result["supabase"] = f"error: {type(exc).__name__}"
        result["status"] = "degraded"

    # Gemini: confirm the model is configured/reachable (no generation call)
    try:
        from services.gemini_client import get_gemini_model
        get_gemini_model()
        result["gemini"] = "ok"
    except Exception as exc:
        result["gemini"] = f"error: {type(exc).__name__}"
        result["status"] = "degraded"

    return result
