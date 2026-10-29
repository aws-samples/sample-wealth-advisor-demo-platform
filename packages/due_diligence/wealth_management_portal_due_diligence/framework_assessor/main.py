"""FastAPI entry point for Framework Assessor agent."""

from __future__ import annotations

import logging

from bedrock_agentcore.runtime.models import PingStatus
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ..schemas import AssessmentBundle, AssessmentTask
from .agent import assess_all_criteria

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Framework Assessor Agent", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/ping")
def ping():
    return PingStatus.HEALTHY


@app.post("/invocations")
async def invocations(task: AssessmentTask) -> AssessmentBundle:
    try:
        return await assess_all_criteria(task)
    except Exception as exc:
        logger.exception("Framework assessment failed for session %s", task.session_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
