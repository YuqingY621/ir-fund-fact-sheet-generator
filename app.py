from __future__ import annotations

from pathlib import Path
import tempfile

import pandas as pd
import streamlit as st

from src.branding import prepare_logo
from src.data_loader import list_available_funds, load_fund_workbook, validate_fund_data
from src.factsheet_builder import FactSheetRequest, build_factsheet_data
from src.metric_catalog import PERFORMANCE_METRICS, PORTFOLIO_METRICS, RISK_METRICS
from src.pdf_exporter import generate_factsheet_pdf
from src.pptx_exporter import generate_factsheet_pptx
from src.localization import localize_factsheet, risk_label, t, translate_period_label

ROOT = Path(__file__).parent
DEMO_WORKBOOK = ROOT / "data" / "IR_Fund_Fact_Sheet_Input_Template.xlsx"

RISK_LABELS = {
    "annualized_volatility": "Annualized Volatility",
    "sharpe_ratio": "Sharpe Ratio",
    "maximum_drawdown": "Maximum Drawdown",
    "beta": "Beta",
    "tracking_error": "Tracking Error",
    "information_ratio": "Information Ratio",
}
PERCENT_RISK = {"annualized_volatility", "maximum_drawdown", "tracking_error"}

st.set_page_config(page_title="IR Fund Fact Sheet Generator", page_icon="📊", layout="wide")


def fmt_pct(value):
    return "N/A" if value is None or pd.isna(value) else f"{float(value):.2%}"


def fmt_ratio(value):
    return "N/A" if value is None or pd.isna(value) else f"{float(value):.2f}"


def fmt_currency(value, currency):
    if value is None or pd.isna(value):
        return "N/A"
    if abs(value) >= 1_000_000_000:
        return f"{currency} {value / 1_000_000_000:,.2f}bn"
    if abs(value) >= 1_000_000:
        return f"{currency} {value / 1_000_000:,.2f}m"
    return f"{currency} {value:,.2f}"


@st.cache_data(show_spinner=False)
def load_demo_data():
    return load_fund_workbook(DEMO_WORKBOOK)


def load_uploaded_workbook(uploaded):
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(uploaded.getvalue())
        path = Path(tmp.name)
    try:
        return load_fund_workbook(path)
    finally:
        path.unlink(missing_ok=True)


def checkbox_group(title, definitions):
    st.markdown(f"#### {title}")
    selected = []
    for metric in definitions:
        if st.checkbox(
            metric.label,
            value=metric.default_selected,
            key=f"{metric.category}_{metric.metric_id}",
            help=metric.description or None,
        ):
            selected.append(metric.metric_id)
    return selected


