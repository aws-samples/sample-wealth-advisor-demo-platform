"""Integration test configuration — loads root .env before tests run."""

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv


@pytest.fixture(autouse=True, scope="session")
def _load_env():
    load_dotenv(dotenv_path=Path(__file__).resolve().parents[4] / ".env")
    if os.environ.get("AWS_REGION") and not os.environ.get("AWS_DEFAULT_REGION"):
        os.environ["AWS_DEFAULT_REGION"] = os.environ["AWS_REGION"]
