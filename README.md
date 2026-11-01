# Vehicle Sales and Purchase Consultation Agent System

An educational Python + Ollama project for used-vehicle consultation in Malaysia. Application prompts, inputs and outputs use English; accompanying Chinese lessons explain the implementation for beginners.

**1 Nov financial logic audit:** Negotiation/Trade-In now invalidate fee confirmation after quote/fee changes, preserve package scope, clear role-dependent values when buyer/seller roles switch, and clarify inclusive/net amounts before calculation. Explicit current/old-vehicle damage is inspection-first, including older saved seller handoffs. Missing requested speed/effort estimates produce named follow-up questions with route/unit checks. Result verification recomputes the policy/reference and retains independent cash arithmetic. **308 offline tests and six actual local Ollama turns passed**, including 21 financial-audit methods. See [fixed issues, examples and remaining limitations](FINANCIAL_AUDIT_20261101_ZH.md) and [acceptance evidence](docs/financial-audit-acceptance-20261101.json). This strengthens software consistency; it does not add current market coverage, authenticate quotes, itemise overlapping costs, verify equivalent replacement cars, or model new-loan interest.

**1 Nov question guidance / Axia fix:** Sell, Negotiation and Trade-In questions append examples from the actual Controller catalogue. It loads 114 records and has no Axia. Missing exact coverage now produces one clear notice plus explicitly labelled format examples from other saved models; these never change the user's vehicle or become price evidence. Quote/fee/loan/mileage/time formats and all form guidance are directly visible. Numeric form placeholders omit units/currency symbols and never prefill values. **287 offline tests passed**, including 13 guidance checks. See [Chinese usage and scope](QUESTION_EXAMPLES_20261101_ZH.md) and [latest acceptance](docs/question-examples-axia-acceptance-20261101.json); [initial 283-test acceptance](docs/question-examples-acceptance-20261101.json) remains historical.

**31 Oct historical Regression:** A trained NumPy Ridge fallback now combines eligible saved ads and historical teaching records (111 training source groups after exclusions). Sell tries exact real comparables first; when insufficient, evaluated Alphard/Harrier inputs within seen variant/year/mileage ranges can obtain a clearly labelled historical prediction. Negotiation can use it as a bounded discussion anchor; Trade-In retains explicit user quotes. Alza/Vellfire fail this development error policy and remain disabled for Regression. This is not a current market model. See [Chinese operation/training guide](HISTORICAL_REGRESSION_GUIDE_ZH.md), [model development results](docs/historical-regression-results.json), [acceptance record](docs/historical-regression-acceptance.json) and [English report notes](docs/HISTORICAL_REGRESSION_REPORT_NOTES.md). No new dependencies.

Historical-fallback acceptance: **274 offline tests passed**; three real local Ollama/planner scenarios completed with passing tool checks. Streamlit rendering was checked with AppTest, separately from real-browser operation; results do not establish current market accuracy or independent recommendation relevance.

**31 Oct recommendation display update:** Buy chat replies and main cards now show ranked vehicle information with reference prices, seats, transmission, mileage and available fuel references. Internal IDs move to expandable **Vehicle details and sources** and remain in **Evidence & checks**. Repeated simulation notices and scoring explanations are removed from the primary recommendation; provenance and simulation assumptions remain in structured evidence and the report notes. Earlier screenshots/acceptance outputs below reflect their dated display versions.

**31 Oct simulation integration:** The Agent/UI load 114 records: 17 original listing snapshots plus 97 user-completed historical simulation records (21 makes, 62 make/model pairs). Simulation prices/seats support Buy demonstrations; unknown listing dates stay unknown. Mixed-cycle/approximate fuel references are displayed without unsupported fuel ranking. They remain excluded from exact market comparables and the market-approved training manifest; the later user-authorised historical regression experiment is described above. See the [step-by-step guide](SIMULATION_DATA_GUIDE_ZH.md), [data audit](docs/simulation-data-audit.json) and [English report notes](docs/SIMULATION_DATA_REPORT_NOTES.md). Older snapshot-only results below are historical evidence.

