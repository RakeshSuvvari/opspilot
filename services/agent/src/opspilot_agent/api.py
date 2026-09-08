from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request

from . import __version__
from .config import Settings
from .runtime import IncidentAgentRuntime
from .schemas import IncidentReport, InvestigationRequest


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings.from_env()
    runtime = IncidentAgentRuntime(settings)
    await runtime.start()
    app.state.settings = settings
    app.state.runtime = runtime
    try:
        yield
    finally:
        await runtime.close()


app = FastAPI(
    title="OpsPilot Agent Service",
    version=__version__,
    lifespan=lifespan,
)


@app.get("/healthz")
async def healthz(request: Request) -> dict[str, object]:
    settings: Settings = request.app.state.settings
    return {
        "status": "ok",
        "version": __version__,
        "model": settings.openai_model,
        "k8s_mcp_url": settings.k8s_mcp_url,
        "rag_enabled": settings.rag_enabled,
        "embedding_model": settings.embedding_model,
    }


@app.get("/v1/tools")
async def tools(request: Request) -> dict[str, object]:
    runtime: IncidentAgentRuntime = request.app.state.runtime
    return {"tools": await runtime.list_tools()}


@app.post("/v1/investigations", response_model=IncidentReport)
async def investigate(
    payload: InvestigationRequest,
    request: Request,
) -> IncidentReport:
    runtime: IncidentAgentRuntime = request.app.state.runtime
    try:
        return await runtime.investigate(payload.query, payload.namespace)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Incident investigation failed: {type(exc).__name__}",
        ) from exc
