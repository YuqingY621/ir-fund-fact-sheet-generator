from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricDefinition:
    metric_id: str
    label: str
    category: str
    default_selected: bool
    format_type: str
    requires_benchmark: bool = False
    requires_risk_free_rate: bool = False
    description: str = ""


PERFORMANCE_METRICS = [
    MetricDefinition("custom_net_performance", "Net Performance", "Performance", True, "percent", description="Point-to-point fund performance for a selected date range."),
    MetricDefinition("standard_performance_table", "Standard Performance Table", "Performance", True, "table", description="YTD, 1Y, 3Y, 5Y, 10Y and since-inception returns."),
    MetricDefinition("calendar_year_returns", "Calendar-Year Performance", "Performance", True, "table"),
    MetricDefinition("growth_of_10000", "Growth of 10,000", "Performance", True, "chart"),
]

RISK_METRICS = [
    MetricDefinition("annualized_volatility", "Annualized Volatility", "Risk", True, "percent"),
    MetricDefinition("sharpe_ratio", "Sharpe Ratio", "Risk", True, "ratio", requires_risk_free_rate=True),
    MetricDefinition("maximum_drawdown", "Maximum Drawdown", "Risk", True, "percent"),
    MetricDefinition("beta", "Beta", "Risk", False, "ratio", requires_benchmark=True),
    MetricDefinition("tracking_error", "Tracking Error", "Risk", False, "percent", requires_benchmark=True),
    MetricDefinition("information_ratio", "Information Ratio", "Risk", False, "ratio", requires_benchmark=True),
]

PORTFOLIO_METRICS = [
    MetricDefinition("top_holdings", "Top Holdings", "Portfolio", True, "table"),
    MetricDefinition("sector_allocation", "Sector Allocation", "Portfolio", True, "chart"),
    MetricDefinition("country_allocation", "Country Allocation", "Portfolio", True, "chart"),
    MetricDefinition("asset_class_allocation", "Asset-Class Allocation", "Portfolio", False, "chart"),
    MetricDefinition("top_10_concentration", "Top 10 Concentration", "Portfolio", False, "percent"),
    MetricDefinition("cash_weight", "Cash Weight", "Portfolio", False, "percent"),
    MetricDefinition("number_of_holdings", "Number of Holdings", "Portfolio", True, "integer"),
]
