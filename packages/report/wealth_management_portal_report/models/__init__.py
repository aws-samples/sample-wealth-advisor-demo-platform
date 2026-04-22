# Report-shaped models for advisor portal report generation
from wealth_management_portal_report.models.client_profile import (
    ActivityLevel,
    AssociatedAccount,
    ClientProfile,
    DocumentLink,
    RiskProfile,
    ServiceModel,
    Sophistication,
)
from wealth_management_portal_report.models.communications import (
    Communications,
    Email,
    Meeting,
    Task,
)
from wealth_management_portal_report.models.market_context import (
    BenchmarkReturn,
    MarketContext,
    MarketEvent,
    SectorPerformance,
)
from wealth_management_portal_report.models.portfolio import (
    CashFlow,
    Holding,
    IncomeExpenseAnalysis,
    PerformanceMetrics,
    Portfolio,
    Position,
    ProjectedCashFlow,
    ProjectedPortfolioValue,
    TargetAllocation,
)

__all__ = [
    "ClientProfile",
    "AssociatedAccount",
    "DocumentLink",
    "RiskProfile",
    "ServiceModel",
    "ActivityLevel",
    "Sophistication",
    "Portfolio",
    "Holding",
    "Position",
    "PerformanceMetrics",
    "CashFlow",
    "IncomeExpenseAnalysis",
    "TargetAllocation",
    "ProjectedCashFlow",
    "ProjectedPortfolioValue",
    "Communications",
    "Meeting",
    "Email",
    "Task",
    "MarketContext",
    "BenchmarkReturn",
    "SectorPerformance",
    "MarketEvent",
]
