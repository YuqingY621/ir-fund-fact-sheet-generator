from __future__ import annotations

from io import BytesIO
from typing import Any

import matplotlib.pyplot as plt
from matplotlib import font_manager
import pandas as pd
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Frame, HRFlowable, Image, Paragraph, Spacer, Table, TableStyle

from src.localization import (
    glossary_text,
    localize_factsheet,
    risk_label,
    t,
    translate_period_label,
    translate_value,
)


CJK_FONT_NAME = "STSong-Light"
try:
    cjk_candidates = [
        "/usr/share/fonts/truetype/arphic-gbsn00lp/gbsn00lp.ttf",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
    ]
    for candidate in cjk_candidates:
        if __import__("pathlib").Path(candidate).exists():
            try:
                pdfmetrics.registerFont(TTFont("IR-CJK", candidate))
                CJK_FONT_NAME = "IR-CJK"
                break
            except Exception:
                continue
    if CJK_FONT_NAME == "STSong-Light":
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
except Exception:
    pass

PERCENT_RISK = {"annualized_volatility", "maximum_drawdown", "tracking_error"}


def _pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):.2%}"


def _ratio(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):.2f}"


def _currency(value: float | None, currency: str) -> str:
    if value is None or pd.isna(value):
        return "-"
    if abs(value) >= 1_000_000_000:
        return f"{currency} {value / 1_000_000_000:,.2f}bn"
    if abs(value) >= 1_000_000:
        return f"{currency} {value / 1_000_000:,.2f}m"
    return f"{currency} {value:,.2f}"


def _font(language: str, bold: bool = False, italic: bool = False) -> str:
    if language == "zh":
        return CJK_FONT_NAME
    if bold:
        return "Helvetica-Bold"
    if italic:
        return "Helvetica-Oblique"
    return "Helvetica"


