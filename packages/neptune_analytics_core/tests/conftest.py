"""Unit tests configuration module."""


# Suppress pytest exit code 5 (no tests collected) until real tests are added
def pytest_sessionfinish(session, exitstatus):
    if exitstatus == 5:
        session.exitstatus = 0
