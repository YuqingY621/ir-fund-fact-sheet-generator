from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


DEFAULT_LOOKBACK_TOLERANCE_DAYS = 7


@dataclass(frozen=True)
class PerformancePoint:
    """One performance result together with the dates used to calculate it."""
    value: float | None
    start_date: pd.Timestamp | None
    end_date: pd.Timestamp | None
    annualized: bool = False


def _prepare_fund_history(
    nav_history: pd.DataFrame,
    fund_id: str,
    as_of_date: str | pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, pd.Timestamp]:
    """
    Filter and sort one fund's NAV history up to the requested reporting date.

    The workbook should already have passed the data validation module before
    performance calculations are run.
    """
    required = {"Date", "Fund_ID", "NAV", "Benchmark_Value"}
    missing = required - set(nav_history.columns)

    if missing:
        raise ValueError(
            "NAV_History is missing required columns: "
            + ", ".join(sorted(missing))
        )

    history = nav_history.loc[
        nav_history["Fund_ID"].astype("string") == str(fund_id)
    ].copy()

    if history.empty:
        raise ValueError(f"No NAV history found for fund {fund_id}")

    history["Date"] = pd.to_datetime(history["Date"], errors="coerce")
    history = history.dropna(subset=["Date"]).sort_values("Date")

    if as_of_date is None:
        requested_date = history["Date"].max()
    else:
        requested_date = pd.Timestamp(as_of_date)

    history = history.loc[history["Date"] <= requested_date].copy()

    if history.empty:
        raise ValueError(
            f"No NAV history for {fund_id} on or before {requested_date.date()}"
        )

    actual_as_of = history["Date"].max()
    return history, actual_as_of


def _value_on_or_before(
    history: pd.DataFrame,
    target_date: pd.Timestamp,
    column: str,
) -> tuple[float | None, pd.Timestamp | None]:
    """Return the latest available value on or before a target date."""
    eligible = history.loc[
        (history["Date"] <= target_date) & history[column].notna(),
        ["Date", column],
    ]

    if eligible.empty:
        return None, None

    row = eligible.iloc[-1]
    return float(row[column]), pd.Timestamp(row["Date"])


def _is_close_enough(
    actual_date: pd.Timestamp | None,
    target_date: pd.Timestamp,
    tolerance_days: int,
) -> bool:
    """
    Avoid using a stale value as if it represented an anniversary or year-end.

    Example:
    if we ask for the NAV one year ago, a normal weekend gap is acceptable,
    but a value from several months earlier is not.
    """
    if actual_date is None:
        return False

    gap = (target_date - actual_date).days
    return 0 <= gap <= tolerance_days


def _return_between(
    start_value: float,
    end_value: float,
) -> float:
    if start_value <= 0 or end_value <= 0:
        raise ValueError("Performance values must be greater than zero")

    return end_value / start_value - 1.0


