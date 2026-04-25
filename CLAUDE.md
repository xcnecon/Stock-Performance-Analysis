# Stock Performance Analysis

## Purpose

This project uses monthly CRSP (Center for Research in Security Prices) data to study the long-run return distribution of US-listed stocks. It answers three questions:

1. **10-year holding period** — What percentage of stocks produce a positive return over 10 years? What does the 10-year return distribution look like?
2. **30-year holding period** — What percentage of stocks produce a positive return over 30 years? What does the 30-year return distribution look like?
3. **Full-life holding period** — What percentage of stocks produce a positive return over their entire listed life? What does that distribution look like?

## Data

- **Source:** CRSP Monthly Stock File (`data/data.csv`, ~2.6 GB, gitignored).
- **Reference:** `data/Monthly Stock File.pdf` documents the schema and field definitions.

## Methodology — survivorship bias is the central concern

The analysis must include every stock that was ever listed during the period under study, not just stocks still trading at the end. Restricting the sample to survivors would systematically overstate returns.

**Delisting rule:** if a stock is acquired, merged, liquidated, or delisted for any reason before the holding period ends, its return is computed from the start of the period to the delisting date (using the CRSP delisting return where available). The stock is not dropped from the sample.

**Holding-period construction:**
- 10-year and 30-year buckets: for each stock, form non-overlapping (or rolling — to be decided) holding periods starting from its listing date. A period that begins but cannot complete because the stock delists early is still included, terminated at the delisting date.
- Full-life: from first available monthly return to last available monthly return (including delisting return).

## Repository layout

- `program/` — analysis code
- `data/` — raw CRSP inputs (large CSV gitignored, PDF schema doc tracked)
- `results/` — output tables, charts, summary statistics
