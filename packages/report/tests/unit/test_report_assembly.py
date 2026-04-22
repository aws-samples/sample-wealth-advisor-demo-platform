# Tests for narrative generation and final markdown assembly logic.
# These tests verify real assembly behavior — no mocked-behavior-for-its-own-sake tests.
from unittest.mock import MagicMock, patch

import pytest

from wealth_management_portal_report.generator import ReportGenerator
from wealth_management_portal_report.report_agent.agent import (
    NARRATIVE_KEYS,
    assemble_markdown,
    invoke_narrative_generator,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_NARRATIVES = {
    "last_interaction_summary": "We spoke on Nov 7.",
    "recent_highlights": "Portfolio up 27%.",
    "portfolio_narrative": "## Portfolio Narrative\n\nStrong performance.",
    "financial_analysis": "## Financial Position Analysis\n\nSustainable.",
    "opportunities": "## Opportunities\n\nRebalancing needed.",
    "relationship_context": "## Relationship Context\n\nLong-standing client.",
    "action_items": "## Action Items\n\nReview allocation.",
}

# deterministic_sections as generator.py produces: client_summary + portfolio_overview.
# The client_summary template leaves {{ last_interaction_summary }} and {{ recent_highlights }}
# as literal strings (they are passed verbatim from the context dict).
# Sentinel tokens <!-- CHART:allocation --> and <!-- CHART:cash_flow --> are placed by the
# portfolio_overview template at the exact insertion points for chart images.
DETERMINISTIC_SECTIONS = (
    "## Client Summary\n\n"
    "| **Recent Highlights** | {{ recent_highlights }} |\n\n"
    "### Last Interaction\n{{ last_interaction_summary }}\n\n"
    "## Portfolio Overview\n\n"
    "### Asset Allocation\n| Asset | % |\n|---|---|\n| Equity | 50% |\n\n"
    "<!-- CHART:allocation -->\n\n"
    "### Performance\n| Period | Return |\n|---|---|\n| YTD | 5% |\n\n"
    "### Recent Cash Flows\n| Period | Net |\n|---|---|\n| 2025-Q4 | $10k |\n\n"
    "<!-- CHART:cash_flow -->\n\n"
    "### Projected Cash Flows\n| Period | Net |\n|---|---|\n| 2026-Q1 | $12k |\n"
)

# Minimal components dict for invoke_narrative_generator tests
SAMPLE_COMPONENTS = {"synthesis_prompts": {k: f"Write the {k} section." for k in NARRATIVE_KEYS}}


def _make_converse_response(narratives: dict) -> dict:
    """Build a minimal Bedrock Converse response with a toolUse block."""
    return {
        "stopReason": "tool_use",
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "toolUse": {
                            "toolUseId": "tooluse_test123",
                            "name": "submit_narratives",
                            "input": narratives,
                        }
                    }
                ],
            }
        },
    }


# ---------------------------------------------------------------------------
# invoke_narrative_generator — happy path
# ---------------------------------------------------------------------------


def test_invoke_narrative_generator_happy_path():
    """Returns the narratives dict when the model invokes submit_narratives correctly."""
    mock_client = MagicMock()
    mock_client.converse.return_value = _make_converse_response(VALID_NARRATIVES)

    with patch("boto3.client", return_value=mock_client):
        result = invoke_narrative_generator(SAMPLE_COMPONENTS)

    assert result == VALID_NARRATIVES


# ---------------------------------------------------------------------------
# invoke_narrative_generator — validation error cases
# ---------------------------------------------------------------------------


def test_invoke_narrative_generator_missing_key_raises_valueerror():
    """Missing key in tool input raises ValueError mentioning the key."""
    missing_key_narratives = {k: v for k, v in VALID_NARRATIVES.items() if k != "action_items"}
    mock_client = MagicMock()
    mock_client.converse.return_value = _make_converse_response(missing_key_narratives)

    with patch("boto3.client", return_value=mock_client), pytest.raises(ValueError, match="action_items"):
        invoke_narrative_generator(SAMPLE_COMPONENTS)


