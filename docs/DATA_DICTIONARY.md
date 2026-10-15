# Vehicle data dictionary and Stage 5 contract

Reviewed on 15 October 2026. The canonical schema is `PassengerCarFrame` in `vehicle_frame.py`.

## Grain and datasets

One real row represents one source advertisement or inventory ID. It is not a verified unique vehicle or a completed transaction. Cross-platform VIN deduplication has not been performed.

- `data/vehicles_demo.json`: eight synthetic teaching fixtures. Never treat their prices or specifications as real evidence.
- `data/vehicles_real.json`: 17 manually reviewed listing snapshots, recorded on 2026-10-15. Eleven are labelled `listed_snapshot`, five `sold`, and one `reserved`. Availability describes the saved page, not live stock.
- `data/source_receipts.json`: source-linked selected facts and specification references. The reproducibility script copies reviewed facts into this file; agreement proves local consistency, not independent truth.

## Fields and units

| Field | Meaning / unit | Unknown and validation rules |
|---|---|---|
| vehicle_id | Source advertisement/inventory identifier | Required and unique in a loaded dataset |
| brand, model | Source-stated identity | Required nonempty text |
| variant | Exact stated trim, e.g. 1.5 SE | Required for real rows; do not pool variants for valuation |
| year | Manufacturing year where stated; title-derived cases retain evidence notes | Integer, 1900 through observation year. Model year / registration year must not be silently substituted |
| transmission | Source-stated transmission label | Null if unknown. Automatic is a broad label; a specific D-CVT is not treated as identical by exact-match valuation |
| currency, price_myr | MYR and advertised total asking amount | Currency fixed to MYR; positive price or null; monthly instalments are not total prices |
| source_kind | synthetic_demo / listing / transaction | Explicit evidence classification |
| price_type | illustrative / asking / transaction | Real listing must be asking; real transaction must be transaction. Sold adverts retain their asking price |
| seats | Number of passenger seats | Integer 1–20 or null; ambiguous text such as '7 & Above' remains unknown |
| mileage_km | Exact odometer reading, kilometres | Nonnegative integer in stored vehicle records or null; do not impute a range midpoint |
| mileage_min_km, mileage_max_km | Advertised odometer bounds, kilometres | Nonnegative bounds or null; minimum cannot exceed maximum; any exact reading must agree with supplied bounds |
| condition | Independently established vehicle condition | All current real rows are null. Seller advertising language is not an independent label |
| availability | listed_snapshot / sold / reserved / unknown | Only real asking listings marked listed_snapshot can enter buying results |
| observed_on | Date this saved dataset records the observation | ISO YYYY-MM-DD; date-only, no time-of-day or precise retrieval timestamp claimed |
| source_updated_on | Date the source states it was updated | ISO date or null; cannot be after observed_on. Unknown update time cannot establish freshness |
| source_reference | Listing evidence URL | Required HTTPS URL for real rows |
| fuel_km_per_l | Manufacturer reference consumption, km per litre | Positive value or null; not measured used-car or city consumption |
| fuel_basis | MDC_claim / eco_driving_claim / synthetic_demo | Required with fuel value; real rows cannot use synthetic_demo. These labels do not prove identical detailed test conditions |
| fuel_source_reference | Source for the matched generation/variant fuel claim | HTTPS URL required when a real fuel value is supplied |
| boot_litres | Reference luggage capacity, litres | Null if unknown; not a cabin width or legroom measure |
| boot_configuration | all_seats_up / third_row_folded | Required with boot value. Only all_seats_up values contribute to luggage scoring |
| length_mm | Overall reference vehicle length, millimetres | Integer or null; a compactness proxy, not a measured parking-difficulty rating |
| specs_source_reference | Specification evidence for dimensions / boot | HTTPS URL required when these real features are populated |
| evidence_notes | Provenance, generation assumptions and ambiguity | Preserve qualifications; do not convert uncertainty into a definite claim |
| vehicle_category, wheels | Inherited PassengerCarFrame defaults | passenger_car and four wheels; class-level defaults |

`null` means unknown, not zero. Seller input is a different frame: `SellerVehicleFrame.mileage_km` supports fractional kilometres after source-text unit conversion, e.g. 900 m → 0.9 km.

## Eligibility, scoring and evidence coverage

Hard filtering checks asking-listing evidence and snapshot availability, then price ≤ budget, seats ≥ required seats, and excluded brands. Unknown hard-constraint values do not pass. It does not automatically relax constraints.

After filtering, `--rank` computes normalized weighted feature contributions, using the public weights and formulas in `LESSON3_ZH.md` and in each result. `--match` deliberately retains hard-filter-only price/ID order.

Every candidate uses the same active weights. Unknown features contribute zero to the evidence-supported lower bound; missing coverage and a possible upper bound are shown. Scores do not establish that a vehicle with unknown features is worse. No statistical confidence interval is claimed.

Fuel scoring is disabled for the whole candidate set if test/claim bases are mixed, or if no eligible candidate has a supported fuel value. Manufacturer reference claims are never presented as independently measured fuel economy.

## What is and is not complete

The current data and scoring contract is sufficient for this bounded educational prototype. Eight of the eleven eligible snapshot rows have fuel and boot values; the three old Alza rows have unknown fuel/boot values. All eleven have length values.

Only 2020 Perodua Alza 1.5 SE Automatic currently has at least three eligible recent comparables under the valuation policy. Other exact model/variant/year/transmission groups do not. Total dataset size is not per-model valuation evidence. No transaction-labelled price or independently inspected condition label is available.

More models, brands, current inventory, calibration and independent ranking/market validation remain future improvements. The operational principle is to display unsupported features as unknown or return insufficient evidence, not invent missing facts.
