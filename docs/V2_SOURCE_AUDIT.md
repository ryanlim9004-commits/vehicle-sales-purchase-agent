# V2 source and scope audit

Research checked 16 Oct 2026; implementation/audit 17 Oct 2026, Malaysia time.
This is a research receipt, not a licence, an advertisement refresh or proof of
market calibration. Existing price inventory remains the 15 Oct snapshot.

## Accepted reference evidence

- [ASEAN NCAP Alza original report](https://www.aseancap.org/uploads/reports/37-perodua-perodua-alza-2022.pdf): tested X, 2022, 2021–2025 protocol. Use explicit all-variant statements for AV equipment. Retain original 81.64 rather than silently replacing it with migrated webpage 81.65. Never transfer to 2020 SE.
- [Perodua Myvi brochure](https://www.perodua.com.my/files/Myvi_Brochure.pdf) and [manufacturer model page](https://www.perodua.com.my/our-models/hatchback/myvi): indexed Nov 2021 brochure revision and H/AV VSC/pre-collision-braking equipment table checked in research. Direct PDF retrieval failed; no local PDF archive is claimed. Curtain-specific fitment and facelift NCAP extension remain unknown. Six total airbags alone does not prove curtain fitment.
- [ASEAN NCAP Vios original report](https://www.aseancap.org/uploads/reports/25-toyota-toyota-vios-2023.pdf): G, 2023, 2021–2025 protocol, 78.7 points. Regional standard/optional statements are insufficient to assert all exact-trim equipment.
- [ASEAN NCAP X50 original report](https://www.aseancap.org/uploads/reports/20260524040535_15d731b9a779.pdf): original 9 Oct 2020 report, Standard, 2017–2020 protocol, 84.26 points. Keep original ESC narrative; migrated page differs. Do not assume Standard AEB or curtain fitment from range-level optionality.
- [Paul Tan Alza AV road test](https://paultan.org/2022/08/18/review-2022-perodua-alza-av-the-best-family-car-below-100k-in-malaysia-not-just-among-7-seater-mpvs/): one review family; no numeric comfort reference yet.
- [Paul Tan Myvi AV facelift test](https://paultan.org/2021/12/16/2022-perodua-myvi-facelift-review/) and [AUTO123 AV one-week test](https://auto123channel.com/2022/02/27/2022-perodua-myvi-car-review-details/): independent publisher families, short/extended use, not ownership reliability. Preserve negative seating/noise observations instead of selecting only favourable comments. Chinese original is briefly paraphrased in English.
- [Paul Tan Vios G test](https://paultan.org/2023/03/19/2023-toyota-vios-review-malaysia/): short media drive, rear/headroom limitations; one family.
- [Carlist Persona Premium review](https://www.carlist.my/news/review-proton-persona-bang-for-buck-for-the-most-part-82478/82478/): April 2021 review, before later MC2 change. Publication year is not manufacturing year. Research only; automatic listing join disabled.
- [Paul Tan Iriz owner review](https://paultan.org/2022/03/22/2019-proton-iriz-long-term-owner-review-two-years-with-the-myvi-rival-loves-hates-who-should-consider/): 2019 Standard manual, about 11,000 km over two years, not daily use. Article context is available; full video/transcript was not inspected. No unseen speech or fault frequency is coded.

Saved data contains short attributed notes, source locators and limitations, not
copied articles, full transcripts or report archives. An article and companion
video, syndication or repeated URL do not become independent evidence. Current
reliability sources do not satisfy the numeric policy. Broader owner-search
results included older generations, different variants, expectations rather than
outcomes and unverifiable claims; none was promoted to exact-2022-AV fault data.

## Price acquisition findings and next gate

[Carlist terms](https://www.carlist.my/terms-and-conditions-of-use),
[Mudah terms](https://www.mudah.my/about/terms-of-service/) and
[Paul Tan used-car terms](https://paultan.org/used-cars/terms-of-service/) were
reviewed during factual research. Automated extraction/reuse restrictions mean
we have not built a bulk scraper or bypassed account/OTP controls. Obtain a usable
export, documented permission or clearly licensed appropriate row-level dataset
before expanding a training collection. A visible public page is not itself a
dataset licence; manually copying at scale does not resolve use conditions.

Carlist's online valuation uses CARSOME and phone/OTP flow; no phone form was
submitted. Mudah price-check navigation did not establish a usable public row API.
An asking advertisement, online estimate, inspected dealer trade-in quote and
verified transaction are different evidence types. Sold/reserved advertisements
remain last advertised prices, not proof of what a buyer paid.

Other investigated leads: JPJ/data.gov.my registration data lacks prices and
odometer/variant labels; old 2015 Carlist samples lack current applicability and
verified reuse conditions; university research papers do not establish a usable
public Malaysian row dataset. [Paqar API documentation](https://paqar.my/api-docs)
describes aggregate asking medians/ranges with variant fallback, not independent
per-car training labels or verified transaction truth. Other crawl/private report
leads still need rights, schema, date and row-level verification. This search did
not find a suitable verified dataset; it does not prove none exists.

`data/regression_manifest.json` intentionally has zero approved training rows.
Do not add simulated labels, foreign prices converted to MYR, aggregate estimates
as pseudo-transactions, midpoint odometers or invented duplicate identifiers.
Keep fees/unknowns, source dates and evidence of car-group deduplication.

## Algorithm references

The small Sugeno implementation is local Python with documented triangle/shoulder
memberships, product AND and constant consequents; it is distinct from a Mamdani
library demo. Ridge minimises squared price errors plus a fixed L2 coefficient
penalty. See [linear model documentation](https://scikit-learn.org/stable/modules/linear_model.html#ridge-regression-and-classification),
[training/test leakage guidance](https://scikit-learn.org/stable/common_pitfalls.html)
and [NumPy solve](https://numpy.org/doc/stable/reference/generated/numpy.linalg.solve.html).
NumPy is already locked; sklearn is not installed or required by this prepared
implementation. No Malaysian market model has been trained or enabled.
