from pathlib import Path

import pandas as pd

from src.branding import prepare_logo
from src.data_loader import load_fund_workbook, validate_fund_data
from src.factsheet_builder import FactSheetRequest, build_factsheet_data
from src.localization import localize_factsheet, t
from src.pdf_exporter import generate_factsheet_pdf
from src.pptx_exporter import generate_factsheet_pptx

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "data" / "IR_Fund_Fact_Sheet_Input_Template.xlsx"


def _data():
    data = load_fund_workbook(WORKBOOK)
    report = validate_fund_data(data)
    assert report.is_valid, report.errors
    return data


def _request():
    return FactSheetRequest(
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
        ],
        portfolio_metrics=[
            "top_holdings",
            "sector_allocation",
            "country_allocation",
            "number_of_holdings",
        ],
        performance_start_date=pd.Timestamp("2019-01-02"),
        performance_end_date=pd.Timestamp("2026-06-30"),
        risk_period_mode="3Y",
        risk_free_rate=0.025,
        top_n_holdings=10,
    )


def test_workbook_and_builder():
    factsheet = build_factsheet_data(_data(), _request())
    assert factsheet["fund"]["Fund_ID"] == "FUND001"
    assert factsheet["performance"]["custom_net_performance"].value is not None
    assert len(factsheet["risk"]) == 3
    assert len(factsheet["portfolio"]["top_holdings"]) == 10


def test_insufficient_long_history_is_na_for_shorter_fund():
    data = _data()
    req = _request()
    req.fund_id = "FUND003"
    req.performance_start_date = pd.Timestamp("2023-01-02")
    factsheet = build_factsheet_data(data, req)
    table = factsheet["performance"]["standard_performance_table"]
    fund_row = table.loc[table["Series"] == "Fund"].iloc[0]
    assert pd.isna(fund_row["5Y"])
    assert pd.isna(fund_row["10Y"])


def test_chinese_localization_keeps_numeric_objects():
    factsheet = build_factsheet_data(_data(), _request())
    localized = localize_factsheet(factsheet, language="zh")
    assert "全球" in localized["fund"]["Fund_Description"]
    assert t("annualized_performance", "zh") == "年化业绩表现 (%)"
    assert (
        localized["performance"]["custom_net_performance"].value
        == factsheet["performance"]["custom_net_performance"].value
    )


def test_logo_validation_rejects_large_bytes():
    too_large = b"0" * (5 * 1024 * 1024 + 1)
    try:
        prepare_logo(too_large, "logo.jpg")
    except ValueError as exc:
        assert "5 MB" in str(exc)
    else:
        raise AssertionError("Expected oversized logo to be rejected")


def test_pdf_generation_in_both_languages():
    factsheet = build_factsheet_data(_data(), _request())
    logo = prepare_logo((ROOT / "assets" / "demo_logo.png").read_bytes(), "demo_logo.png")
    for language in ["en", "zh"]:
        pdf = generate_factsheet_pdf(factsheet, logo_bytes=logo, language=language)
        assert pdf.startswith(b"%PDF")
        assert len(pdf) > 10_000


def test_powerpoint_generation_in_both_languages():
    factsheet = build_factsheet_data(_data(), _request())
    logo = prepare_logo((ROOT / "assets" / "demo_logo.png").read_bytes(), "demo_logo.png")
    for language in ["en", "zh"]:
        pptx = generate_factsheet_pptx(factsheet, logo_bytes=logo, language=language)
        assert pptx.startswith(b"PK")
        assert len(pptx) > 20_000
