"""End-to-end analysis: long-run return distributions of US-listed stocks.

Answers the three questions from CLAUDE.md using CRSP monthly data, in both
nominal and CPI-adjusted (real) terms, and reports the share of stocks that
beat the broad US equity market over each window.

METHODOLOGY — calendar-aligned holding periods
----------------------------------------------
Instead of stock-anchored "buckets" starting from each stock's listing date,
we use calendar-aligned non-overlapping windows so that (1) every observation
in a given window covers the same calendar months, making comparisons clean,
and (2) we can see how the return distribution varies across periods
(Depression, stagflation, dot-com, etc.).

For each calendar window [T, T+N months]:
  - Cohort = every common stock with a row at month T (listed at end of T,
    i.e. "available to buy"). Survivorship-free: a stock that delists during
    the window is still retained with whatever partial return it realized.
  - Window return = prod(1 + MthRet_t) - 1 over months (T, T+N], truncated
    at the stock's delisting month. CRSP embeds the delisting return in
    MthRet on the MthRetFlg == 'DE' row.
  - Windows used:
      10-year: 10 decades from 1925-12 to 2025-12
               (1925-12 - 1935-12, 1935-12 - 1945-12, ..., 2015-12 - 2025-12)
      30-year: 3 non-overlapping windows
               (1925-12 - 1955-12, 1955-12 - 1985-12, 1985-12 - 2015-12)
  - Full-life remains stock-anchored (per CLAUDE.md Q3): one compounded
    return per stock from its first to its last listed month.

UNIVERSE
--------
Common stocks only: SecurityType == 'EQTY' AND IssuerType != 'REIT' (31,565
PERMNOs). Excludes closed-end funds, ETFs (both classified 'FUND' in CRSP),
derivative securities ('DERV'), and REITs.

REAL RETURNS
------------
CPI-U All Urban Consumers (NSA, BLS), monthly 1925-12 - 2025-12, cached in
data/cpi.csv. Monthly real return: (1 + MthRet) / (1 + pi) - 1, where
pi_t = CPI_t / CPI_{t-1} - 1. Real returns are then compounded the same way
as nominal.

MARKET BENCHMARK
----------------
vwretd (CRSP value-weighted total return, with dividends) is the apples-to-
apples comparator for MthRet (also total return). sprtrn (S&P 500 price-only,
no dividends) is reported for reference. For each window, the benchmark is
compounded over exactly the same months so the comparison is window-matched.

OUTPUTS (results/)
------------------
- summary_10y.csv         — 10 decades x {nominal, real}: % positive, pctiles
- summary_30y.csv         — 3 periods  x {nominal, real}
- summary_fulllife.csv    — 1 row x {nominal, real}
- returns_10y.csv         — long-format per-stock returns for every decade
- returns_30y.csv         — long-format per-stock returns for every 30y window
- permno_fulllife.csv     — per-stock full-life return
- market_benchmark.csv    — market & SP500 return per window + % stocks beating
- market_summary.csv      — full-span market and CPI figures
- hist_{10y,30y}_{period}_{nom,real}.png — per-window histograms
- variation_10y.png       — box/violin across the 10 decades
- variation_30y.png       — box/violin across the 3 long windows
- hist_fulllife_{nom,real}.png
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd


# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
ROOT = r"C:\Users\CHENY\Documents\GitHub\Stock-Performance-Analysis"
DATA = os.path.join(ROOT, "data", "data.csv")
CPI = os.path.join(ROOT, "data", "cpi.csv")
RESULTS_DIR = os.path.join(ROOT, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

COLS = [
    "PERMNO", "YYYYMM", "MthRet", "MthRetFlg",
    "SecurityType", "IssuerType",
    "vwretd", "sprtrn",
]
DTYPES = {
    "PERMNO": "int32",
    "YYYYMM": "int32",
    "MthRet": "float64",
    "MthRetFlg": "category",
    "SecurityType": "category",
    "IssuerType": "category",
    "vwretd": "float64",
    "sprtrn": "float64",
}

# Calendar window definitions
# 10-year windows — every decade from 1925-12 to 2025-12
WINDOWS_10Y: list[tuple[int, int]] = [
    (192512, 193512),
    (193512, 194512),
    (194512, 195512),
    (195512, 196512),
    (196512, 197512),
    (197512, 198512),
    (198512, 199512),
    (199512, 200512),
    (200512, 201512),
    (201512, 202512),
]
# 30-year windows — three non-overlapping periods
WINDOWS_30Y: list[tuple[int, int]] = [
    (192512, 195512),
    (195512, 198512),
    (198512, 201512),
]

PCTILES = [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]


# -----------------------------------------------------------------------------
# Load & clean
# -----------------------------------------------------------------------------
def load_panel() -> pd.DataFrame:
    t0 = time.time()
    df = pd.read_csv(DATA, usecols=COLS, dtype=DTYPES, low_memory=False)
    print(f"[load] raw rows = {len(df):,}, PERMNOs = {df.PERMNO.nunique():,}")

    df = df[(df["SecurityType"] == "EQTY") & (df["IssuerType"] != "REIT")].copy()
    print(f"[universe EQTY ex-REIT] rows = {len(df):,}, "
          f"PERMNOs = {df.PERMNO.nunique():,}")

    before = len(df)
    df = df.drop_duplicates(["PERMNO", "YYYYMM"], keep="first")
    print(f"[dedupe] dropped {before - len(df):,} duplicate rows")

    na = int(df["MthRet"].isna().sum())
    df["MthRet"] = df["MthRet"].fillna(0.0)
    print(f"[fill-na] MthRet: {na:,} null rows set to 0")

    df = df.sort_values(["PERMNO", "YYYYMM"]).reset_index(drop=True)

    cpi = pd.read_csv(CPI, dtype={"YYYYMM": "int32", "CPI": "float64"})
    cpi = cpi.sort_values("YYYYMM").reset_index(drop=True)
    cpi["pi"] = cpi["CPI"].pct_change().fillna(0.0)
    print(f"[cpi] {len(cpi)} months, cum factor = "
          f"{cpi.CPI.iloc[-1] / cpi.CPI.iloc[0]:.2f}x, "
          f"annualized {(cpi.CPI.iloc[-1] / cpi.CPI.iloc[0])**(12/len(cpi)) - 1:.2%}")

    df = df.merge(cpi[["YYYYMM", "pi"]], on="YYYYMM", how="left")
    df["real_ret"] = (1.0 + df["MthRet"]) / (1.0 + df["pi"]) - 1.0
    df["real_ret"] = df["real_ret"].fillna(df["MthRet"])

    print(f"[load+merge done] {time.time() - t0:.1f}s")
    return df


# -----------------------------------------------------------------------------
# Compound per stock over a calendar window
# -----------------------------------------------------------------------------
def calendar_window(df: pd.DataFrame, start_ymm: int, end_ymm: int,
                    ret_col: str) -> pd.Series:
    """Return one compounded return per PERMNO for window (start_ymm, end_ymm].

    Cohort = stocks with a row at YYYYMM == start_ymm.
    Compounding uses months strictly after start_ymm and up to end_ymm,
    truncated at the stock's last observed month.
    """
    cohort = df.loc[df["YYYYMM"] == start_ymm, "PERMNO"].unique()
    mask = (df["YYYYMM"] > start_ymm) & (df["YYYYMM"] <= end_ymm) \
           & (df["PERMNO"].isin(cohort))
    sub = df.loc[mask, ["PERMNO", ret_col]]
    log_ret = np.log1p(sub[ret_col].clip(lower=-0.9999))
    log_sum = log_ret.groupby(sub["PERMNO"], sort=False, observed=True).sum()
    # Any cohort member with no post-start rows is extremely rare (would mean
    # the stock vanished after its start-month row). Treat as 0 return.
    missing = set(cohort) - set(log_sum.index)
    if missing:
        log_sum = pd.concat([log_sum, pd.Series(0.0, index=list(missing))])
    return np.expm1(log_sum)


# -----------------------------------------------------------------------------
# Market return over a calendar window
# -----------------------------------------------------------------------------
def window_market_return(df: pd.DataFrame, start_ymm: int, end_ymm: int,
                         col: str) -> float:
    sub = df[["YYYYMM", col]].drop_duplicates("YYYYMM").sort_values("YYYYMM")
    sub = sub[(sub["YYYYMM"] > start_ymm) & (sub["YYYYMM"] <= end_ymm)]
    r = sub[col].fillna(0.0)
    return float(np.prod(1.0 + r) - 1.0)


# -----------------------------------------------------------------------------
# Summary stats
# -----------------------------------------------------------------------------
@dataclass
class Row:
    label: str
    basis: str
    n: int
    pct_positive: float
    mean: float
    median: float
    min_: float
    max_: float
    pct: dict[str, float]


def summarize(r: pd.Series, label: str, basis: str) -> Row:
    r = r.dropna()
    q = r.quantile(PCTILES).to_dict()
    return Row(
        label=label, basis=basis, n=len(r),
        pct_positive=float((r > 0).mean()),
        mean=float(r.mean()), median=float(r.median()),
        min_=float(r.min()), max_=float(r.max()),
        pct={f"p{int(k * 100)}": float(v) for k, v in q.items()},
    )


def to_dict(row: Row) -> dict:
    d = {
        "window": row.label, "basis": row.basis, "n": row.n,
        "pct_positive": row.pct_positive, "mean": row.mean,
        "median": row.median, "min": row.min_, "max": row.max_,
    }
    d.update(row.pct)
    return d


def fmt_window_label(start: int, end: int) -> str:
    s_year = start // 100
    e_year = end // 100
    return f"{s_year}-{e_year}"


# -----------------------------------------------------------------------------
# Core analysis per horizon
# -----------------------------------------------------------------------------
def analyze_calendar_windows(df: pd.DataFrame,
                             windows: list[tuple[int, int]]
                             ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """For each (start, end) window, compound each cohort stock's nominal and
    real return and collect summary stats + % beating market.

    Returns:
        summary_df  — one row per (window, basis)
        returns_df  — long-format (window, PERMNO, nominal_ret, real_ret)
        bench_df    — one row per window (benchmarks + % beat)
    """
    summary_rows: list[Row] = []
    bench_rows: list[dict] = []
    ret_long: list[pd.DataFrame] = []
    for start, end in windows:
        label = fmt_window_label(start, end)
        nom = calendar_window(df, start, end, "MthRet").rename("nominal_ret")
        real = calendar_window(df, start, end, "real_ret").rename("real_ret")

        summary_rows.append(summarize(nom, label, "nominal"))
        summary_rows.append(summarize(real, label, "real (CPI-adj)"))

        # Market benchmarks for this exact window
        mkt = window_market_return(df, start, end, "vwretd")
        sp = window_market_return(df, start, end, "sprtrn")
        # % of cohort beating market
        beats_mkt = (nom > mkt).mean()
        beats_sp = (nom > sp).mean()

        bench_rows.append({
            "window": label,
            "start_ymm": start, "end_ymm": end,
            "n_stocks": int(len(nom)),
            "vwretd_window_return": mkt,
            "sprtrn_window_return": sp,
            "pct_beat_vwretd": float(beats_mkt),
            "pct_beat_sprtrn": float(beats_sp),
            "stock_median_nominal": float(nom.median()),
            "stock_median_real": float(real.median()),
        })

        # Long-format returns dataframe
        df_window = pd.DataFrame({
            "window": label,
            "start_ymm": start, "end_ymm": end,
            "PERMNO": nom.index.astype(int),
            "nominal_ret": nom.values,
            "real_ret": real.reindex(nom.index).values,
        })
        ret_long.append(df_window)

    summary_df = pd.DataFrame([to_dict(r) for r in summary_rows])
    returns_df = pd.concat(ret_long, ignore_index=True)
    bench_df = pd.DataFrame(bench_rows)
    return summary_df, returns_df, bench_df


# -----------------------------------------------------------------------------
# Full-life per stock (stock-anchored, unchanged from before)
# -----------------------------------------------------------------------------
def full_life(df: pd.DataFrame) -> pd.DataFrame:
    g_nom = np.log1p(df["MthRet"].clip(lower=-0.9999)) \
        .groupby(df["PERMNO"], sort=False, observed=True).sum()
    g_real = np.log1p(df["real_ret"].clip(lower=-0.9999)) \
        .groupby(df["PERMNO"], sort=False, observed=True).sum()
    life = df.groupby("PERMNO", sort=False, observed=True).agg(
        first_ymm=("YYYYMM", "min"),
        last_ymm=("YYYYMM", "max"),
        n_months=("MthRet", "size"),
    )
    life["fulllife_nominal"] = np.expm1(g_nom.reindex(life.index))
    life["fulllife_real"] = np.expm1(g_real.reindex(life.index))
    return life.reset_index()


# -----------------------------------------------------------------------------
# Charts
# -----------------------------------------------------------------------------
def fig_variation_across_windows(returns_df: pd.DataFrame, title: str,
                                 outpath: str) -> None:
    """Box + violin of per-window return distributions to visualize
    variation across calendar periods. Returns clipped to [-1, 5] for
    readability; a caption notes the number above the cap per window.
    """
    import matplotlib.pyplot as plt

    windows = returns_df[["window", "start_ymm"]] \
        .drop_duplicates().sort_values("start_ymm")["window"].tolist()

    fig, axes = plt.subplots(2, 1, figsize=(12, 8))
    bases = [("nominal_ret", "Nominal", axes[0]),
             ("real_ret", "Real (CPI-adj)", axes[1])]

    for col, label, ax in bases:
        data = []
        above = []
        pos_pct = []
        medians = []
        for w in windows:
            r = returns_df.loc[returns_df["window"] == w, col].dropna()
            above.append(int((r > 5).sum()))
            data.append(r.clip(lower=-1.0, upper=5.0).values)
            pos_pct.append(float((r > 0).mean()))
            medians.append(float(r.median()))

        parts = ax.violinplot(data, showmedians=False, showextrema=False)
        for body in parts['bodies']:
            body.set_facecolor("#90cdf4")
            body.set_edgecolor("#2b6cb0")
            body.set_alpha(0.6)
        # Add box on top
        bp = ax.boxplot(data, widths=0.15, whis=[5, 95], showfliers=False,
                        patch_artist=True,
                        boxprops=dict(facecolor="white", edgecolor="#1a365d"),
                        medianprops=dict(color="#c53030", linewidth=2))
        ax.axhline(0, color="red", linestyle="--", linewidth=1, alpha=0.6)

        # Labels with % positive below each window
        ax.set_xticks(range(1, len(windows) + 1))
        xticklabels = [f"{w}\n{pp:.0%} +" for w, pp in zip(windows, pos_pct)]
        ax.set_xticklabels(xticklabels, fontsize=9)
        ax.set_ylabel(f"{label} total return\n(clipped to [-1, 5])")
        ax.set_title(f"{title} — {label}")
        ax.set_ylim(-1.2, 5.2)
        ax.grid(True, alpha=0.3, axis="y")

        # Annotate how many stocks are above the cap in each window
        for i, n_above in enumerate(above, 1):
            if n_above > 0:
                ax.text(i, 5.05, f"↑{n_above}", ha="center", va="bottom",
                        fontsize=7, color="#4a5568")

    fig.tight_layout()
    fig.savefig(outpath, dpi=130)
    plt.close(fig)


def fig_pct_positive_by_window(bench_df: pd.DataFrame, summary_df: pd.DataFrame,
                               title: str, outpath: str) -> None:
    """Line/bar chart: % positive by window, nominal vs real, alongside the
    market's own return for that window.
    """
    import matplotlib.pyplot as plt

    windows = bench_df["window"].tolist()
    pp_nom = summary_df[summary_df["basis"] == "nominal"] \
        .set_index("window").loc[windows, "pct_positive"].values
    pp_real = summary_df[summary_df["basis"] == "real (CPI-adj)"] \
        .set_index("window").loc[windows, "pct_positive"].values
    mkt = bench_df["vwretd_window_return"].values
    beat = bench_df["pct_beat_vwretd"].values

    x = np.arange(len(windows))
    w = 0.28

    fig, ax1 = plt.subplots(figsize=(12, 5))
    ax1.bar(x - w, pp_nom, w, label="% positive (nominal)",
            color="#2b6cb0", edgecolor="white")
    ax1.bar(x, pp_real, w, label="% positive (real, CPI-adj)",
            color="#4fd1c5", edgecolor="white")
    ax1.bar(x + w, beat, w, label="% beating CRSP VW market",
            color="#9f7aea", edgecolor="white")
    ax1.axhline(0.5, color="#4a5568", linestyle=":", linewidth=1)
    ax1.set_xticks(x)
    ax1.set_xticklabels(windows, rotation=0, fontsize=9)
    ax1.set_ylabel("Share of stocks")
    ax1.set_ylim(0, 1.0)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _p: f"{v*100:.0f}%"))
    ax1.legend(loc="upper left", fontsize=9)
    ax1.grid(True, alpha=0.3, axis="y")

    # Secondary axis: market return over the window
    ax2 = ax1.twinx()
    ax2.plot(x, mkt, "o-", color="#e53e3e", label="CRSP VW market return", linewidth=2)
    ax2.set_ylabel("Market total return over the window", color="#e53e3e")
    ax2.tick_params(axis="y", labelcolor="#e53e3e")
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _p: f"{v*100:,.0f}%"))

    ax1.set_title(title)
    fig.tight_layout()
    fig.savefig(outpath, dpi=130)
    plt.close(fig)


def fig_per_window_hist(returns_df: pd.DataFrame, window: str,
                        basis_col: str, basis_label: str, outpath: str,
                        linear_xlim: tuple[float, float], months: int) -> None:
    import matplotlib.pyplot as plt
    r = returns_df.loc[returns_df["window"] == window, basis_col].dropna()

    fig, axes = plt.subplots(1, 3, figsize=(16, 4.6))
    lo, hi = linear_xlim
    n = len(r)
    n_above = int((r > hi).sum())

    ax = axes[0]
    ax.hist(r[(r >= lo) & (r <= hi)], bins=60, color="#2b6cb0",
            edgecolor="white", linewidth=0.3)
    ax.axvline(0, color="red", linestyle="--", linewidth=1)
    ax.set_title(f"{window} return, {basis_label}\nlinear view, x in [{lo:g}, {hi:g}]")
    ax.set_xlabel("Total return (simple)")
    ax.set_ylabel("# stocks")
    note = [f"N = {n:,}", f"% positive = {(r > 0).mean():.1%}"]
    if n_above:
        note.append(f"{n_above:,} above +{hi:g}")
    ax.text(0.98, 0.96, "\n".join(note), transform=ax.transAxes,
            ha="right", va="top", fontsize=9,
            bbox=dict(facecolor="white", edgecolor="#cccccc", alpha=0.9))

    ax = axes[1]
    lr = np.log1p(r.clip(lower=-0.9999))
    ax.hist(lr, bins=60, color="#2b6cb0", edgecolor="white", linewidth=0.3)
    ax.axvline(0, color="red", linestyle="--", linewidth=1)
    ax.set_title(f"{window} return, {basis_label}\nlog(1+r) view")
    ax.set_xlabel("log(1 + total return)")
    ax.set_ylabel("# stocks")
    med = float(np.median(lr))
    ax.text(0.98, 0.96,
            f"median log(1+r) = {med:+.2f}\nmedian return = {np.expm1(med):+.1%}",
            transform=ax.transAxes, ha="right", va="top", fontsize=9,
            bbox=dict(facecolor="white", edgecolor="#cccccc", alpha=0.9))

    ax = axes[2]
    ann = (1.0 + r.clip(lower=-0.9999)) ** (12.0 / months) - 1.0
    ax.hist(ann.clip(lower=-1.0, upper=1.0), bins=60, color="#2b6cb0",
            edgecolor="white", linewidth=0.3)
    ax.axvline(0, color="red", linestyle="--", linewidth=1)
    ax.set_title(f"{window} return, {basis_label}\nannualized, x in [-100%, +100%]")
    ax.set_xlabel("Annualized return")
    ax.set_ylabel("# stocks")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _p: f"{v*100:.0f}%"))

    fig.tight_layout()
    fig.savefig(outpath, dpi=130)
    plt.close(fig)


def fig_fulllife(r: pd.Series, title: str, outpath: str,
                 linear_xlim: tuple[float, float]) -> None:
    import matplotlib.pyplot as plt
    r = r.dropna()
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.6))

    lo, hi = linear_xlim
    n_above = int((r > hi).sum())

    ax = axes[0]
    ax.hist(r[(r >= lo) & (r <= hi)], bins=80, color="#2b6cb0",
            edgecolor="white", linewidth=0.3)
    ax.axvline(0, color="red", linestyle="--", linewidth=1)
    ax.set_title(f"{title}\nlinear view, x in [{lo:g}, {hi:g}]")
    ax.set_xlabel("Total return (simple)")
    ax.set_ylabel("# stocks")
    note = [f"N = {len(r):,}", f"% positive = {(r > 0).mean():.1%}"]
    if n_above:
        note.append(f"{n_above:,} above +{hi:g}")
    ax.text(0.98, 0.96, "\n".join(note), transform=ax.transAxes,
            ha="right", va="top", fontsize=9,
            bbox=dict(facecolor="white", edgecolor="#cccccc", alpha=0.9))

    ax = axes[1]
    lr = np.log1p(r.clip(lower=-0.9999))
    ax.hist(lr, bins=80, color="#2b6cb0", edgecolor="white", linewidth=0.3)
    ax.axvline(0, color="red", linestyle="--", linewidth=1)
    ax.set_title(f"{title}\nlog(1+r) view")
    ax.set_xlabel("log(1 + total return)")
    ax.set_ylabel("# stocks")
    med = float(np.median(lr))
    ax.text(0.98, 0.96,
            f"median log(1+r) = {med:+.2f}\nmedian return = {np.expm1(med):+.1%}",
            transform=ax.transAxes, ha="right", va="top", fontsize=9,
            bbox=dict(facecolor="white", edgecolor="#cccccc", alpha=0.9))

    ax = axes[2]
    rs = np.sort(r.values)
    cdf = np.arange(1, len(rs) + 1) / len(rs)
    ax.semilogx(np.clip(1.0 + rs, 1e-3, None), cdf, color="#2b6cb0")
    ax.axvline(1, color="red", linestyle="--", linewidth=1)
    ax.set_title(f"{title}\nCDF on log wealth multiple (1+r)")
    ax.set_xlabel("Wealth multiple (1 + r)")
    ax.set_ylabel("Cumulative share of stocks")
    ax.grid(True, alpha=0.3)
    frac_nonpos = float((r <= 0).mean())
    ax.text(0.02, 0.96,
            f"{frac_nonpos:.1%} of stocks ended at or below break-even",
            transform=ax.transAxes, ha="left", va="top", fontsize=9,
            bbox=dict(facecolor="white", edgecolor="#cccccc", alpha=0.9))

    fig.tight_layout()
    fig.savefig(outpath, dpi=130)
    plt.close(fig)


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main() -> None:
    t0 = time.time()
    df = load_panel()

    print("\n===== 10-year calendar windows =====")
    s10, r10, b10 = analyze_calendar_windows(df, WINDOWS_10Y)
    s10.to_csv(os.path.join(RESULTS_DIR, "summary_10y.csv"), index=False)
    r10.to_csv(os.path.join(RESULTS_DIR, "returns_10y.csv"), index=False)
    print(s10[["window", "basis", "n", "pct_positive", "median"]].to_string(index=False))

    print("\n===== 30-year calendar windows =====")
    s30, r30, b30 = analyze_calendar_windows(df, WINDOWS_30Y)
    s30.to_csv(os.path.join(RESULTS_DIR, "summary_30y.csv"), index=False)
    r30.to_csv(os.path.join(RESULTS_DIR, "returns_30y.csv"), index=False)
    print(s30[["window", "basis", "n", "pct_positive", "median"]].to_string(index=False))

    print("\n===== full-life (stock-anchored) =====")
    life = full_life(df)
    life.to_csv(os.path.join(RESULTS_DIR, "permno_fulllife.csv"), index=False)
    s_life = []
    for basis_col, basis in [("fulllife_nominal", "nominal"),
                             ("fulllife_real", "real (CPI-adj)")]:
        s_life.append(to_dict(summarize(life[basis_col], "full-life", basis)))
    life_summary = pd.DataFrame(s_life)
    life_summary.to_csv(os.path.join(RESULTS_DIR, "summary_fulllife.csv"), index=False)
    print(life_summary[["window", "basis", "n", "pct_positive", "median"]].to_string(index=False))

    # Benchmark table: 10y + 30y + full-life
    b10["horizon"] = "10y"
    b30["horizon"] = "30y"
    # Full-life: market return is over the actual calendar months the stock was listed
    # Per-stock market return over life:
    m = df[["YYYYMM", "vwretd", "sprtrn"]].drop_duplicates("YYYYMM").sort_values("YYYYMM")
    vw_map = dict(zip(m["YYYYMM"].values, m["vwretd"].fillna(0).values))
    sp_map = dict(zip(m["YYYYMM"].values, m["sprtrn"].fillna(0).values))
    dfx = df[["PERMNO", "YYYYMM", "MthRet"]].copy()
    dfx["mkt"] = dfx["YYYYMM"].map(vw_map).fillna(0.0)
    dfx["sp"] = dfx["YYYYMM"].map(sp_map).fillna(0.0)
    stk = np.expm1(np.log1p(dfx["MthRet"].clip(lower=-0.9999))
                   .groupby(dfx["PERMNO"], sort=False, observed=True).sum())
    mkt = np.expm1(np.log1p(dfx["mkt"])
                   .groupby(dfx["PERMNO"], sort=False, observed=True).sum())
    sp = np.expm1(np.log1p(dfx["sp"])
                  .groupby(dfx["PERMNO"], sort=False, observed=True).sum())
    life_bench = pd.DataFrame([{
        "horizon": "full-life",
        "window": "per-stock life",
        "start_ymm": np.nan, "end_ymm": np.nan,
        "n_stocks": int(len(stk)),
        "vwretd_window_return": float(mkt.median()),
        "sprtrn_window_return": float(sp.median()),
        "pct_beat_vwretd": float((stk > mkt).mean()),
        "pct_beat_sprtrn": float((stk > sp).mean()),
        "stock_median_nominal": float(stk.median()),
        "stock_median_real": float(np.nan),
    }])
    bench_all = pd.concat([b10, b30, life_bench], ignore_index=True)
    bench_all.to_csv(os.path.join(RESULTS_DIR, "market_benchmark.csv"), index=False)
    print("\n===== market benchmark =====")
    print(bench_all[["horizon", "window", "n_stocks", "vwretd_window_return",
                     "pct_beat_vwretd", "pct_beat_sprtrn"]].to_string(index=False))

    # Full-span market summary
    vw_full = float(np.prod(1.0 + m["vwretd"].fillna(0)) - 1.0)
    sp_full = float(np.prod(1.0 + m["sprtrn"].fillna(0)) - 1.0)
    n_months = len(m)
    mkt_summary = {
        "sample_start_ymm": int(m["YYYYMM"].min()),
        "sample_end_ymm": int(m["YYYYMM"].max()),
        "n_months": n_months,
        "vwretd_total_return": vw_full,
        "vwretd_cagr": (1.0 + vw_full) ** (12.0 / n_months) - 1.0,
        "sprtrn_total_return": sp_full,
        "sprtrn_cagr": (1.0 + sp_full) ** (12.0 / n_months) - 1.0,
    }
    pd.DataFrame([mkt_summary]).to_csv(
        os.path.join(RESULTS_DIR, "market_summary.csv"), index=False)

    # ------------------- Charts -------------------
    print("\n===== charts =====")
    # 1) Variation across windows — violin+box
    fig_variation_across_windows(
        r10, "10-year calendar-window returns",
        os.path.join(RESULTS_DIR, "variation_10y.png"))
    fig_variation_across_windows(
        r30, "30-year calendar-window returns",
        os.path.join(RESULTS_DIR, "variation_30y.png"))
    # 2) % positive by window bar chart
    fig_pct_positive_by_window(
        b10, s10, "Share of stocks positive by 10-year window, with market context",
        os.path.join(RESULTS_DIR, "pct_positive_10y.png"))
    fig_pct_positive_by_window(
        b30, s30, "Share of stocks positive by 30-year window, with market context",
        os.path.join(RESULTS_DIR, "pct_positive_30y.png"))
    # 3) Per-window histograms
    for start, end in WINDOWS_10Y:
        w = fmt_window_label(start, end)
        for col, basis in [("nominal_ret", "nominal"), ("real_ret", "real")]:
            fig_per_window_hist(
                r10, w, col, basis,
                os.path.join(RESULTS_DIR, f"hist_10y_{w}_{basis}.png"),
                linear_xlim=(-1.0, 5.0), months=120)
    for start, end in WINDOWS_30Y:
        w = fmt_window_label(start, end)
        for col, basis in [("nominal_ret", "nominal"), ("real_ret", "real")]:
            fig_per_window_hist(
                r30, w, col, basis,
                os.path.join(RESULTS_DIR, f"hist_30y_{w}_{basis}.png"),
                linear_xlim=(-1.0, 20.0), months=360)
    # 4) Full-life charts
    fig_fulllife(life["fulllife_nominal"], "Full-life return per stock (nominal)",
                 os.path.join(RESULTS_DIR, "hist_fulllife_nominal.png"),
                 linear_xlim=(-1.0, 10.0))
    fig_fulllife(life["fulllife_real"], "Full-life return per stock (real, CPI-adj)",
                 os.path.join(RESULTS_DIR, "hist_fulllife_real.png"),
                 linear_xlim=(-1.0, 10.0))

    print(f"[saved] charts")
    print(f"\n[total elapsed] {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
