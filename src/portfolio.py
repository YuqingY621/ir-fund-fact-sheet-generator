from __future__ import annotations

import pandas as pd

CASH_LABELS = {"cash", "cash equivalents", "cash & equivalents"}


def get_portfolio_snapshot(
    holdings: pd.DataFrame,
    fund_id: str,
    as_of_date: str | pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, pd.Timestamp]:
    required = {"Date", "Fund_ID", "Security_Name", "Asset_Class", "Weight"}
    missing = required - set(holdings.columns)
    if missing:
        raise ValueError("Holdings is missing required columns: " + ", ".join(sorted(missing)))

    data = holdings.loc[holdings["Fund_ID"].astype("string") == str(fund_id)].copy()
    if data.empty:
        raise ValueError(f"No holdings found for fund {fund_id}")

    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    data["Weight"] = pd.to_numeric(data["Weight"], errors="coerce")
    data = data.dropna(subset=["Date", "Weight"])
    requested = data["Date"].max() if as_of_date is None else pd.Timestamp(as_of_date)
    available = data.loc[data["Date"] <= requested, "Date"]
    if available.empty:
        raise ValueError(f"No holdings for {fund_id} on or before {requested.date()}")
    snapshot_date = available.max()
    return data.loc[data["Date"] == snapshot_date].copy(), pd.Timestamp(snapshot_date)


def _is_cash(snapshot: pd.DataFrame) -> pd.Series:
    asset_class = snapshot["Asset_Class"].astype("string").str.strip().str.lower()
    security_name = snapshot["Security_Name"].astype("string").str.strip().str.lower()
    return asset_class.isin(CASH_LABELS) | security_name.isin(CASH_LABELS) | security_name.eq("cash")


def calculate_number_of_holdings(holdings, fund_id, as_of_date=None, exclude_cash=True) -> int:
    snapshot, _ = get_portfolio_snapshot(holdings, fund_id, as_of_date)
    if exclude_cash:
        snapshot = snapshot.loc[~_is_cash(snapshot)]
    if "Security_ID" in snapshot.columns:
        return int(snapshot["Security_ID"].nunique())
    return int(snapshot["Security_Name"].nunique())


def calculate_cash_weight(holdings, fund_id, as_of_date=None) -> float:
    snapshot, _ = get_portfolio_snapshot(holdings, fund_id, as_of_date)
    return float(snapshot.loc[_is_cash(snapshot), "Weight"].sum())


def calculate_top_holdings(holdings, fund_id, as_of_date=None, top_n=10, exclude_cash=True) -> pd.DataFrame:
    if top_n < 1:
        raise ValueError("top_n must be at least 1")
    snapshot, snapshot_date = get_portfolio_snapshot(holdings, fund_id, as_of_date)
    if exclude_cash:
        snapshot = snapshot.loc[~_is_cash(snapshot)].copy()
    columns = [c for c in ["Security_Name", "ISIN", "Sector", "Country", "Asset_Class", "Weight"] if c in snapshot.columns]
    result = snapshot.sort_values("Weight", ascending=False).head(top_n)[columns].reset_index(drop=True)
    result.insert(0, "Rank", range(1, len(result) + 1))
    result["Snapshot_Date"] = snapshot_date
    return result


def calculate_top_n_concentration(holdings, fund_id, as_of_date=None, top_n=10, exclude_cash=True) -> float:
    return float(calculate_top_holdings(holdings, fund_id, as_of_date, top_n, exclude_cash)["Weight"].sum())


def calculate_allocation(
    holdings: pd.DataFrame,
    fund_id: str,
    category: str,
    as_of_date=None,
    include_cash=True,
    top_n: int | None = None,
    other_label="Other",
) -> pd.DataFrame:
    if category not in {"Sector", "Country", "Asset_Class"}:
        raise ValueError("category must be one of: Sector, Country, Asset_Class")
    snapshot, snapshot_date = get_portfolio_snapshot(holdings, fund_id, as_of_date)
    if not include_cash:
        snapshot = snapshot.loc[~_is_cash(snapshot)].copy()
    if category not in snapshot.columns:
        raise ValueError(f"Holdings has no {category} column")

    working = snapshot[[category, "Weight"]].copy()
    working[category] = working[category].astype("string").fillna("Unclassified").replace({"<NA>": "Unclassified"}).str.strip()
    working.loc[working[category].eq(""), category] = "Unclassified"
    result = working.groupby(category, dropna=False)["Weight"].sum().reset_index().sort_values("Weight", ascending=False).reset_index(drop=True)

    if top_n is not None and top_n >= 1 and len(result) > top_n:
        keep = result.head(top_n).copy()
        other_weight = float(result.iloc[top_n:]["Weight"].sum())
        existing_other = keep[category].astype("string").eq(other_label)
        if existing_other.any():
            keep.loc[existing_other, "Weight"] = keep.loc[existing_other, "Weight"] + other_weight
        elif other_weight > 0:
            keep.loc[len(keep)] = {category: other_label, "Weight": other_weight}
        result = keep.groupby(category, as_index=False)["Weight"].sum().sort_values("Weight", ascending=False).reset_index(drop=True)

    result["Snapshot_Date"] = snapshot_date
    return result


def calculate_sector_allocation(holdings, fund_id, as_of_date=None, include_cash=True, top_n=None):
    return calculate_allocation(holdings, fund_id, "Sector", as_of_date, include_cash, top_n)


def calculate_country_allocation(holdings, fund_id, as_of_date=None, include_cash=True, top_n=None):
    return calculate_allocation(holdings, fund_id, "Country", as_of_date, include_cash, top_n)


def calculate_asset_class_allocation(holdings, fund_id, as_of_date=None):
    return calculate_allocation(holdings, fund_id, "Asset_Class", as_of_date, True, None)
