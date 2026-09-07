from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from typing import Any

import pandas as pd
import requests


UI_LANGUAGES = {"English": "en", "中文": "zh"}

TEXT = {
    "en": {
        "fact_sheet_as_of": "Fact Sheet as of {date}",
        "fund_description": "FUND DESCRIPTION",
        "growth_title": "GROWTH OF HYPOTHETICAL 10,000 SINCE INCEPTION",
        "growth_note": "The growth chart reflects a hypothetical initial investment and compares the selected fund series with its benchmark. Demo data is synthetic.",
        "calendar_performance": "CALENDAR YEAR PERFORMANCE (%)",
        "annualized_performance": "ANNUALIZED PERFORMANCE (%)",
        "net_performance": "Net Performance",
        "past_performance_note": "Past performance does not guarantee future results. Investment return and principal value may fluctuate. Performance shown in this demonstration is calculated from synthetic data and should not be used for investment decisions.",
        "key_facts": "KEY FACTS",
        "asset_class": "Asset Class",
        "benchmark": "Benchmark",
        "launch_date": "Fund Launch Date",
        "currency": "Currency",
        "ticker": "Ticker",
        "net_assets": "Net Assets of Fund",
        "fees": "FEES AND EXPENSES BREAKDOWN",
        "management_fee": "Management Fee",
        "fund_characteristics": "FUND CHARACTERISTICS",
        "number_holdings": "Number of Holdings",
        "cash_weight": "Cash Weight",
        "top10_concentration": "Top 10 Concentration",
        "top_holdings": "TOP HOLDINGS (%)",
        "holdings_change": "Holdings are subject to change.",
        "glossary": "GLOSSARY",
        "sector_allocation": "SECTOR ALLOCATION (%)",
        "country_allocation": "COUNTRY ALLOCATION (%)",
        "asset_class_allocation": "ASSET CLASS ALLOCATION (%)",
        "important_info": "IMPORTANT INFORMATION:",
        "source": "Source",
        "performance_basis": "Performance basis",
        "benchmark_basis": "Benchmark basis",
        "demo_legal_bold": "This document is a synthetic demonstration of an automated investor-relations reporting workflow. The figures are not actual investment results and are not intended as investment advice, a recommendation, an offer, or a solicitation. Production use should rely on administrator-approved NAV and total-return data, approved benchmark series, validated portfolio holdings, and compliance-approved disclosures.",
        "demo_legal": "Past performance does not guarantee future results. Investment return and principal value may fluctuate. Risk statistics are sensitive to the selected measurement period, observation frequency, benchmark methodology, and risk-free rate. Holdings and allocations are subject to change. Users should review all generated documents before external distribution.",
        "data_note": "Data note",
        "footer": "Synthetic demonstration - not for investment use",
        "page": "Page {page}",
        "continued": "Additional selected content continues on page 2.",
        "fund": "Fund",
        "since_inception": "Since Inception",
        "ytd": "YTD",
        "series": "Series",
        "risk_free_rate": "Risk-free rate",
    },
    "zh": {
        "fact_sheet_as_of": "基金概览 - 截至{date}",
        "fund_description": "基金概况",
        "growth_title": "成立以来假设投资10,000的增长",
        "growth_note": "该图展示假设初始投资10,000的增长，并比较基金与基准的表现。演示数据均为虚构数据。",
        "calendar_performance": "年度业绩表现 (%)",
        "annualized_performance": "年化业绩表现 (%)",
        "net_performance": "净收益表现",
        "past_performance_note": "过往业绩并不代表未来表现。投资回报及本金价值可能波动。本演示中的业绩数据由虚构数据计算得出，不应作为投资决策依据。",
        "key_facts": "基金基本信息",
        "asset_class": "资产类别",
        "benchmark": "基准指数",
        "launch_date": "基金成立日期",
        "currency": "币种",
        "ticker": "代码",
        "net_assets": "基金净资产",
        "fees": "费用明细",
        "management_fee": "管理费",
        "fund_characteristics": "基金特征",
        "number_holdings": "持仓数量",
        "cash_weight": "现金占比",
        "top10_concentration": "前十大持仓集中度",
        "top_holdings": "主要持仓 (%)",
        "holdings_change": "持仓可能发生变化。",
        "glossary": "术语说明",
        "sector_allocation": "行业配置 (%)",
        "country_allocation": "国家/地区配置 (%)",
        "asset_class_allocation": "资产类别配置 (%)",
        "important_info": "重要信息：",
        "source": "数据来源",
        "performance_basis": "业绩口径",
        "benchmark_basis": "基准口径",
        "demo_legal_bold": "本文件仅用于展示自动化投资者关系报告流程，所有数据均为虚构示例，并非真实投资业绩。本文件不构成投资建议、推荐、要约或招揽。正式使用时，应采用基金管理人或行政管理人确认的净值及总回报数据、经批准的基准序列、经验证的持仓数据以及合规部门批准的披露文本。",
        "demo_legal": "过往业绩并不代表未来表现。投资回报及本金价值可能波动。风险指标会受到测量期间、观察频率、基准方法以及无风险利率的影响。持仓及配置可能发生变化。任何对外发送的文件均应由相关人员复核。",
        "data_note": "数据说明",
        "footer": "虚构演示 - 不作为投资依据",
        "page": "第{page}页",
        "continued": "其他已选内容见第2页。",
        "fund": "基金",
        "since_inception": "成立以来",
        "ytd": "年初至今",
        "series": "项目",
        "risk_free_rate": "无风险利率",
    },
}

