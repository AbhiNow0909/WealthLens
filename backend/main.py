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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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
    return {"status": "ok"}