def _styles(language: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    body_size = 7.5 if language == "zh" else 7.7
    return {
        "section": ParagraphStyle(
            "Section",
            parent=base["Normal"],
            fontName=_font(language, bold=True),
            fontSize=9.3,
            leading=11.3,
            textColor=colors.black,
            spaceBefore=0,
            spaceAfter=3,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["Normal"],
            fontName=_font(language),
            fontSize=body_size,
            leading=9.4,
            textColor=colors.black,
            spaceAfter=0,
        ),
        "body_bold": ParagraphStyle(
            "BodyBold",
            parent=base["Normal"],
            fontName=_font(language, bold=True),
            fontSize=body_size,
            leading=9.4,
            textColor=colors.black,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["Normal"],
            fontName=_font(language),
            fontSize=6.3,
            leading=7.7,
            textColor=colors.HexColor("#333333"),
        ),
        "small_italic": ParagraphStyle(
            "SmallItalic",
            parent=base["Normal"],
            fontName=_font(language, italic=True),
            fontSize=6.2,
            leading=7.5,
            textColor=colors.HexColor("#333333"),
        ),
        "legal": ParagraphStyle(
            "Legal",
            parent=base["Normal"],
            fontName=_font(language),
            fontSize=6.2,
            leading=7.5,
            textColor=colors.black,
        ),
        "legal_bold": ParagraphStyle(
            "LegalBold",
            parent=base["Normal"],
            fontName=_font(language, bold=True),
            fontSize=6.2,
            leading=7.5,
            textColor=colors.black,
        ),
        "right_value": ParagraphStyle(
            "RightValue",
            parent=base["Normal"],
            fontName=_font(language),
            fontSize=7.1,
            leading=8.6,
            alignment=TA_RIGHT,
        ),
    }


def _separator(space_before: float = 2.2 * mm, space_after: float = 2.1 * mm):
    return HRFlowable(
        width="100%",
        thickness=0.55,
        color=colors.HexColor("#4A4A4A"),
        spaceBefore=space_before,
        spaceAfter=space_after,
    )


def _logo_dimensions(logo_bytes: bytes, max_w: float, max_h: float) -> tuple[float, float]:
    with PILImage.open(BytesIO(logo_bytes)) as im:
        w, h = im.size
    scale = min(max_w / w, max_h / h)
    return w * scale, h * scale


def _date_text(date: pd.Timestamp, language: str) -> str:
    if language == "zh":
        return f"{date.year}年{date.month}月{date.day}日"
    return date.strftime("%B %d, %Y")


def _draw_header(canv, fund, report_date, logo_bytes, page_number, language):
    page_w, page_h = A4
    left = 10 * mm
    right = page_w - 10 * mm
    top = page_h - 10 * mm

    if page_number == 1:
        ticker = str(fund.get("Ticker") or "FUND")[:8]
        box = 18 * mm
        canv.setFillColor(colors.HexColor("#EEEEEE"))
        canv.rect(left, top - box, box, box, fill=1, stroke=0)
        canv.setFillColor(colors.black)
        canv.setFont(_font(language, bold=True), 10.2)
        canv.drawCentredString(left + box / 2, top - box / 2 - 3, ticker)
        title_x = left + box + 6 * mm
    else:
        title_x = left + 1 * mm

    canv.setFillColor(colors.black)
    canv.setFont(_font(language, bold=True), 15.4 if page_number == 1 else 13.2)
    title_y = top - 5.8 * mm
    canv.drawString(title_x, title_y, str(fund.get("Fund_Name", "Fund")))

    if logo_bytes and page_number == 1:
        max_w, max_h = 37 * mm, 15.5 * mm
        w, h = _logo_dimensions(logo_bytes, max_w=max_w, max_h=max_h)
        canv.drawImage(
            ImageReader(BytesIO(logo_bytes)),
            right - w,
            top - h,
            width=w,
            height=h,
            preserveAspectRatio=True,
            mask="auto",
        )

    if page_number == 1:
        date_y = top - 23.1 * mm
        canv.setFont(_font(language, bold=True), 9.1)
        date_string = t("fact_sheet_as_of", language, date=_date_text(report_date, language))
        canv.drawString(left + 0.5 * mm, date_y, date_string)
        rule_y = date_y - 3.2 * mm
    else:
        rule_y = top - 20.3 * mm

    canv.setStrokeColor(colors.HexColor("#4A4A4A"))
    canv.setLineWidth(0.55)
    canv.line(left, rule_y, right, rule_y)
    return rule_y - 3.8 * mm


def _draw_footer(canv, page_number: int, language: str):
    page_w, _ = A4
    canv.setFont(_font(language), 6.0)
    canv.setFillColor(colors.HexColor("#555555"))
    canv.drawString(10 * mm, 7.5 * mm, t("footer", language))
    canv.drawRightString(page_w - 10 * mm, 7.5 * mm, t("page", language, page=page_number))


def _line_chart_image(growth: pd.DataFrame, language: str, width=119 * mm, height=43 * mm) -> Image:
    fig, ax = plt.subplots(figsize=(6.7, 2.65))
    zh_font = None
    if language == "zh":
        try:
            zh_font = font_manager.FontProperties(fname="/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
        except Exception:
            zh_font = None
    ax.plot(growth["Date"], growth["Fund_Growth"], label=t("fund", language), linewidth=1.5, color="#303030")
    ax.plot(growth["Date"], growth["Benchmark_Growth"], label=t("benchmark", language), linewidth=1.35, color="#B7B7B7")
    ax.grid(True, axis="y", alpha=0.35, linewidth=0.6)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="both", labelsize=7)
    legend_kwargs = dict(frameon=False, fontsize=7, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.17))
    if zh_font is not None:
        legend_kwargs["prop"] = zh_font
    ax.legend(**legend_kwargs)
    fig.tight_layout(pad=0.7)
    out = BytesIO()
    fig.savefig(out, format="png", dpi=185, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    out.seek(0)
    return Image(out, width=width, height=height)


def _performance_table(df: pd.DataFrame, language: str, max_width=119 * mm) -> Table:
    working = df.copy()
    columns = list(working.columns)
    display_columns = [translate_period_label(str(c), language) for c in columns]
    if columns and columns[0] == "Series":
        display_columns[0] = t("series", language)
    rows: list[list[str]] = [display_columns]

    for _, row in working.iterrows():
        first_value = str(row[columns[0]])
        if first_value == "Fund":
            first_value = t("fund", language)
        elif first_value == "Benchmark":
            first_value = t("benchmark", language)
        rows.append([first_value] + [_pct(row[c]) for c in columns[1:]])

    first = 27 * mm
    remaining = max_width - first
    others = remaining / max(1, len(columns) - 1)
    table = Table(rows, colWidths=[first] + [others] * (len(columns) - 1), hAlign="LEFT")
    style = [
        ("FONTNAME", (0, 0), (-1, -1), _font(language)),
        ("FONTSIZE", (0, 0), (-1, -1), 6.6 if language == "zh" else 6.8),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.55, colors.HexColor("#555555")),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if language == "en":
        style.extend([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ])
    # Keep the approved neutral style, but target Fund/Benchmark by label rather than row position.
    for r in range(1, len(rows)):
        if rows[r][0] in {t("fund", language), t("benchmark", language)}:
            shade = "#E8E8E8" if rows[r][0] == t("fund", language) else "#F4F4F4"
            style.append(("BACKGROUND", (0, r), (0, r), colors.HexColor(shade)))
    table.setStyle(TableStyle(style))
    return table


def _kv_table(rows, language: str, width=63 * mm) -> Table:
    styles = _styles(language)
    data = [[Paragraph(str(label), styles["body_bold"]), Paragraph(str(value), styles["body"])] for label, value in rows]
    table = Table(data, colWidths=[width * 0.56, width * 0.44], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1.5),
        ("TOPPADDING", (0, 0), (-1, -1), 1.15),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.15),
    ]))
    return table


