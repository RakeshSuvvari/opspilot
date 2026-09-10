from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status

from . import __version__
from .config import Settings
from .remediation_jobs import RemediationJobManager
from .runtime import IncidentAgentRuntime
from .schemas import (
    ApprovalDecisionRequest,
    IncidentReport,
    InvestigationHistoryDetail,
    InvestigationHistoryItem,
    InvestigationRequest,
    RemediationJob,
    RemediationStartRequest,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings.from_env()
    runtime = IncidentAgentRuntime(settings)
    await runtime.start()
    remediation_jobs = RemediationJobManager(runtime)
    app.state.settings = settings
    app.state.runtime = runtime
    app.state.remediation_jobs = remediation_jobs
    try:
        yield
    finally:
        await remediation_jobs.close()
        await runtime.close()


app = FastAPI(
    title="OpsPilot Agent Service",
    version=__version__,
    lifespan=lifespan,
)


@app.get("/healthz")
async def healthz(request: Request) -> dict[str, object]:
    settings: Settings = request.app.state.settings
    runtime: IncidentAgentRuntime = request.app.state.runtime
    history_available = False
    if runtime.history is not None:
        history_available = await runtime.history.ping()
    return {
        "status": "ok",
        "version": __version__,
        "model": settings.openai_model,
        "k8s_mcp_url": settings.k8s_mcp_url,
        "rag_enabled": settings.rag_enabled,
        "embedding_model": settings.embedding_model,
        "github_enabled": settings.github_enabled,
        "phase": 9,
        "save_run_artifacts": settings.save_run_artifacts,
        "remediation_enabled": settings.remediation_enabled,
        "history_enabled": settings.history_enabled,
        "history_available": history_available,
    }


@app.get("/v1/tools")
async def tools(request: Request) -> dict[str, object]:
    runtime: IncidentAgentRuntime = request.app.state.runtime
    return {
        "tools": await runtime.list_tools(
            include_remediation=request.app.state.settings.remediation_enabled
        )
    }




@app.get("/v1/investigations", response_model=list[InvestigationHistoryItem])
async def investigation_history(
    request: Request,
    limit: int = 25,
) -> list[InvestigationHistoryItem]:
    runtime: IncidentAgentRuntime = request.app.state.runtime
    if runtime.history is None:
        return []
    try:
        return await runtime.history.list_investigations(limit=limit)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Incident history unavailable: {type(exc).__name__}",
        ) from exc


@app.get(
    "/v1/investigations/{investigation_id}",
    response_model=InvestigationHistoryDetail,
)
async def investigation_history_detail(
    investigation_id: str,
    request: Request,
) -> InvestigationHistoryDetail:
    runtime: IncidentAgentRuntime = request.app.state.runtime
    if runtime.history is None:
        raise HTTPException(status_code=404, detail="incident history is disabled")
    try:
        item = await runtime.history.get_investigation(investigation_id)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Incident history unavailable: {type(exc).__name__}",
        ) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="investigation not found")
    return item


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


@app.post(
    "/v1/remediations",
    response_model=RemediationJob,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_remediation(
    payload: RemediationStartRequest,
    request: Request,
) -> RemediationJob:
    settings: Settings = request.app.state.settings
    if not settings.remediation_enabled:
        raise HTTPException(
            status_code=409,
            detail="Human-approved remediation is disabled on the agent service.",
        )
    namespace = (payload.namespace or settings.default_namespace).strip()
    if not namespace:
        raise HTTPException(status_code=400, detail="namespace cannot be empty")
    manager: RemediationJobManager = request.app.state.remediation_jobs
    return await manager.start(payload.query, namespace)


@app.get("/v1/remediations/{job_id}", response_model=RemediationJob)
async def get_remediation(job_id: str, request: Request) -> RemediationJob:
    manager: RemediationJobManager = request.app.state.remediation_jobs
    try:
        return await manager.get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="remediation job not found") from exc


@app.post("/v1/remediations/{job_id}/decision", response_model=RemediationJob)
async def decide_remediation(
    job_id: str,
    payload: ApprovalDecisionRequest,
    request: Request,
) -> RemediationJob:
    manager: RemediationJobManager = request.app.state.remediation_jobs
    try:
        return await manager.decide(
            job_id,
            approved=payload.approved,
            call_id=payload.call_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="remediation job not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
