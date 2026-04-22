"""Web Search Agent — AgentCore HTTP server with sources artifact ."""

import asyncio
import json
import logging
import os
import re
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv

try:
    load_dotenv(dotenv_path=Path(__file__).resolve().parents[4] / ".env")
except IndexError:
    load_dotenv()

from . import tools as _tools_mod  # noqa: E402
from .agent import create_agent  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PORT = int(os.environ.get("PORT", 8080))


def _strip_thinking(text: str) -> str:
    return re.sub(r"<thinking>[\s\S]*?</thinking>\s*", "", text).strip()


def serve():
    import uvicorn
    from fastapi import Request
    from strands.multiagent.a2a import A2AServer

    agent = create_agent()
    a2a_server = A2AServer(agent=agent, host="0.0.0.0", port=PORT)
    app = a2a_server.to_fastapi_app()

    @app.get("/ping")
    def ping():
        return ""

    @app.post("/invocations")
    async def invocations(request: Request):
        request_id = str(uuid.uuid4())
        start_time = time.time()
        latency_ms = 0  # ✅ prevent unbound error
        payload = {}  # ✅ ensure safe fallback

        try:
            body = await request.body()
            payload = json.loads(body)

            # Extract user text
            text = ""
            for part in payload.get("params", {}).get("message", {}).get("parts", []):
                if part.get("kind") == "text":
                    text = part.get("text", "")
                    break

            if not text:
                return {
                    "jsonrpc": "2.0",
                    "id": payload.get("id", 1),
                    "error": {"code": -32600, "message": "No text found"},
                }

            session_id = payload.get("params", {}).get("message", {}).get("messageId", "")

            # Create agent (NO tools attached — analysis only)
            a = create_agent(session_id=session_id) if session_id else create_agent()

            # Reset sources
            _tools_mod.last_sources = None

            # -------------------------------
            # STEP 1: TOOL-FIRST EXECUTION
            # -------------------------------
            search_results = _tools_mod.web_search(text)

            # -------------------------------
            # STEP 2: VALIDATE TOOL OUTPUT
            # -------------------------------
            if not search_results or "error" in search_results.lower():
                logger.warning({"event": "tool_failure", "request_id": request_id, "query": text[:200]})

                augmented_prompt = f"""
User Query:
{text}

No reliable web results were found.

STRICT RULES:
- Do NOT hallucinate
- Respond with: "Insufficient real-time data"
"""

            else:
                # -------------------------------
                # STEP 2A: SAFE JSON PARSING + TRUNCATION
                # -------------------------------
                try:
                    parsed = json.loads(search_results)
                    top_results = parsed.get("results", [])[:5]
                    compact_results = json.dumps({"results": top_results}, ensure_ascii=False)
                except Exception:
                    # fallback to raw if parsing fails
                    compact_results = search_results

                # -------------------------------
                # STEP 3: STRICT GROUNDING PROMPT
                # -------------------------------
                augmented_prompt = f"""
You are a enterprise grade financial intelligence system.

You MUST base your response ONLY on the provided web search results.

--------------------------------------------------------------------------------
USER QUERY:
{text}

--------------------------------------------------------------------------------
WEB SEARCH RESULTS (JSON):
{compact_results}

--------------------------------------------------------------------------------
STRICT RULES:

- Use ONLY the above data
- Do NOT use prior knowledge
- Do NOT generate fake market data (S&P, Nasdaq, etc.)
- If data is missing, say "Insufficient evidence"
- Extract sector impact ONLY if supported by results

--------------------------------------------------------------------------------
Generate the response.
"""

            # -------------------------------
            # STEP 4: RUN AGENT
            # -------------------------------
            result = await asyncio.to_thread(a, augmented_prompt)

            reply = str(result) if result else "No response."
            reply = _strip_thinking(reply)

            latency_ms = round((time.time() - start_time) * 1000, 2)

            logger.info(
                {"event": "request_success", "request_id": request_id, "latency_ms": latency_ms, "query": text[:200]}
            )

        except Exception:
            latency_ms = round((time.time() - start_time) * 1000, 2)

            logger.exception({"event": "request_error", "request_id": request_id, "latency_ms": latency_ms})

            reply = "An error occurred while processing the request."

        # -------------------------------
        # STEP 5: ATTACH SOURCES (UI LAYER)
        # -------------------------------
        sources = _tools_mod.last_sources

        artifacts = [{"parts": [{"kind": "text", "text": reply}]}]

        if sources:
            artifacts.append({"parts": [{"kind": "text", "text": f"<!--SOURCES:{json.dumps(sources)}-->"}]})

        return {
            "jsonrpc": "2.0",
            "id": payload.get("id", 1) if payload else 1,  # ✅ safe fallback
            "result": {"artifacts": artifacts, "metadata": {"request_id": request_id, "latency_ms": latency_ms}},
        }

    logger.info("Web Search Agent serving on :%s", PORT)
    uvicorn.run(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    serve()
