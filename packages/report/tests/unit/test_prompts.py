# Tests for AI synthesis prompts
from wealth_management_portal_report.prompts import (
    FINANCIAL_ANALYSIS_PROMPT,
    LAST_INTERACTION_PROMPT,
    NEXT_BEST_ACTION_PROMPT,
    OPPORTUNITIES_PROMPT,
    PORTFOLIO_NARRATIVE_PROMPT,
    RECENT_HIGHLIGHTS_PROMPT,
)


def test_portfolio_narrative_prompt_exists():
    """Portfolio narrative prompt should exist and contain required placeholders."""
    assert PORTFOLIO_NARRATIVE_PROMPT is not None
    assert "{market_context_json}" in PORTFOLIO_NARRATIVE_PROMPT
    assert "{portfolio_json}" in PORTFOLIO_NARRATIVE_PROMPT
    # Should guide LLM to synthesize market → portfolio → actions
    assert "market" in PORTFOLIO_NARRATIVE_PROMPT.lower()
    assert "portfolio" in PORTFOLIO_NARRATIVE_PROMPT.lower()
    assert "action" in PORTFOLIO_NARRATIVE_PROMPT.lower()


def test_portfolio_narrative_prompt_structure():
    """Portfolio narrative prompt should require 4 specific subsections."""
    prompt_lower = PORTFOLIO_NARRATIVE_PROMPT.lower()
    # Check for required subsections
    assert "executive summary" in prompt_lower
    assert "market performance" in prompt_lower
    assert "portfolio performance" in prompt_lower
    assert "asset allocation" in prompt_lower
    # Check for markdown formatting requirement
    assert "###" in PORTFOLIO_NARRATIVE_PROMPT


def test_portfolio_narrative_prompt_requirements():
    """Portfolio narrative prompt should include specific requirements."""
    prompt_lower = PORTFOLIO_NARRATIVE_PROMPT.lower()
    # Reference periods requirement
    assert "reference period" in prompt_lower
    # Instrument-level callouts requirement
    assert "instrument" in prompt_lower and ("name" in prompt_lower or "specific" in prompt_lower)
    # Rebalancing specificity requirement
    assert "rebalancing" in prompt_lower
    # Allocation drift acknowledgment
    assert "drift" in prompt_lower or "expected" in prompt_lower


def test_financial_analysis_prompt_references_new_fields():
    """Updated financial analysis prompt should reference new model fields."""
    assert "{profile_json}" in FINANCIAL_ANALYSIS_PROMPT
    assert "{portfolio_json}" in FINANCIAL_ANALYSIS_PROMPT
    # Should mention new fields in instructions
    prompt_lower = FINANCIAL_ANALYSIS_PROMPT.lower()
    assert "target" in prompt_lower or "allocation" in prompt_lower
    assert "projected" in prompt_lower or "cash flow" in prompt_lower
    assert "volatility" in prompt_lower or "risk" in prompt_lower
    # Should use updated section header
    assert "financial goals sustainability assessment" in prompt_lower


def test_last_interaction_prompt_exists():
    """Last interaction prompt should exist and contain required placeholders."""
    assert LAST_INTERACTION_PROMPT is not None
    assert "{profile_json}" in LAST_INTERACTION_PROMPT
    assert "{communications_json}" in LAST_INTERACTION_PROMPT
    # Should guide LLM to synthesize discussion points and actions
    prompt_lower = LAST_INTERACTION_PROMPT.lower()
    assert "interaction" in prompt_lower or "discussion" in prompt_lower
    assert "action" in prompt_lower


def test_recent_highlights_prompt_exists():
    """Recent highlights prompt should exist and contain required placeholders."""
    assert RECENT_HIGHLIGHTS_PROMPT is not None
    assert "{profile_json}" in RECENT_HIGHLIGHTS_PROMPT
    assert "{portfolio_json}" in RECENT_HIGHLIGHTS_PROMPT
    assert "{communications_json}" in RECENT_HIGHLIGHTS_PROMPT


def test_opportunities_prompt_includes_research_links():
    """Opportunities prompt should instruct LLM to include research report links."""
    assert OPPORTUNITIES_PROMPT is not None
    assert "{profile_json}" in OPPORTUNITIES_PROMPT
    assert "{communications_json}" in OPPORTUNITIES_PROMPT
    assert "{products_json}" in OPPORTUNITIES_PROMPT
    # Should instruct LLM to generate research report titles with dummy URLs
    prompt_lower = OPPORTUNITIES_PROMPT.lower()
    assert "research.internal/reports" in OPPORTUNITIES_PROMPT
    assert "product sheet" in prompt_lower or "products.internal" in OPPORTUNITIES_PROMPT
    # Should reference income coverage ratio and de-capitalisation risk
    assert "income coverage" in prompt_lower or "coverage ratio" in prompt_lower
    assert "de-capitalisation" in prompt_lower or "decapitalisation" in prompt_lower


def test_financial_analysis_prompt_rebalancing_context():
    """Financial analysis prompt should handle rebalancing context correctly."""
    prompt_lower = FINANCIAL_ANALYSIS_PROMPT.lower()
    # Should distinguish normal drift from band breaches
    assert "drift" in prompt_lower and ("normal" in prompt_lower or "expected" in prompt_lower)
    # Should only flag rebalancing when outside bands
    assert "outside" in prompt_lower and ("band" in prompt_lower or "target" in prompt_lower)
    # Should require specific adjustment details
    assert "specify" in prompt_lower or "direction" in prompt_lower
    # Should not recommend rebalancing for drift within bands
    assert "not" in prompt_lower and "within" in prompt_lower


def test_next_best_action_prompt_exists():
    """Next best action prompt should exist and contain required placeholders."""
    assert NEXT_BEST_ACTION_PROMPT is not None
    assert "{profile_json}" in NEXT_BEST_ACTION_PROMPT
    assert "{portfolio_json}" in NEXT_BEST_ACTION_PROMPT
    assert "{communications_json}" in NEXT_BEST_ACTION_PROMPT
