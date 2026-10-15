# Vehicle Sales and Purchase Consultation Agent System

An educational Python + Ollama project for used-vehicle consultation in Malaysia. Application prompts, inputs and outputs use English; accompanying Chinese lessons explain the implementation for beginners.

**Status, 15 October 2026:** the Stage 1–7 consultation tools and Stage 8 bounded Agent Loop are implemented. `agent_cli.py` supports English multi-turn memory, corrections, goal changes, validated tool selection/execution and result checks. `main.py` remains the explicit-action tool CLI. Streamlit UI, independent holdout evaluation and final assignment materials remain pending.

## Implemented features

- **Frames:** BuyerProfileFrame, SellerVehicleFrame and VehicleFrame, including typed slots, unknown values, validation and selected inheritance.
- **Production Rules + Forward Chaining:** derive passenger requirements and lifestyle facts, with rule traces.
- **Hard constraints:** enforce budget, minimum seats and excluded brands before ranking.
- **Weighted Scoring:** explain preference contributions and missing feature coverage; weights are hand-authored, not learned.
- **Rule-Based Valuation:** select comparable listing snapshots and calculate a traceable median and observed asking-price range.
- **Input grounding:** check explicit measurement units and budget currencies against the original message. Unsupported or conflicting readings trigger clarification.
- **Negotiation / Trade-In:** hand-authored buyer/seller limits and asking-reference rules; explicit fees, loan settlement and path-specific replacement quotes; user-estimated time/effort and cash limits.
- **Agent Loop:** typed conversation memory, source-grounded updates, a tool allowlist, checked observations, bounded retries/timeouts and inspectable facts/rules/tools/checks.

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
.\.venv\Scripts\python.exe -m unittest -q test_profile test_matching test_scoring test_valuation test_input_grounding test_stage5_audit test_negotiation test_agent
```

The current baseline has **134 passing test methods**, including 40 Agent methods with multiple subtests. Sixteen existing fixed-input tool scenarios were rechecked in `stages1-7-tool-recheck.json` and `stage7-recheck.json`. The final actual qwen3:4b Agent acceptance passed eight turns across four goals: seven model-driven turns plus `/reset`; see `stage8-live-results.json` and [Stage 8 results](STAGE8_RESULTS.md). Earlier failed development attempts are retained. These checks do not establish holdout extraction, market-price or negotiation-success accuracy. Live evaluation requires a running Ollama service; unit tests and manual tool scenarios do not.

## Repository guide

| Files | Purpose |
|---|---|
| `main.py`, `buyer_profile.py`, `seller_profile.py` | CLI and structured extraction |
| `input_grounding.py` | Source-text unit/currency checks |
| `vehicle_frame.py`, `matching.py`, `scoring.py` | Vehicle knowledge representation, filtering and ranking |
| `valuation.py` | Comparable selection, reference calculation and explanation |
| `consultation_frames.py`, `negotiation.py`, `trade_in.py` | Explicit quotes, decision tree and cash comparison |
| `agent_state.py`, `agent_grounding.py` | Typed memory, goal changes and grounded fact updates |
| `agent_tools.py`, `agent_controller.py`, `agent_cli.py` | Tool registry, execution/check loop and multi-turn CLI |
| `data/`, `examples/` | Curated data, receipts and manual fixtures |
| `test_*.py`, `evaluate_*.py`, `audit_input_cases.py` | Unit tests and model evaluations |
| `STAGE*_RESULTS.md`, evaluation JSON files | Dated implementation evidence |
| [Chinese lessons](README_ZH.md) | Beginner learning entry point |
| [Input validation fix](INPUT_VALIDATION_FIX_ZH.md) | Reproduction, correction and regression evidence |
| [Stage 5/6 acceptance review](STAGE5_STAGE6_REVIEW_ZH.md) | Requirements, fixes, current boundaries and verification |
| [Data dictionary](docs/DATA_DICTIONARY.md) | Record grain, units, evidence and unknown-value rules |
| [Stage 7 guide](STAGE7_GUIDE_ZH.md) | Negotiation, fee semantics, trade-in formulas and manual execution |
| [Stages 1–7 audit](STAGES1_7_AUDIT_ZH.md) | Scope, repairs, asking-price evidence and remaining gaps |
| [Stage 8 guide](STAGE8_GUIDE_ZH.md) | Multi-turn execution, memory, corrections, limits and traces |
| [Accelerated plan](ACCELERATED_PLAN_ZH.md) | Current delivery schedule |
| [Original proposal](docs/PROPOSAL_EN.md) | Historical design intent; current status above takes precedence |

Original lecture slides, course guide PDFs, uploaded attachments, local chat context, unrelated assignments, credentials and installed model weights are not included. The original course chatbot guide and the lecturer-approved agent adaptation are distinct sources; this project does not claim an officially replaced rubric.

## Team workflow

Use a feature branch for each change, run the relevant tests, then open a pull request for review before merging into `main`. Record actual responsibilities and evidence in the assignment workload matrix; commit counts alone do not measure individual contributions.
