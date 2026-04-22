# Tests for portfolio data access models
from wealth_management_portal_portfolio_data_access.models import Client, PortfolioRecord


def test_models_importable():
    """Verify new Redshift-mirroring models can be imported."""
    assert Client is not None
    assert PortfolioRecord is not None
