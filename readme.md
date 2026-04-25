# Stock Performance Analysis

Long-run return distributions of US-listed common stocks using CRSP monthly
data from 1925-12 through 2025-12. The analysis covers 31,565 common-stock
PERMNOs after explicitly filtering to common equity and excluding REITs, ETFs,
closed-end funds, and other non-common-stock securities.

The report has two complementary holding-period views:

- **Stock-anchored periods:** each stock starts its own non-overlapping 10-year
  and 30-year clock from its first observed CRSP month. Delisted stocks are kept
  through their last observed month. Active periods that are incomplete only
  because the sample ends are audited but excluded from headline summaries.
- **Calendar start-cohort windows:** fixed windows such as 1925-1935,
  1935-1945, and 1985-2015. A stock must exist at the window start to enter
  that window; stocks listed midway through the window are not added halfway.

See [`results/report.md`](results/report.md) or [`results/report.docx`](results/report.docx)
for the full write-up.

## Headline Stock-Anchored Results

| Horizon | Basis | Observations | PERMNOs | % positive | Median |
| --- | --- | ---: | ---: | ---: | ---: |
| 10-year | nominal | 49,454 | 28,950 | 57.3 % | +23.7 % |
| 10-year | real (CPI-adj) | 49,454 | 28,950 | 49.9 % | -0.2 % |
| 30-year | nominal | 29,522 | 27,420 | 51.0 % | +2.9 % |
| 30-year | real (CPI-adj) | 29,522 | 27,420 | 44.0 % | -18.5 % |
| Full-life | nominal | 31,565 | 31,565 | 48.1 % | -7.4 % |
| Full-life | real (CPI-adj) | 31,565 | 31,565 | 41.3 % | -29.3 % |

## Layout

```text
program/
  run_analysis.py    analysis, audits, sensitivity checks, chart generation
  build_docx.py      renders results/report.docx and results/report.md
data/
  data.csv           CRSP monthly input, gitignored
  cpi.csv            BLS CPI-U monthly, 1925-2025
  cpi_source.csv     raw CPI source table
  Monthly Stock File.pdf
results/
  report.md, report.docx
  summary_10y.csv, summary_30y.csv, summary_holding_periods.csv
  summary_calendar_10y.csv, summary_calendar_30y.csv
  summary_first_period_by_stock.csv
  summary_first_month_sensitivity.csv
  summary_fulllife.csv, summary_audit.csv, universe_summary.csv
  returns_10y.csv, returns_30y.csv
  returns_calendar_10y.csv, returns_calendar_30y.csv
  holding_period_audit.csv, sparse_history_audit.csv
  permno_fulllife.csv
```

## Running

```bash
python program/run_analysis.py
python program/build_docx.py
```

Requires Python 3.11+, pandas, numpy, matplotlib, and python-docx.
