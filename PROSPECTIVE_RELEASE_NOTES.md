# 2026Q3 Prospective Baseline Release

Release date: November 15, 2026  
Baseline date: September 30, 2026  
Official FFIEC data snapshot: November 14, 2026  
Prospective outcome window: 2026Q4 through 2028Q3

## What is being published

This release publishes bank-level baseline scores for the prespecified T5 prospective test. It applies the public model frozen in version 1.0.1 to the first baseline quarter whose Call Report data were unavailable at the time of the freeze.

The release includes 140 FFIEC Call Report filers with total assets from $10 billion through $250 billion. The frozen model produces complete integrated scores for 139. Charles Schwab Trust Bank remains in the population but receives no integrated score because it reports no loans, leaving the frozen credit ratios without a denominator. The top-decile cutoff is 14 banks.

## Cohort and evaluation rules stated before any outcome is observed

- **Cohort.** The T5 cohort follows operational rule R1 (published in version 1.0.3): banks whose 2026Q3 Call Report shows total assets of $10 billion to $250 billion and complete trigger inputs. The 2022 development diagnostic used the FDIC BankFind financial extract, which also contains insured U.S. branches of foreign banks (for example, Bank of China, Standard Chartered Bank, BBVA, and State Bank of India). Those branches file the FFIEC 002 report rather than the Call Report, so they are outside the T5 cohort and outside the T5 percentile population.
- **Unscored banks.** A cohort bank without a complete integrated score is excluded from the AUC, top-decile capture, and precision calculations and is reported separately with its outcome.
- **Top-decile cutoff.** The cutoff is fixed at 14 banks, as published here.

## What is not being claimed

No prospective outcomes have been observed or evaluated. The eight-quarter outcome window remains open through September 30, 2028. This release therefore reports no AUC, capture rate, precision, superiority, pass, or fail result.

The score is a research prioritization measure. It is not a bank rating, a safety-and-soundness determination, a failure prediction, or a substitute for supervisory analysis.

## Frozen formula

The indicators, percentile construction, weights, interaction term, and trigger are unchanged:

```text
15% rate + 25% funding + 5% credit + 5% capital
+ 20% rate-funding interaction + 30% dominant-risk trigger
```

The dominant-risk trigger remains the larger of the securities market-value-gap percentile and the uninsured-deposit percentile.

## Data provenance and reproducibility

The scores use the official FFIEC Central Data Repository bulk Call Report archive processed on November 14, 2026. The raw ZIP, its checksum, the complete scoring script, processed CSV, workbook tables, and validation reports are included in this release.

The raw-field mapping was independently checked against the cached 2026Q2 FDIC BankFind API extract. All comparable values match exactly except two values for one bank whose Call Report was amended after the cached FDIC index was created. The six FDIC records not present in the Call Report bulk archive are U.S. branches of foreign banks that file FFIEC 002 rather than the Call Report series.

This work was conducted independently using only public regulatory data. It does not use any employer's data, and no employer endorsement is stated or implied.