def _top_holdings_table(top: pd.DataFrame, language: str, width=63 * mm, max_rows=8) -> Table:
    styles = _styles(language)
    data = []
    for _, row in top.head(max_rows).iterrows():
        data.append([
            Paragraph(str(row.get("Security_Name", "")), styles["body"]),
            Paragraph(_pct(row.get("Weight")), styles["right_value"]),
        ])
    if not data:
        data = [[Paragraph("-", styles["body"]), Paragraph("", styles["body"])]]
    table = Table(data, colWidths=[width * 0.72, width * 0.28], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0.8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0.8),
    ]))
    return table


def _allocation_table(df: pd.DataFrame, category: str, language: str, width: float) -> Table:
    styles = _styles(language)
    working = df[[category, "Weight"]].copy().head(10)
    data = [[Paragraph(str(row[category]), styles["body"]), Paragraph(_pct(row["Weight"]), styles["right_value"])] for _, row in working.iterrows()]
    table = Table(data, colWidths=[width * 0.70, width * 0.30], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1.0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.0),
    ]))
    return table


def _risk_period_label(factsheet: dict[str, Any], language: str) -> str:
    risk = factsheet.get("risk", {})
    if not risk:
        return ""
    result = next(iter(risk.values()))
    if result.start_date is None or result.end_date is None:
        return ""
    days = (result.end_date - result.start_date).days
    years = days / 365.25
    if 0.8 <= years <= 1.2:
        return "1年" if language == "zh" else "1y"
    if 2.7 <= years <= 3.3:
        return "3年" if language == "zh" else "3y"
    if 4.6 <= years <= 5.4:
        return "5年" if language == "zh" else "5y"
    if language == "zh":
        return f"{result.start_date.year}.{result.start_date.month}-{result.end_date.year}.{result.end_date.month}"
    return f"{result.start_date.strftime('%b %Y')} - {result.end_date.strftime('%b %Y')}"


