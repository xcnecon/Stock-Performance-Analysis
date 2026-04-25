# Stock Performance Analysis

Long-run return distributions of US-listed common stocks, CRSP monthly 1925-12 – 2025-12, **31,565 stocks** (EQTY ex-REIT, ex-ETF, ex-closed-end-fund). Survivorship-bias-free: every stock that ever listed is retained, delistings terminate the return stream at the delisting value.

**Calendar-window methodology:** every 10-year (1925-35, 1935-45, … 2015-25) and 30-year (1925-55, 1955-85, 1985-2015) window is analysed on its own cohort, so the variation in return distributions across eras (Depression, stagflation, dot-com, mega-cap era) is visible directly.

## Three questions

1. What percentage of US common stocks produce a positive return over each 10-year calendar window?
2. Over each 30-year calendar window?
3. Over each stock's entire listed life?

Each answered in nominal and CPI-adjusted (real) terms, with the share of stocks beating the CRSP value-weighted market total return.

See [`results/report.md`](results/report.md) or [`results/report.docx`](results/report.docx) for the full write-up.

## Headline — % positive across decades (10-year windows)

| Decade | % pos nominal | % pos real | Market return | % beat market |
| --- | ---: | ---: | ---: | ---: |
| 1925-1935 | 40.7 % | 48.8 % | +48 % | 28 % |
| 1935-1945 | 87.6 % | 83.8 % | +137 % | 51 % |
| 1945-1955 | 88.5 % | 78.9 % | +302 % | 29 % |
| 1955-1965 | **89.0 %** | **85.8 %** | +194 % | 41 % |
| 1965-1975 | 59.3 % | **38.0 %** | +31 % | 43 % |
| 1975-1985 | 87.8 % | 79.7 % | +326 % | 47 % |
| 1985-1995 | 57.5 % | 52.1 % | +265 % | **15 %** |
| 1995-2005 | 60.8 % | 56.9 % | +144 % | 28 % |
| 2005-2015 | 55.5 % | 50.7 % | +93 % | 25 % |
| 2015-2025 | 62.2 % | 56.8 % | +252 % | **16 %** |

## Layout

```
program/
  run_analysis.py    — calendar-window analysis (end-to-end)
  build_docx.py      — renders results/report.docx
data/
  data.csv           — CRSP monthly (gitignored, ~2.6 GB)
  cpi.csv            — BLS CPI-U monthly, 1925-2025
  cpi_source.csv     — raw CPI year × month grid
  Monthly Stock File.pdf — CRSP schema
results/             — report.md, report.docx, summaries, charts, long-format returns
```

## Running

```bash
python program/run_analysis.py     # ~50 s
python program/build_docx.py       # ~3 s
```

Requires Python 3.11+, pandas, numpy, matplotlib, python-docx.

## Data

CRSP monthly data (compressed): https://drive.google.com/file/d/1in12j\_ytRMzcS-HjPdPxjIm9EfiwcunB/view?usp=sharing
