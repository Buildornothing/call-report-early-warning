#!/usr/bin/env python3
"""Preliminary Call Report early-warning analysis.

This script constructs a historical 2022Q4 peer sample of FDIC-insured banks
with $10-$250 billion in assets and evaluates transparent risk indicators
against bank failures observed in 2023. It is an exploratory research prototype,
not a production model or a prediction of any institution's condition.

Data sources
------------
* FDIC BankFind Suite Financials API (Call Report-derived quarterly data)
* FDIC BankFind Suite Failures API (historical failure outcomes)
* Federal Reserve Bank of St. Louis FRED CSV service (DFF and DGS10)

Run
---
    python analysis.py --offline   # use the cached source files in data/raw
    python analysis.py             # refresh public source data, then analyze
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
FIGURE_DIR = ROOT / "results" / "figures"
RESULTS_DIR = ROOT / "results"

FDIC_API = "https://api.fdic.gov/banks"
FINANCIAL_FIELDS = [
    "CERT",
    "REPDTE",
    "NAME",
    "ASSET",
    "DEP",
    "EQ",
    "CHBAL",
    "SC",
    "SCMV",
    "DEPUNINS",
    "LNLSGR",
    "NALNLS",
    "P3LNLS",
    "P9LNLS",
]

# All financial values in the FDIC extract are reported in thousands of dollars.
SAMPLE_FILTER = "REPDTE:20221231 AND ASSET:[10000000 TO 250000000]"
ASSET_MIN_THOUSANDS = 10_000_000
ASSET_MAX_THOUSANDS = 250_000_000
STRESSED_SURVIVORS_2023 = {
    "PACIFIC WESTERN BANK",
    "WESTERN ALLIANCE BANK",
    "COMERICA BANK",
    "ZIONS BCORP N A",
    "KEYBANK NATIONAL ASSN",
}

# Hypothesis-driven starting weights. They are tested for sensitivity below and
# must be validated on additional periods before being treated as calibrated.
WEIGHT_SCENARIOS: dict[str, dict[str, float]] = {
    "Base interaction-aware": {
        "rate": 0.30,
        "funding": 0.30,
        "credit": 0.15,
        "capital": 0.10,
        "interaction": 0.15,
    },
    "Equal dimensions": {
        "rate": 0.225,
        "funding": 0.225,
        "credit": 0.225,
        "capital": 0.10,
        "interaction": 0.225,
    },
    "Rate dominant": {
        "rate": 0.40,
        "funding": 0.20,
        "credit": 0.10,
        "capital": 0.10,
        "interaction": 0.20,
    },
    "Funding dominant": {
        "rate": 0.20,
        "funding": 0.40,
        "credit": 0.10,
        "capital": 0.10,
        "interaction": 0.20,
    },
    "Credit dominant": {
        "rate": 0.20,
        "funding": 0.20,
        "credit": 0.35,
        "capital": 0.10,
        "interaction": 0.15,
    },
}


def ensure_directories() -> None:
    for directory in (RAW_DIR, PROCESSED_DIR, FIGURE_DIR, RESULTS_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def fetch_bytes(url: str, attempts: int = 3) -> bytes:
    request = Request(url, headers={"User-Agent": "NIW-call-report-research/0.1"})
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urlopen(request, timeout=60) as response:
                return response.read()
        except Exception as exc:  # pragma: no cover - depends on network
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(2**attempt)
    raise RuntimeError(f"Unable to retrieve {url}") from last_error


def fetch_json(endpoint: str, params: dict[str, Any], path: Path) -> dict[str, Any]:
    url = f"{FDIC_API}/{endpoint}?{urlencode(params)}"
    payload = json.loads(fetch_bytes(url).decode("utf-8"))
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def fetch_csv(url: str, path: Path) -> None:
    path.write_bytes(fetch_bytes(url))


def refresh_sources() -> None:
    fetch_json(
        "financials",
        {
            "filters": SAMPLE_FILTER,
            "fields": ",".join(FINANCIAL_FIELDS),
            "sort_by": "ASSET",
            "sort_order": "DESC",
            "limit": 10000,
            "format": "json",
        },
        RAW_DIR / "fdic_financials_2022q4.json",
    )
    fetch_json(
        "failures",
        {
            "filters": 'FAILYR:["2023" TO "2023"]',
            "fields": "NAME,CERT,CITYST,FAILDATE,QBFASSET,QBFDEP,RESTYPE1",
            "sort_by": "FAILDATE",
            "sort_order": "ASC",
            "limit": 100,
            "format": "json",
        },
        RAW_DIR / "fdic_failures_2023.json",
    )
    fetch_csv(
        "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFF&cosd=2021-01-01&coed=2023-12-31",
        RAW_DIR / "fred_dff.csv",
    )
    fetch_csv(
        "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10&cosd=2021-01-01&coed=2023-12-31",
        RAW_DIR / "fred_dgs10.csv",
    )


def read_fdic_records(path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = [item["data"] for item in payload.get("data", [])]
    return pd.DataFrame(records), payload.get("meta", {})


def safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    result = numerator.astype(float) / denominator.astype(float).replace(0, np.nan)
    return result.replace([np.inf, -np.inf], np.nan)


def risk_percentile(series: pd.Series, higher_is_worse: bool = True) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    ranked = numeric.rank(method="average", pct=True, ascending=higher_is_worse)
    if not higher_is_worse:
        ranked = numeric.rank(method="average", pct=True, ascending=False)
    return ranked


def load_macro_context() -> pd.DataFrame:
    dff = pd.read_csv(RAW_DIR / "fred_dff.csv", parse_dates=["observation_date"])
    dgs10 = pd.read_csv(RAW_DIR / "fred_dgs10.csv", parse_dates=["observation_date"])
    dff["DFF"] = pd.to_numeric(dff["DFF"], errors="coerce")
    dgs10["DGS10"] = pd.to_numeric(dgs10["DGS10"], errors="coerce")
    merged = dff.merge(dgs10, on="observation_date", how="outer").sort_values("observation_date")
    merged["quarter"] = merged["observation_date"].dt.to_period("Q").astype(str)
    quarterly = (
        merged.groupby("quarter", as_index=False)
        .agg(effective_fed_funds_rate=("DFF", "mean"), ten_year_treasury_yield=("DGS10", "mean"))
        .round(3)
    )
    quarterly["fed_funds_change_from_2021q4_pp"] = (
        quarterly["effective_fed_funds_rate"]
        - quarterly.loc[quarterly["quarter"] == "2021Q4", "effective_fed_funds_rate"].iloc[0]
    ).round(3)
    return quarterly


def prepare_peer_metrics(financials: pd.DataFrame, failure_records: pd.DataFrame) -> pd.DataFrame:
    df = financials.copy()
    numeric_fields = [field for field in FINANCIAL_FIELDS if field not in {"NAME", "REPDTE"}]
    for column in numeric_fields:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    # The FDIC API response may include observations outside the requested
    # numeric range. Enforce the stated sample locally before calculating any
    # peer percentiles, component scores, composite scores, or ranks.
    df = df.loc[
        df["ASSET"].between(ASSET_MIN_THOUSANDS, ASSET_MAX_THOUSANDS, inclusive="both")
    ].copy()
    if df.empty:
        raise ValueError("The locally enforced $10bn-$250bn asset filter produced no observations.")

    df["report_date"] = pd.to_datetime(df["REPDTE"], format="%Y%m%d")
    df["assets_billions"] = df["ASSET"] / 1_000_000
    df["capital_ratio"] = safe_divide(df["EQ"], df["ASSET"])
    df["cash_ratio"] = safe_divide(df["CHBAL"], df["ASSET"])
    df["securities_ratio"] = safe_divide(df["SC"], df["ASSET"])
    df["uninsured_deposit_ratio"] = safe_divide(df["DEPUNINS"], df["DEP"])
    df["securities_mtm_gap_to_equity"] = safe_divide((df["SC"] - df["SCMV"]).clip(lower=0), df["EQ"])
    df["noncurrent_loan_ratio"] = safe_divide(df["NALNLS"] + df["P9LNLS"], df["LNLSGR"])
    df["early_delinquency_ratio"] = safe_divide(df["P3LNLS"], df["LNLSGR"])
    df["liquid_asset_coverage"] = safe_divide(df["CHBAL"] + df["SCMV"], df["DEPUNINS"])

    # Component scores are cross-sectional percentile ranks on a 0-1 scale.
    df["rate_securities_pct"] = risk_percentile(df["securities_ratio"], True)
    df["rate_mtm_gap_pct"] = risk_percentile(df["securities_mtm_gap_to_equity"], True)
    df["funding_uninsured_pct"] = risk_percentile(df["uninsured_deposit_ratio"], True)
    df["funding_low_cash_pct"] = risk_percentile(df["cash_ratio"], False)
    df["credit_noncurrent_pct"] = risk_percentile(df["noncurrent_loan_ratio"], True)
    df["credit_early_dq_pct"] = risk_percentile(df["early_delinquency_ratio"], True)
    df["capital_low_buffer_pct"] = risk_percentile(df["capital_ratio"], False)

    df["rate_score"] = df[["rate_securities_pct", "rate_mtm_gap_pct"]].mean(axis=1)
    df["funding_score"] = df[["funding_uninsured_pct", "funding_low_cash_pct"]].mean(axis=1)
    df["credit_score"] = df[["credit_noncurrent_pct", "credit_early_dq_pct"]].mean(axis=1)
    df["capital_score"] = df["capital_low_buffer_pct"]
    df["rate_funding_interaction"] = np.sqrt(df["rate_score"] * df["funding_score"])
    df["dominant_risk_trigger"] = np.maximum(df["rate_mtm_gap_pct"], df["funding_uninsured_pct"])

    failed_certs = set(pd.to_numeric(failure_records["CERT"], errors="coerce").dropna().astype(int))
    df["failed_in_2023"] = df["CERT"].astype(int).isin(failed_certs)
    df["stressed_survivor_2023"] = df["NAME"].isin(STRESSED_SURVIVORS_2023) & ~df["failed_in_2023"]
    df["outcome_group"] = np.select(
        [df["failed_in_2023"], df["stressed_survivor_2023"]],
        ["Failed in 2023", "Stressed survivor in 2023"],
        default="Other peer",
    )
    failure_dates = {
        int(cert): date
        for cert, date in zip(
            pd.to_numeric(failure_records["CERT"], errors="coerce"), failure_records["FAILDATE"], strict=False
        )
        if not pd.isna(cert)
    }
    df["failure_date"] = df["CERT"].astype(int).map(failure_dates)

    for scenario, weights in WEIGHT_SCENARIOS.items():
        label = scenario.lower().replace(" ", "_").replace("-", "_")
        df[f"score_{label}"] = 100 * (
            weights["rate"] * df["rate_score"]
            + weights["funding"] * df["funding_score"]
            + weights["credit"] * df["credit_score"]
            + weights["capital"] * df["capital_score"]
            + weights["interaction"] * df["rate_funding_interaction"]
        )
        df[f"rank_{label}"] = df[f"score_{label}"].rank(method="min", ascending=False).astype("Int64")

    # Diagnostic refinement: preserve a dominant funding or valuation signal so
    # that a low contemporaneous credit score cannot average it away. Because
    # this specification was informed by the 2023 episode, it is explicitly an
    # in-sample hypothesis until tested on earlier and later stress periods.
    df["baseline_average_score"] = df["score_base_interaction_aware"]
    df["trigger_augmented_score"] = 100 * (
        0.15 * df["rate_score"]
        + 0.25 * df["funding_score"]
        + 0.05 * df["credit_score"]
        + 0.05 * df["capital_score"]
        + 0.20 * df["rate_funding_interaction"]
        + 0.30 * df["dominant_risk_trigger"]
    )
    df["baseline_average_rank"] = df["baseline_average_score"].rank(method="min", ascending=False).astype("Int64")
    df["trigger_augmented_rank"] = df["trigger_augmented_score"].rank(method="min", ascending=False).astype("Int64")
    df["integrated_score"] = df["trigger_augmented_score"]
    df["integrated_rank"] = df["trigger_augmented_rank"]
    df["integrated_percentile"] = df["integrated_score"].rank(pct=True) * 100
    df["top_decile_integrated"] = df["integrated_rank"] <= math.ceil(len(df) * 0.10)
    return df.sort_values("integrated_rank")


def top_decile_capture(df: pd.DataFrame) -> pd.DataFrame:
    cutoff = math.ceil(len(df) * 0.10)
    signals = {
        "Trigger-augmented interaction score": ("trigger_augmented_score", False),
        "Baseline weighted-average score": ("baseline_average_score", False),
        "Securities / assets": ("securities_ratio", False),
        "Securities MTM gap / equity": ("securities_mtm_gap_to_equity", False),
        "Uninsured deposits / deposits": ("uninsured_deposit_ratio", False),
        "Cash / assets": ("cash_ratio", True),
        "Noncurrent loans / loans": ("noncurrent_loan_ratio", False),
        "Capital / assets": ("capital_ratio", True),
    }
    failure_total = int(df["failed_in_2023"].sum())
    rows: list[dict[str, Any]] = []
    for signal, (column, ascending) in signals.items():
        ranked = df.sort_values(column, ascending=ascending, na_position="last").head(cutoff)
        captured = int(ranked["failed_in_2023"].sum())
        rows.append(
            {
                "signal": signal,
                "top_decile_bank_count": cutoff,
                "2023_failures_in_sample": failure_total,
                "failures_captured": captured,
                "capture_rate": captured / failure_total if failure_total else np.nan,
                "false_positives": cutoff - captured,
                "precision_in_top_decile": captured / cutoff if cutoff else np.nan,
                "false_positive_share_among_flags": (cutoff - captured) / cutoff if cutoff else np.nan,
            }
        )
    return pd.DataFrame(rows).sort_values(["failures_captured", "signal"], ascending=[False, True])


def failed_bank_profiles(df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "NAME",
        "CERT",
        "failure_date",
        "assets_billions",
        "capital_ratio",
        "cash_ratio",
        "securities_ratio",
        "securities_mtm_gap_to_equity",
        "uninsured_deposit_ratio",
        "noncurrent_loan_ratio",
        "rate_score",
        "funding_score",
        "credit_score",
        "rate_funding_interaction",
        "dominant_risk_trigger",
        "baseline_average_score",
        "baseline_average_rank",
        "trigger_augmented_score",
        "trigger_augmented_rank",
        "integrated_score",
        "integrated_rank",
        "top_decile_integrated",
    ]
    return df.loc[df["failed_in_2023"], columns].sort_values("integrated_rank")


def stressed_survivor_profiles(df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "NAME",
        "CERT",
        "assets_billions",
        "uninsured_deposit_ratio",
        "securities_mtm_gap_to_equity",
        "baseline_average_score",
        "baseline_average_rank",
        "trigger_augmented_score",
        "trigger_augmented_rank",
        "top_decile_integrated",
    ]
    return df.loc[df["stressed_survivor_2023"], columns].sort_values("trigger_augmented_rank")


def peer_summary(df: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "capital_ratio",
        "cash_ratio",
        "securities_ratio",
        "securities_mtm_gap_to_equity",
        "uninsured_deposit_ratio",
        "noncurrent_loan_ratio",
        "early_delinquency_ratio",
        "integrated_score",
    ]
    rows: list[dict[str, Any]] = []
    for metric in metrics:
        for cohort_name, cohort in (("2023 failed banks", df[df["failed_in_2023"]]), ("Other peers", df[~df["failed_in_2023"]])):
            rows.append(
                {
                    "metric": metric,
                    "cohort": cohort_name,
                    "count": int(cohort[metric].notna().sum()),
                    "median": cohort[metric].median(),
                    "mean": cohort[metric].mean(),
                    "p25": cohort[metric].quantile(0.25),
                    "p75": cohort[metric].quantile(0.75),
                }
            )
    return pd.DataFrame(rows)


def weight_sensitivity(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    cutoff = math.ceil(len(df) * 0.10)
    for scenario in WEIGHT_SCENARIOS:
        label = scenario.lower().replace(" ", "_").replace("-", "_")
        for _, bank in df.loc[df["failed_in_2023"]].iterrows():
            rank = int(bank[f"rank_{label}"])
            rows.append(
                {
                    "scenario": scenario,
                    "bank": bank["NAME"],
                    "rank": rank,
                    "top_decile": rank <= cutoff,
                    "score": bank[f"score_{label}"],
                }
            )
    return pd.DataFrame(rows)


def build_summary(
    df: pd.DataFrame,
    failures: pd.DataFrame,
    capture: pd.DataFrame,
    macro: pd.DataFrame,
    financial_meta: dict[str, Any],
) -> dict[str, Any]:
    failed = df[df["failed_in_2023"]].copy()
    stressed = df[df["stressed_survivor_2023"]].copy()
    q4_2022 = macro.loc[macro["quarter"] == "2022Q4"].iloc[0]
    return {
        "analysis_status": "exploratory_prototype_not_a_validated_prediction_model",
        "sample_report_date": "2022-12-31",
        "asset_band_billions": [10, 250],
        "peer_bank_count": int(len(df)),
        "all_2023_fdic_failures": int(len(failures)),
        "2023_failures_in_asset_band": int(df["failed_in_2023"].sum()),
        "top_decile_cutoff": int(math.ceil(len(df) * 0.10)),
        "integrated_top_decile_failures_captured": int(
            capture.loc[capture["signal"] == "Trigger-augmented interaction score", "failures_captured"].iloc[0]
        ),
        "integrated_top_decile_false_positives": int(
            capture.loc[capture["signal"] == "Trigger-augmented interaction score", "false_positives"].iloc[0]
        ),
        "integrated_top_decile_precision": float(
            capture.loc[capture["signal"] == "Trigger-augmented interaction score", "precision_in_top_decile"].iloc[0]
        ),
        "baseline_top_decile_failures_captured": int(
            capture.loc[capture["signal"] == "Baseline weighted-average score", "failures_captured"].iloc[0]
        ),
        "failed_bank_integrated_ranks": {
            row["NAME"]: int(row["integrated_rank"]) for _, row in failed.iterrows()
        },
        "stressed_survivor_integrated_ranks": {
            row["NAME"]: int(row["integrated_rank"]) for _, row in stressed.iterrows()
        },
        "median_integrated_score_failed": round(float(failed["integrated_score"].median()), 2),
        "median_integrated_score_other_peers": round(
            float(df.loc[~df["failed_in_2023"], "integrated_score"].median()), 2
        ),
        "2022q4_effective_fed_funds_average": float(q4_2022["effective_fed_funds_rate"]),
        "2022q4_ten_year_treasury_average": float(q4_2022["ten_year_treasury_yield"]),
        "fdic_api_reported_total": int(financial_meta.get("total", len(df))),
        "limitations": [
            "Only one pre-failure cross-section and three failures in the selected asset band are evaluated.",
            "Weights are transparent hypotheses, not statistically estimated coefficients.",
            "The dominant-risk trigger was specified after diagnostic review of the 2023 episode and is not out-of-sample evidence.",
            "Securities market-value gap is a proxy and is not a full economic-value-of-equity or duration model.",
            "Public Call Report fields do not capture deposit speed, intraday liquidity, or every off-balance-sheet exposure.",
            "Top-decile capture is descriptive and does not establish causation or out-of-sample predictive accuracy.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Use cached raw source files without downloading.")
    args = parser.parse_args()
    ensure_directories()
    if not args.offline:
        refresh_sources()

    financials, financial_meta = read_fdic_records(RAW_DIR / "fdic_financials_2022q4.json")
    failures, _ = read_fdic_records(RAW_DIR / "fdic_failures_2023.json")
    macro = load_macro_context()
    peers = prepare_peer_metrics(financials, failures)
    capture = top_decile_capture(peers)
    profiles = failed_bank_profiles(peers)
    stressed_profiles = stressed_survivor_profiles(peers)
    summary_table = peer_summary(peers)
    sensitivity = weight_sensitivity(peers)
    summary = build_summary(peers, failures, capture, macro, financial_meta)

    # Keep a research-ready analytical file and smaller evidence tables.
    peers.to_csv(PROCESSED_DIR / "peer_metrics_2022q4.csv", index=False)
    capture.to_csv(PROCESSED_DIR / "top_decile_capture.csv", index=False)
    profiles.to_csv(PROCESSED_DIR / "failed_bank_profiles.csv", index=False)
    stressed_profiles.to_csv(PROCESSED_DIR / "stressed_survivor_profiles.csv", index=False)
    summary_table.to_csv(PROCESSED_DIR / "cohort_summary.csv", index=False)
    sensitivity.to_csv(PROCESSED_DIR / "weight_sensitivity.csv", index=False)
    macro.to_csv(PROCESSED_DIR / "macro_context_quarterly.csv", index=False)
    (RESULTS_DIR / "analysis_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