RISK_LABELS = {
    "en": {
        "annualized_volatility": "Annualized Volatility",
        "sharpe_ratio": "Sharpe Ratio",
        "maximum_drawdown": "Maximum Drawdown",
        "beta": "Beta",
        "tracking_error": "Tracking Error",
        "information_ratio": "Information Ratio",
    },
    "zh": {
        "annualized_volatility": "年化波动率",
        "sharpe_ratio": "夏普比率",
        "maximum_drawdown": "最大回撤",
        "beta": "Beta",
        "tracking_error": "跟踪误差",
        "information_ratio": "信息比率",
    },
}

GLOSSARY = {
    "en": {
        "annualized_volatility": "Measures how dispersed daily fund returns are and annualizes the result using 252 trading days. Higher volatility indicates a wider range of historical returns.",
        "sharpe_ratio": "Measures historical excess return relative to volatility. The calculation uses the risk-free rate selected in the application.",
        "maximum_drawdown": "Measures the largest historical decline from a previous NAV peak during the selected measurement period.",
        "beta": "Measures the sensitivity of fund returns to benchmark returns. A beta of 1 indicates similar historical sensitivity to the benchmark.",
        "tracking_error": "Measures the annualized standard deviation of the difference between fund returns and benchmark returns.",
        "information_ratio": "Measures average active return relative to tracking error over the selected measurement period.",
        "net_assets": "The latest available assets-under-management value on or before the selected fact-sheet reporting date.",
        "number_holdings": "The number of portfolio positions in the selected holdings snapshot, excluding cash by default.",
    },
    "zh": {
        "annualized_volatility": "衡量基金日收益率的波动程度，并按每年252个交易日进行年化。数值越高，表示历史收益波动范围越大。",
        "sharpe_ratio": "衡量单位波动风险所对应的历史超额收益。计算使用网页中选择的无风险利率。",
        "maximum_drawdown": "衡量所选期间内基金净值从历史高点到后续低点的最大跌幅。",
        "beta": "衡量基金收益相对于基准收益的敏感程度。Beta为1表示历史敏感度与基准大致一致。",
        "tracking_error": "衡量基金收益与基准收益差异的年化标准差。",
        "information_ratio": "衡量相对于跟踪误差所取得的平均主动收益。",
        "net_assets": "所选报告日期当日或之前最新可用的基金资产管理规模。",
        "number_holdings": "所选持仓快照中的投资组合持仓数量，默认不包含现金。",
    },
}

VALUE_TRANSLATIONS = {
    "Global Equity": "全球股票",
    "European ESG Equity": "欧洲ESG股票",
    "Multi-Asset": "多资产",
    "Equity": "股票",
    "Cash": "现金",
    "Technology": "信息技术",
    "Healthcare": "医疗保健",
    "Financials": "金融",
    "Industrials": "工业",
    "Consumer Discretionary": "可选消费",
    "Utilities": "公用事业",
    "Other": "其他",
    "United States": "美国",
    "Eurozone": "欧元区",
    "Switzerland": "瑞士",
    "France": "法国",
    "United Kingdom": "英国",
    "Japan": "日本",
    "Spain": "西班牙",
    "Taiwan": "中国台湾",
    "Germany": "德国",
    "Annual": "年度",
    "Quarterly": "季度",
    "Accumulating": "累积型",
    "Net of fees (synthetic demo NAV)": "扣费后（虚构演示净值）",
    "Total return benchmark (synthetic demo)": "总回报基准（虚构演示）",
    "Synthetic demo data": "虚构演示数据",
}

