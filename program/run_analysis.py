"""End-to-end analysis of long-run CRSP stock return distributions.

The 10-year and 30-year analyses use stock-anchored, non-overlapping holding
periods that start from each stock's first observed month. If a stock delists
before a planned holding period finishes, the partial period is retained through
the stock's last observed month. If the sample ends before an active stock can
finish the period, the right-censored period is written to the detail file but
excluded from the headline summaries.

Outputs are written to results/.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd


ROOT = r"C:\Users\CHENY\Documents\GitHub\Stock-Performance-Analysis"
DATA = os.path.join(ROOT, "data", "data.csv")
CPI = os.path.join(ROOT, "data", "cpi.csv")
RESULTS_DIR = os.path.join(ROOT, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

COLS = [
    "PERMNO", "YYYYMM", "MthRet", "MthRetFlg",
    "SecurityType", "IssuerType", "SecuritySubType", "ShareType",
]
DTYPES = {
    "PERMNO": "int32",
    "YYYYMM": "int32",
    "MthRet": "float64",
    "MthRetFlg": "category",
    "SecurityType": "category",
    "IssuerType": "category",
    "SecuritySubType": "category",
    "ShareType": "category",
}

PCTILES = [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]
HORIZONS = [(10, 120), (30, 360)]


def yyyymm_to_month_index(yyyymm: pd.Series | np.ndarray) -> np.ndarray:
    values = np.asarray(yyyymm, dtype=np.int64)
    return (values // 100) * 12 + (values % 100) - 1


def month_index_to_yyyymm(month_index: int) -> int:
    year = month_index // 12
    month = month_index % 12 + 1
    return int(year * 100 + month)


def compound_return(values: np.ndarray) -> float:
    values = values[~np.isnan(values)]
    if len(values) == 0:
        return np.nan
    return float(np.prod(1.0 + values) - 1.0)


def load_panel() -> tuple[pd.DataFrame, pd.DataFrame]:
    t0 = time.time()
    df = pd.read_csv(DATA, usecols=COLS, dtype=DTYPES, low_memory=False)
    raw_rows = len(df)
    raw_permnos = df["PERMNO"].nunique()
    print(f"[load] raw rows = {raw_rows:,}, PERMNOs = {raw_permnos:,}")

    df = df[(df["SecurityType"] == "EQTY") & (df["IssuerType"] != "REIT")].copy()
    print(
        f"[universe EQTY ex-REIT] rows = {len(df):,}, "
        f"PERMNOs = {df.PERMNO.nunique():,}"
    )

    before = len(df)
    df = df.drop_duplicates(["PERMNO", "YYYYMM"], keep="first")
    print(f"[dedupe] dropped {before - len(df):,} duplicate rows")

    na = int(df["MthRet"].isna().sum())
    df["MthRet"] = df["MthRet"].fillna(0.0)
    print(f"[fill-na] MthRet: {na:,} null rows set to 0")

    cpi = pd.read_csv(CPI, dtype={"YYYYMM": "int32", "CPI": "float64"})
    cpi = cpi.sort_values("YYYYMM").reset_index(drop=True)
    cpi["pi"] = cpi["CPI"].pct_change().fillna(0.0)
    print(
        f"[cpi] {len(cpi):,} months, cumulative inflation "
        f"{cpi.CPI.iloc[-1] / cpi.CPI.iloc[0]:.2f}x"
    )

    df = df.merge(cpi[["YYYYMM", "pi"]], on="YYYYMM", how="left")
    df["real_ret"] = (1.0 + df["MthRet"]) / (1.0 + df["pi"]) - 1.0
    df["real_ret"] = df["real_ret"].fillna(df["MthRet"])
    df["month_index"] = yyyymm_to_month_index(df["YYYYMM"])
    df = df.sort_values(["PERMNO", "YYYYMM"]).reset_index(drop=True)

    print(f"[load+merge done] {time.time() - t0:.1f}s")
    return df, cpi


def build_holding_periods(df: pd.DataFrame, horizon_years: int,
                          horizon_months: int) -> pd.DataFrame:
    """Build stock-anchored, non-overlapping holding periods.

    Included-in-summary periods are either complete full-horizon observations or
    observations that end early because the stock left the CRSP file before the
    sample end. Active right-censored periods are retained in the detail file for
    auditability but excluded from headline statistics.
    """
    sample_end_idx = int(df["month_index"].max())
    rows: list[dict] = []

    cols = ["YYYYMM", "month_index", "MthRet", "real_ret"]
    for permno, g in df.groupby("PERMNO", sort=False, observed=True):
        g = g[cols].sort_values("month_index")
        month_idx = g["month_index"].to_numpy(dtype=np.int64)
        yyyymm = g["YYYYMM"].to_numpy(dtype=np.int32)
        nominal = g["MthRet"].to_numpy(dtype=np.float64)
        real = g["real_ret"].to_numpy(dtype=np.float64)
        last_idx = int(month_idx[-1])

        start_pos = 0
        period_n = 1
        while start_pos < len(g):
            start_idx = int(month_idx[start_pos])
            target_end_idx = start_idx + horizon_months - 1
            end_idx = min(target_end_idx, last_idx)
            end_pos = int(np.searchsorted(month_idx, end_idx, side="right"))
            if end_pos <= start_pos:
                break

            period_months = month_idx[start_pos:end_pos]
            if last_idx >= target_end_idx:
                terminal_reason = "complete"
            elif last_idx < sample_end_idx:
                terminal_reason = "delisted"
            else:
                terminal_reason = "sample_end"

            rows.append({
                "horizon": f"{horizon_years}y",
                "horizon_months": horizon_months,
                "period_number": period_n,
                "PERMNO": int(permno),
                "start_ymm": int(yyyymm[start_pos]),
                "target_end_ymm": month_index_to_yyyymm(target_end_idx),
                "end_ymm": month_index_to_yyyymm(end_idx),
                "realized_months": int(end_idx - start_idx + 1),
                "observed_rows": int(len(period_months)),
                "terminal_reason": terminal_reason,
                "included_in_summary": terminal_reason != "sample_end",
                "nominal_ret": compound_return(nominal[start_pos:end_pos]),
                "real_ret": compound_return(real[start_pos:end_pos]),
            })

            if terminal_reason != "complete":
                break
            start_pos = int(np.searchsorted(month_idx, target_end_idx + 1, side="left"))
            period_n += 1

    out = pd.DataFrame(rows)
    print(
        f"[{horizon_years}y periods] rows = {len(out):,}, "
        f"in summary = {int(out.included_in_summary.sum()):,}, "
        f"PERMNOs represented = {out.PERMNO.nunique():,}"
    )
    return out


@dataclass
class SummaryRow:
    horizon: str
    basis: str
    n_periods: int
    n_permnos: int
    pct_positive: float
    mean: float
    median: float
    min_: float
    max_: float
    avg_realized_months: float
    pct_complete: float
    pct_delisted: float
    pct: dict[str, float]


def summarize_periods(periods: pd.DataFrame, ret_col: str, basis: str) -> SummaryRow:
    d = periods[periods["included_in_summary"]].copy()
    r = d[ret_col].dropna()
    q = r.quantile(PCTILES).to_dict()
    reasons = d["terminal_reason"].value_counts(normalize=True)
    return SummaryRow(
        horizon=str(d["horizon"].iloc[0]),
        basis=basis,
        n_periods=int(len(r)),
        n_permnos=int(d.loc[r.index, "PERMNO"].nunique()),
        pct_positive=float((r > 0).mean()),
        mean=float(r.mean()),
        median=float(r.median()),
        min_=float(r.min()),
        max_=float(r.max()),
        avg_realized_months=float(d.loc[r.index, "realized_months"].mean()),
        pct_complete=float(reasons.get("complete", 0.0)),
        pct_delisted=float(reasons.get("delisted", 0.0)),
        pct={f"p{int(k * 100)}": float(v) for k, v in q.items()},
    )


def summarize_full_life(life: pd.DataFrame, ret_col: str, basis: str) -> dict:
    r = life[ret_col].dropna()
    q = r.quantile(PCTILES).to_dict()
    row = {
        "horizon": "full-life",
        "basis": basis,
        "n_periods": int(len(r)),
        "n_permnos": int(life.loc[r.index, "PERMNO"].nunique()),
        "pct_positive": float((r > 0).mean()),
        "mean": float(r.mean()),
        "median": float(r.median()),
        "min": float(r.min()),
        "max": float(r.max()),
        "avg_realized_months": float(life.loc[r.index, "n_months"].mean()),
        "pct_complete": np.nan,
        "pct_delisted": np.nan,
    }
    row.update({f"p{int(k * 100)}": float(v) for k, v in q.items()})
    return row


def summary_to_dict(row: SummaryRow) -> dict:
    out = {
        "horizon": row.horizon,
        "basis": row.basis,
        "n_periods": row.n_periods,
        "n_permnos": row.n_permnos,
        "pct_positive": row.pct_positive,
        "mean": row.mean,
        "median": row.median,
        "min": row.min_,
        "max": row.max_,
        "avg_realized_months": row.avg_realized_months,
        "pct_complete": row.pct_complete,
        "pct_delisted": row.pct_delisted,
    }
    out.update(row.pct)
    return out


def full_life(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for permno, g in df.groupby("PERMNO", sort=False, observed=True):
        g = g.sort_values("month_index")
        start_idx = int(g["month_index"].iloc[0])
        end_idx = int(g["month_index"].iloc[-1])
        rows.append({
            "PERMNO": int(permno),
            "first_ymm": int(g["YYYYMM"].iloc[0]),
            "last_ymm": int(g["YYYYMM"].iloc[-1]),
            "n_months": int(end_idx - start_idx + 1),
            "observed_rows": int(len(g)),
            "fulllife_nominal": compound_return(g["MthRet"].to_numpy(dtype=np.float64)),
            "fulllife_real": compound_return(g["real_ret"].to_numpy(dtype=np.float64)),
        })
    return pd.DataFrame(rows)


def universe_summary(df: pd.DataFrame, cpi: pd.DataFrame) -> pd.DataFrame:
    perm = df.drop_duplicates("PERMNO")
    issuer = (
        perm.groupby("IssuerType", observed=True)["PERMNO"]
        .nunique().sort_values(ascending=False)
    )
    share = (
        perm.groupby("ShareType", observed=True)["PERMNO"]
        .nunique().sort_values(ascending=False)
    )
    out = {
        "raw_rows_after_universe_filter": int(len(df)),
        "permnos": int(df["PERMNO"].nunique()),
        "sample_start_ymm": int(df["YYYYMM"].min()),
        "sample_end_ymm": int(df["YYYYMM"].max()),
        "n_months": int(df["YYYYMM"].nunique()),
        "mthret_null_filled_nt": int((df["MthRetFlg"] == "NT").sum()),
        "cpi_start_ymm": int(cpi["YYYYMM"].min()),
        "cpi_end_ymm": int(cpi["YYYYMM"].max()),
        "cpi_factor": float(cpi["CPI"].iloc[-1] / cpi["CPI"].iloc[0]),
        "cpi_cagr": float((cpi["CPI"].iloc[-1] / cpi["CPI"].iloc[0]) ** (12 / len(cpi)) - 1),
        "issuer_counts": "; ".join(f"{k}: {int(v)}" for k, v in issuer.items()),
        "share_type_counts": "; ".join(f"{k}: {int(v)}" for k, v in share.items()),
    }
    return pd.DataFrame([out])


def period_audit(periods: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for horizon, d in periods.groupby("horizon", sort=False):
        reasons = d["terminal_reason"].value_counts()
        included = d[d["included_in_summary"]]
        rows.append({
            "horizon": horizon,
            "all_started_periods": int(len(d)),
            "all_started_permnos": int(d["PERMNO"].nunique()),
            "included_periods": int(len(included)),
            "included_permnos": int(included["PERMNO"].nunique()),
            "complete_periods": int(reasons.get("complete", 0)),
            "delisted_partial_periods": int(reasons.get("delisted", 0)),
            "sample_end_censored_periods": int(reasons.get("sample_end", 0)),
            "median_realized_months_included": float(included["realized_months"].median()),
        })
    return pd.DataFrame(rows)


def fig_distribution(periods: pd.DataFrame, ret_col: str, title: str,
                     outpath: str, linear_xlim: tuple[float, float]) -> None:
    import matplotlib.pyplot as plt

    d = periods[periods["included_in_summary"]].copy()
    r = d[ret_col].dropna()
    months = d.loc[r.index, "realized_months"].clip(lower=1)

    fig, axes = plt.subplots(1, 3, figsize=(16, 4.6))
    lo, hi = linear_xlim
    n_above = int((r > hi).sum())

    ax = axes[0]
    ax.hist(r[(r >= lo) & (r <= hi)], bins=80, color="#2b6cb0",
            edgecolor="white", linewidth=0.3)
    ax.axvline(0, color="red", linestyle="--", linewidth=1)
    ax.set_title(f"{title}\nlinear view, x in [{lo:g}, {hi:g}]")
    ax.set_xlabel("Total return")
    ax.set_ylabel("# holding periods")
    note = [f"N = {len(r):,}", f"% positive = {(r > 0).mean():.1%}"]
    if n_above:
        note.append(f"{n_above:,} above +{hi:g}")
    ax.text(0.98, 0.96, "\n".join(note), transform=ax.transAxes,
            ha="right", va="top", fontsize=9,
            bbox=dict(facecolor="white", edgecolor="#cccccc", alpha=0.9))

    ax = axes[1]
    lr = np.log1p(r.clip(lower=-0.999999))
    ax.hist(lr, bins=80, color="#2b6cb0", edgecolor="white", linewidth=0.3)
    ax.axvline(0, color="red", linestyle="--", linewidth=1)
    ax.set_title(f"{title}\nlog(1+r) view")
    ax.set_xlabel("log(1 + total return)")
    ax.set_ylabel("# holding periods")

    ax = axes[2]
    ann = (1.0 + r.clip(lower=-0.999999)) ** (12.0 / months) - 1.0
    ax.hist(ann.clip(lower=-1.0, upper=1.0), bins=80, color="#2b6cb0",
            edgecolor="white", linewidth=0.3)
    ax.axvline(0, color="red", linestyle="--", linewidth=1)
    ax.set_title(f"{title}\nannualized using realized months")
    ax.set_xlabel("Annualized return")
    ax.set_ylabel("# holding periods")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _p: f"{v*100:.0f}%"))

    fig.tight_layout()
    fig.savefig(outpath, dpi=130)
    plt.close(fig)


def fig_full_life(life: pd.DataFrame, ret_col: str, title: str,
                  outpath: str, linear_xlim: tuple[float, float]) -> None:
    import matplotlib.pyplot as plt

    r = life[ret_col].dropna()
    months = life.loc[r.index, "n_months"].clip(lower=1)

    fig, axes = plt.subplots(1, 3, figsize=(16, 4.6))
    lo, hi = linear_xlim

    ax = axes[0]
    ax.hist(r[(r >= lo) & (r <= hi)], bins=80, color="#2b6cb0",
            edgecolor="white", linewidth=0.3)
    ax.axvline(0, color="red", linestyle="--", linewidth=1)
    ax.set_title(f"{title}\nlinear view, x in [{lo:g}, {hi:g}]")
    ax.set_xlabel("Total return")
    ax.set_ylabel("# stocks")
    ax.text(0.98, 0.96, f"N = {len(r):,}\n% positive = {(r > 0).mean():.1%}",
            transform=ax.transAxes, ha="right", va="top", fontsize=9,
            bbox=dict(facecolor="white", edgecolor="#cccccc", alpha=0.9))

    ax = axes[1]
    lr = np.log1p(r.clip(lower=-0.999999))
    ax.hist(lr, bins=80, color="#2b6cb0", edgecolor="white", linewidth=0.3)
    ax.axvline(0, color="red", linestyle="--", linewidth=1)
    ax.set_title(f"{title}\nlog(1+r) view")
    ax.set_xlabel("log(1 + total return)")
    ax.set_ylabel("# stocks")

    ax = axes[2]
    ann = (1.0 + r.clip(lower=-0.999999)) ** (12.0 / months) - 1.0
    ax.hist(ann.clip(lower=-1.0, upper=1.0), bins=80, color="#2b6cb0",
            edgecolor="white", linewidth=0.3)
    ax.axvline(0, color="red", linestyle="--", linewidth=1)
    ax.set_title(f"{title}\nannualized using listed life")
    ax.set_xlabel("Annualized return")
    ax.set_ylabel("# stocks")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _p: f"{v*100:.0f}%"))

    fig.tight_layout()
    fig.savefig(outpath, dpi=130)
    plt.close(fig)


def remove_obsolete_outputs() -> None:
    obsolete_names = [
        "market_benchmark.csv",
        "market_summary.csv",
        "variation_10y.png",
        "variation_30y.png",
        "pct_positive_10y.png",
        "pct_positive_30y.png",
    ]
    for name in obsolete_names:
        path = os.path.join(RESULTS_DIR, name)
        if os.path.exists(path):
            os.remove(path)
    for name in os.listdir(RESULTS_DIR):
        if name.startswith(("hist_10y_", "hist_30y_")) and "-" in name:
            os.remove(os.path.join(RESULTS_DIR, name))


def main() -> None:
    t0 = time.time()
    remove_obsolete_outputs()
    df, cpi = load_panel()

    period_frames = []
    summary_rows = []
    for years, months in HORIZONS:
        periods = build_holding_periods(df, years, months)
        period_frames.append(periods)
        periods.to_csv(os.path.join(RESULTS_DIR, f"returns_{years}y.csv"), index=False)
        summary_rows.append(summary_to_dict(summarize_periods(periods, "nominal_ret", "nominal")))
        summary_rows.append(summary_to_dict(summarize_periods(periods, "real_ret", "real (CPI-adj)")))

    periods_all = pd.concat(period_frames, ignore_index=True)
    periods_all.to_csv(os.path.join(RESULTS_DIR, "holding_period_audit.csv"), index=False)
    audit = period_audit(periods_all)
    audit.to_csv(os.path.join(RESULTS_DIR, "summary_audit.csv"), index=False)

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(os.path.join(RESULTS_DIR, "summary_holding_periods.csv"), index=False)
    summary[summary["horizon"] == "10y"].to_csv(
        os.path.join(RESULTS_DIR, "summary_10y.csv"), index=False)
    summary[summary["horizon"] == "30y"].to_csv(
        os.path.join(RESULTS_DIR, "summary_30y.csv"), index=False)

    print("\n===== holding-period summaries =====")
    print(summary[[
        "horizon", "basis", "n_periods", "n_permnos", "pct_positive",
        "median", "avg_realized_months", "pct_complete", "pct_delisted",
    ]].to_string(index=False))
    print("\n===== audit =====")
    print(audit.to_string(index=False))

    life = full_life(df)
    life.to_csv(os.path.join(RESULTS_DIR, "permno_fulllife.csv"), index=False)
    life_summary = pd.DataFrame([
        summarize_full_life(life, "fulllife_nominal", "nominal"),
        summarize_full_life(life, "fulllife_real", "real (CPI-adj)"),
    ])
    life_summary.to_csv(os.path.join(RESULTS_DIR, "summary_fulllife.csv"), index=False)

    universe_summary(df, cpi).to_csv(os.path.join(RESULTS_DIR, "universe_summary.csv"), index=False)

    print("\n===== full-life =====")
    print(life_summary[[
        "horizon", "basis", "n_periods", "n_permnos", "pct_positive", "median"
    ]].to_string(index=False))

    print("\n===== charts =====")
    for periods in period_frames:
        horizon = str(periods["horizon"].iloc[0])
        linear_xlim = (-1.0, 5.0) if horizon == "10y" else (-1.0, 20.0)
        fig_distribution(
            periods, "nominal_ret", f"{horizon} stock-anchored holding-period returns (nominal)",
            os.path.join(RESULTS_DIR, f"hist_{horizon}_nominal.png"), linear_xlim)
        fig_distribution(
            periods, "real_ret", f"{horizon} stock-anchored holding-period returns (real)",
            os.path.join(RESULTS_DIR, f"hist_{horizon}_real.png"), linear_xlim)

    fig_full_life(
        life, "fulllife_nominal", "Full-life return per stock (nominal)",
        os.path.join(RESULTS_DIR, "hist_fulllife_nominal.png"), (-1.0, 10.0))
    fig_full_life(
        life, "fulllife_real", "Full-life return per stock (real, CPI-adj)",
        os.path.join(RESULTS_DIR, "hist_fulllife_real.png"), (-1.0, 10.0))

    print(f"[total elapsed] {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
