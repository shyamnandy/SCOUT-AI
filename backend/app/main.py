"""ScoutAI — FastAPI Application Entry Point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.database import init_indexes
from app.routes import auth, chat, topics, newsletters, slots

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup: create database indexes
    await init_indexes()
    print("[OK] ScoutAI API started - database indexes initialized")
    yield
    # Shutdown
    print("[BYE] ScoutAI API shutting down")


app = FastAPI(
    title="ScoutAI API",
    description="Personalized AI News Curator — API Layer",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the frontend origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(topics.router)
app.include_router(newsletters.router)
app.include_router(slots.router)


@app.get("/")
async def root():
    return {
        "app": "ScoutAI API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}
