"""Voice Gateway — FastAPI WebSocket server with BidiAgent + Nova Sonic.

Endpoints:
- GET  /ping  — health check (required by AgentCore)
- WS   /ws    — bidirectional audio streaming
"""

import contextlib
import logging
import os
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from strands.experimental.bidi.agent import BidiAgent
from strands.experimental.bidi.models.nova_sonic import BidiNovaSonicModel

from .agent import SYSTEM_PROMPT, TOOLS

try:
    load_dotenv(dotenv_path=Path(__file__).resolve().parents[4] / ".env")
except IndexError:
    load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PORT = int(os.environ.get("PORT", 9005))
BEDROCK_REGION = os.environ.get("BEDROCK_REGION", os.environ.get("AWS_REGION", "us-east-1"))
MODEL_ID = os.environ.get("VOICE_AGENT_BEDROCK_MODEL_ID", "amazon.nova-2-sonic-v1:0")

_allowed_origins = os.environ.get("ALLOWED_ORIGINS", "").split(",") if os.environ.get("ALLOWED_ORIGINS") else ["*"]
app = FastAPI(title="Voice Gateway")
app.add_middleware(CORSMiddleware, allow_origins=_allowed_origins, allow_methods=["*"], allow_headers=["*"])


@app.get("/ping")
async def ping():
    return JSONResponse({"status": "ok"})


@app.get("/health")
def health():
    return {"status": "ok", "service": "voice-gateway"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    voice_id = websocket.query_params.get("voice_id", "tiffany")
    logger.info("WebSocket connection from %s, voice: %s", websocket.client, voice_id)

    agent = None
    try:
        model = BidiNovaSonicModel(
            region=BEDROCK_REGION,
            model_id=MODEL_ID,
            provider_config={
                "audio": {
                    "input_sample_rate": 16000,
                    "output_sample_rate": 16000,
                    "voice": voice_id,
                }
            },
            tools=TOOLS,
        )

        agent = BidiAgent(
            model=model,
            tools=TOOLS,
            system_prompt=SYSTEM_PROMPT,
        )

        await agent.run(
            inputs=[websocket.receive_json],
            outputs=[websocket.send_json],
        )

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error("Error in voice chat: %s", e, exc_info=True)
        with contextlib.suppress(Exception):
            await websocket.send_json({"type": "error", "message": str(e)})
    finally:
        if agent:
            try:
                await agent.stop()
            except Exception as cleanup_err:
                logger.warning("Cleanup error: %s", cleanup_err)
        with contextlib.suppress(Exception):
            await websocket.close()


if __name__ == "__main__":
    logger.info("Voice Gateway starting on :%s (region=%s, model=%s)", PORT, BEDROCK_REGION, MODEL_ID)
    host = "0.0.0.0" if os.getenv("CONTAINER_ENV") else "127.0.0.1"
    uvicorn.run(app, host=host, port=PORT)
