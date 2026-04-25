"""Render results/report.docx and results/report.md from analysis outputs."""
from __future__ import annotations

import os
from typing import Iterable, Sequence

import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = r"C:\Users\CHENY\Documents\GitHub\Stock-Performance-Analysis"
RESULTS = os.path.join(ROOT, "results")


def pct(x: float, d: int = 1) -> str:
    if pd.isna(x):
        return "n/a"
    return f"{x * 100:.{d}f} %"


def signed_pct(x: float, d: int = 1) -> str:
    if pd.isna(x):
        return "n/a"
    sign = "+" if x >= 0 else "-"
    return f"{sign}{abs(x) * 100:.{d}f} %"


def mult(x: float) -> str:
    if pd.isna(x):
        return "n/a"
    if x <= -1:
        return "-100.0 %"
    value = 1 + x
    return f"{value:,.2f}x" if value < 10 else f"{value:,.0f}x"


def set_cell_shading(cell, color_hex: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color_hex)
    tc_pr.append(shd)


def add_heading(doc: Document, text: str, level: int) -> None:
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.color.rgb = RGBColor(0x1A, 0x36, 0x5D)


def add_para(doc: Document, text: str) -> None:
    doc.add_paragraph(text)


def add_table(doc: Document, headers: Sequence[str],
              rows: Iterable[Sequence[str]]) -> None:
    rows = list(rows)
    tbl = doc.add_table(rows=1 + len(rows), cols=len(headers))
    tbl.style = "Light Grid Accent 1"
    tbl.autofit = True
    for j, h in enumerate(headers):
        cell = tbl.cell(0, j)
        cell.text = ""
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h)
        r.bold = True
        r.font.size = Pt(9)
        set_cell_shading(cell, "E2E8F0")
    for i, row in enumerate(rows, start=1):
        for j, value in enumerate(row):
            cell = tbl.cell(i, j)
            cell.text = ""
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if j == 0 else WD_ALIGN_PARAGRAPH.RIGHT
            r = p.add_run(str(value))
            r.font.size = Pt(9)


def add_picture(doc: Document, filename: str, width_in: float = 6.8) -> None:
    path = os.path.join(RESULTS, filename)
    if os.path.exists(path):
        doc.add_picture(path, width=Inches(width_in))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER


def load_outputs() -> dict[str, pd.DataFrame]:
    return {
        "s10": pd.read_csv(os.path.join(RESULTS, "summary_10y.csv")),
        "s30": pd.read_csv(os.path.join(RESULTS, "summary_30y.csv")),
        "slife": pd.read_csv(os.path.join(RESULTS, "summary_fulllife.csv")),
        "first": pd.read_csv(os.path.join(RESULTS, "summary_first_period_by_stock.csv")),
        "cal10": pd.read_csv(os.path.join(RESULTS, "summary_calendar_10y.csv")),
        "cal30": pd.read_csv(os.path.join(RESULTS, "summary_calendar_30y.csv")),
        "sens": pd.read_csv(os.path.join(RESULTS, "summary_first_month_sensitivity.csv")),
        "audit": pd.read_csv(os.path.join(RESULTS, "summary_audit.csv")),
        "universe": pd.read_csv(os.path.join(RESULTS, "universe_summary.csv")),
    }


def compact_summary_rows(summary: pd.DataFrame) -> list[list[str]]:
    rows = []
    for _, row in summary.iterrows():
        rows.append([
            row["horizon"],
            row["basis"],
            f"{int(row['n_periods']):,}",
            f"{int(row['n_permnos']):,}",
            pct(row["pct_positive"]),
            signed_pct(row["median"]),
            mult(row["mean"]),
            pct(row["pct_complete"]),
            pct(row["pct_delisted"]),
            pct(row["pct_sparse"], 3),
        ])
    return rows


def first_period_rows(first: pd.DataFrame) -> list[list[str]]:
    rows = []
    for _, row in first.iterrows():
        rows.append([
            row["horizon"],
            row["basis"],
            f"{int(row['n_permnos']):,}",
            pct(row["pct_positive"]),
            signed_pct(row["median"]),
            pct(row["pct_complete"]),
            pct(row["pct_delisted"]),
        ])
    return rows


def calendar_rows(summary: pd.DataFrame) -> list[list[str]]:
    rows = []
    windows = summary["window"].drop_duplicates().tolist()
    for window in windows:
        d = summary[summary["window"] == window].set_index("basis")
        nom = d.loc["nominal"]
        real = d.loc["real (CPI-adj)"]
        rows.append([
            window,
            f"{int(nom['n_periods']):,}",
            pct(nom["pct_positive"]),
            pct(real["pct_positive"]),
            signed_pct(nom["median"]),
            signed_pct(real["median"]),
            pct(nom["pct_delisted"]),
        ])
    return rows


