"""Portfolio Due Diligence REST API — Lambda (DynamoDB + async invoke) or local (in-memory)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import UTC, datetime
from uuid import uuid4

import boto3
from fastapi import HTTPException
from pydantic import BaseModel

from ..common.a2a_client import get_agent_endpoint, invoke_agent
from ..models import DDReport, DDSession, DDStatus
from ..schemas import DDProgressEvent, DDRequest
from ..seed_data import MANAGER_BY_PORTFOLIO, SAMPLE_PORTFOLIOS
from .repository import DDRepository

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use init.py's app in Lambda mode, standalone FastAPI for local dev
_is_lambda = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

if _is_lambda:
    from .init import app  # noqa: I001
    from .init import lambda_handler as _mangum_handler
else:
    from fastapi import FastAPI  # noqa: I001
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(title="Portfolio DD API", version="1.0.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    _mangum_handler = None

repo = DDRepository()

# In-memory fallback for local dev (when DynamoDB not available)
_sessions: dict[str, DDSession] = {}
_reports: dict[str, DDReport] = {}
_hitl_flags: dict[str, dict[str, dict]] = {}


# ── Request/Response models ────────────────────────────────────────────────────


class StartReviewRequest(BaseModel):
    portfolio_id: str
    initiated_by: str = "system"
    criteria_ids: list[str] = []


class StartReviewResponse(BaseModel):
    session_id: str
    portfolio_id: str
    portfolio_name: str
    status: str
    started_at: str


class SessionStatusResponse(BaseModel):
    session_id: str
    portfolio_id: str
    portfolio_name: str
    status: str
    started_at: str
    completed_at: str | None
    overall_score: float | None = None
    recommendation: str | None = None
    hitl_required: bool = False


class HITLResolveRequest(BaseModel):
    resolution: str
    reviewer_notes: str = ""
    reviewer: str = ""


# ── Pipeline runner (invoked async in Lambda, or as background task locally) ──


def _emit_event(session_id: str, event: DDProgressEvent) -> None:
    if repo.is_available:
        repo.append_event(session_id, event.model_dump(mode="json"))


async def _run_pipeline(
    session_id: str,
    portfolio_id: str,
    portfolio_name: str,
    manager_name: str,
    criteria_ids: list[str] | None = None,
) -> None:
    """Drive the supervisor agent and persist results."""
    _emit_event(
        session_id,
        DDProgressEvent(
            session_id=session_id,
            event_type="pipeline_started",
            message=f"Starting due diligence for {portfolio_name}",
        ),
    )

    request = DDRequest(
        session_id=session_id,
        portfolio_id=portfolio_id,
        portfolio_name=portfolio_name,
        manager_name=manager_name,
        criteria_ids=criteria_ids or [],
    )

    try:
        ep = get_agent_endpoint("dd-supervisor")
        result = await invoke_agent(ep, request.model_dump_json())
        report_data = result.get("report", result) if isinstance(result, dict) else result
        report = DDReport.model_validate(report_data)

        # Build HITL flags with criterion_id for frontend matching
        from ..framework import DD_FRAMEWORK_V1

        flags = []
        if report.hitl_required:
            for reason in report.hitl_reasons:
                flag_id = f"flag_{uuid4().hex[:8]}"
                cid = ""
                for c in DD_FRAMEWORK_V1:
                    if c.criterion_id in reason or c.name in reason:
                        cid = c.criterion_id
                        break
                flags.append(
                    {
                        "flag_id": flag_id,
                        "criterion_id": cid,
                        "reason": reason,
                        "status": "pending",
                        "resolved_at": None,
                        "reviewer_notes": "",
                    }
                )
                _emit_event(
                    session_id,
                    DDProgressEvent(
                        session_id=session_id,
                        event_type="hitl_flag",
                        message=reason,
                        data={"flag_id": flag_id},
                    ),
                )

        # Persist results
        if repo.is_available:
            repo.save_report(session_id, report.model_dump(mode="json"))
            repo.update_session(
                session_id,
                {
                    "status": "complete",
                    "completed_at": datetime.now(UTC).isoformat(),
                    "overall_score": str(report.overall_score),
                    "recommendation": report.recommendation,
                    "hitl_required": report.hitl_required,
                    "hitl_flags": flags,
                },
            )
        else:
            _reports[session_id] = report
            session = _sessions.get(session_id)
            if session:
                session.status = DDStatus.COMPLETE
                session.completed_at = datetime.utcnow()
            _hitl_flags[session_id] = {f["flag_id"]: f for f in flags}

        _emit_event(
            session_id,
            DDProgressEvent(
                session_id=session_id,
                event_type="report_ready",
                message="Due diligence report is ready.",
                score=report.overall_score,
                data={
                    "recommendation": report.recommendation,
                    "overall_rag": report.overall_rag,
                    "hitl_required": report.hitl_required,
                },
            ),
        )

    except Exception as exc:
        logger.error("Pipeline failed for session %s: %s", session_id, exc)
        if repo.is_available:
            repo.update_session(session_id, {"status": "failed"})
            repo.append_event(
                session_id,
                {
                    "session_id": session_id,
                    "event_type": "error",
                    "message": str(exc),
                },
            )
        else:
            session = _sessions.get(session_id)
            if session:
                session.status = DDStatus.FAILED


# ── Endpoints ──────────────────────────────────────────────────────────────────


@app.get("/ping")
def ping():
    return {"status": "ok", "service": "portfolio-dd-api"}


@app.post("/dd/sessions", status_code=202, response_model=StartReviewResponse)
async def start_review(req: StartReviewRequest):
    """Kick off a new DD session for a portfolio."""
    pf_data = next((p for p in SAMPLE_PORTFOLIOS if p["portfolio_id"] == req.portfolio_id), None)
    if not pf_data:
        raise HTTPException(status_code=404, detail=f"Portfolio {req.portfolio_id} not found")

    pf_name = pf_data.get("name", req.portfolio_id)
    mgr_data = MANAGER_BY_PORTFOLIO.get(req.portfolio_id, {})
    mgr_name = mgr_data.get("name", "Unknown Manager")

    session = DDSession(
        portfolio_id=req.portfolio_id,
        portfolio_name=pf_name,
        manager_name=mgr_name,
        initiated_by=req.initiated_by,
        status=DDStatus.IN_PROGRESS,
    )

    if repo.is_available:
        repo.create_session(
            {
                "session_id": session.session_id,
                "portfolio_id": session.portfolio_id,
                "portfolio_name": session.portfolio_name,
                "manager_name": mgr_name,
                "status": session.status,
                "started_at": session.started_at.isoformat(),
            }
        )
        # Fire async Lambda self-invoke
        boto3.client("lambda").invoke(
            FunctionName=os.environ["AWS_LAMBDA_FUNCTION_NAME"],
            InvocationType="Event",
            Payload=json.dumps(
                {
                    "action": "run_pipeline",
                    "session_id": session.session_id,
                    "portfolio_id": session.portfolio_id,
                    "portfolio_name": session.portfolio_name,
                    "manager_name": mgr_name,
                    "criteria_ids": req.criteria_ids,
                }
            ).encode(),
        )
    else:
        _sessions[session.session_id] = session
        asyncio.create_task(
            _run_pipeline(session.session_id, session.portfolio_id, session.portfolio_name, mgr_name, req.criteria_ids)
        )

    return StartReviewResponse(
        session_id=session.session_id,
        portfolio_id=session.portfolio_id,
        portfolio_name=session.portfolio_name,
        status=session.status,
        started_at=session.started_at.isoformat(),
    )


@app.get("/dd/sessions/{session_id}", response_model=SessionStatusResponse)
async def get_session(session_id: str):
    """Return status and summary for a DD session."""
    if repo.is_available:
        data = repo.get_session(session_id)
        if not data:
            raise HTTPException(status_code=404, detail="Session not found")
        return SessionStatusResponse(
            session_id=data["session_id"],
            portfolio_id=data["portfolio_id"],
            portfolio_name=data["portfolio_name"],
            status=data["status"],
            started_at=data["started_at"],
            completed_at=data.get("completed_at"),
            overall_score=float(data["overall_score"]) if data.get("overall_score") else None,
            recommendation=data.get("recommendation"),
            hitl_required=data.get("hitl_required", False),
        )

    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    report = _reports.get(session_id)
    return SessionStatusResponse(
        session_id=session.session_id,
        portfolio_id=session.portfolio_id,
        portfolio_name=session.portfolio_name,
        status=session.status,
        started_at=session.started_at.isoformat(),
        completed_at=session.completed_at.isoformat() if session.completed_at else None,
        overall_score=report.overall_score if report else None,
        recommendation=report.recommendation if report else None,
        hitl_required=report.hitl_required if report else False,
    )


@app.get("/dd/sessions/{session_id}/events")
async def get_events(session_id: str):
    """Return progress events for a DD session (polling replacement for SSE)."""
    if repo.is_available:
        data = repo.get_session(session_id)
        if not data:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"events": data.get("events", [])}

    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"events": []}


@app.get("/dd/sessions/{session_id}/report")
async def get_report(session_id: str):
    """Return the completed DD report."""
    if repo.is_available:
        data = repo.get_session(session_id)
        if not data:
            raise HTTPException(status_code=404, detail="Session not found")
        if data["status"] == "in_progress":
            raise HTTPException(status_code=202, detail="Report not yet ready")
        report = repo.get_report(session_id)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        return report

    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    report = _reports.get(session_id)
    if not report:
        session = _sessions[session_id]
        if session.status == DDStatus.IN_PROGRESS:
            raise HTTPException(status_code=202, detail="Report not yet ready")
        raise HTTPException(status_code=404, detail="Report not found")
    return report.model_dump()


@app.get("/dd/sessions/{session_id}/hitl")
async def list_hitl_flags(session_id: str):
    """List all HITL flags for a session."""
    if repo.is_available:
        data = repo.get_session(session_id)
        if not data:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"flags": data.get("hitl_flags", [])}

    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"flags": list(_hitl_flags.get(session_id, {}).values())}


@app.post("/dd/sessions/{session_id}/hitl/{flag_id}/resolve")
async def resolve_hitl_flag(session_id: str, flag_id: str, req: HITLResolveRequest):
    """Record a human reviewer's decision on a HITL flag."""
    valid_resolutions = {"approved", "rejected", "escalated"}
    if req.resolution not in valid_resolutions:
        raise HTTPException(status_code=400, detail=f"resolution must be one of {valid_resolutions}")

    if repo.is_available:
        data = repo.get_session(session_id)
        if not data:
            raise HTTPException(status_code=404, detail="Session not found")
        repo.update_hitl_flag(
            session_id,
            flag_id,
            {
                "status": req.resolution,
                "resolved_at": datetime.now(UTC).isoformat(),
                "reviewer_notes": req.reviewer_notes,
                "reviewer": req.reviewer,
            },
        )
        return {"flag_id": flag_id, "status": req.resolution, "message": "Resolution recorded"}

    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    flags = _hitl_flags.get(session_id)
    if not flags or flag_id not in flags:
        raise HTTPException(status_code=404, detail="Flag not found")
    flag = flags[flag_id]
    flag["status"] = req.resolution
    flag["resolved_at"] = datetime.now(UTC).isoformat()
    flag["reviewer_notes"] = req.reviewer_notes
    flag["reviewer"] = req.reviewer
    return {"flag_id": flag_id, "status": req.resolution, "message": "Resolution recorded"}


