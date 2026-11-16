#!/usr/bin/env python3
"""Publish the frozen v1.0.1 model's 2026Q3 prospective baseline scores.

The script reads only public, cached FFIEC and FDIC files distributed with this
release. It does not tune any indicator, percentile rule, weight, interaction
term, or trigger. The 2026Q3 scores are baseline measurements; the prespecified
eight-quarter outcome window remains open through 2028Q3.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
RESULTS_DIR = ROOT / "results"

Q3_ZIP = RAW_DIR / "ffiec_call_report_2026q3.zip"
Q2_ZIP = RAW_DIR / "ffiec_call_report_2026q2_validation.zip"
Q2_FDIC = RAW_DIR / "fdic_financials_2026q2_validation.json"

ASSET_MIN_THOUSANDS = 10_000_000
ASSET_MAX_THOUSANDS = 250_000_000
BASELINE_DATE = "2026-09-30"
OUTCOME_WINDOW_END = "2028-09-30"
FFIEC_SNAPSHOT_DATE = "2026-11-14"

RAW_FIELDS = [
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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_tsv(
    archive: zipfile.ZipFile,
    member: str,
    *,
    schedule: bool = True,
) -> pd.DataFrame:
    with archive.open(member) as raw:
        text = io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace")
        return pd.read_csv(
            text,
            sep="\t",
            skiprows=[1] if schedule else None,
            dtype=str,
            low_memory=False,
        )


def numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column].replace({"CONF": np.nan}), errors="coerce")


def coalesce(frame: pd.DataFrame, consolidated: str, domestic: str) -> pd.Series:
    return numeric(frame, consolidated).combine_first(numeric(frame, domestic))


def merge_schedule(
    left: pd.DataFrame,
    right: pd.DataFrame,
    columns: list[str],
) -> pd.DataFrame:
    keep = ["IDRSSD", *[column for column in columns if column in right.columns]]
    return left.merge(right[keep], on="IDRSSD", how="left", validate="one_to_one")


def load_call_report(archive_path: Path, date_token: str) -> pd.DataFrame:
    prefix = "FFIEC CDR Call"
    with zipfile.ZipFile(archive_path) as archive:
        por = read_tsv(
            archive,
            f"{prefix} Bulk POR {date_token}.txt",
            schedule=False,
        )
        por.columns = [column.strip('"') for column in por.columns]
        por["IDRSSD"] = pd.to_numeric(por["IDRSSD"], errors="coerce")
        por["CERT"] = pd.to_numeric(por["FDIC Certificate Number"], errors="coerce")
        raw = por[
            [
                "IDRSSD",
                "CERT",
                "Financial Institution Name",
                "Financial Institution State",
                "Financial Institution Filing Type",
                "Last Date/Time Submission Updated On",
            ]
        ].copy()

        rc = read_tsv(archive, f"{prefix} Schedule RC {date_token}.txt")
        rc["IDRSSD"] = pd.to_numeric(rc["IDRSSD"], errors="coerce")
        raw = merge_schedule(
            raw,
            rc,
            [
                "RCFD2170",
                "RCON2170",
                "RCFD3210",
                "RCON3210",
                "RCON2200",
                "RCFN2200",
                "RCFD1773",
                "RCON1773",
                "RCFDJA22",
                "RCONJA22",
                "RCFDJJ34",
                "RCONJJ34",
                "RCFD0071",
                "RCON0071",
                "RCFD0081",
                "RCON0081",
                "RCFDB528",
                "RCONB528",
                "RCFD5369",
                "RCON5369",
            ],
        )

        rcb = read_tsv(archive, f"{prefix} Schedule RCB {date_token}(1 of 2).txt")
        rcb["IDRSSD"] = pd.to_numeric(rcb["IDRSSD"], errors="coerce")
        raw = merge_schedule(raw, rcb, ["RCFD1771", "RCON1771"])

        rcn = read_tsv(archive, f"{prefix} Schedule RCN {date_token}.txt")
        rcn["IDRSSD"] = pd.to_numeric(rcn["IDRSSD"], errors="coerce")
        raw = merge_schedule(
            raw,
            rcn,
            [
                "RCFD1403",
                "RCON1403",
                "RCFD1406",
                "RCON1406",
                "RCFD1407",
                "RCON1407",
            ],
        )

        rco = read_tsv(archive, f"{prefix} Schedule RCO {date_token}(1 of 2).txt")
        rco["IDRSSD"] = pd.to_numeric(rco["IDRSSD"], errors="coerce")
        raw = merge_schedule(raw, rco, ["RCON5597"])

    call_report = pd.DataFrame(
        {
            "IDRSSD": raw["IDRSSD"],
            "CERT": raw["CERT"],
            "NAME": raw["Financial Institution Name"].str.strip(),
            "STATE": raw["Financial Institution State"].str.strip(),
            "FILING_TYPE": raw["Financial Institution Filing Type"].str.strip(),
            "SUBMISSION_UPDATED": raw["Last Date/Time Submission Updated On"].str.strip(),
            "ASSET": coalesce(raw, "RCFD2170", "RCON2170"),
            "DEP": numeric(raw, "RCON2200").fillna(0)
            + numeric(raw, "RCFN2200").fillna(0),
            "EQ": coalesce(raw, "RCFD3210", "RCON3210"),
            "CHBAL": coalesce(raw, "RCFD0071", "RCON0071").fillna(0)
            + coalesce(raw, "RCFD0081", "RCON0081").fillna(0),
            "SC": coalesce(raw, "RCFDJJ34", "RCONJJ34").fillna(0)
            + coalesce(raw, "RCFD1773", "RCON1773").fillna(0)
            + coalesce(raw, "RCFDJA22", "RCONJA22").fillna(0),
            "SCMV": coalesce(raw, "RCFD1771", "RCON1771").fillna(0)
            + coalesce(raw, "RCFD1773", "RCON1773").fillna(0),
            "DEPUNINS": numeric(raw, "RCON5597"),
            "LNLSGR": coalesce(raw, "RCFDB528", "RCONB528").fillna(0)
            + coalesce(raw, "RCFD5369", "RCON5369").fillna(0),
            "NALNLS": coalesce(raw, "RCFD1403", "RCON1403"),
            "P3LNLS": coalesce(raw, "RCFD1406", "RCON1406"),
            "P9LNLS": coalesce(raw, "RCFD1407", "RCON1407"),
        }
    )
    return call_report


def safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    result = numerator.astype(float) / denominator.astype(float).replace(0, np.nan)
    return result.replace([np.inf, -np.inf], np.nan)


def risk_percentile(series: pd.Series, higher_is_worse: bool = True) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    return values.rank(method="average", pct=True, ascending=higher_is_worse)


def build_prospective_scores(call_report: pd.DataFrame) -> pd.DataFrame:
    frame = call_report.loc[
        call_report["ASSET"].between(
            ASSET_MIN_THOUSANDS,
            ASSET_MAX_THOUSANDS,
            inclusive="both",
        )
    ].copy()
    if frame.empty:
        raise ValueError("The $10bn-$250bn Call Report population is empty.")

    frame["REPDTE"] = "20260930"
    frame["assets_billions"] = frame["ASSET"] / 1_000_000
    frame["capital_ratio"] = safe_divide(frame["EQ"], frame["ASSET"])
    frame["cash_ratio"] = safe_divide(frame["CHBAL"], frame["ASSET"])
    frame["securities_ratio"] = safe_divide(frame["SC"], frame["ASSET"])
    frame["uninsured_deposit_ratio"] = safe_divide(frame["DEPUNINS"], frame["DEP"])
    frame["securities_mtm_gap_to_equity"] = safe_divide(
        (frame["SC"] - frame["SCMV"]).clip(lower=0),
        frame["EQ"],
    )
    frame["noncurrent_loan_ratio"] = safe_divide(
        frame["NALNLS"] + frame["P9LNLS"],
        frame["LNLSGR"],
    )
    frame["early_delinquency_ratio"] = safe_divide(
        frame["P3LNLS"],
        frame["LNLSGR"],
    )
    frame["liquid_asset_coverage"] = safe_divide(
        frame["CHBAL"] + frame["SCMV"],
        frame["DEPUNINS"],
    )

    frame["rate_securities_pct"] = risk_percentile(frame["securities_ratio"], True)
    frame["rate_mtm_gap_pct"] = risk_percentile(
        frame["securities_mtm_gap_to_equity"], True
    )
    frame["funding_uninsured_pct"] = risk_percentile(
        frame["uninsured_deposit_ratio"], True
    )
    frame["funding_low_cash_pct"] = risk_percentile(frame["cash_ratio"], False)
    frame["credit_noncurrent_pct"] = risk_percentile(
        frame["noncurrent_loan_ratio"], True
    )
    frame["credit_early_dq_pct"] = risk_percentile(
        frame["early_delinquency_ratio"], True
    )
    frame["capital_low_buffer_pct"] = risk_percentile(frame["capital_ratio"], False)

    frame["rate_score"] = frame[
        ["rate_securities_pct", "rate_mtm_gap_pct"]
    ].mean(axis=1)
    frame["funding_score"] = frame[
        ["funding_uninsured_pct", "funding_low_cash_pct"]
    ].mean(axis=1)
    frame["credit_score"] = frame[
        ["credit_noncurrent_pct", "credit_early_dq_pct"]
    ].mean(axis=1)
    frame["capital_score"] = frame["capital_low_buffer_pct"]
    frame["rate_funding_interaction"] = np.sqrt(
        frame["rate_score"] * frame["funding_score"]
    )
    frame["dominant_risk_trigger"] = np.maximum(
        frame["rate_mtm_gap_pct"], frame["funding_uninsured_pct"]
    )

    # Frozen v1.0.1 specification. Do not retune during the outcome window.
    frame["integrated_score"] = 100 * (
        0.15 * frame["rate_score"]
        + 0.25 * frame["funding_score"]
        + 0.05 * frame["credit_score"]
        + 0.05 * frame["capital_score"]
        + 0.20 * frame["rate_funding_interaction"]
        + 0.30 * frame["dominant_risk_trigger"]
    )
    frame["integrated_rank"] = frame["integrated_score"].rank(
        method="min", ascending=False
    ).astype("Int64")
    frame["integrated_percentile"] = (
        frame["integrated_score"].rank(pct=True) * 100
    )
    top_decile_cutoff = math.ceil(len(frame) * 0.10)
    frame["top_decile_integrated"] = (
        frame["integrated_rank"] <= top_decile_cutoff
    )
    frame["score_status"] = np.select(
        [
            frame["integrated_score"].notna(),
            frame["LNLSGR"].fillna(0).le(0),
        ],
        [
            "Scored",
            "Not scored - no loan denominator for frozen credit ratios",
        ],
        default="Not scored - incomplete required ratio",
    )
    frame["prospective_test_status"] = (
        "Baseline published; outcomes not evaluated; window open through 2028Q3"
    )
    return frame.sort_values(
        ["integrated_rank", "ASSET"],
        ascending=[True, False],
        na_position="last",
    )


def validate_q2_mapping() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    call_report = load_call_report(Q2_ZIP, "06302026")
    call_report = call_report.loc[
        call_report["ASSET"].between(
            ASSET_MIN_THOUSANDS,
            ASSET_MAX_THOUSANDS,
            inclusive="both",
        )
    ].copy()

    with Q2_FDIC.open(encoding="utf-8") as handle:
        fdic_payload = json.load(handle)
    fdic = pd.DataFrame([record["data"] for record in fdic_payload["data"]])
    for column in ["CERT", *RAW_FIELDS]:
        fdic[column] = pd.to_numeric(fdic[column], errors="coerce")

    joined = fdic[["CERT", "NAME", *RAW_FIELDS]].merge(
        call_report[
            ["CERT", "SUBMISSION_UPDATED", *RAW_FIELDS]
        ],
        on="CERT",
        how="left",
        suffixes=("_FDIC", "_FFIEC"),
        validate="one_to_one",
    )

    summaries: list[dict[str, object]] = []
    discrepancies: list[dict[str, object]] = []
    for field in RAW_FIELDS:
        api_values = joined[f"{field}_FDIC"]
        call_values = joined[f"{field}_FFIEC"]
        comparable = api_values.notna() & call_values.notna()
        differences = call_values - api_values
        mismatch = comparable & differences.ne(0)
        summaries.append(
            {
                "field": field,
                "records_compared": int(comparable.sum()),
                "exact_matches": int((comparable & differences.eq(0)).sum()),
                "mismatch_count": int(mismatch.sum()),
                "max_absolute_difference_thousands": (
                    float(differences.loc[comparable].abs().max())
                    if comparable.any()
                    else None
                ),
            }
        )
        for _, row in joined.loc[mismatch].iterrows():
            discrepancies.append(
                {
                    "field": field,
                    "CERT": int(row["CERT"]),
                    "NAME": row["NAME"],
                    "FDIC_API_value_thousands": row[f"{field}_FDIC"],
                    "FFIEC_bulk_value_thousands": row[f"{field}_FFIEC"],
                    "difference_thousands": differences.loc[row.name],
                    "Call_Report_submission_updated": row["SUBMISSION_UPDATED"],
                    "explanation": (
                        "The current FFIEC bulk file reflects a later amended filing than "
                        "the cached FDIC API index; this is a source-vintage difference, "
                        "not a field-mapping difference."
                    ),
                }
            )

    unmatched = joined.loc[joined["ASSET_FFIEC"].isna(), ["CERT", "NAME"]]
    metadata = {
        "validation_period": "2026Q2",
        "fdic_api_records_in_asset_band": int(len(fdic)),
        "ffiec_call_report_records_in_asset_band": int(len(call_report)),
        "matched_records": int(joined["ASSET_FFIEC"].notna().sum()),
        "fdic_records_not_in_call_report_bulk": int(len(unmatched)),
        "not_in_call_report_names": unmatched["NAME"].tolist(),
        "not_in_call_report_explanation": (
            "These six records are U.S. branches of foreign banks that file FFIEC 002, "
            "not the FFIEC Call Report series used for this methodology."
        ),
        "fdic_api_index_created": fdic_payload.get("meta", {})
        .get("index", {})
        .get("createTimestamp"),
        "mapping_conclusion": (
            "The mapping reproduces the cached FDIC fields exactly for all comparable "
            "records except two values for one bank whose Call Report was amended after "
            "the FDIC API index was created."
        ),
    }
    return pd.DataFrame(summaries), pd.DataFrame(discrepancies), metadata


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    mapping_summary, mapping_discrepancies, mapping_metadata = validate_q2_mapping()
    mapping_summary.to_csv(RESULTS_DIR / "q2_mapping_validation.csv", index=False)
    mapping_discrepancies.to_csv(
        RESULTS_DIR / "q2_mapping_discrepancies.csv", index=False
    )
    with (RESULTS_DIR / "q2_mapping_validation.json").open("w", encoding="utf-8") as handle:
        json.dump(mapping_metadata, handle, indent=2)
        handle.write("\n")

    q3_call_report = load_call_report(Q3_ZIP, "09302026")
    scores = build_prospective_scores(q3_call_report)
    score_path = PROCESSED_DIR / "prospective_scores_2026q3.csv"
    scores.to_csv(score_path, index=False, float_format="%.12g")
    scores.to_json(
        PROCESSED_DIR / "prospective_scores_2026q3.json",
        orient="records",
        indent=2,
    )
    mapping_summary.to_json(
        RESULTS_DIR / "q2_mapping_validation_rows.json",
        orient="records",
        indent=2,
    )
    mapping_discrepancies.to_json(
        RESULTS_DIR / "q2_mapping_discrepancy_rows.json",
        orient="records",
        indent=2,
    )

    unscored = scores.loc[
        scores["integrated_score"].isna(),
        ["NAME", "CERT", "score_status"],
    ].to_dict(orient="records")
    summary = {
        "release_version": "1.1.0",
        "baseline_quarter": "2026Q3",
        "baseline_date": BASELINE_DATE,
        "ffiec_snapshot_date": FFIEC_SNAPSHOT_DATE,
        "source": "FFIEC Central Data Repository bulk Call Report files",
        "source_url": "https://cdr.ffiec.gov/public/PWS/DownloadBulkData.aspx",
        "asset_band": "$10 billion to $250 billion, inclusive",
        "eligible_call_report_filers": int(len(scores)),
        "banks_with_complete_integrated_scores": int(scores["integrated_score"].notna().sum()),
        "banks_not_scored": int(scores["integrated_score"].isna().sum()),
        "unscored_records": unscored,
        "top_decile_cutoff_bank_count": int(math.ceil(len(scores) * 0.10)),
        "top_decile_flagged_bank_count": int(scores["top_decile_integrated"].fillna(False).sum()),
        "outcome_window_end": OUTCOME_WINDOW_END,
        "outcome_status": "Open; no prospective outcomes evaluated",
        "performance_status": "Not yet evaluable",
        "frozen_model": (
            "15% rate + 25% funding + 5% credit + 5% capital + "
            "20% rate-funding interaction + 30% dominant-risk trigger"
        ),
        "dominant_risk_trigger": (
            "Maximum of the securities market-value-gap percentile and the "
            "uninsured-deposit percentile"
        ),
        "interpretation_warning": (
            "The scores are research prioritization measures, not bank ratings, "
            "safety-and-soundness determinations, or failure predictions."
        ),
        "raw_zip_sha256": sha256(Q3_ZIP),
        "processed_scores_sha256": sha256(score_path),
        "mapping_validation": mapping_metadata,
    }
    with (RESULTS_DIR / "prospective_summary_2026q3.json").open(
        "w", encoding="utf-8"
    ) as handle:
        json.dump(summary, handle, indent=2)
        handle.write("\n")

    print(
        f"Published {len(scores)} eligible 2026Q3 Call Report records; "
        f"{scores['integrated_score'].notna().sum()} received complete scores."
    )
    print(
        "No prospective outcomes were evaluated. The outcome window remains open "
        "through 2028Q3."
    )


if __name__ == "__main__":
    main()
