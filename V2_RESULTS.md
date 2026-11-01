# V2 development acceptance — 17 Oct 2026

**1 Nov latest financial audit:** **308 offline tests passed in 27.961s**, including 21 focused financial-audit methods. Six actual local qwen3:4b turns also passed on matching code/data. Negotiation/Trade-In quote meaning, scoped fee confirmation and invalidation, role-switch memory, direct damage history, saved seller handoffs, route/unit/time follow-ups, and policy/reference verification are covered. An initial 11-method baseline reproduced 11 failed assertions/subcases; dated intermediate 306/307-test records are retained locally. See [audit and remaining limits](FINANCIAL_AUDIT_20261101_ZH.md) and [current acceptance](docs/financial-audit-acceptance-20261101.json). No new dependency, dataset or price model was added. Cash arithmetic does not prove current market accuracy, quote authenticity, equivalent replacement packages, financing affordability or actual deal success.

**1 Nov subsequent Axia guidance fix:** Confirmed the 114-row catalogue loads correctly but contains no Axia. Missing exact context now retains explicitly labelled other-model input examples and one coverage notice, without substituting vehicle facts or valuation evidence. All helper-form field guidance is directly visible; numeric placeholders match the actual parser. **287 offline tests passed in 26.942s**, including 13 example-specific checks. See [current usage](QUESTION_EXAMPLES_20261101_ZH.md) and [latest acceptance](docs/question-examples-axia-acceptance-20261101.json). Earlier same-day initial guidance results below are historical.

Two actual local qwen3:4b turns replayed the user's wording (26.48s / 19.06s), correctly storing Perodua/Axia and showing qualified examples despite absent Axia coverage. Core code/data hashes match final offline and live records. AppTest covers actual chat text and visible form guidance in all three areas; no new real-browser acceptance is claimed.

**1 Nov question guidance:** Sell/Negotiation/Trade-In questions append catalogue-backed contextual identity examples and explicitly labelled format/declaration samples. Forms share hints without prefilled facts. **283 offline tests passed in 23.491s**, including 9 guidance/context/non-autofill/AppTest cases. See [usage](QUESTION_EXAMPLES_20261101_ZH.md) and [acceptance](docs/question-examples-acceptance-20261101.json). This batch did not rerun actual Ollama or real-browser acceptance; historical model development/live records below remain dated evidence.

**31 Oct later Regression update:** The user authorised combined real-snapshot/historical teaching training. A separate historical Ridge model uses 111 conservative source groups and is connected to Sell, Negotiation and Trade-In, with exact real comparables retaining priority. Only Alphard/Harrier groups pass the fixed development error policy and input scope; Alza/Vellfire fail, sparse groups remain disabled. See [operation guide](HISTORICAL_REGRESSION_GUIDE_ZH.md), [training report](docs/historical-regression-results.json) and [acceptance](docs/historical-regression-acceptance.json). The stricter market manifest still has 0 approved rows; no current-market validation is claimed. Dated tables below retain the earlier state.

Final 31 Oct historical-fallback verification: **274 offline tests passed in 21.949s**; actual local qwen3:4b completed Sell and Negotiation natural-language inputs plus a structured-form Trade-In/planner input (58.37s / 53.78s / 26.06s), all Python checks passed. AppTest covers historical result rendering for all three goals; no new real-browser, independent-user or current-market-accuracy claim follows. Initial 273-test pass and restricted-environment temporary-folder failure are distinguished in the acceptance record. Runtime business code matches the live run; the later changes add one boundary test, source fingerprint coverage and documentation.

**31 Oct update:** Default Agent/UI data now include 97 user-completed historical simulation records alongside the 17 original source snapshots. They expand Buy scenario coverage, retain unknown stock/dates, and are excluded from market valuation and approved regression training. See [simulation guide](SIMULATION_DATA_GUIDE_ZH.md) and [structural audit](docs/simulation-data-audit.json). The dated table and results below describe the earlier V2 acceptance.

Status: fuzzy matching and scoped research integration delivered for the current
evidence coverage. The complete V2 data/model goal is **not finished**.
See V2_GUIDE_ZH.md for the beginner guide and docs/V2_SOURCE_AUDIT.md for receipts.