def _build_page1_left(factsheet, language):
    styles = _styles(language)
    fund = factsheet["fund"]
    performance = factsheet.get("performance", {})
    story = [Paragraph(t("fund_description", language), styles["section"])]
    description = fund.get("Fund_Description")
    story.append(Paragraph(str(description) if description and not pd.isna(description) else "-", styles["body"]))
    story.append(_separator())

    growth = performance.get("growth_of_10000")
    if growth is not None:
        story.append(Paragraph(t("growth_title", language), styles["section"]))
        story.append(_line_chart_image(growth, language))
        story.append(Spacer(1, 1.4 * mm))
        story.append(Paragraph(t("growth_note", language), styles["small_italic"]))
        story.append(Spacer(1, 2.1 * mm))

    calendar = performance.get("calendar_year_returns")
    if calendar is not None:
        pivot = calendar.pivot(index="Series", columns="Period", values="Return").reset_index()
        story.append(Paragraph(t("calendar_performance", language), styles["section"]))
        story.append(_performance_table(pivot, language))
        story.append(Spacer(1, 2.8 * mm))

    standard = performance.get("standard_performance_table")
    if standard is not None:
        story.append(Paragraph(t("annualized_performance", language), styles["section"]))
        story.append(_performance_table(standard, language))
        story.append(Spacer(1, 2.0 * mm))

    custom = performance.get("custom_net_performance")
    if custom is not None:
        period = ""
        if custom.start_date is not None and custom.end_date is not None:
            period = (
                f"{custom.start_date.year}.{custom.start_date.month}-{custom.end_date.year}.{custom.end_date.month}"
                if language == "zh"
                else f"{custom.start_date.strftime('%b %Y')} - {custom.end_date.strftime('%b %Y')}"
            )
        custom_table = Table([[t("net_performance", language), period, _pct(custom.value)]], colWidths=[38 * mm, 51 * mm, 30 * mm], hAlign="LEFT")
        custom_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), _font(language)),
            ("FONTSIZE", (0, 0), (-1, -1), 6.6),
            ("ALIGN", (-1, 0), (-1, 0), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.55, colors.HexColor("#555555")),
            ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#E8E8E8")),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(custom_table)
        story.append(Spacer(1, 2.2 * mm))

    story.append(Paragraph(t("past_performance_note", language), styles["small_italic"]))
    story.append(_separator(space_before=1.8 * mm, space_after=0))
    return story


def _build_page1_right(factsheet, language):
    styles = _styles(language)
    fund = factsheet["fund"]
    latest_nav = factsheet.get("latest_nav") or {}
    portfolio = factsheet.get("portfolio", {})
    risk = factsheet.get("risk", {})
    story = []

    launch = "-"
    if pd.notna(fund.get("Launch_Date")):
        d = pd.Timestamp(fund.get("Launch_Date"))
        launch = f"{d.year}/{d.month}/{d.day}" if language == "zh" else d.strftime("%m/%d/%Y")

    key_rows = [
        (t("asset_class", language) + " :", translate_value(fund.get("Asset_Class"), language)),
        (t("benchmark", language) + " :", str(fund.get("Benchmark_Name", "-"))),
        (t("launch_date", language) + " :", launch),
        (t("currency", language) + " :", str(fund.get("Currency", "-"))),
        (t("ticker", language) + " :", str(fund.get("Ticker", "-"))),
        (t("net_assets", language) + " :", _currency(latest_nav.get("AUM"), str(fund.get("Currency", "")))),
    ]
    story.append(Paragraph(t("key_facts", language), styles["section"]))
    story.append(_kv_table(key_rows, language))
    story.append(_separator(1.6 * mm, 1.6 * mm))

    story.append(Paragraph(t("fees", language), styles["section"]))
    story.append(_kv_table([(t("management_fee", language), _pct(fund.get("Management_Fee")))], language))
    story.append(_separator(1.6 * mm, 1.6 * mm))

    story.append(Paragraph(t("fund_characteristics", language), styles["section"]))
    period_label = _risk_period_label(factsheet, language)
    characteristic_rows = []
    for metric_id, result in risk.items():
        label = risk_label(metric_id, language)
        if period_label:
            label = f"{label} ({period_label})"
        value = _pct(result.value) if metric_id in PERCENT_RISK else _ratio(result.value)
        characteristic_rows.append((label + " :", value))
    if "number_of_holdings" in portfolio:
        characteristic_rows.append((t("number_holdings", language) + " :", str(portfolio["number_of_holdings"])))
    if "cash_weight" in portfolio:
        characteristic_rows.append((t("cash_weight", language) + " :", _pct(portfolio["cash_weight"])))
    if "top_10_concentration" in portfolio:
        characteristic_rows.append((t("top10_concentration", language) + " :", _pct(portfolio["top_10_concentration"])))
    if not characteristic_rows:
        characteristic_rows.append((t("number_holdings", language) + " :", "-"))
    story.append(_kv_table(characteristic_rows, language))
    story.append(_separator(1.6 * mm, 1.6 * mm))

    story.append(Paragraph(t("top_holdings", language), styles["section"]))
    top = portfolio.get("top_holdings")
    if top is not None:
        story.append(_top_holdings_table(top, language, max_rows=8))
    story.append(Paragraph(t("holdings_change", language), styles["small_italic"]))
    story.append(_separator(space_before=1.5 * mm, space_after=0))
    return story


