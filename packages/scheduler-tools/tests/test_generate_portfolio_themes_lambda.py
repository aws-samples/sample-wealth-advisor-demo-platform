"""
Unit tests for generate_portfolio_themes Lambda function
"""
import pytest
import json
from unittest.mock import Mock, patch
from wealth_management_portal_scheduler_tools.lambda_functions.generate_portfolio_themes import (
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
                "client_id": "CL00014",
                "themes_generated": 15,
                "stocks_covered": 5,
                "message": "Successfully generated 15 themes across 5 stocks for CL00014"
            })
        }]
    }
    return client


@pytest.fixture
def lambda_context():
    """Create a mock Lambda context"""
    context = Mock()
    context.function_name = "GeneratePortfolioThemes"
    context.memory_limit_in_mb = 512
    context.invoked_function_arn = "arn:aws:lambda:us-west-2:123456789012:function:GeneratePortfolioThemes"
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
        with patch('wealth_management_portal_scheduler_tools.lambda_functions.generate_portfolio_themes.MCPClient', return_value=mock_mcp_client):
            result = _invoke_web_crawler_mcp(
                mcp_arn="arn:aws:bedrock-agentcore:us-west-2:123456789012:agent-runtime/test-mcp",
                tool_name="generate_portfolio_themes_for_client",
                arguments={
                    "client_id": "CL00014",
                    "top_n_stocks": 5,
                    "themes_per_stock": 3,
                    "hours": 48
                }
            )
            
            # Verify result
            assert result["success"] is True
            assert result["themes_generated"] == 15
            assert result["client_id"] == "CL00014"
            
            # Verify MCP client was called correctly
            assert mock_mcp_client.call_tool_sync.called
            call_args = mock_mcp_client.call_tool_sync.call_args
            assert call_args[1]["name"] == "generate_portfolio_themes_for_client"
            assert call_args[1]["arguments"]["client_id"] == "CL00014"
            assert call_args[1]["arguments"]["top_n_stocks"] == 5


def test_lambda_handler_success(mock_mcp_client, lambda_context):
    """Test successful Lambda execution"""
    event = {"client_id": "CL00014"}
    
    mock_credentials = Mock()
    mock_credentials.access_key = "test_key"
    mock_credentials.secret_key = "test_secret"
    mock_credentials.token = "test_token"
    
    mock_session = Mock()
    mock_session.get_credentials.return_value.get_frozen_credentials.return_value = mock_credentials
    
    with patch('boto3.Session', return_value=mock_session):
        with patch('wealth_management_portal_scheduler_tools.lambda_functions.generate_portfolio_themes.MCPClient', return_value=mock_mcp_client):
            with patch.dict('os.environ', {
                'WEB_CRAWLER_MCP_ARN': 'arn:aws:bedrock-agentcore:us-west-2:123456789012:agent-runtime/test-mcp',
                'TOP_N_STOCKS': '5',
                'THEMES_PER_STOCK': '3',
                'THEME_HOURS': '48',
                'AWS_REGION': 'us-west-2'
            }):
                result = lambda_handler(event, lambda_context)
                
                # Verify result
                assert result["statusCode"] == 200
                assert result["client_id"] == "CL00014"
                assert result["themes_generated"] == 15
                assert result["stocks_covered"] == 5
                assert "timestamp" in result
                assert "Successfully" in result["summary"]


def test_lambda_handler_missing_client_id(lambda_context):
    """Test Lambda execution with missing client_id"""
    event = {}
    
    with patch.dict('os.environ', {
        'WEB_CRAWLER_MCP_ARN': 'arn:aws:bedrock-agentcore:us-west-2:123456789012:agent-runtime/test-mcp'
    }):
        result = lambda_handler(event, lambda_context)
        
        # Verify error response
        assert result["statusCode"] == 500
        assert "error" in result
        assert "client_id is required" in result["error"]


