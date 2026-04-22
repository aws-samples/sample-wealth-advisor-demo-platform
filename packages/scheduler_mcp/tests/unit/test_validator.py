import pytest

from wealth_management_portal_scheduler_mcp.validator import ValidationError, validate_expression


def test_valid_cron():
    validate_expression("cron(0 16 * * ? *)")


def test_valid_rate_hours():
    validate_expression("rate(6 hours)")


def test_valid_rate_minutes():
    validate_expression("rate(30 minutes)")


def test_valid_rate_day():
    validate_expression("rate(1 day)")


def test_invalid_cron_wrong_field_count():
    with pytest.raises(ValidationError, match="6 space-separated fields"):
        validate_expression("cron(0 16 *)")


def test_invalid_rate_missing_unit():
    with pytest.raises(ValidationError):
        validate_expression("rate(6)")


def test_standard_cron_rejected_with_suggestion():
    with pytest.raises(ValidationError, match="EventBridge format"):
        validate_expression("0 16 * * *")


def test_empty_string():
    with pytest.raises(ValidationError, match="empty"):
        validate_expression("")


def test_whitespace_only():
    with pytest.raises(ValidationError, match="empty"):
        validate_expression("   ")


def test_garbage_string():
    with pytest.raises(ValidationError):
        validate_expression("not-a-cron")