def _build_glossary_columns(factsheet, language):
    styles = _styles(language)
    entries = []
    for metric_id in factsheet.get("risk", {}):
        text = glossary_text(metric_id, language)
        if text:
            entries.append((risk_label(metric_id, language), text))
    entries += [
        (t("net_assets", language), glossary_text("net_assets", language)),
        (t("number_holdings", language), glossary_text("number_holdings", language)),
    ]
    midpoint = (len(entries) + 1) // 2

    def make_story(items, include_heading):
        story = []
        if include_heading:
            story.append(Paragraph(t("glossary", language), styles["section"]))
        for title, text in items:
            story.append(Paragraph(f"{title}: {text}", styles["body"]))
            story.append(Spacer(1, 1.15 * mm))
        return story

    return make_story(entries[:midpoint], True), make_story(entries[midpoint:], False)


def _build_allocation_columns(factsheet, language):
    styles = _styles(language)
    portfolio = factsheet.get("portfolio", {})
    left, right = [], []
    if "sector_allocation" in portfolio:
        left.append(Paragraph(t("sector_allocation", language), styles["section"]))
        left.append(_allocation_table(portfolio["sector_allocation"], "Sector", language, 82 * mm))
    if "asset_class_allocation" in portfolio:
        if left:
            left.append(_separator(2 * mm, 1.6 * mm))
        left.append(Paragraph(t("asset_class_allocation", language), styles["section"]))
        left.append(_allocation_table(portfolio["asset_class_allocation"], "Asset_Class", language, 82 * mm))
    if "country_allocation" in portfolio:
        right.append(Paragraph(t("country_allocation", language), styles["section"]))
        right.append(_allocation_table(portfolio["country_allocation"], "Country", language, 82 * mm))
    return left, right


def _important_information(factsheet, language):
    styles = _styles(language)
    fund = factsheet["fund"]
    pieces = [Paragraph(t("important_info", language), styles["section"])]
    source = fund.get("Source")
    if source and not pd.isna(source):
        pieces.append(Paragraph(f"{t('source', language)}: {source}.", styles["legal"]))
        pieces.append(Spacer(1, 0.8 * mm))
    basis = []
    if fund.get("Performance_Basis") and not pd.isna(fund.get("Performance_Basis")):
        basis.append(f"{t('performance_basis', language)}: {fund.get('Performance_Basis')}")
    if fund.get("Benchmark_Return_Type") and not pd.isna(fund.get("Benchmark_Return_Type")):
        basis.append(f"{t('benchmark_basis', language)}: {fund.get('Benchmark_Return_Type')}")
    if basis:
        pieces.append(Paragraph(". ".join(basis) + ".", styles["legal_bold"]))
        pieces.append(Spacer(1, 0.8 * mm))
    pieces.append(Paragraph(t("demo_legal_bold", language), styles["legal_bold"]))
    pieces.append(Spacer(1, 0.9 * mm))
    pieces.append(Paragraph(t("demo_legal", language), styles["legal"]))
    for warning in factsheet.get("warnings", []):
        pieces.append(Spacer(1, 0.8 * mm))
        pieces.append(Paragraph(f"{t('data_note', language)}: {warning}", styles["legal"]))
    return pieces