**26 Oct menu and cancellation:** Results, evidence and research are accessed from the right-side hamburger **Menu**. The app's **Stop** button cancels an active streamed Ollama request through its owned worker process. A background turn uses isolated memory; cancellation discards unfinished updates and allows the next request without shutting down the page. See [verification and limits](STOP_MENU_20261026_ZH.md).

**26 Oct palette:** Brick red `#B80C09` highlights primary actions, dark brown `#6B2B06` marks headings, and `#E5E7E6` / `#B7B5B3` provide the main and sidebar surfaces. White input cards and dark body text support readability. See the [current page](docs/palette-20261026.png) and [scoped interface verification](docs/palette-20261026.json).

**26 Oct input experience:** The chat composer is highlighted and placed inside the consultation above the collapsed helper form. Confirmed session inputs are behind a **View confirmed details** button with readable labels. Amounts such as `RM1 million` in chat and `1million` in MYR form fields are checked against the complete source text; unsupported formats receive correction examples. A customer budget is an upper bound, not limited by saved listing prices. See the [input guide](INPUT_GUIDANCE_20261026_ZH.md).

**26 Oct update:** [Buy follow-up clarification fix](BUY_FOLLOWUP_FIX_20261026_ZH.md) resolves stale driving-use questions, preserves stated travel wording, clarifies ambiguous "safe fuel" and handles named no-preference answers in chat and forms. All 232 offline tests and the final three-turn actual Ollama replay passed; actual browser conversation evidence and earlier failures are retained separately. [Malaysia dataset integration plan](DATA_IMPORT_PLAN_ZH.md) explains the existing JSON storage and proposed historical candidate pipeline; no SQL Server installation is needed. Historical Kaggle rows are not activated stock or approved regression training data. Verification records identify the development source before its subsequent Git delivery.

**22 Oct development record:** [Driving-use memory and form fix](USAGE_FIX_20261022_ZH.md): 213 offline checks and two actual Ollama checks passed. Driving use is now a multiselect. [Kaggle candidate review](docs/KAGGLE_RESEARCH_20261022.md) rejects the supplied synthetic dataset and records a quarantined historical Malaysian alternative; active stock and regression approval are unchanged. These are historical checks; the 26 Oct record describes the later fix.

**New teammates: start with the [step-by-step Windows setup and test guide](TEAM_GUIDE_ZH.md).** It covers GitHub access/clone, Python/Ollama installation, the exact browser entry point, four consultation scenarios, local reports and troubleshooting. Use the [test record template](TEAM_TEST_RECORD_TEMPLATE_ZH.md) and [independent-case instructions](evaluation/INDEPENDENT_CASES_GUIDE_ZH.md). [Handoff verification and remaining work](TEAM_HANDOFF_RESULTS.md) separates local installation checks from actual teammate reproduction.

After the first-time installation in that guide, the main commands are:

```powershell
.\.venv\Scripts\python.exe team_check.py --ollama
.\.venv\Scripts\python.exe run_team_tests.py --tester YOUR_NAME
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

The app entry point is `streamlit_app.py`, launched with Streamlit. Local reports now default to timestamped files under ignored `team_results/`; `evaluate_v2_live.py --tester YOUR_NAME` preserves the committed historical results. These scripts do not automatically upload or notify anyone.

**Status, 17 October 2026:** V2 formal Sugeno fuzzy ranking, optional safety/comfort/reliability priorities and scoped reference research are connected to the existing Agent and English Streamlit UI. See [V2 Chinese guide](V2_GUIDE_ZH.md), [acceptance and remaining gaps](V2_RESULTS.md) and [source audit](docs/V2_SOURCE_AUDIT.md). There are 7 research profiles for 6 model names, distinct from the unchanged 17 asking-price advertisements. Reliability values remain Unknown because evidence is insufficient. Ridge training/evaluation preparation exists, but no Malaysian price model has been trained or enabled. Independent evaluation, usable price-data expansion, cross-computer reproduction and final assignment materials remain pending.

V2 is the default for Agent/UI and `main.py --rank`. Use `--ranking-policy v1` for the preserved weighted baseline; historical ranking evaluation files describe v1. The research tab never adds stock or makes budget-eligibility claims. Prices remain the 15 Oct snapshot; reference research was checked 16 Oct, not live inventory.

**Learning notes:** the historical annotation-only revision covered 34 Python modules and 275 class/function definitions, preserving their ASTs and passing the then-current 134 tests. Stage 9 adds functional code with English explanations; the old `comment-only-verification.json` is historical evidence, not a claim that the UI revision leaves behavior unchanged. Start with the [Chinese code guide](CODE_GUIDE_ZH.md), [command reference](COMMANDS_ZH.md) and [JSON reference](docs/JSON_FILES_GUIDE_ZH.md).

Start the browser interface with the installed project environment:

```powershell
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