def render_preview(factsheet, language="en"):
    fund = factsheet["fund"]
    st.header(str(fund.get("Fund_Name", "Fund")))
    st.caption(f"{t('fact_sheet_as_of', language, date=factsheet['reporting_date'].strftime('%d %B %Y'))}")
    if pd.notna(fund.get("Fund_Description")):
        st.write(str(fund.get("Fund_Description")))

    latest = factsheet.get("latest_nav") or {}
    cols = st.columns(4)
    cols[0].metric(t("asset_class", language), str(fund.get("Asset_Class", "N/A")))
    cols[1].metric(t("benchmark", language), str(fund.get("Benchmark_Name", "N/A")))
    cols[2].metric(t("net_assets", language), fmt_currency(latest.get("AUM"), str(fund.get("Currency", ""))))
    cols[3].metric(t("management_fee", language), fmt_pct(fund.get("Management_Fee")))

    perf = factsheet.get("performance", {})
    if perf:
        st.subheader("业绩表现" if language == "zh" else "Performance")
        custom = perf.get("custom_net_performance")
        if custom is not None:
            label = t("net_performance", language)
            if custom.start_date is not None and custom.end_date is not None:
                label += f" ({custom.start_date.strftime('%b %Y')} - {custom.end_date.strftime('%b %Y')})"
            st.metric(label, fmt_pct(custom.value))

        standard = perf.get("standard_performance_table")
        if standard is not None:
            display = standard.copy()
            for c in display.columns:
                if c != "Series":
                    display[c] = display[c].map(fmt_pct)
            st.markdown("**标准业绩表现**" if language == "zh" else "**Standard Performance**")
            st.dataframe(display, hide_index=True, use_container_width=True)

        calendar = perf.get("calendar_year_returns")
        if calendar is not None:
            pivot = calendar.pivot(index="Series", columns="Period", values="Return").reset_index()
            for c in pivot.columns:
                if c != "Series":
                    pivot[c] = pivot[c].map(fmt_pct)
            st.markdown("**年度业绩表现**" if language == "zh" else "**Calendar-Year Performance**")
            st.dataframe(pivot, hide_index=True, use_container_width=True)

        growth = perf.get("growth_of_10000")
        if growth is not None:
            chart = growth.set_index("Date")[["Fund_Growth", "Benchmark_Growth"]].rename(
                columns={"Fund_Growth": "Fund", "Benchmark_Growth": "Benchmark"}
            )
            st.markdown("**假设初始投资增长**" if language == "zh" else "**Growth of Initial Investment**")
            st.line_chart(chart, use_container_width=True)

    risk = factsheet.get("risk", {})
    if risk:
        st.subheader("风险指标" if language == "zh" else "Risk Metrics")
        rows = []
        for metric_id, result in risk.items():
            rows.append({
                "Metric": risk_label(metric_id, language),
                "Value": fmt_pct(result.value) if metric_id in PERCENT_RISK else fmt_ratio(result.value),
                "Start Date": None if result.start_date is None else result.start_date.date(),
                "End Date": None if result.end_date is None else result.end_date.date(),
                "Observations": result.observations,
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    portfolio = factsheet.get("portfolio", {})
    if portfolio:
        st.subheader("投资组合" if language == "zh" else "Portfolio")
        summary = []
        if "number_of_holdings" in portfolio:
            summary.append((t("number_holdings", language), str(portfolio["number_of_holdings"])))
        if "cash_weight" in portfolio:
            summary.append((t("cash_weight", language), fmt_pct(portfolio["cash_weight"])))
        if "top_10_concentration" in portfolio:
            summary.append((t("top10_concentration", language), fmt_pct(portfolio["top_10_concentration"])))
        if summary:
            cols = st.columns(len(summary))
            for col, (label, value) in zip(cols, summary):
                col.metric(label, value)

        top = portfolio.get("top_holdings")
        if top is not None:
            display = top[[c for c in ["Rank", "Security_Name", "Sector", "Country", "Weight"] if c in top.columns]].copy()
            display["Weight"] = display["Weight"].map(fmt_pct)
            display = display.rename(columns={"Security_Name": "Security"})
            st.markdown("**主要持仓**" if language == "zh" else "**Top Holdings**")
            st.dataframe(display, hide_index=True, use_container_width=True)

        for key, category, title in [
            ("sector_allocation", "Sector", "Sector Allocation"),
            ("country_allocation", "Country", "Country Allocation"),
            ("asset_class_allocation", "Asset_Class", "Asset-Class Allocation"),
        ]:
            allocation = portfolio.get(key)
            if allocation is not None:
                st.markdown(f"**{title}**")
                st.bar_chart(allocation[[category, "Weight"]].set_index(category), use_container_width=True)


st.title("IR Fund Fact Sheet Generator")
st.caption("Local prototype for reusable investor reporting from Excel data.")

with st.sidebar:
    st.header("1. Data Source")
    source_mode = st.radio("Workbook", ["Use demo workbook", "Upload local Excel workbook"])
    uploaded_workbook = None
    if source_mode == "Upload local Excel workbook":
        uploaded_workbook = st.file_uploader("Upload .xlsx workbook", type=["xlsx"])

    st.header("2. Branding")
    uploaded_logo = st.file_uploader("Company / fund logo", type=["jpg", "jpeg", "png"])
    logo_bytes = None
    if uploaded_logo is not None:
        try:
            logo_bytes = prepare_logo(uploaded_logo.getvalue(), uploaded_logo.name)
            st.image(logo_bytes, caption="Logo preview", width=180)
            st.caption("The logo will appear in the upper-right corner of page 1 only.")
        except ValueError as exc:
            st.error(str(exc))

    st.header("3. Output Language")
    language_label = st.selectbox("Report language", ["English", "中文"], index=0)
    report_language = "zh" if language_label == "中文" else "en"
    openrouter_api_key = None
    openrouter_model = None
    if report_language == "zh":
        st.caption("Standard financial labels use a fixed Chinese dictionary. An OpenRouter key is optional and is only used for narrative text not covered by the demo dictionary.")
        openrouter_api_key = st.text_input("OpenRouter API key (optional)", type="password") or None
        openrouter_model = st.text_input("OpenRouter model ID (optional)", value="openai/gpt-4.1-mini") or None

try:
    if source_mode == "Use demo workbook":
        data = load_demo_data()
    elif uploaded_workbook is not None:
        data = load_uploaded_workbook(uploaded_workbook)
    else:
        st.info("Upload an Excel workbook to continue.")
        st.stop()
except Exception as exc:
    st.error(f"Could not load workbook: {exc}")
    st.stop()

validation = validate_fund_data(data)
if not validation.is_valid:
    st.error("Workbook validation failed.")
    for error in validation.errors:
        st.error(error)
    st.stop()
if validation.warnings:
    with st.expander("Workbook validation warnings"):
        for warning in validation.warnings:
            st.warning(warning)

funds = list_available_funds(data)
with st.sidebar:
    st.header("4. Fund & Date")
    options = dict(zip(funds["Fund_Name"], funds["Fund_ID"]))
    selected_fund_name = st.selectbox("Fund", list(options))
    fund_id = options[selected_fund_name]
    fund_nav = data["NAV_History"].loc[data["NAV_History"]["Fund_ID"].astype("string") == str(fund_id)]
    min_date = pd.Timestamp(fund_nav["Date"].min())
    max_date = pd.Timestamp(fund_nav["Date"].max())
    reporting_date = pd.Timestamp(st.date_input(
        "Fact-sheet reporting date",
        value=max_date.date(),
        min_value=min_date.date(),
        max_value=max_date.date(),
    ))

c1, c2, c3 = st.columns(3)
with c1:
    selected_performance = checkbox_group("Performance Content", PERFORMANCE_METRICS)
    performance_start = min_date
    performance_end = reporting_date
    if "custom_net_performance" in selected_performance:
        performance_start = pd.Timestamp(st.date_input(
            "Performance start date", min_date.date(), min_value=min_date.date(), max_value=reporting_date.date()
        ))
        performance_end = pd.Timestamp(st.date_input(
            "Performance end date", reporting_date.date(), min_value=performance_start.date(), max_value=reporting_date.date()
        ))

with c2:
    selected_risk = checkbox_group("Risk Metrics", RISK_METRICS)
    risk_period = st.selectbox("Risk measurement period", ["1Y", "3Y", "5Y", "Since Inception", "Custom"], index=1)
    risk_start = None
    risk_end = reporting_date
    if risk_period == "Custom":
        risk_start = pd.Timestamp(st.date_input(
            "Risk start date", min_date.date(), min_value=min_date.date(), max_value=reporting_date.date()
        ))
        risk_end = pd.Timestamp(st.date_input(
            "Risk end date", reporting_date.date(), min_value=risk_start.date(), max_value=reporting_date.date()
        ))
    risk_free_rate = 0.0
    if "sharpe_ratio" in selected_risk:
        risk_free_rate = st.number_input(
            "Annual risk-free rate (%)", min_value=-5.0, max_value=25.0, value=2.5, step=0.1
        ) / 100.0

with c3:
    selected_portfolio = checkbox_group("Portfolio Content", PORTFOLIO_METRICS)
    top_n = st.number_input(
        "Number of top holdings", min_value=3, max_value=20, value=10, step=1,
        disabled="top_holdings" not in selected_portfolio,
    )

request = FactSheetRequest(
    fund_id=fund_id,
    reporting_date=reporting_date,
    performance_metrics=selected_performance,
    risk_metrics=selected_risk,
    portfolio_metrics=selected_portfolio,
    performance_start_date=performance_start,
    performance_end_date=performance_end,
    risk_period_mode=risk_period,
    risk_start_date=risk_start,
    risk_end_date=risk_end,
    risk_free_rate=risk_free_rate,
    top_n_holdings=int(top_n),
)

try:
    factsheet = build_factsheet_data(data, request)
except Exception as exc:
    st.error(f"Could not build fact sheet: {exc}")
    st.stop()

st.divider()
preview_factsheet = localize_factsheet(factsheet, language=report_language, api_key=openrouter_api_key, model=openrouter_model)
render_preview(preview_factsheet, report_language)

for warning in factsheet.get("warnings", []):
    st.warning(warning)

pdf_bytes = generate_factsheet_pdf(
    factsheet,
    logo_bytes=logo_bytes,
    language=report_language,
    openrouter_api_key=openrouter_api_key,
    openrouter_model=openrouter_model,
)
pptx_bytes = generate_factsheet_pptx(
    factsheet,
    logo_bytes=logo_bytes,
    language=report_language,
    openrouter_api_key=openrouter_api_key,
    openrouter_model=openrouter_model,
)
safe_name = "_".join(str(factsheet["fund"].get("Fund_Name", "Fund")).split())
lang_suffix = "ZH" if report_language == "zh" else "EN"
pdf_filename = f"{safe_name}_{reporting_date.date()}_{lang_suffix}_Fact_Sheet.pdf"
pptx_filename = f"{safe_name}_{reporting_date.date()}_{lang_suffix}_Fact_Sheet.pptx"
d1, d2 = st.columns(2)
with d1:
    st.download_button(
        "下载PDF" if report_language == "zh" else "Download PDF Fact Sheet",
        data=pdf_bytes,
        file_name=pdf_filename,
        mime="application/pdf",
        use_container_width=True,
    )
with d2:
    st.download_button(
        "下载可编辑PowerPoint" if report_language == "zh" else "Download Editable PowerPoint",
        data=pptx_bytes,
        file_name=pptx_filename,
        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        use_container_width=True,
    )

st.caption(
    "Synthetic demo data only. Production use should rely on administrator-approved NAV, benchmark, holdings and compliance data."
)
