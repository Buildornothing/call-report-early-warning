# Call Report Early-Warning Methodology v1.1.0

This folder contains the code and cached public data used to reproduce the corrected December 31, 2022 diagnostic and the frozen model's September 30, 2026 prospective baseline scores in `call_report_preliminary_analysis.xlsx`.

## Release scope

- The $10 billion to $250 billion asset filter is applied locally **before** percentiles, component scores, composite scores, and ranks are calculated.
- The corrected sample contains 149 banks and excludes every institution outside the stated asset band.
- The integrated trigger captures the three in-band 2023 failures in the top 15, but it also flags 12 nonfailures. Its top-decile precision is therefore 20%, and its false-positive share is 80%.
- Uninsured-deposit concentration alone also captures all three failures in the 2023 diagnostic. The workbook does not claim that the integrated score is superior.
- The 2023 trigger and weights remain explicitly labeled post-hoc and in-sample.
- The historical diagnostic sheets anonymize nonfailed institutions. The prospective publication identifies institutions so the public scores are auditable; the names and underlying Call Report data are public.

## Changes in v1.1.0

- Publishes the prespecified T5 baseline scores using the FFIEC 2026Q3 bulk Call Report release processed on November 14, 2026.
- Applies the indicators, percentile construction, weights, rate-funding interaction, and dominant-risk trigger exactly as frozen in version 1.0.1. Nothing was retuned after seeing the 2026Q3 data.
- Includes 140 Call Report filers in the frozen $10 billion to $250 billion asset band. Of these, 139 receive complete integrated scores. Charles Schwab Trust Bank is retained in the population but is not assigned an integrated score because it reports no loans, so the frozen credit ratios have no denominator.
- Defines the T5 cohort under operational rule R1 (v1.0.3): banks whose 2026Q3 Call Report shows total assets of $10 billion to $250 billion and complete trigger inputs. The 2022 development diagnostic used the FDIC BankFind financial extract, which also contains insured U.S. branches of foreign banks (for example, Bank of China, Standard Chartered Bank, BBVA, and State Bank of India) that file the FFIEC 002 report rather than the Call Report. Those branches are therefore outside the T5 cohort and outside the T5 percentile population. This population definition is stated before any prospective outcome is observed.
- States the treatment of unscored banks before any outcome is observed: a bank in the T5 cohort without a complete integrated score is excluded from the AUC, top-decile capture, and precision calculations and is reported separately with its outcome. The top-decile cutoff remains 14 banks, as published in this release.
- Flags 14 institutions under the frozen top-decile rule. These flags are research prioritization measures, not bank ratings, safety-and-soundness determinations, or failure predictions.
- Opens, but does not evaluate, the eight-quarter prospective outcome window through 2028Q3. No AUC, precision, capture, superiority, pass, or fail claim is reported in this release.
- Adds an offline field-mapping validation against 2026Q2 FDIC BankFind data. The mapping matches every comparable field exactly except two values for one bank whose Call Report was amended after the cached FDIC API index was created. Six foreign-bank branches in the FDIC sample are documented as FFIEC 002 filers and are not part of the Call Report population.
- Adds the official FFIEC 2026Q3 raw ZIP, the Q2 validation sources, the publication script, processed scores, validation reports, updated workbook sheets, and complete checksums.

## Changes in v1.0.4

- Relabels the historical test T3 as "Historical holdout: 2008–2009" so the title matches its frozen design: a single 2007Q4 baseline with FDIC failures counted in the following eight quarters (2008Q1–2009Q4). The test design is unchanged.
- Updates the matching references on the Purpose and Review Findings sheets.
- Does not change the indicators, weights, interaction term, trigger, test designs, pass marks, or operational rules. No T3, T4, or T5 results have been calculated as of this release.

## Changes in v1.0.3

- Adds operational rules R1–R8 to the validation roadmap for tests T3–T5: eligibility fixed at the baseline quarter, failure definition, worst-quarter measurement of capital and credit deterioration, treatment of mergers, exits, and missing Call Reports, an inconclusive rule when fewer than five outcome banks occur, confidence-interval methods, and data provenance.
- Specifies a single 2007Q4 baseline for the 2008–2011 test (T3), with failure in the following eight quarters.
- Applies the inconclusive rule to the 2019–2020 test (T4) as well as the prospective test (T5).
- Adds the Zenodo concept DOI to `CITATION.cff`.
- No bank-level 2019–2020 test results were calculated or inspected before the v1.0.2 test definition and pass criteria were publicly timestamped. No T3, T4, or T5 results have been calculated as of this release.
- Does not change the indicators, percentile construction, weights, interaction term, or dominant-risk trigger frozen in version 1.0.1.

## Changes in v1.0.2

