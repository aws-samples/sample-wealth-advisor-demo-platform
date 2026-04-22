"""
Unit tests for generate_general_themes Lambda function
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from wealth_management_portal_scheduler_tools.lambda_functions.generate_general_themes import (
    lambda_handler,
    _invoke_web_crawler_mcp,
)


@pytest.fixture
def mock_mcp_client():
    """Create a mock MCP client"""
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    
    # Mock MCP response format
    client.call_tool_sync.return_value = {
        "content": [{
            "text": json.dumps({
                "success": True,
                "themes_generated": 6,
                "message": "Successfully generated 6 general market themes"
            })
        }]
    }
    return client


@pytest.fixture
def lambda_context():
    """Create a mock Lambda context"""
    context = Mock()
    context.function_name = "GenerateGeneralThemes"
    context.memory_limit_in_mb = 512
    context.invoked_function_arn = "arn:aws:lambda:us-west-2:123456789012:function:GenerateGeneralThemes"
    context.aws_request_id = "test-request-id"
    return context


def test_invoke_web_crawler_mcp(mock_mcp_client):
    """Test _invoke_web_crawler_mcp helper function"""
    mock_credentials = Mock()
    mock_credentials.access_key = "test_key"
    mock_credentials.secret_key = "test_secret"
    mock_credentials.token = "test_token"
    
    mock_session = Mock()
    mock_session.get_credentials.return_value.get_frozen_credentials.return_value = mock_credentials
    
    with patch('boto3.Session', return_value=mock_session):
        with patch('wealth_management_portal_scheduler_tools.lambda_functions.generate_general_themes.MCPClient', return_value=mock_mcp_client):
            result = _invoke_web_crawler_mcp(
                mcp_arn="arn:aws:bedrock-agentcore:us-west-2:123456789012:agent-runtime/test-mcp",
                tool_name="generate_general_themes",
                arguments={"hours": 48, "limit": 6}
            )
            
            # Verify result
            assert result["success"] is True
            assert result["themes_generated"] == 6
            
            # Verify MCP client was called correctly
            assert mock_mcp_client.call_tool_sync.called
            call_args = mock_mcp_client.call_tool_sync.call_args
            assert call_args[1]["name"] == "generate_general_themes"
            assert call_args[1]["arguments"]["hours"] == 48
            assert call_args[1]["arguments"]["limit"] == 6


def test_lambda_handler_success(mock_mcp_client, lambda_context):
    """Test successful Lambda execution"""
    event = {}
    
    mock_credentials = Mock()
    mock_credentials.access_key = "test_key"
    mock_credentials.secret_key = "test_secret"
    mock_credentials.token = "test_token"
    
    mock_session = Mock()
    mock_session.get_credentials.return_value.get_frozen_credentials.return_value = mock_credentials
    
    with patch('boto3.Session', return_value=mock_session):
        with patch('wealth_management_portal_scheduler_tools.lambda_functions.generate_general_themes.MCPClient', return_value=mock_mcp_client):
            with patch.dict('os.environ', {
                'WEB_CRAWLER_MCP_ARN': 'arn:aws:bedrock-agentcore:us-west-2:123456789012:agent-runtime/test-mcp',
                'THEME_HOURS': '48',
                'THEME_LIMIT': '6',
                'AWS_REGION': 'us-west-2'
            }):
                result = lambda_handler(event, lambda_context)
                
                # Verify result
                assert result["statusCode"] == 200
                assert result["themes_generated"] == 6
                assert "timestamp" in result
                assert "Successfully" in result["summary"]


def test_lambda_handler_missing_mcp_arn(lambda_context):
    """Test Lambda execution with missing MCP ARN"""
    event = {}
    
    with patch.dict('os.environ', {}, clear=True):
        result = lambda_handler(event, lambda_context)
        
        # Verify error response
        assert result["statusCode"] == 500
        assert "error" in result
        assert "WEB_CRAWLER_MCP_ARN" in result["error"]


def test_lambda_handler_mcp_failure(mock_mcp_client, lambda_context):
    """Test Lambda execution when MCP tool fails"""
    event = {}
    
    # Mock MCP failure response
    mock_mcp_client.call_tool_sync.return_value = {
        "content": [{
            "text": json.dumps({
                "success": False,
                "error": "Theme generation failed"
            })
        }]
    }
    
    mock_credentials = Mock()
    mock_credentials.access_key = "test_key"
    mock_credentials.secret_key = "test_secret"
    mock_credentials.token = "test_token"
    
    mock_session = Mock()
    mock_session.get_credentials.return_value.get_frozen_credentials.return_value = mock_credentials
    
    with patch('boto3.Session', return_value=mock_session):
        with patch('wealth_management_portal_scheduler_tools.lambda_functions.generate_general_themes.MCPClient', return_value=mock_mcp_client):
            with patch.dict('os.environ', {
                'WEB_CRAWLER_MCP_ARN': 'arn:aws:bedrock-agentcore:us-west-2:123456789012:agent-runtime/test-mcp',
                'THEME_HOURS': '48',
                'THEME_LIMIT': '6',
                'AWS_REGION': 'us-west-2'
            }):
                result = lambda_handler(event, lambda_context)
                
                # Verify error response
                assert result["statusCode"] == 500
                assert "error" in result
                assert "Theme generation failed" in result["error"]


def test_lambda_handler_agentcore_exception(mock_mcp_client, lambda_context):
    """Test Lambda execution when MCP client raises exception"""
    event = {}
    
    # Mock MCP client exception
    mock_mcp_client.call_tool_sync.side_effect = Exception("MCP connection failed")
    
    mock_credentials = Mock()
    mock_credentials.access_key = "test_key"
    mock_credentials.secret_key = "test_secret"
    mock_credentials.token = "test_token"
    
    mock_session = Mock()
    mock_session.get_credentials.return_value.get_frozen_credentials.return_value = mock_credentials
    
    with patch('boto3.Session', return_value=mock_session):
        with patch('wealth_management_portal_scheduler_tools.lambda_functions.generate_general_themes.MCPClient', return_value=mock_mcp_client):
            with patch.dict('os.environ', {
                'WEB_CRAWLER_MCP_ARN': 'arn:aws:bedrock-agentcore:us-west-2:123456789012:agent-runtime/test-mcp',
                'THEME_HOURS': '48',
                'THEME_LIMIT': '6',
                'AWS_REGION': 'us-west-2'
            }):
                result = lambda_handler(event, lambda_context)
                
                # Verify error response
                assert result["statusCode"] == 500
                assert "error" in result
                assert "MCP connection failed" in result["error"]
                assert "traceback" in result
