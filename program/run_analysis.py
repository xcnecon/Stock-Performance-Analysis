"""End-to-end analysis of long-run CRSP stock return distributions.

The project reports two complementary holding-period views:

1. Stock-anchored, non-overlapping 10-year and 30-year periods. Every PERMNO
   starts its own clock at its first observed CRSP month. Delisted stocks remain
   in the sample through their last observed month. Periods that are incomplete
   only because the sample ends are retained in detail files but excluded from
   headline summaries.
2. Calendar start-cohort windows, such as 1925-12 to 1935-12. A stock must be
   present at the start of the window to enter that window; IPOs/listings that
   occur midway through the window are not added halfway. Delisters after the
   start are retained through their last observed month.

Outputs are written to results/.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Iterable

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
    "SecurityEndDt", "SecurityActiveFlg",
    "DelActionType", "DelStatusType", "DelReasonType", "DelPaymentType",
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
    "SecurityEndDt": "string",
    "SecurityActiveFlg": "category",
    "DelActionType": "category",
    "DelStatusType": "category",
    "DelReasonType": "category",
    "DelPaymentType": "category",
}

PCTILES = [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]
HORIZONS = [(10, 120), (30, 360)]
WINDOWS_10Y = [
    (192512, 193512), (193512, 194512), (194512, 195512),
    (195512, 196512), (196512, 197512), (197512, 198512),
    (198512, 199512), (199512, 200512), (200512, 201512),
    (201512, 202512),
]
WINDOWS_30Y = [(192512, 195512), (195512, 198512), (198512, 201512)]

PERIOD_COLS = [
    "YYYYMM", "month_index", "MthRet", "real_ret", "MthRetFlg",
    "SecurityEndDt", "SecurityActiveFlg",
    "DelActionType", "DelStatusType", "DelReasonType", "DelPaymentType",
]


def yyyymm_to_month_index(yyyymm: pd.Series | np.ndarray | int) -> np.ndarray | int:
    values = np.asarray(yyyymm, dtype=np.int64)
    out = (values // 100) * 12 + (values % 100) - 1
    if np.isscalar(yyyymm):
        return int(out)
    return out


def month_index_to_yyyymm(month_index: int) -> int:
    year = month_index // 12
    month = month_index % 12 + 1
    return int(year * 100 + month)


def fmt_window_label(start: int, end: int) -> str:
    return f"{start // 100}-{end // 100}"


def value_or_blank(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value)


def compound_return(values: np.ndarray, empty_value: float = np.nan) -> float:
    values = values[~np.isnan(values)]
    if len(values) == 0:
        return float(empty_value)
    return float(np.prod(1.0 + values) - 1.0)


def terminal_fields(row: pd.Series, prefix: str = "terminal_") -> dict[str, str]:
    return {
        f"{prefix}mthretflg": value_or_blank(row.get("MthRetFlg")),
        f"{prefix}security_end_dt": value_or_blank(row.get("SecurityEndDt")),
        f"{prefix}security_active_flg": value_or_blank(row.get("SecurityActiveFlg")),
        f"{prefix}del_action_type": value_or_blank(row.get("DelActionType")),
        f"{prefix}del_status_type": value_or_blank(row.get("DelStatusType")),
        f"{prefix}del_reason_type": value_or_blank(row.get("DelReasonType")),
        f"{prefix}del_payment_type": value_or_blank(row.get("DelPaymentType")),
    }


def load_panel() -> tuple[pd.DataFrame, pd.DataFrame]:
    t0 = time.time()
    df = pd.read_csv(DATA, usecols=COLS, dtype=DTYPES, low_memory=False)
    print(f"[load] raw rows = {len(df):,}, PERMNOs = {df.PERMNO.nunique():,}")

    universe_mask = (
        (df["SecurityType"] == "EQTY")
        & (df["SecuritySubType"] == "COM")
        & (df["IssuerType"] != "REIT")
    )
    excluded_common_like = df[
        (df["SecurityType"] == "EQTY")
        & (df["SecuritySubType"] != "COM")
        & (df["IssuerType"] != "REIT")
    ]["PERMNO"].nunique()
    df = df[universe_mask].copy()
    subtype_counts = df.groupby("SecuritySubType", observed=True)["PERMNO"].nunique()
    print(
        f"[universe EQTY/COM ex-REIT] rows = {len(df):,}, "
        f"PERMNOs = {df.PERMNO.nunique():,}, "
        f"non-COM EQTY ex-REIT excluded PERMNOs = {excluded_common_like:,}"
    )
    print(f"[universe subtype check] {subtype_counts.to_dict()}")

    before = len(df)
    df = df.drop_duplicates(["PERMNO", "YYYYMM"], keep="first")
    print(f"[dedupe] dropped {before - len(df):,} duplicate rows")

    na_mask = df["MthRet"].isna()
    na_by_flag = df.loc[na_mask, "MthRetFlg"].value_counts(dropna=False).to_dict()
    df["MthRet"] = df["MthRet"].fillna(0.0)
    print(f"[fill-na] MthRet null rows set to 0: {int(na_mask.sum()):,}; by flag {na_by_flag}")

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
    sample_end_idx = int(df["month_index"].max())
    rows: list[dict] = []

    for permno, g in df.groupby("PERMNO", sort=False, observed=True):
        g = g[PERIOD_COLS].sort_values("month_index").reset_index(drop=True)
        month_idx = g["month_index"].to_numpy(dtype=np.int64)
        yyyymm = g["YYYYMM"].to_numpy(dtype=np.int32)
        nominal = g["MthRet"].to_numpy(dtype=np.float64)
        real = g["real_ret"].to_numpy(dtype=np.float64)
        last_idx = int(month_idx[-1])
        stock_terminal = terminal_fields(g.iloc[-1], "stock_terminal_")

        start_pos = 0
        period_n = 1
        while start_pos < len(g):
            start_idx = int(month_idx[start_pos])
            target_end_idx = start_idx + horizon_months - 1
            end_idx = min(target_end_idx, last_idx)
            end_pos = int(np.searchsorted(month_idx, end_idx, side="right"))
            if end_pos <= start_pos:
                break

            if last_idx >= target_end_idx:
                terminal_reason = "complete"
            elif last_idx < sample_end_idx:
                terminal_reason = "delisted"
            else:
                terminal_reason = "sample_end"

            realized_months = int(end_idx - start_idx + 1)
            observed_rows = int(end_pos - start_pos)
            skip_first_start = start_pos + 1 if period_n == 1 else start_pos
            period_end_fields = terminal_fields(g.iloc[end_pos - 1], "period_end_")

            rows.append({
                "analysis": "stock_anchored",
                "horizon": f"{horizon_years}y",
                "horizon_months": horizon_months,
                "window": "",
                "period_number": period_n,
                "PERMNO": int(permno),
                "start_ymm": int(yyyymm[start_pos]),
                "target_end_ymm": month_index_to_yyyymm(target_end_idx),
                "end_ymm": month_index_to_yyyymm(end_idx),
                "realized_months": realized_months,
                "observed_rows": observed_rows,
                "missing_calendar_months": realized_months - observed_rows,
                "is_sparse_history": observed_rows < realized_months,
                "terminal_reason": terminal_reason,
                "included_in_summary": terminal_reason != "sample_end",
                "nominal_ret": compound_return(nominal[start_pos:end_pos]),
                "real_ret": compound_return(real[start_pos:end_pos]),
                "nominal_ret_skip_first_observed": compound_return(
                    nominal[skip_first_start:end_pos], empty_value=0.0),
                "real_ret_skip_first_observed": compound_return(
                    real[skip_first_start:end_pos], empty_value=0.0),
                **period_end_fields,
                **stock_terminal,
            })

            if terminal_reason != "complete":
                break
            start_pos = int(np.searchsorted(month_idx, target_end_idx + 1, side="left"))
            period_n += 1

    out = pd.DataFrame(rows)
    print(
        f"[{horizon_years}y stock periods] rows = {len(out):,}, "
        f"in summary = {int(out.included_in_summary.sum()):,}, "
        f"PERMNOs represented = {out.PERMNO.nunique():,}, "
        f"sparse periods = {int(out.is_sparse_history.sum()):,}"
    )
    return out


def build_calendar_windows(df: pd.DataFrame, windows: Iterable[tuple[int, int]],
                           horizon_years: int) -> pd.DataFrame:
    sample_end_idx = int(df["month_index"].max())
    grouped = {permno: g[PERIOD_COLS].sort_values("month_index").reset_index(drop=True)
               for permno, g in df.groupby("PERMNO", sort=False, observed=True)}
    rows: list[dict] = []

    for start_ymm, end_ymm in windows:
        label = fmt_window_label(start_ymm, end_ymm)
        start_idx = int(yyyymm_to_month_index(start_ymm))
        target_end_idx = int(yyyymm_to_month_index(end_ymm))
        cohort = df.loc[df["YYYYMM"] == start_ymm, "PERMNO"].drop_duplicates().to_numpy()

        for permno in cohort:
            g = grouped[int(permno)]
            month_idx = g["month_index"].to_numpy(dtype=np.int64)
            nominal = g["MthRet"].to_numpy(dtype=np.float64)
            real = g["real_ret"].to_numpy(dtype=np.float64)
            last_idx = int(month_idx[-1])
            stock_terminal = terminal_fields(g.iloc[-1], "stock_terminal_")

            start_pos = int(np.searchsorted(month_idx, start_idx + 1, side="left"))
            end_idx = min(target_end_idx, last_idx)
            end_pos = int(np.searchsorted(month_idx, end_idx, side="right"))

            if last_idx >= target_end_idx:
                terminal_reason = "complete"
            elif last_idx < sample_end_idx:
                terminal_reason = "delisted"
            else:
                terminal_reason = "sample_end"

            realized_months = max(int(end_idx - start_idx), 0)
            observed_rows = max(int(end_pos - start_pos), 0)
            if observed_rows > 0:
                period_end_fields = terminal_fields(g.iloc[end_pos - 1], "period_end_")
            else:
                period_end_fields = terminal_fields(g.iloc[0], "period_end_")

            rows.append({
                "analysis": "calendar_window",
                "horizon": f"{horizon_years}y",
                "horizon_months": target_end_idx - start_idx,
                "window": label,
                "period_number": 1,
                "PERMNO": int(permno),
                "start_ymm": start_ymm,
                "target_end_ymm": end_ymm,
                "end_ymm": month_index_to_yyyymm(end_idx),
                "realized_months": realized_months,
                "observed_rows": observed_rows,
                "missing_calendar_months": realized_months - observed_rows,
                "is_sparse_history": observed_rows < realized_months,
                "terminal_reason": terminal_reason,
                "included_in_summary": terminal_reason != "sample_end",
                "nominal_ret": compound_return(nominal[start_pos:end_pos], empty_value=0.0),
                "real_ret": compound_return(real[start_pos:end_pos], empty_value=0.0),
                "nominal_ret_skip_first_observed": np.nan,
                "real_ret_skip_first_observed": np.nan,
                **period_end_fields,
                **stock_terminal,
            })

    out = pd.DataFrame(rows)
    print(
        f"[{horizon_years}y calendar windows] rows = {len(out):,}, "
        f"PERMNOs represented = {out.PERMNO.nunique():,}, "
        f"sparse periods = {int(out.is_sparse_history.sum()):,}"
    )
    return out


@dataclass
class SummaryRow:
    analysis: str
    horizon: str
    window: str
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
    pct_sample_end: float
    pct_sparse: float
    pct: dict[str, float]


def summarize_subset(d: pd.DataFrame, ret_col: str, basis: str,
                     analysis: str, horizon: str, window: str = "") -> SummaryRow:
    d = d[d["included_in_summary"]].copy()
    r = d[ret_col].dropna()
    reasons = d.loc[r.index, "terminal_reason"].value_counts(normalize=True)
    q = r.quantile(PCTILES).to_dict()
    return SummaryRow(
        analysis=analysis,
        horizon=horizon,
        window=window,
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
        pct_sample_end=float(reasons.get("sample_end", 0.0)),
        pct_sparse=float(d.loc[r.index, "is_sparse_history"].mean()),
        pct={f"p{int(k * 100)}": float(v) for k, v in q.items()},
    )


def summary_to_dict(row: SummaryRow) -> dict:
    out = {
        "analysis": row.analysis,
        "horizon": row.horizon,
        "window": row.window,
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
        "pct_sample_end": row.pct_sample_end,
        "pct_sparse": row.pct_sparse,
    }
    out.update(row.pct)
    return out


def summarize_full_life(life: pd.DataFrame, ret_col: str, basis: str) -> dict:
    r = life[ret_col].dropna()
    q = r.quantile(PCTILES).to_dict()
    row = {
        "analysis": "full_life",
        "horizon": "full-life",
        "window": "",
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
        "pct_sample_end": np.nan,
        "pct_sparse": float(life.loc[r.index, "is_sparse_history"].mean()),
    }
    row.update({f"p{int(k * 100)}": float(v) for k, v in q.items()})
    return row


def full_life(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for permno, g in df.groupby("PERMNO", sort=False, observed=True):
        g = g[PERIOD_COLS].sort_values("month_index").reset_index(drop=True)
        start_idx = int(g["month_index"].iloc[0])
        end_idx = int(g["month_index"].iloc[-1])
        n_months = int(end_idx - start_idx + 1)
        observed_rows = int(len(g))
        rows.append({
            "PERMNO": int(permno),
            "first_ymm": int(g["YYYYMM"].iloc[0]),
            "last_ymm": int(g["YYYYMM"].iloc[-1]),
            "n_months": n_months,
            "observed_rows": observed_rows,
            "missing_calendar_months": n_months - observed_rows,
            "is_sparse_history": observed_rows < n_months,
            "fulllife_nominal": compound_return(g["MthRet"].to_numpy(dtype=np.float64)),
            "fulllife_real": compound_return(g["real_ret"].to_numpy(dtype=np.float64)),
            "fulllife_nominal_skip_first_observed": compound_return(
                g["MthRet"].to_numpy(dtype=np.float64)[1:], empty_value=0.0),
            "fulllife_real_skip_first_observed": compound_return(
                g["real_ret"].to_numpy(dtype=np.float64)[1:], empty_value=0.0),
            **terminal_fields(g.iloc[-1], "stock_terminal_"),
        })
    return pd.DataFrame(rows)


def period_audit(periods: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (analysis, horizon), d in periods.groupby(["analysis", "horizon"], sort=False):
        reasons = d["terminal_reason"].value_counts()
        included = d[d["included_in_summary"]]
        rows.append({
            "analysis": analysis,
            "horizon": horizon,
            "all_started_periods": int(len(d)),
            "all_started_permnos": int(d["PERMNO"].nunique()),
            "included_periods": int(len(included)),
            "included_permnos": int(included["PERMNO"].nunique()),
            "complete_periods": int(reasons.get("complete", 0)),
            "delisted_partial_periods": int(reasons.get("delisted", 0)),
            "sample_end_censored_periods": int(reasons.get("sample_end", 0)),
            "sparse_periods": int(d["is_sparse_history"].sum()),
            "median_realized_months_included": float(included["realized_months"].median()),
        })
    return pd.DataFrame(rows)


def universe_summary(df: pd.DataFrame, cpi: pd.DataFrame) -> pd.DataFrame:
    out = {
        "raw_rows_after_universe_filter": int(len(df)),
        "permnos": int(df["PERMNO"].nunique()),
        "sample_start_ymm": int(df["YYYYMM"].min()),
        "sample_end_ymm": int(df["YYYYMM"].max()),
        "n_months": int(df["YYYYMM"].nunique()),
        "mthret_null_filled_nt": int((df["MthRetFlg"] == "NT").sum()),
        "post_filter_security_subtypes": "; ".join(
            f"{k}: {int(v)}"
            for k, v in df.groupby("SecuritySubType", observed=True)["PERMNO"].nunique().items()
        ),
        "cpi_start_ymm": int(cpi["YYYYMM"].min()),
        "cpi_end_ymm": int(cpi["YYYYMM"].max()),
        "cpi_factor": float(cpi["CPI"].iloc[-1] / cpi["CPI"].iloc[0]),
        "cpi_cagr": float((cpi["CPI"].iloc[-1] / cpi["CPI"].iloc[0]) ** (12 / len(cpi)) - 1),
    }
    return pd.DataFrame([out])


def build_summary(periods: pd.DataFrame, analysis_name: str) -> pd.DataFrame:
    rows = []
    for horizon, d in periods.groupby("horizon", sort=False):
        rows.append(summary_to_dict(summarize_subset(d, "nominal_ret", "nominal", analysis_name, horizon)))
        rows.append(summary_to_dict(summarize_subset(d, "real_ret", "real (CPI-adj)", analysis_name, horizon)))
    return pd.DataFrame(rows)


def build_calendar_summary(periods: pd.DataFrame, analysis_name: str) -> pd.DataFrame:
    rows = []
    for (horizon, window), d in periods.groupby(["horizon", "window"], sort=False):
        rows.append(summary_to_dict(summarize_subset(d, "nominal_ret", "nominal", analysis_name, horizon, window)))
        rows.append(summary_to_dict(summarize_subset(d, "real_ret", "real (CPI-adj)", analysis_name, horizon, window)))
    return pd.DataFrame(rows)


def first_period_summary(periods: pd.DataFrame) -> pd.DataFrame:
    d = periods[periods["period_number"] == 1].copy()
    return build_summary(d, "stock_anchored_first_period")


def first_month_sensitivity(periods: pd.DataFrame, life: pd.DataFrame) -> pd.DataFrame:
    rows = []
    configs = [
        ("include first observed return", "nominal_ret", "real_ret"),
        ("skip first observed return", "nominal_ret_skip_first_observed", "real_ret_skip_first_observed"),
    ]
    for convention, nom_col, real_col in configs:
        for horizon, d in periods.groupby("horizon", sort=False):
            for col, basis in [(nom_col, "nominal"), (real_col, "real (CPI-adj)")]:
                s = summarize_subset(d, col, basis, "first_month_sensitivity", horizon)
                row = summary_to_dict(s)
                row["convention"] = convention
                rows.append(row)

        for col, basis in [
            ("fulllife_nominal" if "include" in convention else "fulllife_nominal_skip_first_observed", "nominal"),
            ("fulllife_real" if "include" in convention else "fulllife_real_skip_first_observed", "real (CPI-adj)"),
        ]:
            r = life[col].dropna()
            q = r.quantile(PCTILES).to_dict()
            row = {
                "analysis": "first_month_sensitivity",
                "horizon": "full-life",
                "window": "",
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
                "pct_sample_end": np.nan,
                "pct_sparse": float(life.loc[r.index, "is_sparse_history"].mean()),
                "convention": convention,
            }
            row.update({f"p{int(k * 100)}": float(v) for k, v in q.items()})
            rows.append(row)
    return pd.DataFrame(rows)


def sparse_history_audit(*frames: pd.DataFrame) -> pd.DataFrame:
    sparse = []
    for frame in frames:
        cols = [
            "analysis", "horizon", "window", "PERMNO", "start_ymm", "end_ymm",
            "realized_months", "observed_rows", "missing_calendar_months",
            "terminal_reason", "included_in_summary",
        ]
        existing_cols = [c for c in cols if c in frame.columns]
        d = frame[frame["is_sparse_history"]][existing_cols].copy()
        sparse.append(d)
    if not sparse:
        return pd.DataFrame()
    return pd.concat(sparse, ignore_index=True)


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


def fig_calendar_pct_positive(summary_df: pd.DataFrame, horizon: str,
                              outpath: str) -> None:
    import matplotlib.pyplot as plt

    d = summary_df[summary_df["horizon"] == horizon].copy()
    windows = d["window"].drop_duplicates().tolist()
    nom = d[d["basis"] == "nominal"].set_index("window").loc[windows, "pct_positive"]
    real = d[d["basis"] == "real (CPI-adj)"].set_index("window").loc[windows, "pct_positive"]

    x = np.arange(len(windows))
    width = 0.36
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(x - width / 2, nom, width, label="Nominal", color="#2b6cb0")
    ax.bar(x + width / 2, real, width, label="Real (CPI-adj)", color="#4fd1c5")
    ax.axhline(0.5, color="#4a5568", linestyle=":", linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels(windows, fontsize=9)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Share positive")
    ax.set_title(f"{horizon} calendar start-cohort windows: share positive")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _p: f"{v*100:.0f}%"))
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(outpath, dpi=130)
    plt.close(fig)


def remove_obsolete_outputs() -> None:
    prefixes = (
        "hist_10y_", "hist_30y_", "calendar_pct_positive_",
    )
    obsolete_names = [
        "market_benchmark.csv", "market_summary.csv",
        "variation_10y.png", "variation_30y.png",
        "pct_positive_10y.png", "pct_positive_30y.png",
    ]
    for name in os.listdir(RESULTS_DIR):
        if name in obsolete_names or (
            name.endswith(".png") and name.startswith(prefixes)
            and name not in {
                "hist_10y_nominal.png", "hist_10y_real.png",
                "hist_30y_nominal.png", "hist_30y_real.png",
            }
        ):
            os.remove(os.path.join(RESULTS_DIR, name))


def main() -> None:
    t0 = time.time()
    remove_obsolete_outputs()
    df, cpi = load_panel()

    stock_frames = []
    for years, months in HORIZONS:
        periods = build_holding_periods(df, years, months)
        stock_frames.append(periods)
        periods.to_csv(os.path.join(RESULTS_DIR, f"returns_{years}y.csv"), index=False)
    stock_periods = pd.concat(stock_frames, ignore_index=True)

    cal10 = build_calendar_windows(df, WINDOWS_10Y, 10)
    cal30 = build_calendar_windows(df, WINDOWS_30Y, 30)
    calendar_periods = pd.concat([cal10, cal30], ignore_index=True)
    cal10.to_csv(os.path.join(RESULTS_DIR, "returns_calendar_10y.csv"), index=False)
    cal30.to_csv(os.path.join(RESULTS_DIR, "returns_calendar_30y.csv"), index=False)

    stock_summary = build_summary(stock_periods, "stock_anchored")
    stock_summary.to_csv(os.path.join(RESULTS_DIR, "summary_holding_periods.csv"), index=False)
    stock_summary[stock_summary["horizon"] == "10y"].to_csv(
        os.path.join(RESULTS_DIR, "summary_10y.csv"), index=False)
    stock_summary[stock_summary["horizon"] == "30y"].to_csv(
        os.path.join(RESULTS_DIR, "summary_30y.csv"), index=False)

    first_period_summary(stock_periods).to_csv(
        os.path.join(RESULTS_DIR, "summary_first_period_by_stock.csv"), index=False)

    calendar_summary = build_calendar_summary(calendar_periods, "calendar_window")
    calendar_summary.to_csv(os.path.join(RESULTS_DIR, "summary_calendar_windows.csv"), index=False)
    calendar_summary[calendar_summary["horizon"] == "10y"].to_csv(
        os.path.join(RESULTS_DIR, "summary_calendar_10y.csv"), index=False)
    calendar_summary[calendar_summary["horizon"] == "30y"].to_csv(
        os.path.join(RESULTS_DIR, "summary_calendar_30y.csv"), index=False)

    all_periods = pd.concat([stock_periods, calendar_periods], ignore_index=True)
    all_periods.to_csv(os.path.join(RESULTS_DIR, "holding_period_audit.csv"), index=False)
    period_audit(all_periods).to_csv(os.path.join(RESULTS_DIR, "summary_audit.csv"), index=False)

    life = full_life(df)
    life.to_csv(os.path.join(RESULTS_DIR, "permno_fulllife.csv"), index=False)
    life_summary = pd.DataFrame([
        summarize_full_life(life, "fulllife_nominal", "nominal"),
        summarize_full_life(life, "fulllife_real", "real (CPI-adj)"),
    ])
    life_summary.to_csv(os.path.join(RESULTS_DIR, "summary_fulllife.csv"), index=False)

    first_month_sensitivity(stock_periods, life).to_csv(
        os.path.join(RESULTS_DIR, "summary_first_month_sensitivity.csv"), index=False)
    sparse_history_audit(stock_periods, calendar_periods).to_csv(
        os.path.join(RESULTS_DIR, "sparse_history_audit.csv"), index=False)
    universe_summary(df, cpi).to_csv(os.path.join(RESULTS_DIR, "universe_summary.csv"), index=False)

    print("\n===== stock-anchored summaries =====")
    print(stock_summary[[
        "horizon", "basis", "n_periods", "n_permnos", "pct_positive",
        "median", "avg_realized_months", "pct_complete", "pct_delisted", "pct_sparse",
    ]].to_string(index=False))
    print("\n===== calendar-window summaries =====")
    print(calendar_summary[[
        "horizon", "window", "basis", "n_periods", "pct_positive", "median",
    ]].to_string(index=False))
    print("\n===== full-life =====")
    print(life_summary[["horizon", "basis", "n_permnos", "pct_positive", "median"]].to_string(index=False))

    print("\n===== charts =====")
    for periods in stock_frames:
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
    fig_calendar_pct_positive(
        calendar_summary, "10y", os.path.join(RESULTS_DIR, "calendar_pct_positive_10y.png"))
    fig_calendar_pct_positive(
        calendar_summary, "30y", os.path.join(RESULTS_DIR, "calendar_pct_positive_30y.png"))

    print(f"[total elapsed] {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
