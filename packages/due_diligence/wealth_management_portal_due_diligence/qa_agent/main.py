"""FastAPI entry point for QA Agent."""

from __future__ import annotations

import logging

from bedrock_agentcore.runtime.models import PingStatus
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ..schemas import QAResult, QATask
from .agent import qa_check

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="QA Agent", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/ping")
def ping():
    return PingStatus.HEALTHY


@app.post("/invocations")
async def invocations(task: QATask) -> QAResult:
    try:
        return await qa_check(task)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
