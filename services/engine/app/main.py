"""Chainos Engine FastAPI app. M0 exposes health + an LLM-router probe; later
milestones mount the agent, tickets, publish, and Production read routers."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import __version__
from .config import get_settings
from .llm import Tier, get_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Datastore connections are opened lazily by their repositories.
    yield


app = FastAPI(title="Chainos Engine", version=__version__, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, Any]:
    s = get_settings()
    return {
        "status": "ok",
        "version": __version__,
        "llm_mode": "offline" if s.offline else "live",
        "default_provider": s.llm_default_provider,
    }


class RouterProbe(BaseModel):
    tier: Tier = Tier.LOW
    prompt: str = "Say hello to Chainos."


@app.post("/debug/llm")
def debug_llm(body: RouterProbe) -> dict[str, Any]:
    """Probe the router end-to-end (offline by default). Never exposes keys."""
    resp = get_router().prompt(body.tier, body.prompt)
    return {"model": resp.model, "tier": resp.tier, "text": resp.text}
