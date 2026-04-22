"""Unit tests configuration module."""

import os

import pytest


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Set up test environment variables."""
    os.environ["REPORT_S3_BUCKET"] = "test-reports-bucket"
