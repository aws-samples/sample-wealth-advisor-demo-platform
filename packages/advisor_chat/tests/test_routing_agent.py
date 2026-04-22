"""Tests for routing_agent/agent.py — AgentCore invoke and agent creation."""

from unittest.mock import patch


@patch("wealth_management_portal_advisor_chat.routing_agent.agent.BedrockModel")
def test_create_agent(mock_model):
    from wealth_management_portal_advisor_chat.routing_agent.agent import create_agent

    agent = create_agent()
    assert agent is not None
