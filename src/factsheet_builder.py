from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from src.performance import (
    calculate_calendar_year_returns,
    calculate_custom_period_return,
    calculate_growth_of_investment,
    calculate_performance_summary,
)
from src.portfolio import (
    calculate_asset_class_allocation,
    calculate_cash_weight,
    calculate_country_allocation,
    calculate_number_of_holdings,
    calculate_sector_allocation,
    calculate_top_holdings,
    calculate_top_n_concentration,
    get_portfolio_snapshot,
)
from src.risk_metrics import calculate_selected_risk_metrics


@dataclass
class FactSheetRequest:
    fund_id: str
    reporting_date: pd.Timestamp
    performance_metrics: list[str]
    risk_metrics: list[str]
    portfolio_metrics: list[str]
    performance_start_date: pd.Timestamp | None = None
    performance_end_date: pd.Timestamp | None = None
    risk_period_mode: str = "3Y"
    risk_start_date: pd.Timestamp | None = None
    risk_end_date: pd.Timestamp | None = None
    risk_free_rate: float = 0.0
    top_n_holdings: int = 10
    initial_investment: float = 10_000.0


def _fund_row(fund_master: pd.DataFrame, fund_id: str) -> pd.Series:
    rows = fund_master.loc[fund_master["Fund_ID"].astype("string") == str(fund_id)]
    if rows.empty:
        raise ValueError(f"Fund {fund_id} not found in Fund_Master")
    return rows.iloc[0]


def _risk_period_kwargs(mode, reporting_date, start_date, end_date) -> dict[str, Any]:
    normalized = mode.strip().lower()
    if normalized in {"1y", "3y", "5y"}:
        return {"years": int(normalized[0]), "start_date": None, "end_date": reporting_date}
    if normalized in {"since inception", "since_inception"}:
        return {"years": None, "start_date": None, "end_date": reporting_date}
    if normalized == "custom":
        if start_date is None:
            raise ValueError("A custom risk period requires a start date")
        return {
            "years": None,
            "start_date": pd.Timestamp(start_date),
            "end_date": reporting_date if end_date is None else pd.Timestamp(end_date),
        }
    raise ValueError(f"Unknown risk period mode: {mode}")


def build_factsheet_data(data: dict[str, pd.DataFrame], request: FactSheetRequest) -> dict[str, Any]:
    """Assemble exactly the sections selected in the web app."""
    fund = _fund_row(data["Fund_Master"], request.fund_id)
    nav_history = data["NAV_History"]
    holdings = data["Holdings"]
    reporting_date = pd.Timestamp(request.reporting_date)

    fund_nav = nav_history.loc[
        (nav_history["Fund_ID"].astype("string") == str(request.fund_id))
        & (nav_history["Date"] <= reporting_date)
    ].sort_values("Date")
    latest_nav = None if fund_nav.empty else fund_nav.iloc[-1].to_dict()

    output: dict[str, Any] = {
        "fund": fund.to_dict(),
        "reporting_date": reporting_date,
        "latest_nav": latest_nav,
        "performance": {},
        "risk": {},
        "portfolio": {},
        "warnings": [],
    }

    if "custom_net_performance" in request.performance_metrics:
        if request.performance_start_date is None:
            raise ValueError("Net Performance requires a start date")
        perf_end = reporting_date if request.performance_end_date is None else pd.Timestamp(request.performance_end_date)
        output["performance"]["custom_net_performance"] = calculate_custom_period_return(
            nav_history, request.fund_id, request.performance_start_date, perf_end, column="NAV", annualize=False
        )

    if "standard_performance_table" in request.performance_metrics:
        output["performance"]["standard_performance_table"] = calculate_performance_summary(
            nav_history, request.fund_id, as_of_date=reporting_date
        )
    if "calendar_year_returns" in request.performance_metrics:
        output["performance"]["calendar_year_returns"] = calculate_calendar_year_returns(
            nav_history, request.fund_id, as_of_date=reporting_date, max_periods=5
        )
    if "growth_of_10000" in request.performance_metrics:
        output["performance"]["growth_of_10000"] = calculate_growth_of_investment(
            nav_history, request.fund_id, initial_investment=request.initial_investment, as_of_date=reporting_date
        )

    if request.risk_metrics:
        risk_kwargs = _risk_period_kwargs(
            request.risk_period_mode, reporting_date, request.risk_start_date, request.risk_end_date
        )
        output["risk"] = calculate_selected_risk_metrics(
            nav_history,
            request.fund_id,
            request.risk_metrics,
            annual_risk_free_rate=request.risk_free_rate,
            as_of_date=reporting_date,
            **risk_kwargs,
        )
        output["risk_period"] = risk_kwargs

    if request.portfolio_metrics:
        _, snapshot_date = get_portfolio_snapshot(holdings, request.fund_id, reporting_date)
        output["portfolio"]["snapshot_date"] = snapshot_date
        if snapshot_date < reporting_date:
            output["warnings"].append(
                f"Holdings snapshot is {snapshot_date.date()}, before fact-sheet date {reporting_date.date()}."
            )

        if "top_holdings" in request.portfolio_metrics:
            output["portfolio"]["top_holdings"] = calculate_top_holdings(
                holdings, request.fund_id, reporting_date, request.top_n_holdings, True
            )
        if "sector_allocation" in request.portfolio_metrics:
            output["portfolio"]["sector_allocation"] = calculate_sector_allocation(
                holdings, request.fund_id, reporting_date, True, 8
            )
        if "country_allocation" in request.portfolio_metrics:
            output["portfolio"]["country_allocation"] = calculate_country_allocation(
                holdings, request.fund_id, reporting_date, True, 8
            )
        if "asset_class_allocation" in request.portfolio_metrics:
            output["portfolio"]["asset_class_allocation"] = calculate_asset_class_allocation(
                holdings, request.fund_id, reporting_date
            )
        if "top_10_concentration" in request.portfolio_metrics:
            output["portfolio"]["top_10_concentration"] = calculate_top_n_concentration(
                holdings, request.fund_id, reporting_date, 10, True
            )
        if "cash_weight" in request.portfolio_metrics:
            output["portfolio"]["cash_weight"] = calculate_cash_weight(holdings, request.fund_id, reporting_date)
        if "number_of_holdings" in request.portfolio_metrics:
            output["portfolio"]["number_of_holdings"] = calculate_number_of_holdings(
                holdings, request.fund_id, reporting_date, True
            )

    return output
