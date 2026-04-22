"""EventBridge cron/rate expression validator."""

import re

_CRON_RE = re.compile(r"^cron\((\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\)$")
_RATE_RE = re.compile(r"^rate\(\d+\s+(minute|minutes|hour|hours|day|days)\)$")
_STANDARD_CRON_RE = re.compile(r"^\S+\s+\S+\s+\S+\s+\S+\s+\S+$")


class ValidationError(ValueError):
    pass


def _normalize_cron(expression: str) -> str:
    """Fix common LLM formatting issues in cron expressions (e.g. '*?' → '* ?')."""
    if not expression.startswith("cron("):
        return expression
    inner = expression[5:-1].strip()
    # Split merged fields: '*?' → '* ?', '1/5*' → '1/5 *', etc.
    inner = re.sub(r"(\S)\?", r"\1 ?", inner)
    inner = re.sub(r"\?(\S)", r"? \1", inner)
    return f"cron({inner})"


def validate_expression(expression: str) -> str:
    """Validate an EventBridge cron or rate expression. Raises ValidationError on failure.

    Returns the (possibly normalized) expression.
    """
    if not expression or not expression.strip():
        raise ValidationError("Expression must not be empty.")

    expression = _normalize_cron(expression)

    if _CRON_RE.match(expression):
        return expression

    if _RATE_RE.match(expression):
        return expression

    if expression.startswith("cron("):
        raise ValidationError(
            f"Invalid EventBridge cron expression '{expression}'. "
            "Expected 6 space-separated fields: cron(minutes hours day-of-month month day-of-week year). "
            "Example: cron(0 16 * * ? *). Retry with a corrected expression."
        )

    if expression.startswith("rate("):
        raise ValidationError(
            f"Invalid rate expression '{expression}'. "
            "Expected format: rate(<value> <unit>) where unit is minute(s), hour(s), or day(s). "
            "Example: rate(6 hours). Retry with a corrected expression."
        )

    if _STANDARD_CRON_RE.match(expression.strip()):
        raise ValidationError(
            f"Standard 5-field cron '{expression}' is not supported. "
            "Use EventBridge format: cron(minutes hours day-of-month month day-of-week year), "
            "e.g. cron(0 16 * * ? *)."
        )

    raise ValidationError(
        f"Invalid expression '{expression}'. "
        "Use EventBridge cron format: cron(0 16 * * ? *) or rate format: rate(6 hours)."
    )
