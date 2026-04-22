"""Tests for client search agent SQL extraction."""

from wealth_management_portal_client_search.client_search_agent.main import _extract_sql


def test_extract_sql_plain():
    assert _extract_sql("SELECT * FROM clients LIMIT 100") == "SELECT * FROM clients LIMIT 100"


def test_extract_sql_from_code_block():
    text = "```sql\nSELECT * FROM clients WHERE segment = 'HNW' LIMIT 100\n```"
    assert "HNW" in _extract_sql(text)


def test_extract_sql_with_surrounding_text():
    text = "Here is the query:\nSELECT * FROM clients WHERE city ILIKE '%NYC%' LIMIT 50\nThis should work."
    result = _extract_sql(text)
    assert result.startswith("SELECT")
    assert "NYC" in result


def test_extract_sql_no_match():
    assert _extract_sql("I don't know") is None
