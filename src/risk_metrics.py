from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

import pandas as pd

from src.performance import calculate_daily_returns

TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True)
class RiskMetricResult:
    value: float | None
    start_date: pd.Timestamp | None
    end_date: pd.Timestamp | None
    observations: int


def _filter_period(
    returns: pd.DataFrame,
    years: int | None = 3,
    start_date: str | pd.Timestamp | None = None,
    end_date: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    if returns.empty:
        return returns.copy()

    result = returns.copy()

    if end_date is not None:
        result = result.loc[result["Date"] <= pd.Timestamp(end_date)].copy()

    if result.empty:
        return result

    actual_end = result["Date"].max()

    if start_date is not None:
        start = pd.Timestamp(start_date)
        if start > actual_end:
            return result.iloc[0:0].copy()
        result = result.loc[result["Date"] >= start].copy()
    elif years is not None:
        if years < 1:
            raise ValueError("years must be at least 1 or None")
        start_target = actual_end - pd.DateOffset(years=years)
        result = result.loc[result["Date"] > start_target].copy()

    return result


def _get_returns_for_period(
    nav_history: pd.DataFrame,
    fund_id: str,
    as_of_date: str | pd.Timestamp | None,
    years: int | None,
    start_date: str | pd.Timestamp | None,
    end_date: str | pd.Timestamp | None,
) -> pd.DataFrame:
    effective_end = end_date if end_date is not None else as_of_date
    returns = calculate_daily_returns(
        nav_history,
        fund_id,
        as_of_date=effective_end,
    )
    return _filter_period(
        returns,
        years=years,
        start_date=start_date,
        end_date=end_date,
    )


def _result(value: float | None, dates: pd.Series) -> RiskMetricResult:
    dates = dates.dropna()
    if dates.empty:
        return RiskMetricResult(value, None, None, 0)
    return RiskMetricResult(
        value,
        pd.Timestamp(dates.min()),
        pd.Timestamp(dates.max()),
        int(len(dates)),
    )


def calculate_annualized_volatility(
    nav_history: pd.DataFrame,
    fund_id: str,
    as_of_date: str | pd.Timestamp | None = None,
    years: int | None = 3,
    start_date: str | pd.Timestamp | None = None,
    end_date: str | pd.Timestamp | None = None,
) -> RiskMetricResult:
    returns = _get_returns_for_period(
        nav_history, fund_id, as_of_date, years, start_date, end_date
    )
    clean = returns.dropna(subset=["Fund_Return"])
    if len(clean) < 2:
        return _result(None, clean["Date"])
    value = clean["Fund_Return"].std(ddof=1) * sqrt(TRADING_DAYS_PER_YEAR)
    return _result(float(value), clean["Date"])


def calculate_beta(
    nav_history: pd.DataFrame,
    fund_id: str,
    as_of_date: str | pd.Timestamp | None = None,
    years: int | None = 3,
    start_date: str | pd.Timestamp | None = None,
    end_date: str | pd.Timestamp | None = None,
) -> RiskMetricResult:
    returns = _get_returns_for_period(
        nav_history, fund_id, as_of_date, years, start_date, end_date
    )
    clean = returns.dropna(subset=["Fund_Return", "Benchmark_Return"])
    if len(clean) < 2:
        return _result(None, clean["Date"])
    benchmark_variance = clean["Benchmark_Return"].var(ddof=1)
    if benchmark_variance == 0:
        return _result(None, clean["Date"])
    beta = clean["Fund_Return"].cov(clean["Benchmark_Return"]) / benchmark_variance
    return _result(float(beta), clean["Date"])


def calculate_tracking_error(
    nav_history: pd.DataFrame,
    fund_id: str,
    as_of_date: str | pd.Timestamp | None = None,
    years: int | None = 3,
    start_date: str | pd.Timestamp | None = None,
    end_date: str | pd.Timestamp | None = None,
) -> RiskMetricResult:
    returns = _get_returns_for_period(
        nav_history, fund_id, as_of_date, years, start_date, end_date
    )
    clean = returns.dropna(subset=["Active_Return"])
    if len(clean) < 2:
        return _result(None, clean["Date"])
    value = clean["Active_Return"].std(ddof=1) * sqrt(TRADING_DAYS_PER_YEAR)
    return _result(float(value), clean["Date"])


def calculate_max_drawdown(
    nav_history: pd.DataFrame,
    fund_id: str,
    as_of_date: str | pd.Timestamp | None = None,
    years: int | None = 3,
    start_date: str | pd.Timestamp | None = None,
    end_date: str | pd.Timestamp | None = None,
) -> RiskMetricResult:
    returns = _get_returns_for_period(
        nav_history, fund_id, as_of_date, years, start_date, end_date
    )
    clean = returns.dropna(subset=["NAV"]).copy()
    if clean.empty:
        return _result(None, clean["Date"])
    drawdown = clean["NAV"] / clean["NAV"].cummax() - 1.0
    return _result(float(drawdown.min()), clean["Date"])


def calculate_sharpe_ratio(
    nav_history: pd.DataFrame,
    fund_id: str,
    annual_risk_free_rate: float = 0.0,
    as_of_date: str | pd.Timestamp | None = None,
    years: int | None = 3,
    start_date: str | pd.Timestamp | None = None,
    end_date: str | pd.Timestamp | None = None,
) -> RiskMetricResult:
    returns = _get_returns_for_period(
        nav_history, fund_id, as_of_date, years, start_date, end_date
    )
    clean = returns.dropna(subset=["Fund_Return"])
    if len(clean) < 2:
        return _result(None, clean["Date"])

    daily_rf = (1.0 + annual_risk_free_rate) ** (1.0 / TRADING_DAYS_PER_YEAR) - 1.0
    excess_daily = clean["Fund_Return"] - daily_rf
    daily_vol = clean["Fund_Return"].std(ddof=1)
    if daily_vol == 0:
        return _result(None, clean["Date"])
    value = excess_daily.mean() / daily_vol * sqrt(TRADING_DAYS_PER_YEAR)
    return _result(float(value), clean["Date"])


def calculate_information_ratio(
    nav_history: pd.DataFrame,
    fund_id: str,
    as_of_date: str | pd.Timestamp | None = None,
    years: int | None = 3,
    start_date: str | pd.Timestamp | None = None,
    end_date: str | pd.Timestamp | None = None,
) -> RiskMetricResult:
    returns = _get_returns_for_period(
        nav_history, fund_id, as_of_date, years, start_date, end_date
    )
    clean = returns.dropna(subset=["Active_Return"])
    if len(clean) < 2:
        return _result(None, clean["Date"])
    daily_te = clean["Active_Return"].std(ddof=1)
    if daily_te == 0:
        return _result(None, clean["Date"])
    value = clean["Active_Return"].mean() / daily_te * sqrt(TRADING_DAYS_PER_YEAR)
    return _result(float(value), clean["Date"])


RISK_CALCULATORS = {
    "annualized_volatility": calculate_annualized_volatility,
    "sharpe_ratio": calculate_sharpe_ratio,
    "maximum_drawdown": calculate_max_drawdown,
    "beta": calculate_beta,
    "tracking_error": calculate_tracking_error,
    "information_ratio": calculate_information_ratio,
}


def calculate_selected_risk_metrics(
    nav_history: pd.DataFrame,
    fund_id: str,
    selected_metrics: list[str],
    annual_risk_free_rate: float = 0.0,
    as_of_date: str | pd.Timestamp | None = None,
    years: int | None = 3,
    start_date: str | pd.Timestamp | None = None,
    end_date: str | pd.Timestamp | None = None,
) -> dict[str, RiskMetricResult]:
    results: dict[str, RiskMetricResult] = {}

    for metric_id in selected_metrics:
        if metric_id not in RISK_CALCULATORS:
            raise ValueError(f"Unknown risk metric: {metric_id}")
        calculator = RISK_CALCULATORS[metric_id]
        kwargs = dict(
            nav_history=nav_history,
            fund_id=fund_id,
            as_of_date=as_of_date,
            years=years,
            start_date=start_date,
            end_date=end_date,
        )
        if metric_id == "sharpe_ratio":
            kwargs["annual_risk_free_rate"] = annual_risk_free_rate
        results[metric_id] = calculator(**kwargs)

    return results