Open `http://127.0.0.1:8501`. The data/reference baseline remains 15 Oct 2026; no current-date selector or live search is included. The 26 Oct layout removes the snapshot sidebar block and its reset/stop/download buttons, plus the two technical/snapshot captions below the page introduction. Record-level sources and dates remain in results/evidence. Use `/reset` or `/stop` in chat between turns. Keep Ollama and the Streamlit process running. See the [Stage 9 beginner guide](STAGE9_GUIDE_ZH.md).

## Implemented features

- **Frames:** BuyerProfileFrame, SellerVehicleFrame and VehicleFrame, including typed slots, unknown values, validation and selected inheritance.
- **Production Rules + Forward Chaining:** derive passenger requirements and lifestyle facts, with rule traces.
- **Hard constraints:** enforce budget, minimum seats and excluded brands before ranking.
- **Weighted Scoring:** explain preference contributions and missing feature coverage; weights are hand-authored, not learned.
- **Rule-Based Valuation:** select comparable listing snapshots and calculate a traceable median and observed asking-price range.
- **Input grounding:** check explicit measurement units and budget currencies against the original message. Unsupported or conflicting readings trigger clarification.
- **Negotiation / Trade-In:** hand-authored buyer/seller limits and asking-reference rules; explicit fees, loan settlement and path-specific replacement quotes; user-estimated time/effort and cash limits.
- **Agent Loop:** typed conversation memory, source-grounded updates, a tool allowlist, checked observations, bounded retries/timeouts and inspectable facts/rules/tools/checks.
- **Browser UI:** English chat and typed update forms over the same Controller, per-tab temporary memory and checked result panels. The consultation download button was removed in the 26 Oct layout revision.

Ollama extracts fact patches and proposes tools through schema-constrained JSON requests; Python validates, executes, checks and renders verified results. This is a bounded hybrid controller, not a claim of verified native Ollama `tool_calls` support. Earlier native-protocol failures are retained in the development evidence.

## Setup on Windows PowerShell

Use Python 3.13 (the tested version is 3.13.15) and install Ollama separately. From this repository directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
ollama pull qwen3:4b
```

Keep the Ollama service running at `http://127.0.0.1:11434`. Model weights and virtual environments are not included in Git. Manual JSON fixtures and unit tests do not require Ollama.

## Run

Start the multi-turn Agent (no new dependencies needed on the existing installation):

```powershell
.\.venv\Scripts\python.exe agent_cli.py --as-of 2026-10-15
```

At `You:`, enter `I want to buy a car. Save fuel.`, answer its questions, then try `Change my budget to RM35000.`. `/reset` clears the session, `/stop` cancels the consultation while retaining facts, and `/quit` exits. Optional persistence and a reproducible dialogue:

```powershell
.\.venv\Scripts\python.exe agent_cli.py --session sessions/demo.json --as-of 2026-10-15
.\.venv\Scripts\python.exe agent_cli.py --script examples/agent_buy_dialogue.json --as-of 2026-10-15
.\.venv\Scripts\python.exe agent_cli.py --message "I want to buy a car. Budget RM50000, at least five seats, mainly city commuting." --as-of 2026-10-15 --json
```

Session files stay local and are ignored by Git. The historical `--as-of` date reproduces the saved teaching snapshot; it does not refresh listings or establish current market evidence. See the [Stage 8 guide](STAGE8_GUIDE_ZH.md) for selling, negotiation, Trade-In and trace inspection.

