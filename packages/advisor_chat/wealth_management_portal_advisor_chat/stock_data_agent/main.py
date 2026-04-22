"""Stock Data Agent — AgentCore HTTP server entry point."""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

try:
    load_dotenv(dotenv_path=Path(__file__).resolve().parents[4] / ".env")
except IndexError:
    load_dotenv()

from ..common.agentcore_server import serve_agent  # noqa: E402
from .agent import create_agent  # noqa: E402

logging.basicConfig(level=logging.INFO)

PORT = int(os.environ.get("PORT", 8080))


def serve():
    serve_agent(create_agent, "Stock Data Agent", PORT)


if __name__ == "__main__":
    serve()