def generate_factsheet_pdf(
    factsheet: dict[str, Any],
    logo_bytes: bytes | None = None,
    language: str = "en",
    openrouter_api_key: str | None = None,
    openrouter_model: str | None = None,
) -> bytes:
    """Generate the approved iShares-style two-page fact sheet in English or Simplified Chinese."""
    language = "zh" if language == "zh" else "en"
    factsheet = localize_factsheet(
        factsheet,
        language=language,
        api_key=openrouter_api_key,
        model=openrouter_model,
    )
    buffer = BytesIO()
    canv = pdfcanvas.Canvas(buffer, pagesize=A4)
    fund = factsheet["fund"]
    report_date = pd.Timestamp(factsheet["reporting_date"])
    page_w, _ = A4

    body_top = _draw_header(canv, fund, report_date, logo_bytes, 1, language)
    bottom = 13 * mm
    left_x, left_w, gap = 10.5 * mm, 120.5 * mm, 3.0 * mm
    right_x = left_x + left_w + gap
    right_w = page_w - 10.5 * mm - right_x
    frame_h = body_top - bottom

    left_frame = Frame(left_x, bottom, left_w, frame_h, 0, 0, 0, 0, showBoundary=0)
    right_frame = Frame(right_x, bottom, right_w, frame_h, 0, 0, 0, 0, showBoundary=0)
    left_story = _build_page1_left(factsheet, language)
    right_story = _build_page1_right(factsheet, language)
    left_frame.addFromList(left_story, canv)
    right_frame.addFromList(right_story, canv)
    if left_story or right_story:
        canv.setFillColor(colors.HexColor("#555555"))
        canv.setFont(_font(language, italic=True), 6.0)
        canv.drawString(left_x, 10.7 * mm, t("continued", language))
    _draw_footer(canv, 1, language)
    canv.showPage()

    body_top_2 = _draw_header(canv, fund, report_date, logo_bytes, 2, language)
    content_left = 10.5 * mm
    content_right = page_w - 10.5 * mm
    content_w = content_right - content_left
    col_gap = 5.0 * mm
    col_w = (content_w - col_gap) / 2

    glossary_height = 59 * mm
    glossary_bottom = body_top_2 - glossary_height
    gl_left = Frame(content_left, glossary_bottom, col_w, glossary_height, 0, 0, 0, 0, showBoundary=0)
    gl_right = Frame(content_left + col_w + col_gap, glossary_bottom, col_w, glossary_height, 0, 0, 0, 0, showBoundary=0)
    glossary_left, glossary_right = _build_glossary_columns(factsheet, language)
    gl_left.addFromList(glossary_left, canv)
    gl_right.addFromList(glossary_right, canv)
    canv.setStrokeColor(colors.HexColor("#777777"))
    canv.setLineWidth(0.45)
    canv.line(content_left, glossary_bottom - 1.5 * mm, content_right, glossary_bottom - 1.5 * mm)

    alloc_top = glossary_bottom - 4.8 * mm
    alloc_height = 48 * mm
    alloc_bottom = alloc_top - alloc_height
    alloc_left_story, alloc_right_story = _build_allocation_columns(factsheet, language)
    if alloc_left_story or alloc_right_story:
        Frame(content_left, alloc_bottom, col_w, alloc_height, 0, 0, 0, 0, showBoundary=0).addFromList(alloc_left_story, canv)
        Frame(content_left + col_w + col_gap, alloc_bottom, col_w, alloc_height, 0, 0, 0, 0, showBoundary=0).addFromList(alloc_right_story, canv)
        info_top = alloc_bottom - 3.5 * mm
        canv.line(content_left, info_top + 1.5 * mm, content_right, info_top + 1.5 * mm)
    else:
        info_top = alloc_top - 2.5 * mm

    info_bottom = 13 * mm
    info_frame = Frame(content_left, info_bottom, content_w, info_top - info_bottom, 0, 0, 0, 0, showBoundary=0)
    info_story = _important_information(factsheet, language)
    info_frame.addFromList(info_story, canv)
    _draw_footer(canv, 2, language)
    canv.save()
    return buffer.getvalue()
