from pathlib import Path
import pandas as pd

from src.branding import prepare_logo
from src.data_loader import load_fund_workbook, validate_fund_data
from src.factsheet_builder import FactSheetRequest, build_factsheet_data
from src.pdf_exporter import generate_factsheet_pdf

ROOT = Path(__file__).parent


def main():
    data = load_fund_workbook(ROOT / "data" / "IR_Fund_Fact_Sheet_Input_Template.xlsx")
    validation = validate_fund_data(data)
    if not validation.is_valid:
        raise SystemExit(validation.errors)

    request = FactSheetRequest(
        fund_id="FUND001",
        reporting_date=pd.Timestamp("2026-06-30"),
        performance_metrics=[
            "custom_net_performance",
            "standard_performance_table",
            "calendar_year_returns",
            "growth_of_10000",
        ],
        risk_metrics=[
            "annualized_volatility",
            "sharpe_ratio",
            "maximum_drawdown",
            "beta",
            "tracking_error",
        ],
        portfolio_metrics=[
            "top_holdings",
            "sector_allocation",
            "country_allocation",
            "number_of_holdings",
            "cash_weight",
            "top_10_concentration",
        ],
        performance_start_date=pd.Timestamp("2019-01-02"),
        performance_end_date=pd.Timestamp("2026-06-30"),
        risk_period_mode="3Y",
        risk_free_rate=0.025,
    )

    factsheet = build_factsheet_data(data, request)
    logo = prepare_logo((ROOT / "assets" / "demo_logo.png").read_bytes(), "demo_logo.png")
    output = ROOT / "examples" / "Example_Fund_Fact_Sheet.pdf"
    output.write_bytes(generate_factsheet_pdf(factsheet, logo_bytes=logo))
    print(output)


if __name__ == "__main__":
    main()
