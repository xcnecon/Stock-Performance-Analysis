# Stock Performance Analysis

## Purpose

This project uses monthly CRSP (Center for Research in Security Prices) data to
study the long-run return distribution of US-listed stocks. It answers three
questions:

1. **10-year holding period** - What percentage of stocks produce a positive
   return over 10 years? What does the 10-year return distribution look like?
2. **30-year holding period** - What percentage of stocks produce a positive
   return over 30 years? What does the 30-year return distribution look like?
3. **Full-life holding period** - What percentage of stocks produce a positive
   return over their entire listed life? What does that distribution look like?

## Data

- **Source:** CRSP Monthly Stock File (`data/data.csv`, ~2.6 GB, gitignored).
- **Reference:** `data/Monthly Stock File.pdf` documents the schema and field
  definitions.

## Methodology - Survivorship Bias Is The Central Concern

The analysis must include every stock that was ever listed during the period
under study, not just stocks still trading at the end. Restricting the sample to
survivors would systematically overstate returns.

The universe is US-listed common stocks. The code explicitly filters to common
equity and excludes REITs, ETFs, closed-end funds, and other non-common-stock
securities.

**Delisting rule:** if a stock is acquired, merged, liquidated, or delisted for
any reason before the holding period ends, its return is computed from the start
of the period to the delisting date using the CRSP monthly return stream. The
stock is not dropped from the sample.

**Holding-period construction:**

- Stock-anchored 10-year and 30-year periods: for each stock, form
  non-overlapping holding periods starting from its first observed CRSP month.
  A period that begins but cannot complete because the stock delists early is
  still included, terminated at the stock's last observed month.
- Calendar start-cohort windows: fixed windows such as 1925-1935, 1935-1945,
  and 1985-2015. A stock must exist at the window start to enter that window;
  stocks listed midway through the window are not added halfway.
- Active periods that are incomplete only because the sample ends are retained
  in the detail/audit output but excluded from headline holding-period
  summaries.
- Full-life: from first available monthly return to last available monthly
  return.

Detail outputs include CRSP terminal fields, sparse-history flags, a
first-period-per-stock companion summary, and a first-observed-return
sensitivity table.

## Repository Layout

- `program/` - analysis code
- `data/` - raw CRSP inputs (large CSV gitignored, PDF schema doc tracked)
- `results/` - output tables, charts, summary statistics