@app.get("/dd/portfolios")
async def list_portfolios():
    """Return the list of sample portfolios available for DD."""
    return {"portfolios": SAMPLE_PORTFOLIOS}


@app.get("/dd/sessions")
async def list_sessions_endpoint():
    """Return all DD sessions."""
    if repo.is_available:
        sessions = repo.list_sessions()
        return {"sessions": sessions}
    return {
        "sessions": [
            {
                "session_id": s.session_id,
                "portfolio_id": s.portfolio_id,
                "portfolio_name": s.portfolio_name,
                "status": s.status,
                "started_at": s.started_at.isoformat(),
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                "overall_score": None,
                "recommendation": None,
                "hitl_required": False,
            }
            for s in _sessions.values()
        ]
    }


@app.get("/dd/portfolios/{portfolio_id}/documents")
async def list_source_documents(portfolio_id: str):
    """Return source documents available for a portfolio."""
    from ..seed_data import SOURCE_DOCUMENTS

    docs = SOURCE_DOCUMENTS.get(portfolio_id, [])
    return {"documents": docs}


@app.get("/dd/portfolios/{portfolio_id}/documents/url")
async def get_document_url(portfolio_id: str, key: str):
    """Generate a presigned S3 URL for a source document."""
    from ..seed_data import SOURCE_DOCUMENTS

    docs = SOURCE_DOCUMENTS.get(portfolio_id, [])
    if not any(d["key"] == key for d in docs):
        raise HTTPException(status_code=404, detail="Document not found")

    bucket = os.environ.get("DD_SOURCE_DOCS_BUCKET")
    if not bucket:
        raise HTTPException(status_code=500, detail="Source docs bucket not configured")

    s3_client = boto3.client("s3")
    url = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=3600,
    )
    return {"url": url}


