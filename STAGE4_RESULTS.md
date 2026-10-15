# Stage 4 valuation verification — 2026-10-15

- Added SellerVehicleFrame, English structured extraction, traceable comparator rules, --value CLI, reproducible date option, and optional explicitly uncalibrated mileage/condition scenario.
- 40 unit tests passed (28 prior + 12 valuation tests).
- A qwen3:4b seller-extraction-to-reference development case passed in 18.2 seconds; full evidence in stage4-live-result.json.
- Fixed fixture: three recent exact-model/year/variant/transmission listing snapshots, median asking MYR44800, observed range MYR35888–45000.
- Default returns reference_only, no personalized mileage/condition correction. Illustrative opt-in has market_validated=false and midpoint MYR43092 for the published fair-condition fixture assumptions.
- Tests cover insufficient samples, missing facts, major damage, key mismatches, freshness/future dates, duplicates, synthetic exclusion, money rounding, mileage ranges, missing mileage and extrapolation.
- One live development case does not establish general extraction accuracy or market valuation accuracy. Comparable condition is not independently verified; price labels are asking prices. No trend estimation or calibrated adjustment model is claimed.
- No new dependency installed. Dynamic Agent tool calling, negotiation, memory and UI remain future stages.