The following `main.py` commands run individual tools:

Extract a buyer profile and run inference:

```powershell
.\.venv\Scripts\python.exe main.py --text "Budget RM60000, six-person family, mainly city commuting, save fuel."
```

Filter synthetic demonstration records without Ollama:

```powershell
.\.venv\Scripts\python.exe main.py --fixture examples/family_no_toyota.json --match
```

Rank eligible vehicles from the curated real-source snapshots:

```powershell
.\.venv\Scripts\python.exe main.py --fixture examples/city_buyer.json --rank
```

Calculate a seller reference from the saved snapshot:

```powershell
.\.venv\Scripts\python.exe main.py --fixture examples/seller_alza.json --value --as-of 2026-10-15
```

Check natural-language mileage conversion:

```powershell
.\.venv\Scripts\python.exe main.py --text "I want to sell my Perodua Alza 1.5 SE, manufactured in 2020, automatic, 50000 m, fair condition. No major accident and no flood damage." --value --as-of 2026-10-15
```

The normalized mileage should be **50.0 km**, with an explanation in `input_validation_notes`. Missing units are clarified rather than guessed.

Run the manual negotiation and trade-in tools without Ollama:

```powershell
.\.venv\Scripts\python.exe main.py --fixture examples/negotiation_buyer.json --negotiate --valuation-seller examples/seller_alza.json --as-of 2026-10-15
.\.venv\Scripts\python.exe main.py --fixture examples/trade_in.json --trade-in
```

The buyer counter is 44500 MYR under the stated total budget. The synthetic trade-in example requires 41500 MYR additional cash versus 37000 MYR after private sale. Fees must be explicit and confirmed complete; missing or partial fees are never silently treated as zero. See [Stage 7 instructions](STAGE7_GUIDE_ZH.md) for definitions and seller/unknown-fee examples.

Use `main.py --help` for all options. Select exactly one of `--text` and `--fixture`; actions `--match`, `--rank`, `--value`, `--negotiate` and `--trade-in` are mutually exclusive. Stage 7 actions in this explicit CLI require `--fixture`; use `agent_cli.py` for natural-language negotiation/Trade-In. `--valuation-seller` runs the actual valuation tool and links its observation by vehicle identity/date for either action. In the Agent, a known vehicle identity enables an identity-only asking reference without inventing mileage or condition. An asking reference never supplies a missing trade-in cash offer. `--vehicles` accepts another validated dataset. Paths in these examples assume the current directory is the repository root.

## Data and valuation limits

- `data/vehicles_demo.json` contains eight fictional teaching records.
- `data/vehicles_real.json` contains 17 manually curated, source-linked listing snapshots, including sold/reserved records. These are asking prices, not verified transaction prices or live inventory.
- Source receipts, dates, units and data-quality findings are retained under `data/`.
- Default valuation returns `reference_only`; it is not personalized for mileage or condition. At least three eligible comparables are required by the current policy.
- `--illustrative-adjustments` explicitly enables uncalibrated teaching assumptions, labelled `market_validated=false`. This does not establish market valuation accuracy.
- `--as-of 2026-10-15` reproduces the dated teaching snapshot. Do not use a historical date to present old listings as current market evidence.
- Input guards support a bounded set of English forms; they do not guarantee all natural-language extraction is correct.

## Verification

```powershell
.\.venv\Scripts\python.exe run_team_tests.py --tester YOUR_NAME
```

On 19 Oct, **195 offline tests passed** in a fresh virtual environment using a staged-repository export: the earlier 184 tests plus 11 setup/report-preservation boundary tests. Two actual Ollama CLI turns and five tool-command checks also passed. See [handoff results and limitations](TEAM_HANDOFF_RESULTS.md) and the [machine-readable record](docs/handoff-20261019.json). This is an isolated installation on Ryan's computer, not teammate or cross-computer acceptance. Streamlit AppTest covers reruns, forms, all four result types and retained submissions with explicit Retry/Discard. Its model replies are scripted and Python tools are real. Earlier actual Ollama V2 turns and their failure/fix history remain in [V2 results](V2_RESULTS.md). These checks do not establish independent extraction/relevance, market-price or deal-success accuracy. Live evaluation requires Ollama; offline tests do not.

