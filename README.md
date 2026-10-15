# Vehicle Sales and Purchase Consultation Agent System

An educational Python + Ollama project for used-vehicle consultation in Malaysia. Application prompts, inputs and outputs use English; accompanying Chinese lessons explain the implementation for beginners.

**Status, 15 October 2026:** buyer extraction, rule inference, hard-constraint matching, lifestyle scoring, and seller asking-price reference tools are implemented. The CLI selects actions explicitly. Dynamic Agent Loop, conversation memory, negotiation/trade-in advice and Streamlit UI are planned.

## Implemented features

- **Frames:** BuyerProfileFrame, SellerVehicleFrame and VehicleFrame, including typed slots, unknown values, validation and selected inheritance.
- **Production Rules + Forward Chaining:** derive passenger requirements and lifestyle facts, with rule traces.
- **Hard constraints:** enforce budget, minimum seats and excluded brands before ranking.
- **Weighted Scoring:** explain preference contributions and missing feature coverage; weights are hand-authored, not learned.
- **Rule-Based Valuation:** select comparable listing snapshots and calculate a traceable median and observed asking-price range.
- **Input grounding:** check explicit measurement units and budget currencies against the original message. Unsupported or conflicting readings trigger clarification.

Ollama extracts structured facts; Python validates them, applies domain rules and calculates results. The current CLI does not yet implement autonomous tool selection.

## Setup on Windows PowerShell

Use Python 3.13 (the tested version is 3.13.15) and install Ollama separately. From this repository directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
ollama pull qwen3:4b
```

Keep the Ollama service running at `http://127.0.0.1:11434`. Model weights and virtual environments are not included in Git. Manual JSON fixtures and unit tests do not require Ollama.

## Run

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

Use `main.py --help` for all options. Select exactly one of `--text` and `--fixture`; actions `--match`, `--rank` and `--value` are mutually exclusive. `--vehicles` accepts another validated dataset. Paths in these examples assume the current directory is the repository root.

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
.\.venv\Scripts\python.exe -m unittest -q test_profile test_matching test_scoring test_valuation test_input_grounding
```

The current baseline has **59 passing test methods**, some containing multiple subtests. Saved local-model evaluations are development evidence, not comprehensive extraction or market accuracy measurements. Live evaluation scripts require a running Ollama service.

## Repository guide

| Files | Purpose |
|---|---|
| `main.py`, `buyer_profile.py`, `seller_profile.py` | CLI and structured extraction |
| `input_grounding.py` | Source-text unit/currency checks |
| `vehicle_frame.py`, `matching.py`, `scoring.py` | Vehicle knowledge representation, filtering and ranking |
| `valuation.py` | Comparable selection, reference calculation and explanation |
| `data/`, `examples/` | Curated data, receipts and manual fixtures |
| `test_*.py`, `evaluate_*.py`, `audit_input_cases.py` | Unit tests and model evaluations |
| `STAGE*_RESULTS.md`, evaluation JSON files | Dated implementation evidence |
| [Chinese lessons](README_ZH.md) | Beginner learning entry point |
| [Input validation fix](INPUT_VALIDATION_FIX_ZH.md) | Reproduction, correction and regression evidence |
| [Accelerated plan](ACCELERATED_PLAN_ZH.md) | Current delivery schedule |
| [Original proposal](docs/PROPOSAL_EN.md) | Historical design intent; current status above takes precedence |

Original lecture slides, course guide PDFs, uploaded attachments, local chat context, unrelated assignments, credentials and installed model weights are not included. The original course chatbot guide and the lecturer-approved agent adaptation are distinct sources; this project does not claim an officially replaced rubric.

## Team workflow

Use a feature branch for each change, run the relevant tests, then open a pull request for review before merging into `main`. Record actual responsibilities and evidence in the assignment workload matrix; commit counts alone do not measure individual contributions.
