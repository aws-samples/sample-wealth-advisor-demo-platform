"""Tests for common/redshift.py — MCP-based query execution."""

from wealth_management_portal_advisor_chat.common.redshift import _convert_to_named


def test_convert_to_named_placeholders():
    sql, params = _convert_to_named("SELECT * FROM t WHERE id = %s AND name = %s", ["CL001", "Alice"])
    assert ":p0" in sql
    assert ":p1" in sql
    assert params == ["CL001", "Alice"]


def test_convert_no_params():
    sql, params = _convert_to_named("SELECT 1", None)
    assert sql == "SELECT 1"
    assert params is None