def calculate_daily_returns(
    nav_history: pd.DataFrame,
    fund_id: str,
    as_of_date: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """
    Return daily fund, benchmark and active returns.

    Output columns:
    Date, Fund_ID, NAV, Benchmark_Value,
    Fund_Return, Benchmark_Return, Active_Return
    """
    history, _ = _prepare_fund_history(
        nav_history,
        fund_id,
        as_of_date,
    )

    result = history[
        ["Date", "Fund_ID", "NAV", "Benchmark_Value"]
    ].copy()

    result["Fund_Return"] = result["NAV"].pct_change(fill_method=None)
    result["Benchmark_Return"] = result["Benchmark_Value"].pct_change(
        fill_method=None
    )
    result["Active_Return"] = (
        result["Fund_Return"] - result["Benchmark_Return"]
    )

    return result


def calculate_ytd_return(
    nav_history: pd.DataFrame,
    fund_id: str,
    column: str = "NAV",
    as_of_date: str | pd.Timestamp | None = None,
    tolerance_days: int = DEFAULT_LOOKBACK_TOLERANCE_DAYS,
) -> PerformancePoint:
    """
    Calculate year-to-date performance.

    For a fund launched during the reporting year, the first available value
    in that year is used as the starting point.
    """
    history, actual_as_of = _prepare_fund_history(
        nav_history,
        fund_id,
        as_of_date,
    )

    end_value, end_date = _value_on_or_before(
        history,
        actual_as_of,
        column,
    )

    previous_year_end = pd.Timestamp(
        year=actual_as_of.year - 1,
        month=12,
        day=31,
    )

    start_value, start_date = _value_on_or_before(
        history,
        previous_year_end,
        column,
    )

    if not _is_close_enough(
        start_date,
        previous_year_end,
        tolerance_days,
    ):
        current_year = history.loc[
            history["Date"].dt.year == actual_as_of.year,
            ["Date", column],
        ].dropna()

        if current_year.empty:
            return PerformancePoint(None, None, end_date, False)

        first = current_year.iloc[0]
        start_value = float(first[column])
        start_date = pd.Timestamp(first["Date"])

    if start_value is None or end_value is None:
        return PerformancePoint(None, start_date, end_date, False)

    return PerformancePoint(
        _return_between(start_value, end_value),
        start_date,
        end_date,
        False,
    )


def calculate_trailing_return(
    nav_history: pd.DataFrame,
    fund_id: str,
    years: int,
    column: str = "NAV",
    as_of_date: str | pd.Timestamp | None = None,
    tolerance_days: int = DEFAULT_LOOKBACK_TOLERANCE_DAYS,
) -> PerformancePoint:
    """
    Calculate trailing performance.

    1-year performance is reported as a cumulative return.
    Multi-year performance is annualized using the actual number of days
    between observations.
    """
    if years < 1:
        raise ValueError("years must be at least 1")

    history, actual_as_of = _prepare_fund_history(
        nav_history,
        fund_id,
        as_of_date,
    )

    end_value, end_date = _value_on_or_before(
        history,
        actual_as_of,
        column,
    )

    target_start = actual_as_of - pd.DateOffset(years=years)
    start_value, start_date = _value_on_or_before(
        history,
        target_start,
        column,
    )

    if not _is_close_enough(start_date, target_start, tolerance_days):
        return PerformancePoint(None, start_date, end_date, years > 1)

    if start_value is None or end_value is None or start_date is None:
        return PerformancePoint(None, start_date, end_date, years > 1)

    total_return = _return_between(start_value, end_value)

    if years == 1:
        return PerformancePoint(
            total_return,
            start_date,
            end_date,
            False,
        )

    elapsed_days = (end_date - start_date).days

    if elapsed_days <= 0:
        return PerformancePoint(None, start_date, end_date, True)

    annualized_return = (
        (end_value / start_value) ** (365.25 / elapsed_days) - 1.0
    )

    return PerformancePoint(
        annualized_return,
        start_date,
        end_date,
        True,
    )


def calculate_since_inception_return(
    nav_history: pd.DataFrame,
    fund_id: str,
    column: str = "NAV",
    as_of_date: str | pd.Timestamp | None = None,
) -> PerformancePoint:
    """
    Calculate performance from the first available observation.

    If at least one year of history is available, the result is annualized.
    Otherwise, the cumulative return is returned.
    """
    history, actual_as_of = _prepare_fund_history(
        nav_history,
        fund_id,
        as_of_date,
    )

    clean = history.loc[
        history[column].notna(),
        ["Date", column],
    ]

    if clean.empty:
        return PerformancePoint(None, None, None, False)

    first = clean.iloc[0]
    last = clean.iloc[-1]

    start_value = float(first[column])
    end_value = float(last[column])
    start_date = pd.Timestamp(first["Date"])
    end_date = pd.Timestamp(last["Date"])

    total_return = _return_between(start_value, end_value)
    elapsed_days = (end_date - start_date).days

    if elapsed_days < 365:
        return PerformancePoint(
            total_return,
            start_date,
            end_date,
            False,
        )

    annualized_return = (
        (end_value / start_value) ** (365.25 / elapsed_days) - 1.0
    )

    return PerformancePoint(
        annualized_return,
        start_date,
        end_date,
        True,
    )


def calculate_performance_summary(
    nav_history: pd.DataFrame,
    fund_id: str,
    as_of_date: str | pd.Timestamp | None = None,
    periods: Iterable[int] = (1, 3, 5, 10),
) -> pd.DataFrame:
    """
    Build a fact-sheet-ready performance table for fund and benchmark.

    Example output columns:
    Series, YTD, 1Y, 3Y, 5Y, 10Y, Since Inception
    """
    rows: list[dict[str, object]] = []

    for series_name, column in [
        ("Fund", "NAV"),
        ("Benchmark", "Benchmark_Value"),
    ]:
        row: dict[str, object] = {"Series": series_name}

        ytd = calculate_ytd_return(
            nav_history,
            fund_id,
            column=column,
            as_of_date=as_of_date,
        )
        row["YTD"] = ytd.value

        for years in periods:
            point = calculate_trailing_return(
                nav_history,
                fund_id,
                years=years,
                column=column,
                as_of_date=as_of_date,
            )
            row[f"{years}Y"] = point.value

        since_inception = calculate_since_inception_return(
            nav_history,
            fund_id,
            column=column,
            as_of_date=as_of_date,
        )
        row["Since Inception"] = since_inception.value

        rows.append(row)

    return pd.DataFrame(rows)


def calculate_calendar_year_returns(
    nav_history: pd.DataFrame,
    fund_id: str,
    as_of_date: str | pd.Timestamp | None = None,
    max_periods: int = 5,
    tolerance_days: int = DEFAULT_LOOKBACK_TOLERANCE_DAYS,
) -> pd.DataFrame:
    """
    Calculate calendar-year performance for fund and benchmark.

    The current incomplete year is labelled 'YYYY YTD'.
    For the inception year, performance begins with the first available
    observation because there is no prior year-end NAV.
    """
    history, actual_as_of = _prepare_fund_history(
        nav_history,
        fund_id,
        as_of_date,
    )

    first_year = int(history["Date"].min().year)
    years = list(range(first_year, actual_as_of.year + 1))
    years = years[-max_periods:]

    records: list[dict[str, object]] = []

    for year in years:
        year_end_target = pd.Timestamp(year=year, month=12, day=31)
        period_end_target = min(year_end_target, actual_as_of)

        for series_name, column in [
            ("Fund", "NAV"),
            ("Benchmark", "Benchmark_Value"),
        ]:
            end_value, end_date = _value_on_or_before(
                history,
                period_end_target,
                column,
            )

            if end_value is None or end_date is None:
                performance = None
                start_date = None
            elif year == first_year:
                inception_year = history.loc[
                    history["Date"].dt.year == year,
                    ["Date", column],
                ].dropna()

                if inception_year.empty:
                    performance = None
                    start_date = None
                else:
                    first = inception_year.iloc[0]
                    start_value = float(first[column])
                    start_date = pd.Timestamp(first["Date"])
                    performance = _return_between(
                        start_value,
                        end_value,
                    )
            else:
                previous_year_end = pd.Timestamp(
                    year=year - 1,
                    month=12,
                    day=31,
                )
                start_value, start_date = _value_on_or_before(
                    history,
                    previous_year_end,
                    column,
                )

                if (
                    start_value is None
                    or not _is_close_enough(
                        start_date,
                        previous_year_end,
                        tolerance_days,
                    )
                ):
                    performance = None
                else:
                    performance = _return_between(
                        start_value,
                        end_value,
                    )

            is_current_incomplete_year = (
                year == actual_as_of.year
                and actual_as_of < year_end_target
            )
            period_label = (
                f"{year} YTD"
                if is_current_incomplete_year
                else str(year)
            )

            records.append(
                {
                    "Series": series_name,
                    "Period": period_label,
                    "Return": performance,
                    "Start_Date": start_date,
                    "End_Date": end_date,
                }
            )

    return pd.DataFrame(records)


def calculate_growth_of_investment(
    nav_history: pd.DataFrame,
    fund_id: str,
    initial_investment: float = 10_000.0,
    as_of_date: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """
    Normalize fund and benchmark history to the same starting investment.

    This table will later feed the fact-sheet performance chart.
    """
    if initial_investment <= 0:
        raise ValueError("initial_investment must be greater than zero")

    history, _ = _prepare_fund_history(
        nav_history,
        fund_id,
        as_of_date,
    )

    result = history[
        ["Date", "Fund_ID", "NAV", "Benchmark_Value"]
    ].dropna(subset=["NAV", "Benchmark_Value"]).copy()

    if result.empty:
        raise ValueError(
            f"No usable fund/benchmark history found for {fund_id}"
        )

    first_nav = float(result["NAV"].iloc[0])
    first_benchmark = float(result["Benchmark_Value"].iloc[0])

    result["Fund_Growth"] = (
        initial_investment * result["NAV"] / first_nav
    )
    result["Benchmark_Growth"] = (
        initial_investment
        * result["Benchmark_Value"]
        / first_benchmark
    )

    return result[
        [
            "Date",
            "Fund_ID",
            "Fund_Growth",
            "Benchmark_Growth",
        ]
    ]



def calculate_custom_period_return(
    nav_history: pd.DataFrame,
    fund_id: str,
    start_date: str | pd.Timestamp,
    end_date: str | pd.Timestamp,
    column: str = "NAV",
    annualize: bool = False,
) -> PerformancePoint:
    """Calculate point-to-point performance for a user-selected date range.

    The first available observation on or after ``start_date`` and the last
    available observation on or before ``end_date`` are used. This is practical
    for periods that start or end on weekends or market holidays.
    """
    start_target = pd.Timestamp(start_date)
    end_target = pd.Timestamp(end_date)

    if start_target > end_target:
        raise ValueError("start_date must be on or before end_date")

    history, _ = _prepare_fund_history(
        nav_history,
        fund_id,
        as_of_date=end_target,
    )

    clean = history.loc[
        (history["Date"] >= start_target)
        & (history["Date"] <= end_target)
        & history[column].notna(),
        ["Date", column],
    ]

    if len(clean) < 2:
        return PerformancePoint(None, None, None, annualize)

    first = clean.iloc[0]
    last = clean.iloc[-1]
    start_value = float(first[column])
    end_value = float(last[column])
    actual_start = pd.Timestamp(first["Date"])
    actual_end = pd.Timestamp(last["Date"])
    total_return = _return_between(start_value, end_value)

    if not annualize:
        return PerformancePoint(
            total_return,
            actual_start,
            actual_end,
            False,
        )

    elapsed_days = (actual_end - actual_start).days
    if elapsed_days <= 0:
        return PerformancePoint(None, actual_start, actual_end, True)

    annualized_return = (
        (end_value / start_value) ** (365.25 / elapsed_days) - 1.0
    )
    return PerformancePoint(
        annualized_return,
        actual_start,
        actual_end,
        True,
    )

def format_percent_table(
    table: pd.DataFrame,
    decimals: int = 2,
) -> pd.DataFrame:
    """
    Create a presentation copy of a performance table.

    Calculations remain numeric in the core functions. Formatting is kept
    separate so later Streamlit and PDF code can choose their own style.
    """
    formatted = table.copy()

    for column in formatted.columns:
        if column == "Series":
            continue

        formatted[column] = formatted[column].map(
            lambda value: (
                "N/A"
                if pd.isna(value)
                else f"{float(value):.{decimals}%}"
            )
        )

    return formatted