DEMO_NARRATIVES = {
    "A diversified global equity strategy seeking long-term capital growth through high-quality companies across developed markets.": "本基金采用全球多元化股票投资策略，主要投资于发达市场中的优质企业，旨在实现长期资本增值。",
    "A European equity strategy integrating sustainability criteria and focusing on companies with resilient business models and improving ESG profiles.": "本基金采用欧洲股票投资策略，将可持续发展因素纳入投资分析，并关注商业模式稳健且ESG表现持续改善的企业。",
    "A diversified multi-asset strategy combining equities, bonds and cash with the objective of delivering smoother long-term risk-adjusted returns.": "本基金采用多元资产配置策略，综合投资股票、债券及现金，旨在获得更平稳的长期风险调整后回报。",
}


def t(key: str, language: str = "en", **kwargs: Any) -> str:
    lang = "zh" if language == "zh" else "en"
    template = TEXT[lang].get(key, TEXT["en"].get(key, key))
    return template.format(**kwargs) if kwargs else template


def risk_label(metric_id: str, language: str = "en") -> str:
    lang = "zh" if language == "zh" else "en"
    return RISK_LABELS[lang].get(metric_id, metric_id)


def glossary_text(metric_id: str, language: str = "en") -> str:
    lang = "zh" if language == "zh" else "en"
    return GLOSSARY[lang].get(metric_id, "")


def translate_value(value: Any, language: str = "en") -> str:
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return "-"
    text = str(value)
    if language != "zh":
        return text
    return VALUE_TRANSLATIONS.get(text, text)


def translate_period_label(label: str, language: str = "en") -> str:
    if language != "zh":
        return label
    mapping = {
        "YTD": "年初至今",
        "1Y": "1年",
        "3Y": "3年",
        "5Y": "5年",
        "10Y": "10年",
        "Since Inception": "成立以来",
    }
    if label in mapping:
        return mapping[label]
    if label.endswith(" YTD"):
        return label.replace(" YTD", " 年初至今")
    return label


def _openrouter_translate(text: str, api_key: str, model: str) -> str:
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Translate asset-management investor-relations text from English to Simplified Chinese. "
                        "Keep fund names, benchmark names, security names, tickers, ISINs, currency codes, dates and all numeric values unchanged. "
                        "Use concise professional terminology suitable for a Chinese institutional fund fact sheet. Return only the translation."
                    ),
                },
                {"role": "user", "content": text},
            ],
        },
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()
    return payload["choices"][0]["message"]["content"].strip()


@lru_cache(maxsize=256)
def translate_narrative(
    text: str,
    language: str = "en",
    api_key: str | None = None,
    model: str | None = None,
) -> str:
    if language != "zh" or not text:
        return text
    if text in DEMO_NARRATIVES:
        return DEMO_NARRATIVES[text]
    if api_key and model:
        try:
            return _openrouter_translate(text, api_key, model)
        except Exception:
            return text
    return text


def localize_factsheet(
    factsheet: dict[str, Any],
    language: str = "en",
    api_key: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Return a presentation copy. Numeric results are never sent to the LLM."""
    localized = deepcopy(factsheet)
    if language != "zh":
        return localized

    fund = localized.get("fund", {})
    description = fund.get("Fund_Description")
    if isinstance(description, str):
        fund["Fund_Description"] = translate_narrative(
            description,
            language="zh",
            api_key=api_key,
            model=model,
        )

    for key in ["Asset_Class", "Distribution_Frequency", "Performance_Basis", "Benchmark_Return_Type", "Source"]:
        if key in fund:
            fund[key] = translate_value(fund[key], "zh")

    for key in ["sector_allocation", "country_allocation", "asset_class_allocation"]:
        df = localized.get("portfolio", {}).get(key)
        if df is None:
            continue
        df = df.copy()
        category = {
            "sector_allocation": "Sector",
            "country_allocation": "Country",
            "asset_class_allocation": "Asset_Class",
        }[key]
        if category in df.columns:
            df[category] = df[category].map(lambda x: translate_value(x, "zh"))
        localized["portfolio"][key] = df

    return localized
