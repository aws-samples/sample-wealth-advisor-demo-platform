import json
import os
from unittest.mock import MagicMock, Mock, patch

import pytest

from wealth_management_portal_scheduler_tools.lambda_functions.generate_report import lambda_handler

# Set required env vars for all tests
os.environ["REPORT_AGENT_ARN"] = "arn:aws:bedrock-agentcore:us-west-2:123456789:runtime/test-agent"
os.environ["AWS_REGION"] = "us-west-2"


def _mock_agentcore_response(data: dict) -> MagicMock:
    """Create a mock invoke_agent_runtime response."""
    mock_stream = MagicMock()
    mock_stream.read.return_value = json.dumps(data).encode()
    return {"response": mock_stream}


def test_handler_generates_report():
    """Test handler invokes report agent via AgentCore SDK and returns metadata."""
    response_data = {
        "report_id": "RPT-123",
        "s3_path": "reports/CLT-001/RPT-123.pdf",
        "status": "complete",
    }

    with patch(
        "wealth_management_portal_scheduler_tools.lambda_functions.generate_report._get_agentcore_client"
    ) as mock_get_client:
        mock_agentcore = Mock()
        mock_get_client.return_value = mock_agentcore
        mock_agentcore.invoke_agent_runtime.return_value = _mock_agentcore_response(response_data)

        result = lambda_handler({"client_id": "CLT-001"}, Mock())

        assert result["client_id"] == "CLT-001"
        assert result["report_id"] == "RPT-123"
        assert result["status"] == "complete"

        # Verify invoke_agent_runtime was called with correct args
        call_kwargs = mock_agentcore.invoke_agent_runtime.call_args.kwargs
        assert call_kwargs["agentRuntimeArn"] == os.environ["REPORT_AGENT_ARN"]
        assert json.loads(call_kwargs["payload"]) == {"client_id": "CLT-001"}


def test_handler_raises_error_when_no_client_id():
    """Test handler raises error when client_id missing."""
    with pytest.raises(ValueError, match="client_id is required"):
        lambda_handler({}, Mock())


def test_handler_raises_on_agent_error():
    """Test handler propagates exception when AgentCore call fails."""
    with patch(
        "wealth_management_portal_scheduler_tools.lambda_functions.generate_report._get_agentcore_client"
    ) as mock_get_client:
        mock_agentcore = Mock()
        mock_get_client.return_value = mock_agentcore
        mock_agentcore.invoke_agent_runtime.side_effect = Exception("Runtime invocation failed")

        with pytest.raises(Exception, match="Runtime invocation failed"):
            lambda_handler({"client_id": "CLT-001"}, Mock())


def test_handler_raises_when_report_agent_arn_missing():
    """Test handler raises KeyError when REPORT_AGENT_ARN env var is missing."""
    with patch.dict(os.environ, {}, clear=True):
        os.environ["AWS_REGION"] = "us-west-2"
        with pytest.raises(KeyError):
            lambda_handler({"client_id": "CLT-001"}, Mock())
