# Kaggle candidate check — 22 October 2026

This is a scoped data-admission check alongside the usage-input fix. No candidate has been imported into recommendation stock or the regression manifest.

## User-supplied notebook: unsuitable for real-market use

- [Ahmed Essam notebook](https://www.kaggle.com/code/ahmedessamsaber/cars-dataset) points to [Sourav Banerjee Cars Dataset](https://www.kaggle.com/datasets/iamsouravbanerjee/cars-dataset).
- Its data card explicitly attributes the simulated records to Mockaroo. The notebook reports 30,000 rows and eight columns: purchaser names, residence country, car brand/model/color/year and payment-card type. There is no asking/transaction price, odometer, seating or fuel-consumption column.
- The notebook's Apache label is not the dataset's license. The dataset page displays Other (specified in description), version1, updated17Oct2023.
- Decision: reject for market calibration, real inventory, recommendation specifications and price-regression labels. No copy of its rows was downloaded. This conclusion is about the inspected dataset, not all datasets on Kaggle.

## Alternative historical Malaysian candidate

Source: [tanshihjen / Malaysia_Resale_Carlist](https://www.kaggle.com/datasets/tanshihjen/malaysia-resale-carlist), version1, page updated6May2024. The uploader describes scraped Malaysian resale advertisements and declares Apache2.0. This records the uploader's claim; original listing provenance/use conditions have not been independently established.

The public Kaggle download endpoint returned one ZIP containing resale_car.csv. The archive and the authored profile/notebook are retained outside the application repository in vehicle-agent-research/kaggle-20261022. The browser download event did not yield a confirmed file; successful acquisition here was through the public dataset download endpoint, without credentials or accepting new terms. No live marketplace scraper was run.

| Actual CSV check | Result | Consequence |
|---|---:|---|
| Rows / columns | 974 / 7 | Advertisement records, not verified unique physical vehicles |
| Strictly formatted RM list prices | 969 | Asking labels only; never substitute monthly payments |
| Missing list price | 5 | Exclude from price modelling |
| Missing model label | 82 | Identity needs verification; cannot assume a model |
| Distinct nonmissing model strings | 167 | Strings are not 167 verified variants with full specifications |
| Exact normalized duplicate rows | 1 | Removing this row would not solve hidden duplicate vehicles |
| Descriptions beginning with two years | 97 | Do not guess which is manufacture versus registration |
| Mileage ranges / exact km strings | 963 / 11 | Keep bounds; a range is not an exact odometer |
| Monthly field contains a market-estimate promotion | 4 | Not an installment or independent target price |

No dedicated columns establish individual listing URLs/IDs, VINs, observation dates, manufacturing year, exact variant, seats, fuel consumption, complete fees or transaction price. A year appearing once in a title still is not independently verified as manufacture year. Downloading in2026 does not make these current2026 observations. Seller claims in descriptions do not prove clean accident/flood histories or zero complete fees.

Machine-readable checks and SHA256: [candidate quality](kaggle-candidate-quality-20261022.json). The local companion notebook and source script reproduce these counts from the retained ZIP using Python standard-library modules; no new package is required. Raw records are not redistributed in this application repository.

## Admission decision and useful next work

Status: **historical research candidate; active_in_agent=false; approved training rows=0**. It may support a clearly dated historical asking-price experiment after provenance/use, identity and duplicate/holdout policies are resolved. It cannot certify current Malaysian fair value, transaction prices, trade-in offers or available stock.

Next: establish source/use and observation scope; clean price/identity and retain mileage intervals; resolve grouping for independent holdout; join exact-year/variant Malaysian specification sources including seats. Evaluate a historical asking-price baseline/regression only after those checks; review its error and scope before considering integration. Existing Agent data, frozen demo date and uncalibrated valuation limits stay unchanged by this research.
