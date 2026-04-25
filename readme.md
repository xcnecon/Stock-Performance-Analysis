# Stock Performance Analysis

Long-run return distributions of US-listed common stocks using CRSP monthly
data from 1925-12 through 2025-12. The analysis covers 31,565 common-stock
PERMNOs after filtering to `SecurityType == 'EQTY'` and excluding REIT issuers.

The core methodology is survivorship-bias aware: 10-year and 30-year results
use stock-anchored, non-overlapping holding periods that start from each stock's
first observed CRSP month. If a stock delists before the planned horizon ends,
the partial return through its last observed month is included. Active periods
that are incomplete only because the sample ends are kept in the audit file but
excluded from headline summaries.

Market-return comparisons have been removed so the report focuses on the
distribution of individual stock outcomes.

See [`results/report.md`](results/report.md) or [`results/report.docx`](results/report.docx)
for the full write-up.

## Headline Results

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
  run_analysis.py    stock-anchored analysis and chart generation
  build_docx.py      renders results/report.docx and results/report.md
data/
  data.csv           CRSP monthly input, gitignored
  cpi.csv            BLS CPI-U monthly, 1925-2025
  cpi_source.csv     raw CPI source table
  Monthly Stock File.pdf
results/
  report.md, report.docx
  summary_10y.csv, summary_30y.csv, summary_holding_periods.csv
  summary_fulllife.csv, summary_audit.csv, universe_summary.csv
  returns_10y.csv, returns_30y.csv, holding_period_audit.csv
  permno_fulllife.csv
  hist_10y_nominal.png, hist_10y_real.png
  hist_30y_nominal.png, hist_30y_real.png
  hist_fulllife_nominal.png, hist_fulllife_real.png
```

## Running

```bash
python program/run_analysis.py
python program/build_docx.py
```

Requires Python 3.11+, pandas, numpy, matplotlib, and python-docx.