def full_life_rows(slife: pd.DataFrame) -> list[list[str]]:
    rows = []
    for _, row in slife.iterrows():
        rows.append([
            row["basis"],
            f"{int(row['n_permnos']):,}",
            pct(row["pct_positive"]),
            signed_pct(row["median"]),
            mult(row["mean"]),
            mult(row["max"]),
            pct(row["pct_sparse"], 3),
        ])
    return rows


def sensitivity_rows(sens: pd.DataFrame) -> list[list[str]]:
    rows = []
    for horizon in ["10y", "30y", "full-life"]:
        for basis in ["nominal", "real (CPI-adj)"]:
            d = sens[(sens["horizon"] == horizon) & (sens["basis"] == basis)]
            inc = d[d["convention"] == "include first observed return"].iloc[0]
            skip = d[d["convention"] == "skip first observed return"].iloc[0]
            rows.append([
                horizon,
                basis,
                pct(inc["pct_positive"]),
                pct(skip["pct_positive"]),
                signed_pct(inc["median"]),
                signed_pct(skip["median"]),
            ])
    return rows


def audit_rows(audit: pd.DataFrame) -> list[list[str]]:
    rows = []
    for _, row in audit.iterrows():
        rows.append([
            row["analysis"],
            row["horizon"],
            f"{int(row['all_started_periods']):,}",
            f"{int(row['all_started_permnos']):,}",
            f"{int(row['included_periods']):,}",
            f"{int(row['complete_periods']):,}",
            f"{int(row['delisted_partial_periods']):,}",
            f"{int(row['sample_end_censored_periods']):,}",
            f"{int(row['sparse_periods']):,}",
        ])
    return rows


def markdown_table(headers: Sequence[str], rows: Iterable[Sequence[str]]) -> str:
    rows = list(rows)
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] + ["---:"] * (len(headers) - 1)) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join(map(str, row)) + " |")
    return "\n".join(out)