def test_invoke_narrative_generator_empty_value_raises_valueerror():
    """Empty string value in tool input raises ValueError mentioning 'empty'."""
    empty_value_narratives = {**VALID_NARRATIVES, "opportunities": ""}
    mock_client = MagicMock()
    mock_client.converse.return_value = _make_converse_response(empty_value_narratives)

    with patch("boto3.client", return_value=mock_client), pytest.raises(ValueError, match="empty"):
        invoke_narrative_generator(SAMPLE_COMPONENTS)


def test_invoke_narrative_generator_non_string_value_raises_valueerror():
    """Non-string value in tool input raises ValueError."""
    non_string_narratives = {**VALID_NARRATIVES, "relationship_context": ["a", "b"]}
    mock_client = MagicMock()
    mock_client.converse.return_value = _make_converse_response(non_string_narratives)

    with patch("boto3.client", return_value=mock_client), pytest.raises(ValueError):
        invoke_narrative_generator(SAMPLE_COMPONENTS)


# ---------------------------------------------------------------------------
# invoke_narrative_generator — no toolUse block
# ---------------------------------------------------------------------------


def test_invoke_narrative_generator_no_tool_use_block_raises_runtimeerror():
    """Response with only a text block (no toolUse) raises RuntimeError."""
    text_only_response = {
        "stopReason": "end_turn",
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"text": "Here are the narratives..."}],
            }
        },
    }
    mock_client = MagicMock()
    mock_client.converse.return_value = text_only_response

    with patch("boto3.client", return_value=mock_client), pytest.raises(RuntimeError, match="submit_narratives"):
        invoke_narrative_generator(SAMPLE_COMPONENTS)


# ---------------------------------------------------------------------------
# invoke_narrative_generator — API call shape verification
# ---------------------------------------------------------------------------


def test_invoke_narrative_generator_uses_forced_tool_choice():
    """Converse is called with forced toolChoice and correct required schema."""
    mock_client = MagicMock()
    mock_client.converse.return_value = _make_converse_response(VALID_NARRATIVES)

    with patch("boto3.client", return_value=mock_client):
        invoke_narrative_generator(SAMPLE_COMPONENTS)

    call_kwargs = mock_client.converse.call_args.kwargs
    tool_config = call_kwargs["toolConfig"]

    # Forced tool choice must name submit_narratives
    assert tool_config["toolChoice"] == {"tool": {"name": "submit_narratives"}}

    # Schema required list must equal list(NARRATIVE_KEYS)
    schema = tool_config["tools"][0]["toolSpec"]["inputSchema"]["json"]
    assert schema["required"] == list(NARRATIVE_KEYS)


# ---------------------------------------------------------------------------
# assemble_markdown — section ordering and content
# ---------------------------------------------------------------------------


def test_assemble_markdown_contains_all_narrative_sections():
    """All 7 narrative values appear in the assembled markdown."""
    result = assemble_markdown(DETERMINISTIC_SECTIONS, VALID_NARRATIVES)
    for value in VALID_NARRATIVES.values():
        # last_interaction_summary and recent_highlights are embedded in deterministic
        assert value in result


def test_assemble_markdown_section_order():
    """Sections appear in the required order: client summary → portfolio overview →
    portfolio_narrative → financial_analysis → opportunities → relationship_context → action_items."""
    result = assemble_markdown(DETERMINISTIC_SECTIONS, VALID_NARRATIVES)
    positions = {
        "client_summary": result.index("## Client Summary"),
        "portfolio_overview": result.index("## Portfolio Overview"),
        "portfolio_narrative": result.index(VALID_NARRATIVES["portfolio_narrative"]),
        "financial_analysis": result.index(VALID_NARRATIVES["financial_analysis"]),
        "opportunities": result.index(VALID_NARRATIVES["opportunities"]),
        "relationship_context": result.index(VALID_NARRATIVES["relationship_context"]),
        "action_items": result.index(VALID_NARRATIVES["action_items"]),
    }
    assert positions["client_summary"] < positions["portfolio_overview"]
    assert positions["portfolio_overview"] < positions["portfolio_narrative"]
    assert positions["portfolio_narrative"] < positions["financial_analysis"]
    assert positions["financial_analysis"] < positions["opportunities"]
    assert positions["opportunities"] < positions["relationship_context"]
    assert positions["relationship_context"] < positions["action_items"]


