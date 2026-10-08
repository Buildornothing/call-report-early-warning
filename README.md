# Call Report Preliminary Analysis

This folder contains the code and cached public data used to reproduce the corrected December 31, 2022 cross-sectional analysis in `call_report_preliminary_analysis.xlsx`.

## What changed

- The $10 billion to $250 billion asset filter is applied locally **before** percentiles, component scores, composite scores, and ranks are calculated.
- The corrected sample contains 149 banks and excludes every institution outside the stated asset band.
- The integrated trigger captures the three in-band 2023 failures in the top 15, but it also flags 12 nonfailures. Its top-decile precision is therefore 20%, and its false-positive share is 80%.
- Uninsured-deposit concentration alone also captures all three failures in the 2023 diagnostic. The workbook does not claim that the integrated score is superior.
- The 2023 trigger and weights are explicitly labeled post-hoc and in-sample. They must be frozen and independently timestamped before the planned 2008–2011 test.
- The filing workbook anonymizes nonfailed institutions. The cached FDIC source files remain unaltered public-source records and therefore contain institution names.

## Reproduce the analysis

Requirements: Python 3.11 or newer, pandas, and numpy.

From this directory, run:

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

## research use


`SHA256SUMS.txt` records the integrity hashes for the archived code and source files.