@app.get("/dd/sessions/{session_id}/report/html")
async def get_report_html(session_id: str):
    """Return the DD report rendered as HTML."""
    from fastapi.responses import HTMLResponse

    from ..report_drafter.render import render_html

    if repo.is_available:
        data = repo.get_session(session_id)
        if not data:
            raise HTTPException(status_code=404, detail="Session not found")
        report_data = repo.get_report(session_id)
        if not report_data:
            raise HTTPException(status_code=404, detail="Report not found")
        html = render_html(
            report_data,
            portfolio_name=data.get("portfolio_name", ""),
            manager_name=data.get("manager_name", ""),
        )
        return HTMLResponse(content=html)

    raise HTTPException(status_code=404, detail="Report not available")


# ── Lambda handler (dual-mode: API Gateway via Mangum, or async pipeline invoke) ──


def handler(event, context):
    """Lambda entry point — routes between API requests and async pipeline invocations."""
    if isinstance(event, dict) and event.get("action") == "run_pipeline":
        try:
            asyncio.run(
                _run_pipeline(
                    session_id=event["session_id"],
                    portfolio_id=event["portfolio_id"],
                    portfolio_name=event["portfolio_name"],
                    manager_name=event.get("manager_name", ""),
                    criteria_ids=event.get("criteria_ids", []),
                )
            )
        except Exception as exc:
            logger.error("Pipeline handler failed: %s", exc)
            if repo.is_available:
                repo.update_session(event["session_id"], {"status": "failed"})
                repo.append_event(
                    event["session_id"],
                    {
                        "session_id": event["session_id"],
                        "event_type": "error",
                        "message": str(exc),
                    },
                )
        return {"status": "done"}
    # Ensure event loop exists for Mangum (Python 3.12 doesn't auto-create one)
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    return _mangum_handler(event, context)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8092)))
