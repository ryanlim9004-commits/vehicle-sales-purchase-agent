# Stage 3 verification — 2026-10-15

Implemented: real-source listing seed snapshot, extended frame provenance, asking/transaction distinction, exact/ranged mileage, sold/reserved filtering, luggage priority extraction, and weighted heuristic ranking after hard filtering.

## Verification

- 28 unit tests passed (existing 13 + 15 scoring/source tests).
- All 17 curated records pass schema checks; 17 IDs and source URLs are unique.
- 11 listed snapshots, five sold, one reserved. All 17 prices are asking prices.
- 16 records have exact or ranged mileage; seven lack verified reference fuel/boot values; all lack independently verified condition.
- Fixed city/luggage fixture: nine records eligible, Top 3 IDs PT_K4EDNMNYPG, PT_7PRLM3GLPK, CS_C606800. Scores 71.970, 71.526, 69.941 under published v1 assumptions. This is an algorithm result on a frozen sample, not purchase advice.
- Live qwen3:4b city/luggage English extraction + ranking passed in 19.31 seconds.
- Live qwen3:4b six-person household English extraction + ranking passed in 5.79 seconds; three old Alza candidates have no verified fuel values, so fuel scoring is explicitly unavailable.
- Full live records: stage3-live-results.json. Fixed output: stage3-fixture-result.json. Quality profile: data/quality_report.json. Reviewed fact/source receipts: data/source_receipts.json.

## Limits

Two live development cases do not establish general accuracy. No holdout population, representative market sample, transaction labels or VIN-based deduplication exists yet. Cached and dated listings cannot guarantee current availability. Manufacturer fuel claims are not used-car measurements. City compactness and luggage are documented proxies, and all scoring weights/anchors are design assumptions. Incompatible fuel claim bases are not compared. Missing evidence produces conservative score bounds and coverage indicators, not a statistical confidence interval.

No new dependency was installed. Valuation, negotiation, multi-turn Agent Controller and UI remain future stages. The accelerated target is a recordable core by 23 October, with concentrated video production from 24 October; see ACCELERATED_PLAN_ZH.md.