def test_assemble_markdown_placeholders_replaced():
    """{{ last_interaction_summary }} and {{ recent_highlights }} are replaced with model output."""
    result = assemble_markdown(DETERMINISTIC_SECTIONS, VALID_NARRATIVES)
    assert "{{ last_interaction_summary }}" not in result
    assert "{{ recent_highlights }}" not in result
    assert VALID_NARRATIVES["last_interaction_summary"] in result
    assert VALID_NARRATIVES["recent_highlights"] in result


def test_assemble_markdown_deterministic_sections_preserved():
    """Deterministic content (tables, headers) is preserved verbatim in the output."""
    result = assemble_markdown(DETERMINISTIC_SECTIONS, VALID_NARRATIVES)
    assert "## Portfolio Overview" in result
    assert "### Asset Allocation" in result
    assert "### Recent Cash Flows" in result


def test_assemble_markdown_chart_refs_present():
    """Both chart image references appear in the assembled markdown."""
    result = assemble_markdown(DETERMINISTIC_SECTIONS, VALID_NARRATIVES)
    assert "![allocation](allocation.svg)" in result
    assert "![cash_flow](cash_flow.svg)" in result


def test_assemble_markdown_allocation_chart_after_allocation_table():
    """allocation.svg ref appears after the Asset Allocation table, before Performance."""
    result = assemble_markdown(DETERMINISTIC_SECTIONS, VALID_NARRATIVES)
    alloc_table_end = result.index("| Equity | 50% |")
    alloc_chart = result.index("![allocation](allocation.svg)")
    performance = result.index("### Performance")
    assert alloc_table_end < alloc_chart < performance


def test_assemble_markdown_cash_flow_chart_after_cash_flow_table():
    """cash_flow.svg ref appears after the Recent Cash Flows table, before Projected Cash Flows."""
    result = assemble_markdown(DETERMINISTIC_SECTIONS, VALID_NARRATIVES)
    cash_flow_table_end = result.index("| 2025-Q4 | $10k |")
    cash_flow_chart = result.index("![cash_flow](cash_flow.svg)")
    projected = result.index("### Projected Cash Flows")
    assert cash_flow_table_end < cash_flow_chart < projected


def test_assemble_markdown_missing_allocation_sentinel_raises():
    """Missing <!-- CHART:allocation --> in deterministic_sections raises ValueError."""
    bad_sections = DETERMINISTIC_SECTIONS.replace("<!-- CHART:allocation -->", "")
    with pytest.raises(ValueError, match="CHART:allocation"):
        assemble_markdown(bad_sections, VALID_NARRATIVES)


def test_assemble_markdown_missing_cash_flow_sentinel_raises():
    """Missing <!-- CHART:cash_flow --> in deterministic_sections raises ValueError."""
    bad_sections = DETERMINISTIC_SECTIONS.replace("<!-- CHART:cash_flow -->", "")
    with pytest.raises(ValueError, match="CHART:cash_flow"):
        assemble_markdown(bad_sections, VALID_NARRATIVES)


# ---------------------------------------------------------------------------
# Drift-prevention: NARRATIVE_KEYS must match generator synthesis_prompts keys
# ---------------------------------------------------------------------------


def test_narrative_keys_match_generator_synthesis_prompts():
    """NARRATIVE_KEYS must exactly match the keys ReportGenerator puts in synthesis_prompts.

    This test fails loudly if anyone adds/removes a prompt in generator.py without
    updating NARRATIVE_KEYS in agent.py.
    """
    from pathlib import Path

    from wealth_management_portal_report.models import (
        ClientProfile,
        Communications,
        MarketContext,
        Portfolio,
    )

    fixtures = Path(__file__).parent.parent / "fixtures" / "clients" / "gray"
    profile = ClientProfile.model_validate_json((fixtures / "profile.json").read_text())
    portfolio = Portfolio.model_validate_json((fixtures / "portfolio.json").read_text())
    communications = Communications.model_validate_json((fixtures / "communications.json").read_text())
    market_context = MarketContext.model_validate_json((fixtures / "market_context.json").read_text())

    result = ReportGenerator().generate(profile, portfolio, communications, [], market_context)
    assert set(NARRATIVE_KEYS) == set(result["synthesis_prompts"].keys())
