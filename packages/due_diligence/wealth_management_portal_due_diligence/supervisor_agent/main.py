"""FastAPI entry point for DD Supervisor agent."""

from __future__ import annotations

import logging

from bedrock_agentcore.runtime.models import PingStatus
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ..schemas import DDAgentResult, DDRequest
from .agent import run_dd_pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="DD Supervisor Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/ping")
def ping():
    return PingStatus.HEALTHY


@app.post("/invocations")
async def invocations(body: DDRequest):
    try:
        report = await run_dd_pipeline(body)
        return DDAgentResult(
            session_id=body.session_id,
            portfolio_id=body.portfolio_id,
            portfolio_name=body.portfolio_name,
            report=report.model_dump(),  # type: ignore[arg-type]
            qa_iterations=1,
            status="complete",
        )
    except Exception as exc:
        logger.exception("DD pipeline failed for session %s", body.session_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