def build_docx(data: dict[str, pd.DataFrame]) -> None:
    doc = Document()
    for section in doc.sections:
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)
        section.top_margin = Inches(0.7)
        section.bottom_margin = Inches(0.7)

    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10.5)

    s10 = data["s10"]
    s30 = data["s30"]
    slife = data["slife"]
    first = data["first"]
    cal10 = data["cal10"]
    cal30 = data["cal30"]
    sens = data["sens"]
    audit = data["audit"]
    universe = data["universe"].iloc[0]

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = title.add_run("Long-run return distributions of US-listed stocks")
    r.bold = True
    r.font.size = Pt(17)
    r.font.color.rgb = RGBColor(0x1A, 0x36, 0x5D)

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sr = subtitle.add_run(
        f"CRSP monthly, {int(universe['permnos']):,} common-stock PERMNOs, "
        f"{int(universe['sample_start_ymm'])}-{int(universe['sample_end_ymm'])}"
    )
    sr.italic = True
    sr.font.size = Pt(11)

    add_heading(doc, "TL;DR", 1)
    ten_nom = s10[s10["basis"] == "nominal"].iloc[0]
    ten_real = s10[s10["basis"] == "real (CPI-adj)"].iloc[0]
    cal_last = cal10[(cal10["window"] == "2015-2025") & (cal10["basis"] == "nominal")].iloc[0]
    life_nom = slife[slife["basis"] == "nominal"].iloc[0]
    life_real = slife[slife["basis"] == "real (CPI-adj)"].iloc[0]
    for text in [
        (
            f"Stock-anchored 10-year stock-periods: {pct(ten_nom['pct_positive'])} "
            f"positive nominal and {pct(ten_real['pct_positive'])} positive real."
        ),
        (
            f"Calendar start-cohort windows are reported separately; for example, "
            f"{pct(cal_last['pct_positive'])} of the 2015-2025 start-cohort observations "
            "were positive in nominal terms."
        ),
        (
            f"Full-life per stock: {pct(life_nom['pct_positive'])} positive nominal and "
            f"{pct(life_real['pct_positive'])} positive real."
        ),
    ]:
        doc.add_paragraph(text, style="List Bullet")

    add_heading(doc, "1. Data And Universe", 1)
    add_para(
        doc,
        f"The analysis uses {int(universe['permnos']):,} US-listed common-stock PERMNOs "
        f"and {int(universe['raw_rows_after_universe_filter']):,} monthly stock observations "
        "after duplicate removal."
    )
    add_para(doc, "The universe explicitly requires common stock and excludes REITs, ETFs, closed-end funds, and other non-common-stock securities.")
    add_para(
        doc,
        f"CPI-U inflation factor from {int(universe['cpi_start_ymm'])} to "
        f"{int(universe['cpi_end_ymm'])}: {universe['cpi_factor']:.2f}x "
        f"({pct(universe['cpi_cagr'], 2)} annualized)."
    )

    add_heading(doc, "2. Methodology", 1)
    add_para(
        doc,
        "The primary stock-anchored view builds non-overlapping 10-year and 30-year "
        "stock-periods from each stock's first observed CRSP month. Delisted stocks "
        "remain in the sample through their last observed month. Periods incomplete "
        "only because the sample ends are retained in detail files but excluded from "
        "headline summaries."
    )
    add_para(
        doc,
        "The calendar-window view forms start cohorts at fixed dates such as 1925-12, "
        "1935-12, and so on. A stock must be present at the start of a calendar window; "
        "stocks that list midway through that window are not added halfway."
    )
    add_para(
        doc,
        "Detail files include CRSP terminal fields and sparse-history flags for auditability. "
        "The main return convention includes the first observed monthly return; a sensitivity "
        "table also reports results after skipping that first observed return."
    )

    add_heading(doc, "3. Stock-Anchored Results", 1)
    add_heading(doc, "All Non-Overlapping Stock-Periods", 2)
    add_table(
        doc,
        ["Horizon", "Basis", "Periods", "PERMNOs", "% positive", "Median", "Mean multiple",
         "% complete", "% delisted", "% sparse"],
        compact_summary_rows(pd.concat([s10, s30], ignore_index=True)),
    )
    add_picture(doc, "hist_10y_nominal.png")
    add_picture(doc, "hist_10y_real.png")
    add_picture(doc, "hist_30y_nominal.png")
    add_picture(doc, "hist_30y_real.png")

    add_heading(doc, "First Period Per Stock", 2)
    add_table(
        doc,
        ["Horizon", "Basis", "Stocks", "% positive", "Median", "% complete", "% delisted"],
        first_period_rows(first),
    )

    add_heading(doc, "4. Calendar Start-Cohort Windows", 1)
    add_heading(doc, "10-Year Windows", 2)
    add_table(
        doc,
        ["Window", "N", "% positive nominal", "% positive real", "Median nominal",
         "Median real", "% delisted"],
        calendar_rows(cal10),
    )
    add_picture(doc, "calendar_pct_positive_10y.png")

    add_heading(doc, "30-Year Windows", 2)
    add_table(
        doc,
        ["Window", "N", "% positive nominal", "% positive real", "Median nominal",
         "Median real", "% delisted"],
        calendar_rows(cal30),
    )
    add_picture(doc, "calendar_pct_positive_30y.png")

    add_heading(doc, "5. Full-Life Results", 1)
    add_table(
        doc,
        ["Basis", "Stocks", "% positive", "Median", "Mean multiple", "Max multiple", "% sparse"],
        full_life_rows(slife),
    )
    add_picture(doc, "hist_fulllife_nominal.png")
    add_picture(doc, "hist_fulllife_real.png")

    add_heading(doc, "6. Robustness And Audit", 1)
    add_heading(doc, "First Observed Return Sensitivity", 2)
    add_table(
        doc,
        ["Horizon", "Basis", "% positive incl.", "% positive skip", "Median incl.", "Median skip"],
        sensitivity_rows(sens),
    )
    add_heading(doc, "Period Audit", 2)
    add_table(
        doc,
        ["Analysis", "Horizon", "Started periods", "Started PERMNOs", "Included periods",
         "Complete", "Delisted partial", "Sample-end censored", "Sparse"],
        audit_rows(audit),
    )

    add_heading(doc, "7. Caveats", 1)
    for text in [
        "Stock-anchored headline summaries are stock-period summaries; long-lived stocks can contribute multiple non-overlapping periods.",
        "The first-period-per-stock table gives a one-stock-one-vote companion view.",
        "Calendar windows are start-cohort views and do not include stocks that list after the window begins.",
        "Not-traded months with missing MthRet are set to 0 to preserve the monthly return timeline.",
        "Sparse histories are rare and listed in sparse_history_audit.csv.",
        "Delisting outcomes are measured using the CRSP monthly returns present in the file.",
    ]:
        doc.add_paragraph(text, style="List Bullet")

    add_heading(doc, "8. Reproducibility", 1)
    p = doc.add_paragraph()
    r = p.add_run("python program/run_analysis.py\npython program/build_docx.py")
    r.font.name = "Consolas"
    r.font.size = Pt(10)

    outpath = os.path.join(RESULTS, "report.docx")
    doc.save(outpath)
    print(f"[saved] {outpath} ({os.path.getsize(outpath):,} bytes)")


