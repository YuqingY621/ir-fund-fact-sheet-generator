from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd


REQUIRED_SHEETS = {
    "Fund_Master": {
        "Fund_ID",
        "Fund_Name",
        "Ticker",
        "Asset_Class",
        "Benchmark_Name",
        "Launch_Date",
        "Currency",
        "Management_Fee",
        "Fund_Description",
    },
    "NAV_History": {
        "Date",
        "Fund_ID",
        "NAV",
        "Benchmark_Value",
        "AUM",
    },
    "Holdings": {
        "Date",
        "Fund_ID",
        "Security_Name",
        "Sector",
        "Country",
        "Asset_Class",
        "Weight",
    },
    "Fund_Stats": {
        "Date",
        "Fund_ID",
        "Shares_Outstanding",
        "Net_Subscriptions",
        "Net_Redemptions",
        "Cash_Weight",
    },
}

DATE_COLUMNS = {
    "Fund_Master": ["Launch_Date"],
    "NAV_History": ["Date"],
    "Holdings": ["Date"],
    "Fund_Stats": ["Date"],
}

NUMERIC_COLUMNS = {
    "Fund_Master": ["Management_Fee", "Risk_Level"],
    "NAV_History": ["NAV", "Market_Price", "Benchmark_Value", "AUM"],
    "Holdings": ["Weight"],
    "Fund_Stats": [
        "Shares_Outstanding",
        "Net_Subscriptions",
        "Net_Redemptions",
        "Cash_Weight",
    ],
}


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


def _clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize column names and remove fully empty rows."""
    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]
    return df.dropna(how="all")


def _convert_types(sheet_name: str, df: pd.DataFrame) -> pd.DataFrame:
    """Convert date and numeric columns into predictable Python types."""
    df = df.copy()

    for col in DATE_COLUMNS.get(sheet_name, []):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    for col in NUMERIC_COLUMNS.get(sheet_name, []):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "Fund_ID" in df.columns:
        df["Fund_ID"] = df["Fund_ID"].astype("string").str.strip()

    return df


def load_fund_workbook(file_path: str | Path) -> dict[str, pd.DataFrame]:
    """
    Read the IR input workbook and return one DataFrame per sheet.

    The function deliberately separates loading from validation.
    That makes the project easier to maintain when the workbook grows.
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Workbook not found: {file_path}")

    data: dict[str, pd.DataFrame] = {}

    with pd.ExcelFile(file_path) as excel_file:
        missing_sheets = set(REQUIRED_SHEETS) - set(excel_file.sheet_names)

        if missing_sheets:
            missing = ", ".join(sorted(missing_sheets))
            raise ValueError(f"Missing required sheet(s): {missing}")

        for sheet_name in REQUIRED_SHEETS:
            df = pd.read_excel(excel_file, sheet_name=sheet_name)
            df = _clean_columns(df)
            df = _convert_types(sheet_name, df)
            data[sheet_name] = df

    return data


