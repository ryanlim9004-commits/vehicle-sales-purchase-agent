# Historical Ridge fallback: report material

## Scope and data

The user authorised a combined historical teaching experiment on 31 October 2026. It considers 17 saved asking-price advertisements and 97 user-completed historical simulation records. After excluding one advertisement with unknown mileage and two conservative repeated identity/year/transmission/mileage signatures, 111 rows remain: 16 saved asking snapshots and 95 simulation rows. This grouping does not establish VIN-level independence. Source dates and simulation provenance remain unchanged. Sold/reserved advertisements retain asking labels. No market-approved training rows have been added to the separate stricter `regression_manifest.json`.

## Learning method

A fixed NumPy Ridge model learns log historical scenario price from standardised manufacturing year, log(1 + mileage proxy), displacement readable from variant text and one-hot brand/model/transmission categories. Mileage intervals use declared midpoints in the model only; exact odometers are not invented in the source catalogue. Missing displacement is encoded by a zero sentinel, not asserted as a physical engine capacity. No observation-age feature is computed from unknown advertisement dates. Seats, fuel economy, subjective condition and damage penalties are not price-training inputs. Coefficients describe associations in the mixed historical sample, not causal depreciation or condition effects.

## Development evaluation

Before evaluating, the policy fixes Ridge alpha at 1.0 and requires at least five conservative source groups per model/transmission. Each group is left out once while the remaining dataset fits coefficients, scaling and category vocabulary. The comparator is the median training price for the same brand/model/transmission. Historical demo eligibility requires lower MAE than that baseline, MAE no more than 20% of mean group price and maximum observed relative error no more than 40%. These are teaching design choices, not market certification. No holdout-driven parameter search is performed.

Alphard Automatic has nine evaluation groups, MAE MYR22,945.92 versus baseline MYR34,722.50. Harrier Automatic has five, MAE MYR11,493.56 versus MYR13,459.90. Alza Automatic (seven) and Vellfire Automatic (six) fail; sparse models are not enabled. The sample is small and evaluation is developmental, not external, independent or temporal validation. The subsequently fitted serving artifact includes the full eligible dataset. Its input hash and content identifier are checked before inference. Displayed prediction +/- development MAE is an illustrative error guide, not a confidence interval or guaranteed price bound.

## Agent integration

Sell retains priority for at least three eligible exact real-source listed comparables. When those are insufficient, the historical model may return a separately named `historical_reference`, with the real comparable `reference` still null. Prediction requires an evaluated model, a previously seen exact variant and manufacturing year/mileage inside that variant's observed ranges. This enables bounded interpolation, not estimation for arbitrary unseen models. Known major accident/flood reports retain the inspection-first path.

Negotiation can use a verified historical prediction as a labelled discussion anchor, while preserving complete fees, buyer total caps and seller minimum net proceeds after settlement. The current-market position remains unassessed. Trade-In displays historical context but computes both financial alternatives from explicit user quotes. Missing dealer/private-sale quotes are not replaced by the learned asking-price proxy. Prediction, identity, mileage, model/data hashes and resulting financial rules are recomputed by Python checks before completion. The existing Controller and English Streamlit results expose the prediction, scope, sources and development error. Unknown mileage can be declined without preventing ordinary limit/quote calculations.

## Evidence and remaining work

Use `historical-regression-results.json` for model development figures and `historical-regression-acceptance.json` for actual engineering/model-run outcomes. Synthetic quote fixtures verify arithmetic and flow; they do not prove deal success, current market accuracy or independent recommendation relevance. Expand dated, usable, deduplicated samples within each intended model/variant/generation and obtain independent evaluations before broadening coverage or making current-market claims.