def build_markdown(data: dict[str, pd.DataFrame]) -> None:
    s10 = data["s10"]
    s30 = data["s30"]
    slife = data["slife"]
    first = data["first"]
    cal10 = data["cal10"]
    cal30 = data["cal30"]
    sens = data["sens"]
    audit = data["audit"]
    universe = data["universe"].iloc[0]

    lines = [
        "# Long-run return distributions of US-listed stocks",
        "",
        (
            f"CRSP monthly, {int(universe['permnos']):,} common-stock PERMNOs, "
            f"{int(universe['sample_start_ymm'])}-{int(universe['sample_end_ymm'])}."
        ),
        "",
        "## Methodology",
        "",
        "The primary view uses stock-anchored, non-overlapping 10-year and 30-year "
        "stock-periods. Delisted stocks are retained through their last observed CRSP month; "
        "sample-end-censored active periods are audited but excluded from headline summaries.",
        "",
        "A second calendar start-cohort view reports fixed windows such as 1925-1935 and 1935-1945. "
        "Stocks must exist at the start of a calendar window to enter it.",
        "",
        "## Data And Universe",
        "",
        f"- Monthly stock observations after duplicate removal: {int(universe['raw_rows_after_universe_filter']):,}",
        f"- PERMNOs: {int(universe['permnos']):,}",
        "- Universe: US-listed common stocks, excluding REITs, ETFs, closed-end funds, and other non-common-stock securities",
        f"- CPI factor: {universe['cpi_factor']:.2f}x ({pct(universe['cpi_cagr'], 2)} annualized)",
        "",
        "## Stock-Anchored Results",
        "",
        markdown_table(
            ["Horizon", "Basis", "Periods", "PERMNOs", "% positive", "Median", "Mean multiple",
             "% complete", "% delisted", "% sparse"],
            compact_summary_rows(pd.concat([s10, s30], ignore_index=True)),
        ),
        "",
        "![10-year nominal](hist_10y_nominal.png)",
        "![10-year real](hist_10y_real.png)",
        "![30-year nominal](hist_30y_nominal.png)",
        "![30-year real](hist_30y_real.png)",
        "",
        "### First Period Per Stock",
        "",
        markdown_table(
            ["Horizon", "Basis", "Stocks", "% positive", "Median", "% complete", "% delisted"],
            first_period_rows(first),
        ),
        "",
        "## Calendar Start-Cohort Windows",
        "",
        "### 10-Year Windows",
        "",
        markdown_table(
            ["Window", "N", "% positive nominal", "% positive real", "Median nominal",
             "Median real", "% delisted"],
            calendar_rows(cal10),
        ),
        "",
        "![10-year calendar share positive](calendar_pct_positive_10y.png)",
        "",
        "### 30-Year Windows",
        "",
        markdown_table(
            ["Window", "N", "% positive nominal", "% positive real", "Median nominal",
             "Median real", "% delisted"],
            calendar_rows(cal30),
        ),
        "",
        "![30-year calendar share positive](calendar_pct_positive_30y.png)",
        "",
        "## Full-Life Results",
        "",
        markdown_table(
            ["Basis", "Stocks", "% positive", "Median", "Mean multiple", "Max multiple", "% sparse"],
            full_life_rows(slife),
        ),
        "",
        "![Full-life nominal](hist_fulllife_nominal.png)",
        "![Full-life real](hist_fulllife_real.png)",
        "",
        "## Robustness And Audit",
        "",
        "### First Observed Return Sensitivity",
        "",
        markdown_table(
            ["Horizon", "Basis", "% positive incl.", "% positive skip", "Median incl.", "Median skip"],
            sensitivity_rows(sens),
        ),
        "",
        "### Period Audit",
        "",
        markdown_table(
            ["Analysis", "Horizon", "Started periods", "Started PERMNOs", "Included periods",
             "Complete", "Delisted partial", "Sample-end censored", "Sparse"],
            audit_rows(audit),
        ),
        "",
        "## Caveats",
        "",
        "- Stock-anchored headline summaries are stock-period summaries; long-lived stocks can contribute multiple non-overlapping periods.",
        "- The first-period-per-stock table gives a one-stock-one-vote companion view.",
        "- Calendar windows are start-cohort views and do not include stocks that list after the window begins.",
        "- Not-traded months with missing MthRet are set to 0 to preserve the monthly return timeline.",
        "- Sparse histories are rare and listed in sparse_history_audit.csv.",
        "- Delisting outcomes are measured using the CRSP monthly returns present in the file.",
        "",
        "## Reproducibility",
        "",
        "```bash",
        "python program/run_analysis.py",
        "python program/build_docx.py",
        "```",
        "",
    ]

    outpath = os.path.join(RESULTS, "report.md")
    with open(outpath, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    print(f"[saved] {outpath} ({os.path.getsize(outpath):,} bytes)")


def main() -> None:
    data = load_outputs()
    build_docx(data)
    build_markdown(data)


if __name__ == "__main__":
    main()