def validate_fund_data(
    data: dict[str, pd.DataFrame],
    holdings_tolerance: float = 0.01,
) -> ValidationReport:
    """
    Run data-quality checks before any fact-sheet calculations.

    Errors mean the fact sheet should not be generated.
    Warnings mean the data can be loaded, but a human should review it.
    """
    report = ValidationReport()

    # 1. Required columns
    for sheet_name, required_columns in REQUIRED_SHEETS.items():
        df = data[sheet_name]
        missing_columns = required_columns - set(df.columns)

        if missing_columns:
            report.errors.append(
                f"{sheet_name}: missing columns: "
                + ", ".join(sorted(missing_columns))
            )

    if report.errors:
        return report

    fund_master = data["Fund_Master"]
    nav = data["NAV_History"]
    holdings = data["Holdings"]
    stats = data["Fund_Stats"]

    # 2. Required-key null checks
    required_non_null = {
        "Fund_Master": ["Fund_ID", "Fund_Name", "Launch_Date", "Currency"],
        "NAV_History": ["Date", "Fund_ID", "NAV", "Benchmark_Value"],
        "Holdings": ["Date", "Fund_ID", "Security_Name", "Weight"],
        "Fund_Stats": ["Date", "Fund_ID"],
    }

    for sheet_name, columns in required_non_null.items():
        df = data[sheet_name]
        for col in columns:
            if df[col].isna().any():
                count = int(df[col].isna().sum())
                report.errors.append(
                    f"{sheet_name}.{col}: {count} missing value(s)"
                )

    # 3. Fund IDs must be unique in the master table
    duplicated_funds = fund_master[
        fund_master["Fund_ID"].duplicated(keep=False)
    ]["Fund_ID"].dropna().unique()

    if len(duplicated_funds) > 0:
        report.errors.append(
            "Fund_Master: duplicate Fund_ID values: "
            + ", ".join(map(str, duplicated_funds))
        )

    # 4. Foreign-key checks
    valid_fund_ids = set(fund_master["Fund_ID"].dropna())

    for sheet_name in ["NAV_History", "Holdings", "Fund_Stats"]:
        unknown = (
            set(data[sheet_name]["Fund_ID"].dropna()) - valid_fund_ids
        )
        if unknown:
            report.errors.append(
                f"{sheet_name}: unknown Fund_ID values: "
                + ", ".join(sorted(map(str, unknown)))
            )

    # 5. Duplicate records
    duplicate_keys = {
        "NAV_History": ["Date", "Fund_ID"],
        "Fund_Stats": ["Date", "Fund_ID"],
    }

    if "Security_ID" in holdings.columns:
        duplicate_keys["Holdings"] = ["Date", "Fund_ID", "Security_ID"]
    else:
        duplicate_keys["Holdings"] = ["Date", "Fund_ID", "Security_Name"]

    for sheet_name, keys in duplicate_keys.items():
        df = data[sheet_name]
        duplicate_count = int(df.duplicated(keys).sum())
        if duplicate_count:
            report.errors.append(
                f"{sheet_name}: {duplicate_count} duplicate record(s) "
                f"for key {keys}"
            )

    # 6. Numeric sanity checks
    if (nav["NAV"].dropna() <= 0).any():
        report.errors.append("NAV_History: NAV must be greater than 0")

    if (nav["Benchmark_Value"].dropna() <= 0).any():
        report.errors.append(
            "NAV_History: Benchmark_Value must be greater than 0"
        )

    if (nav["AUM"].dropna() < 0).any():
        report.errors.append("NAV_History: AUM cannot be negative")

    if ((holdings["Weight"].dropna() < 0) |
        (holdings["Weight"].dropna() > 1)).any():
        report.errors.append(
            "Holdings: Weight must be between 0 and 1"
        )

    if ((stats["Cash_Weight"].dropna() < 0) |
        (stats["Cash_Weight"].dropna() > 1)).any():
        report.errors.append(
            "Fund_Stats: Cash_Weight must be between 0 and 1"
        )

    # 7. Portfolio weights should total approximately 100%
    weight_totals = (
        holdings.groupby(["Date", "Fund_ID"], dropna=False)["Weight"]
        .sum()
        .reset_index(name="Total_Weight")
    )

    for _, row in weight_totals.iterrows():
        difference = abs(float(row["Total_Weight"]) - 1.0)
        if difference > holdings_tolerance:
            report.warnings.append(
                f"Holdings: {row['Fund_ID']} on "
                f"{row['Date'].date()} totals "
                f"{row['Total_Weight']:.2%}, not 100%"
            )

    # 8. Cash weight in Holdings should agree with Fund_Stats
    cash_holdings = holdings[
        holdings["Asset_Class"].astype("string").str.lower() == "cash"
    ]

    if not cash_holdings.empty:
        cash_by_fund = (
            cash_holdings.groupby(["Date", "Fund_ID"])["Weight"]
            .sum()
            .reset_index(name="Holdings_Cash_Weight")
        )

        cash_check = stats.merge(
            cash_by_fund,
            on=["Date", "Fund_ID"],
            how="left",
        )

        cash_check["Holdings_Cash_Weight"] = (
            cash_check["Holdings_Cash_Weight"].fillna(0)
        )

        for _, row in cash_check.iterrows():
            if pd.isna(row["Cash_Weight"]):
                continue

            difference = abs(
                float(row["Cash_Weight"])
                - float(row["Holdings_Cash_Weight"])
            )

            if difference > holdings_tolerance:
                report.warnings.append(
                    f"Cash weight mismatch for {row['Fund_ID']} on "
                    f"{row['Date'].date()}: "
                    f"Fund_Stats={row['Cash_Weight']:.2%}, "
                    f"Holdings={row['Holdings_Cash_Weight']:.2%}"
                )

    # 9. Each fund should have NAV data on or after launch
    for _, fund in fund_master.iterrows():
        fund_id = fund["Fund_ID"]
        fund_nav = nav[nav["Fund_ID"] == fund_id]

        if fund_nav.empty:
            report.errors.append(
                f"NAV_History: no NAV observations for {fund_id}"
            )
            continue

        first_nav = fund_nav["Date"].min()
        launch_date = fund["Launch_Date"]

        if pd.notna(launch_date) and first_nav < launch_date:
            report.warnings.append(
                f"{fund_id}: NAV history begins before Launch_Date"
            )

    # 10. Summary used by the command-line checker and later by Streamlit
    report.summary = {
        "fund_count": int(fund_master["Fund_ID"].nunique()),
        "nav_observations": int(len(nav)),
        "nav_start_date": nav["Date"].min(),
        "nav_end_date": nav["Date"].max(),
        "holdings_rows": int(len(holdings)),
        "fund_stats_rows": int(len(stats)),
    }

    return report


def list_available_funds(
    data: dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """Return a small clean table for a future fund-selection dropdown."""
    columns = [
        "Fund_ID",
        "Fund_Name",
        "Ticker",
        "Asset_Class",
        "Currency",
    ]
    return data["Fund_Master"][columns].copy()


def get_latest_reporting_date(
    data: dict[str, pd.DataFrame],
    fund_id: str,
) -> pd.Timestamp:
    """Find the most recent NAV date available for one fund."""
    fund_nav = data["NAV_History"].loc[
        data["NAV_History"]["Fund_ID"] == fund_id,
        "Date",
    ]

    if fund_nav.empty:
        raise ValueError(f"No NAV data found for {fund_id}")

    return fund_nav.max()