def test_lambda_handler_missing_mcp_arn(lambda_context):
    """Test Lambda execution with missing MCP ARN"""
    event = {"client_id": "CL00014"}
    
    with patch.dict('os.environ', {}, clear=True):
        result = lambda_handler(event, lambda_context)
        
        # Verify error response
        assert result["statusCode"] == 500
        assert "error" in result
        assert "WEB_CRAWLER_MCP_ARN" in result["error"]


def test_lambda_handler_mcp_failure(mock_mcp_client, lambda_context):
    """Test Lambda execution when MCP tool fails"""
    event = {"client_id": "CL00014"}
    
    # Mock MCP failure response
    mock_mcp_client.call_tool_sync.return_value = {
        "content": [{
            "text": json.dumps({
                "success": False,
                "error": "No holdings found for client CL00014"
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
        with patch('wealth_management_portal_scheduler_tools.lambda_functions.generate_portfolio_themes.MCPClient', return_value=mock_mcp_client):
            with patch.dict('os.environ', {
                'WEB_CRAWLER_MCP_ARN': 'arn:aws:bedrock-agentcore:us-west-2:123456789012:agent-runtime/test-mcp',
                'TOP_N_STOCKS': '5',
                'THEMES_PER_STOCK': '3',
                'THEME_HOURS': '48',
                'AWS_REGION': 'us-west-2'
            }):
                result = lambda_handler(event, lambda_context)
                
                # Verify error response
                assert result["statusCode"] == 500
                assert "error" in result
                assert "No holdings found" in result["error"]


def test_lambda_handler_agentcore_exception(mock_mcp_client, lambda_context):
    """Test Lambda execution when MCP client raises exception"""
    event = {"client_id": "CL00014"}
    
    # Mock MCP client exception
    mock_mcp_client.call_tool_sync.side_effect = Exception("MCP connection failed")
    
    mock_credentials = Mock()
    mock_credentials.access_key = "test_key"
    mock_credentials.secret_key = "test_secret"
    mock_credentials.token = "test_token"
    
    mock_session = Mock()
    mock_session.get_credentials.return_value.get_frozen_credentials.return_value = mock_credentials
    
    with patch('boto3.Session', return_value=mock_session):
        with patch('wealth_management_portal_scheduler_tools.lambda_functions.generate_portfolio_themes.MCPClient', return_value=mock_mcp_client):
            with patch.dict('os.environ', {
                'WEB_CRAWLER_MCP_ARN': 'arn:aws:bedrock-agentcore:us-west-2:123456789012:agent-runtime/test-mcp',
                'TOP_N_STOCKS': '5',
                'THEMES_PER_STOCK': '3',
                'THEME_HOURS': '48',
                'AWS_REGION': 'us-west-2'
            }):
                result = lambda_handler(event, lambda_context)
                
                # Verify error response
                assert result["statusCode"] == 500
                assert "error" in result
                assert "MCP connection failed" in result["error"]
                assert "traceback" in result


def test_lambda_handler_custom_parameters(mock_mcp_client, lambda_context):
    """Test Lambda execution with custom parameters"""
    event = {"client_id": "CL00015"}
    
    mock_credentials = Mock()
    mock_credentials.access_key = "test_key"
    mock_credentials.secret_key = "test_secret"
    mock_credentials.token = "test_token"
    
    mock_session = Mock()
    mock_session.get_credentials.return_value.get_frozen_credentials.return_value = mock_credentials
    
    with patch('boto3.Session', return_value=mock_session):
        with patch('wealth_management_portal_scheduler_tools.lambda_functions.generate_portfolio_themes.MCPClient', return_value=mock_mcp_client):
            with patch.dict('os.environ', {
                'WEB_CRAWLER_MCP_ARN': 'arn:aws:bedrock-agentcore:us-west-2:123456789012:agent-runtime/test-mcp',
                'TOP_N_STOCKS': '10',
                'THEMES_PER_STOCK': '5',
                'THEME_HOURS': '72',
                'AWS_REGION': 'us-west-2'
            }):
                result = lambda_handler(event, lambda_context)
                
                # Verify result includes custom parameters
                assert result["statusCode"] == 200
                assert result["top_n_stocks"] == 10
                assert result["themes_per_stock"] == 5
                assert result["hours"] == 72