## Repository guide

| Files | Purpose |
|---|---|
| `main.py`, `buyer_profile.py`, `seller_profile.py` | CLI and structured extraction |
| `input_grounding.py` | Source-text unit/currency checks |
| `vehicle_frame.py`, `matching.py`, `scoring.py` | Vehicle knowledge representation, filtering and ranking |
| `fuzzy_lifestyle.py`, `lifestyle_v2.py`, `vehicle_evidence.py` | V2 Sugeno rules, ranking and scoped safety/review references |
| `price_regression.py`, `audit_v2.py` | Gated inactive Ridge experiment and reproducible data-coverage audit |
| `historical_price_regression.py`, `evaluate_historical_live.py` | Separate trained historical Ridge fallback, per-model development gates and real Ollama acceptance |
| `valuation.py` | Comparable selection, reference calculation and explanation |
| `consultation_frames.py`, `negotiation.py`, `trade_in.py` | Explicit quotes, decision tree and cash comparison |
| `agent_state.py`, `agent_grounding.py` | Typed memory, goal changes and grounded fact updates |
| `agent_tools.py`, `agent_controller.py`, `agent_cli.py` | Tool registry, execution/check loop and multi-turn CLI |
| `streamlit_app.py`, `form_inputs.py`, `ui_session.py` | English browser presentation, validated form adapter and per-tab state/export |
| `data/`, `examples/` | Curated data, receipts and manual fixtures |
| `test_*.py`, `evaluate_*.py`, `audit_input_cases.py` | Unit tests and model evaluations |
| `STAGE*_RESULTS.md`, evaluation JSON files | Dated implementation evidence |
| [Chinese lessons](README_ZH.md) | Beginner learning entry point |
| [V2 guide](V2_GUIDE_ZH.md), [V2 results](V2_RESULTS.md) | Current scope, formulas, commands, actual verification and remaining data gates |
| [Code reading guide](CODE_GUIDE_ZH.md) | Python concepts, file responsibilities, algorithms and test interpretation |
| [Command reference](COMMANDS_ZH.md) | PowerShell commands, CLI flags, prerequisites and output files |
| [JSON reference](docs/JSON_FILES_GUIDE_ZH.md) | Dataset, fixture, evaluation and session field explanations |
| [Input validation fix](INPUT_VALIDATION_FIX_ZH.md) | Reproduction, correction and regression evidence |
| [Stage 5/6 acceptance review](STAGE5_STAGE6_REVIEW_ZH.md) | Requirements, fixes, current boundaries and verification |
| [Data dictionary](docs/DATA_DICTIONARY.md) | Record grain, units, evidence and unknown-value rules |
| [Stage 7 guide](STAGE7_GUIDE_ZH.md) | Negotiation, fee semantics, trade-in formulas and manual execution |
| [Stages 1–7 audit](STAGES1_7_AUDIT_ZH.md) | Scope, repairs, asking-price evidence and remaining gaps |
| [Stage 8 guide](STAGE8_GUIDE_ZH.md) | Multi-turn execution, memory, corrections, limits and traces |
| [Stage 9 guide](STAGE9_GUIDE_ZH.md) | Browser startup, four tasks, forms, sources and evidence capture |
| [Stage 9 decisions](docs/STAGE9_DECISIONS.md) | User-confirmed scope, date policy and integration boundaries |
| [Accelerated plan](ACCELERATED_PLAN_ZH.md) | Current delivery schedule |
| [Original proposal](docs/PROPOSAL_EN.md) | Historical design intent; current status above takes precedence |

Original lecture slides, course guide PDFs, uploaded attachments, local chat context, unrelated assignments, credentials and installed model weights are not included. The original course chatbot guide and the lecturer-approved agent adaptation are distinct sources; this project does not claim an officially replaced rubric.

## Team workflow

Use a feature branch for each change, run the relevant tests, then open a pull request for review before merging into `main`. Record actual responsibilities and evidence in the assignment workload matrix; commit counts alone do not measure individual contributions.