| Item | Verified state | Remaining boundary |
|---|---|---|
| Price inventory | 17 saved asking-price advertisements: 11 listed snapshots, 5 sold, 1 reserved | No new purchasable inventory added this batch; sold is not transaction price |
| Comparable valuation | Existing rule-based exact-identity asking references retained; only 2020 Alza 1.5 SE Automatic has at least 3 eligible comparables under the frozen policy | Broader coverage and suitable row-level training data still needed |
| Formal Fuzzy Logic | Pure-Python zero-order Sugeno; triangle/shoulder membership; product AND; 3/9 rules; explicit trace; replaces separate fuel/boot points | Anchors/weights/rule constants are design policy, not learned customer relevance |
| Safety research | 4 model reports/equipment references across 5 profiles, exact scope; protocol retained; partial unknown equipment disclosed | No used-car inspection; no cross-protocol star averaging; broader coverage pending |
| Comfort research | 6 attributed review records; 2022 Myvi AV has 2 publisher families and numeric coded reference .3125 | Other profiles insufficient; review coding needs independent human review/relevance evaluation |
| Reliability opinion engine | Ownership-period guard, source-family aggregation, disagreements, insufficient-evidence abstention implemented and tested | **Zero real profiles satisfy numeric reliability evidence policy**; no failure-rate claim |
| Research catalogue | 6 model names, 7 year/variant profiles; source dates, limitations and unknown price/fees/availability shown | Research is not stock; Persona April-2021 review is research-only because same-year changes are unresolved |
| Regression preparation | Typed dataset, use-condition gate, duplicate-car grouping, held-out test groups, train-only transforms, NumPy Ridge, MAE/RMSE and identity-median baseline implemented | 0 approved training rows; **no Malaysian market model trained or enabled**; deployment scope/checker/UI integration after data and model evaluation |
| Agent and UI | New preferences share grounding, state, actual tools and result checks; read-only research browsing; bounds/coverage/source explanations | Current lookup uses saved data; no live search/date switch |
| Negotiation / Trade-In | Existing asking context, explicit user offers, complete fees and loan arithmetic preserved | Asking price is not dealer quote/private-sale proceeds; no real成交成功率 claim |
| Independent assessment | Empty authored-case template and cross-computer checklist prepared | No confirmed independent teammate submissions or second-computer execution recorded |

Full offline command:

```powershell
.\.venv\Scripts\python.exe -m unittest -q test_profile test_matching test_scoring test_valuation test_input_grounding test_stage5_audit test_negotiation test_agent test_streamlit_ui test_v2 test_price_regression
```

Result after the final code fix: **184 tests passed in 14.567 seconds** (152
existing + 32 V2 checks). Tests include original financial tools and real
Streamlit AppTest rendering, source/year/variant boundaries, subjective review
coding, missing-data bounds, fuzzy arithmetic, tamper rejection, new forms and
the gated regression experiment. Model replies are scripted in offline Agent/UI
tests; synthetic regression fixtures verify engineering only, not market accuracy.
`pip check` passed; `git diff --check` passed. NumPy was already in the lock and
installation; requirements.txt now lists it as a direct dependency. No new package
was installed for this batch.

`evaluate_v2_live.py` then executed two actual local Ollama turns on the final
usage-recovery implementation: **both passed**, 40.36 and 35.10 seconds. Full
inputs, assertions, executed tools and checks are in `v2-live-results.json`.
They check named priorities, memory, corrected budget, excluded brand, nine
rules for supported inputs and no invented rules for missing inputs. They are
development cases, not independent relevance/market accuracy.

Failure history is retained. `docs/v2-live-initial-check.json` shows an overly
strict acceptance assertion expecting nine rules even for unknown inputs; the
script was corrected to match the documented abstention policy. A subsequent
real run omitted explicit city-commuting usage and asked an unnecessary question;
`docs/v2-live-missing-usage.json` retains that failure. `BUY_USAGE_SOURCE` now
recovers only affirmative, explicit source phrases into an empty usage slot;
negated/unstated phrases are tested. The final two-turn acceptance passed after
this fix. Do not describe these development passes as universal NLU accuracy.

The earlier browser chat displayed a verified V2 buy result and scoped review
details. Browser download automation did not return a new usable file during
this run; no new successful manual-download acceptance is claimed. Existing V1
download acceptance is historical. The final V2 CLI trace and browser screenshots
are separate evidence; one is not presented as the other's export.

After the final module restart, a real browser form submitted budget60000,
5 seats, city use, fuel/luggage/safety/reliability high and comfort medium.
It went through the actual Ollama planner/tools/checks and finished complete:
Top3 CL18625566 (45.710; coverage76.471%), CL18939959 (42.259;64.706%),
PT_K4EDNMNYPG (37.980;52.941%). The score/bounds and asking sources are
visible in `docs/v2-buy-ui.jpg`; AX observations are in
`docs/v2-browser-results.txt`. Read-only research selection displayed the
Persona ambiguity warning and its own attributed review, saved in
`docs/v2-research-ui.jpg` and `docs/v2-browser-research.txt` (AX observation diff).
Research browsing did not start a consultation; the earlier verified buy result
remained when returning to Results. Final local Streamlit service listens only
on127.0.0.1:8501. This is one additional actual form/planner acceptance, separate
from the final two CLI turns and the earlier browser chat.

Reproduce coverage with `python audit_v2.py --output v2-data-audit.json` using
the project interpreter. The audit records file hashes and separates listing
coverage from research coverage. Price date remains **15 Oct 2026**; research
review date **16 Oct 2026**; this acceptance date **17 Oct 2026**, Malaysia time.

Next: usable price data and stronger applicable review coverage → Ridge training
and per-identity evaluation → valuation/negotiation/controller/checker/UI activation
only if supported → independently authored cases and another computer → report,
video, presentation, Q&A and contribution evidence. Cancelled trend/depreciation,
condition/damage calibration, real-deal uplift proof and all vision work are not
reintroduced as requirements. This development acceptance was recorded on
17 Oct before Git delivery; subsequent delivery is recorded in the Git history.
