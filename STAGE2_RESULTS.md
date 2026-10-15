# Stage 2 verification

Recorded on 2026-10-14.

- 13 unit tests passed: five existing buyer-profile tests and eight vehicle/filtering tests.
- A live qwen3:4b request extracted the English goal: budget MYR 60000, six-person household, city commute, high fuel priority, exclude Toyota.
- The resulting pipeline returned status=matches_found, checked_count=8, matched_count=2; IDs DEMO001 and DEMO006.
- Manual family fixture without Toyota exclusion yields DEMO001, DEMO002, DEMO006, including the exact budget-boundary record.
- Invalid/duplicate records, unknown price/seats, multiple rejection reasons, conflicting profiles and soft preferred brands are covered by unit tests.

All records in vehicles_demo.json are invented teaching fixtures. This verifies extraction/integration and deterministic hard filtering, not real-market quality or fuel-economy ranking. Matching display order is price then ID, not a preference score. No new Python dependency was required.
