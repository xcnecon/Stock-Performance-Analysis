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
    if value < 10:
        return f"{value:,.2f}x"
    return f"{value:,.0f}x"


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
        "audit": pd.read_csv(os.path.join(RESULTS, "summary_audit.csv")),
        "universe": pd.read_csv(os.path.join(RESULTS, "universe_summary.csv")),
    }


def summary_rows(summary: pd.DataFrame) -> list[list[str]]:
    rows = []
    for _, row in summary.iterrows():
        rows.append([
            row["basis"],
            f"{int(row['n_periods']):,}",
            f"{int(row['n_permnos']):,}",
            pct(row["pct_positive"]),
            signed_pct(row["median"]),
            mult(row["mean"]),
            pct(row["pct_complete"]),
            pct(row["pct_delisted"]),
            f"{row['avg_realized_months']:.1f}",
        ])
    return rows


def percentile_rows(summary: pd.DataFrame) -> list[list[str]]:
    rows = []
    for _, row in summary.iterrows():
        rows.append([
            row["basis"],
            signed_pct(row["p5"]),
            signed_pct(row["p25"]),
            signed_pct(row["p50"]),
            signed_pct(row["p75"]),
            signed_pct(row["p95"]),
        ])
    return rows


def build_docx(data: dict[str, pd.DataFrame]) -> None:
    doc = Document()
    for section in doc.sections:
        section.left_margin = Inches(0.85)
        section.right_margin = Inches(0.85)
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)

    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10.5)

    s10 = data["s10"]
    s30 = data["s30"]
    slife = data["slife"]
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
    thirty_nom = s30[s30["basis"] == "nominal"].iloc[0]
    life_nom = slife[slife["basis"] == "nominal"].iloc[0]
    life_real = slife[slife["basis"] == "real (CPI-adj)"].iloc[0]
    for text in [
        (
            f"10-year stock-anchored holding periods: {pct(ten_nom['pct_positive'])} "
            f"positive nominal and {pct(ten_real['pct_positive'])} positive real."
        ),
        (
            f"30-year stock-anchored holding periods: {pct(thirty_nom['pct_positive'])} "
            f"positive nominal, with many observations ending early because the stock delisted."
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
        f"The analysis uses {int(universe['permnos']):,} US-listed common-stock "
        f"PERMNOs and {int(universe['raw_rows_after_universe_filter']):,} monthly "
        "stock observations after duplicate removal."
    )
    add_para(
        doc,
        "The universe excludes REITs, ETFs, closed-end funds, and other non-common-stock securities."
    )
    add_para(
        doc,
        f"CPI-U inflation factor from {int(universe['cpi_start_ymm'])} to "
        f"{int(universe['cpi_end_ymm'])}: {universe['cpi_factor']:.2f}x "
        f"({pct(universe['cpi_cagr'], 2)} annualized)."
    )

    add_heading(doc, "2. Methodology", 1)
    add_para(
        doc,
        "The 10-year and 30-year analyses use stock-anchored, non-overlapping "
        "holding periods starting from each stock's first observed CRSP month. "
        "A stock that delists before the planned horizon is retained through its "
        "last observed month. Active periods that are cut off only because the "
        "sample ends are written to the audit file but excluded from headline summaries."
    )
    add_para(doc, "The report focuses on the distribution of individual stock outcomes.")

    add_heading(doc, "3. Holding-Period Results", 1)
    add_heading(doc, "10-Year Periods", 2)
    add_table(
        doc,
        ["Basis", "Periods", "PERMNOs", "% positive", "Median", "Mean multiple",
         "% complete", "% delisted", "Avg months"],
        summary_rows(s10),
    )
    add_picture(doc, "hist_10y_nominal.png")
    add_picture(doc, "hist_10y_real.png")

    add_heading(doc, "10-Year Percentiles", 2)
    add_table(doc, ["Basis", "p5", "p25", "Median", "p75", "p95"], percentile_rows(s10))

    add_heading(doc, "30-Year Periods", 2)
    add_table(
        doc,
        ["Basis", "Periods", "PERMNOs", "% positive", "Median", "Mean multiple",
         "% complete", "% delisted", "Avg months"],
        summary_rows(s30),
    )
    add_picture(doc, "hist_30y_nominal.png")
    add_picture(doc, "hist_30y_real.png")

    add_heading(doc, "30-Year Percentiles", 2)
    add_table(doc, ["Basis", "p5", "p25", "Median", "p75", "p95"], percentile_rows(s30))

    add_heading(doc, "4. Full-Life Results", 1)
    add_table(
        doc,
        ["Basis", "Stocks", "% positive", "Median", "Mean multiple", "Max multiple"],
        [
            [
                row["basis"], f"{int(row['n_permnos']):,}", pct(row["pct_positive"]),
                signed_pct(row["median"]), mult(row["mean"]), mult(row["max"]),
            ]
            for _, row in slife.iterrows()
        ],
    )
    add_picture(doc, "hist_fulllife_nominal.png")
    add_picture(doc, "hist_fulllife_real.png")

    add_heading(doc, "5. Audit", 1)
    add_table(
        doc,
        ["Horizon", "Started periods", "Started PERMNOs", "Included periods",
         "Included PERMNOs", "Complete", "Delisted partial", "Sample-end censored"],
        [
            [
                row["horizon"],
                f"{int(row['all_started_periods']):,}",
                f"{int(row['all_started_permnos']):,}",
                f"{int(row['included_periods']):,}",
                f"{int(row['included_permnos']):,}",
                f"{int(row['complete_periods']):,}",
                f"{int(row['delisted_partial_periods']):,}",
                f"{int(row['sample_end_censored_periods']):,}",
            ]
            for _, row in audit.iterrows()
        ],
    )

    add_heading(doc, "6. Caveats", 1)
    for text in [
        "Headline holding-period summaries exclude active periods that are right-censored by the sample end.",
        "Not-traded months with missing MthRet are set to 0 to preserve the monthly return timeline.",
        "The 10-year and 30-year observations are stock-periods, so long-lived stocks can contribute multiple non-overlapping periods.",
        "Delisting outcomes are measured using the CRSP monthly returns present in the file.",
    ]:
        doc.add_paragraph(text, style="List Bullet")

    add_heading(doc, "7. Files Produced", 1)
    files = doc.add_paragraph()
    files.add_run(
        "results/\n"
        "  report.md, report.docx\n"
        "  summary_10y.csv, summary_30y.csv, summary_holding_periods.csv\n"
        "  summary_fulllife.csv, summary_audit.csv, universe_summary.csv\n"
        "  returns_10y.csv, returns_30y.csv, holding_period_audit.csv\n"
        "  permno_fulllife.csv\n"
        "  hist_10y_nominal.png, hist_10y_real.png\n"
        "  hist_30y_nominal.png, hist_30y_real.png\n"
        "  hist_fulllife_nominal.png, hist_fulllife_real.png"
    ).font.name = "Consolas"
    for run in files.runs:
        run.font.size = Pt(8.5)

    add_heading(doc, "8. Reproducibility", 1)
    p = doc.add_paragraph()
    r = p.add_run("python program/run_analysis.py\npython program/build_docx.py")
    r.font.name = "Consolas"
    r.font.size = Pt(10)

    outpath = os.path.join(RESULTS, "report.docx")
    doc.save(outpath)
    print(f"[saved] {outpath} ({os.path.getsize(outpath):,} bytes)")


def markdown_table(headers: Sequence[str], rows: Iterable[Sequence[str]]) -> str:
    rows = list(rows)
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] + ["---:"] * (len(headers) - 1)) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join(map(str, row)) + " |")
    return "\n".join(out)


