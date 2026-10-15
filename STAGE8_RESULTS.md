# Stage 8 implementation and verification

Reviewed: 15 October 2026. Model: local qwen3:4b. Application language: English.

## Implemented scope

The bounded hybrid Agent follows: understand goal → inspect required facts → ask or request a business tool → execute → independently check → continue or finish. Typed memory preserves confirmed facts across turns; explicit corrections, goal changes, candidate selection, reset and optional local session persistence are supported.

The model requests tools through schema-constrained JSON. Python validates the allowlist and arguments, constructs parameters from checked facts, executes actual tools, returns observations and controls completion. Action choices are constrained by the current stage; business tools are also checked against the active goal. Final English prices and IDs are rendered from checked results. This is not verified native Ollama `tool_calls` support.

Limits: 90 seconds per model request, 240 seconds per turn, one model retry, ten tool requests and two tool repair errors per turn. A separate worker process enforces a cancellable wall-clock request limit. Input, dataset, trace and saved-session sizes are bounded. Unit tests cover actual worker cancellation without requiring network access.

## Verification evidence

- **134 unit test methods passed**, including 40 Agent methods and multiple subtests. These cover memory, source grounding, supported units/types/currencies, invalid corrections, quote roles, fee completeness, goal changes, damage handoff, tool/result validation, timeout/retry/stop limits and session persistence.
- **16 existing fixed-input tool cases passed recheck**: eight Stage 5/6 cases in `stages1-7-tool-recheck.json` and eight negotiation/Trade-In cases in `stage7-recheck.json`.
- `trade-in-reference-recheck.json` verifies that the explicit tool CLI can link an actual asking-price observation while retaining user-provided trade-in quotes and cash arithmetic.
- **Final actual Ollama acceptance: 8/8 turns passed**, comprising seven model-driven turns and one `/reset`. Full inputs, expectations, observations, checks, traces and timings are in `stage8-live-results.json`.

| Goal / turn | Verified outcome | Seconds |
|---|---|---:|
| Buy 1 | Ask for missing budget, seats and use; retain fuel preference | 14.63 |
| Buy 2 | Merge the answer; return three eligible saved Alza listings | 26.54 |
| Buy 3 | Budget correction to RM35000; retain family/fuel facts; no matches | 21.45 |
| Buy 4 | `/reset` clears goal and facts; no model request | 0.00 |
| Sell 1 | 50000 m → 50 km; actual asking median RM44800 | 34.91 |
| Negotiate 1 | Actual asking reference RM44800; buyer counter RM44500 within total budget | 46.26 |
| Trade-In 1 | Correct goal/old-car identity; RM35000 gross quote and RM10000 settlement; ask for missing information | 38.58 |
| Trade-In 2 | Merge remaining quotes; cash differences RM41500/RM37000, private-sale advantage RM4500; separate asking context RM44800 | 62.37 |

The final Trade-In trace includes `compare_trade_in → get_price_reference → compare_trade_in → check_result → finish` after inspection. The controller permits another business call when new evidence is obtained; it checks the final observation before completion. Website asking prices never become missing dealer cash offers.

Run unit checks from the repository directory:

```powershell
.\.venv\Scripts\python.exe -m unittest -q test_profile test_matching test_scoring test_valuation test_input_grounding test_stage5_audit test_negotiation test_agent
```

To repeat the model acceptance with Ollama running (this replaces the named output):

```powershell
.\.venv\Scripts\python.exe evaluate_agent.py --output stage8-live-results-rerun.json
```

## Development failures and repairs

Earlier attempts are preserved rather than counted as successes: `stage8-smoke.json`, `stage8-smoke-fixed.json`, `stage8-structured-smoke.json`, `stage8-valid-actions-smoke.json`, `stage8-live-initial-failures.json`, `stage8-live-before-trade-scope-fix.json` and `stage8-live-before-quote-role-fix.json`.

Native tool-call attempts timed out or returned text without an executable tool call. The accepted implementation switched to schema-constrained JSON requests. Further development runs exposed numeric/boolean/case formatting, incomplete all-fee confirmation, wrong Trade-In goal selection, repeated-goal evidence handling, and a gross trade-in quote assigned to a replacement-price slot. Repairs added lossless type normalization, sentence-level fee exception checks, explicit-intent and goal-scoped extraction, and deterministic quote-role grounding against the user's labels. Corresponding regression cases were added before the final complete rerun.

## Interpretation and remaining work

The eight final turns are development acceptance cases used during debugging. They are not an independent holdout, an all-attempt success rate, a general English understanding accuracy estimate or a market-price validation. Model output and latency may vary on reruns. Quotes, fees and time estimates in these scenarios are synthetic inputs; linked website records are frozen asking-price snapshots.

Data remains 17 saved ads, 11 eligible listing snapshots and only one exact vehicle group with three recent valuation comparables. Transaction labels, independent condition labels, market-calibrated adjustments and independent ranking relevance evaluation remain absent. Horsepower, drivetrain and fuel-tank preferences are not implemented criteria.

Streamlit UI, broader system/holdout evaluation, report, video, presentation/Q&A and contribution evidence remain pending. No additional dependencies were installed. Git history identifies the delivered Stage 5–8 version; local session files are excluded from version control.
