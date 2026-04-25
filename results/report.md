# Long-run return distributions of US-listed stocks

CRSP monthly, 31,565 common-stock PERMNOs, 192512-202512.

## Methodology

The 10-year and 30-year analyses use stock-anchored, non-overlapping holding periods. Delisted stocks are retained through their last observed CRSP month. Active periods that are incomplete only because the sample ends are excluded from headline summaries and counted in the audit table.

## Data And Universe

- Monthly stock observations after duplicate removal: 4,405,424
- PERMNOs: 31,565
- Universe: US-listed common stocks, excluding REITs, ETFs, closed-end funds, and other non-common-stock securities
- CPI factor: 18.73x (2.94 % annualized)

## 10-Year Results

| Basis | Periods | PERMNOs | % positive | Median | Mean multiple | % complete | % delisted | Avg months |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| nominal | 49,454 | 28,950 | 57.3 % | +23.7 % | 2.29x | 47.1 % | 52.9 % | 83.7 |
| real (CPI-adj) | 49,454 | 28,950 | 49.9 % | -0.2 % | 1.71x | 47.1 % | 52.9 % | 83.7 |

![10-year nominal](hist_10y_nominal.png)
![10-year real](hist_10y_real.png)

## 30-Year Results

| Basis | Periods | PERMNOs | % positive | Median | Mean multiple | % complete | % delisted | Avg months |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| nominal | 29,522 | 27,420 | 51.0 % | +2.9 % | 6.87x | 10.9 % | 89.1 % | 128.1 |
| real (CPI-adj) | 29,522 | 27,420 | 44.0 % | -18.5 % | 2.98x | 10.9 % | 89.1 % | 128.1 |

![30-year nominal](hist_30y_nominal.png)
![30-year real](hist_30y_real.png)

## Full-Life Results

| Basis | Stocks | % positive | Median | Mean multiple | Max multiple |
| --- | ---: | ---: | ---: | ---: | ---: |
| nominal | 31,565 | 48.1 % | -7.4 % | 295x | 4,421,137x |
| real (CPI-adj) | 31,565 | 41.3 % | -29.3 % | 20x | 245,578x |

![Full-life nominal](hist_fulllife_nominal.png)
![Full-life real](hist_fulllife_real.png)

## Audit

| Horizon | Started periods | Started PERMNOs | Included periods | Included PERMNOs | Complete | Delisted partial | Sample-end censored |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 10y | 54,688 | 31,565 | 49,454 | 28,950 | 23,269 | 26,185 | 5,234 |
| 30y | 34,766 | 31,565 | 29,522 | 27,420 | 3,219 | 26,303 | 5,244 |

## Caveats

- Headline holding-period summaries exclude active periods that are right-censored by the sample end.
- Not-traded months with missing MthRet are set to 0 to preserve the monthly return timeline.
- Long-lived stocks can contribute multiple non-overlapping stock-period observations.
- Delisting outcomes are measured using the CRSP monthly returns present in the file.

## Reproducibility

```bash
python program/run_analysis.py
python program/build_docx.py
```