def build_markdown(data: dict[str, pd.DataFrame]) -> None:
    s10 = data["s10"]
    s30 = data["s30"]
    slife = data["slife"]
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
        "The 10-year and 30-year analyses use stock-anchored, non-overlapping holding periods. "
        "Delisted stocks are retained through their last observed CRSP month. Active periods "
        "that are incomplete only because the sample ends are excluded from headline summaries "
        "and counted in the audit table.",
        "",
        "## Data And Universe",
        "",
        f"- Monthly stock observations after duplicate removal: {int(universe['raw_rows_after_universe_filter']):,}",
        f"- PERMNOs: {int(universe['permnos']):,}",
        "- Universe: US-listed common stocks, excluding REITs, ETFs, closed-end funds, and other non-common-stock securities",
        f"- CPI factor: {universe['cpi_factor']:.2f}x ({pct(universe['cpi_cagr'], 2)} annualized)",
        "",
        "## 10-Year Results",
        "",
        markdown_table(
            ["Basis", "Periods", "PERMNOs", "% positive", "Median", "Mean multiple",
             "% complete", "% delisted", "Avg months"],
            summary_rows(s10),
        ),
        "",
        "![10-year nominal](hist_10y_nominal.png)",
        "![10-year real](hist_10y_real.png)",
        "",
        "## 30-Year Results",
        "",
        markdown_table(
            ["Basis", "Periods", "PERMNOs", "% positive", "Median", "Mean multiple",
             "% complete", "% delisted", "Avg months"],
            summary_rows(s30),
        ),
        "",
        "![30-year nominal](hist_30y_nominal.png)",
        "![30-year real](hist_30y_real.png)",
        "",
        "## Full-Life Results",
        "",
        markdown_table(
            ["Basis", "Stocks", "% positive", "Median", "Mean multiple", "Max multiple"],
            [
                [
                    row["basis"], f"{int(row['n_permnos']):,}", pct(row["pct_positive"]),
                    signed_pct(row["median"]), mult(row["mean"]), mult(row["max"]),
                ]
                for _, row in slife.iterrows()
            ],
        ),
        "",
        "![Full-life nominal](hist_fulllife_nominal.png)",
        "![Full-life real](hist_fulllife_real.png)",
        "",
        "## Audit",
        "",
        markdown_table(
            ["Horizon", "Started periods", "Started PERMNOs", "Included periods",
             "Included PERMNOs", "Complete", "Delisted partial", "Sample-end censored"],
            [
                [
                    row["horizon"],
                    f"{int(row['all_started_periods']):,}",
                    f"{int(row['all_started_permnos']):,}",
                    f"{int(row['included_periods']):,}",
                    f"{int(row['included_permnos']):,}",
                    f"{int(row['complete_periods']):,}",
                    f"{int(row['delisted_partial_periods']):,}",
                    f"{int(row['sample_end_censored_periods']):,}",
                ]
                for _, row in audit.iterrows()
            ],
        ),
        "",
        "## Caveats",
        "",
        "- Headline holding-period summaries exclude active periods that are right-censored by the sample end.",
        "- Not-traded months with missing MthRet are set to 0 to preserve the monthly return timeline.",
        "- Long-lived stocks can contribute multiple non-overlapping stock-period observations.",
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