- Marks the specification-freeze step complete. Version 1.0.1 was archived on October 8, 2026, at [https://doi.org/10.5281/zenodo.23246551](https://doi.org/10.5281/zenodo.23246551).
- Adds a locked-specification 2019–2020 pandemic-stress test (T4) and a prospective test (T5) to the validation roadmap, and renumbers the later tests T6–T9.
- States quantitative pass marks before either test is run.
- Updates the milestones to distinguish the completed freeze from future validation work, schedules the smaller-bank extension (T8) and a bank self-assessment template, and corrects test references.
- Removes the placeholder `data/raw/text.txt` file.
- Expands `SHA256SUMS.txt` to cover the workbook and every distributed release file except the manifest itself.

## Frozen model specification

Versions 1.0.2 through 1.1.0 do not change the indicators, percentile construction, weights, interaction, or dominant-risk trigger published in version 1.0.1. The trigger-augmented score remains:

```text
15% rate + 25% funding + 5% credit + 5% capital
+ 20% rate-funding interaction + 30% dominant-risk trigger
```

The dominant-risk trigger remains the maximum of the securities market-value-gap percentile and uninsured-deposit percentile.

## Added validation tests and pass marks

The workbook contains the complete test definitions. In summary:

- **2019–2020 pandemic-stress test (T4).** Primary test: apply the frozen v1.0.1 specification without retuning to a single 2019Q4 baseline and follow each bank for four quarters through 2020Q4. Secondary robustness test: rolling 2019Q1–2019Q4 baselines, each followed for four quarters, with bank-clustered confidence intervals. The outcome is measured over the same four-quarter window for every component, at the worst quarter in that window: FDIC failure, a decline in equity-to-assets of at least 2 percentage points, or an increase in noncurrent loans-to-gross loans of at least 1 percentage point that also reaches 2%. An eight-quarter failure analysis may be reported separately as a secondary endpoint. Any results from 2020 baselines are labeled contemporaneous monitoring, not pre-stress prediction. The primary test passes only if the integrated score has an AUC of at least 0.70, exceeds the best single-ratio AUC by at least 0.03, and improves top-decile precision by at least 5 percentage points; the test is inconclusive if the primary cohort has fewer than five outcome banks; secondary and monitoring results do not determine pass or fail.
- **Prospective test (T5).** Use a single 2026Q3 baseline, the first quarter whose Call Report data were not available when version 1.0.1 was frozen. Follow each eligible bank for eight quarters through 2028Q3, using the same outcome components measured at the worst quarter in that eight-quarter window. The test has the same pass marks as the T4 primary test. If fewer than five outcome events occur, report the test as inconclusive and continue prospective observation without retuning.

- **Operational rules (R1–R8).** The workbook's Validation Roadmap defines eligibility, failures, worst-quarter deterioration, mergers and missing reports, the inconclusive rule, confidence intervals (DeLong for AUC; bank-level bootstrap with 2,000 resamples for capture and precision; bank-clustered bootstrap for rolling cohorts), and data provenance.

A failed or inconclusive test will be reported. No superiority claim will be made unless the prespecified criteria are met.

## Reproduce the analysis

Requirements: Python 3.11 or newer, pandas, and numpy.

From this directory, run the historical diagnostic:

```bash
python analysis.py --offline
```

The command reads only the cached files in `data/raw/` and writes generated outputs to `data/processed/` and `results/`.

Expected controls:

- peer-bank count: 149;
- banks outside the $10 billion to $250 billion band: 0;
- integrated-score ranks of the three failures: 5, 10, and 15;
- top-decile integrated-score false positives: 12;
- top-decile integrated-score precision: 20%;
- stressed-survivor ranks: 21, 25, 32, 33, and 75 among 144 banks with complete trigger scores.

Publish the 2026Q3 prospective baseline and rerun the field-mapping validation with:

```bash
python prospective_2026q3.py
```

That command reads only the cached public files in `data/raw/` and writes:

- `data/processed/prospective_scores_2026q3.csv`;
- `results/prospective_summary_2026q3.json`;
- `results/q2_mapping_validation.csv` and `.json`; and
- `results/q2_mapping_discrepancies.csv`.

Expected prospective controls:

- eligible 2026Q3 Call Report filers in the asset band: 140;
- banks with complete integrated scores: 139;
- frozen top-decile cutoff and flagged count: 14;
- prospective outcomes evaluated: 0; and
- outcome window end: September 30, 2028.

## Research use
Author: Anjola Odunaike. See `CITATION.cff` for citation details.

`SHA256SUMS.txt` records the integrity hashes for the complete release package, including the workbook.

This work was conducted independently using only public regulatory data. It does not use any employer's data, and no employer endorsement is stated or implied.
