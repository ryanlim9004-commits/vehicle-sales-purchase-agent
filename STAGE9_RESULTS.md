# Stage 9 browser UI and verification

Reviewed: 16 October 2026. Streamlit 1.66.0, Python 3.13.15, local qwen3:4b. Saved data and reference date: 15 October 2026.

## Delivered scope

- English chat and four consultation areas: Buy, Sell, Negotiation and Trade-In.
- Supplementary forms with strict parsing, explicit unknown/zero handling and identity-dependent quote invalidation through the existing Controller.
- Checked candidate cards/comparison, score breakdown, valuation reference/selection details, negotiation calculations, Trade-In cash paths and source explanations.
- Per-tab state, reset, between-turn stop, bounded history, request deduplication, local-inference serialization and manual JSON download. A busy-model submission is retained with explicit Retry/Discard; it never runs automatically. No automatic chat files.
- Public snapshot labels, including the main page on narrow screens. No current-date selector, live search, market-calibrated adjustments, photo analysis or cloud deployment.

Structured forms skip only model extraction. Their typed patch goes through existing source grounding, memory merge, actual Ollama planning, tool execution and independent checks. Trace distinguishes explicit form input from model extraction. `main.py` and `agent_cli.py` remain available.

## Tests

**152 test methods passed in the final full regression run (10.087 seconds): 134 existing methods plus 18 new UI/form/session methods.** Multiple methods include subtests.

The new tests cover unit normalization, MYR cents precision, blank/unknown/zero semantics, unsupported fields, list replacement, household clarification, invalidating old quotes, actual buy/sell/negotiation/trade-in tools, checked-result display gates, safe source links, tab isolation, reset and read-only export. Actual Streamlit AppTest exercises initial render, navigation, reruns, form/chat submissions, candidate cards and all financial result renderers using a scripted model backend. Final review added regression tests that hold the actual shared lock, check retained request IDs, explicitly retry exactly once and discard/reset without model calls. Valuation ranges retain two decimal places and use wrapping text. Business tools are real. A scripted backend is used only by tests; production has no fake model fallback.

```powershell
.\.venv\Scripts\python.exe -m unittest -q test_profile test_matching test_scoring test_valuation test_input_grounding test_stage5_audit test_negotiation test_agent test_streamlit_ui
```

`pip check` passed. Exact installed versions are saved in requirements-lock.txt. The first sandbox AppTest attempt encountered Windows temporary-directory permissions and was stopped; acceptance runs outside that sandbox passed. A narrow-screen visual check found truncated metric prices, corrected by using wrapping normal-sized price text; the final regression includes the updated presentation assertion.

## Actual browser + Ollama evidence

| Scenario | Observed result | Evidence |
|---|---|---|
| English buyer chat | Missing budget/seats/use prompted; fuel priority recorded | stage9-browser-buy.json |
| Form answer in the same tab | Budget60000, household6, city commuting, excludeToyota; fuel preference retained; three checked Alza candidates | stage9-browser-buy.json |
| Manual browser download | Downloaded JSON parsed and verified against actual facts/tool checks | Four stage9-browser-*.json files |
| Browser reload | New tab session state appeared as Not started; no automatic history restoration | Observed in browser |
| Complete Trade-In form | Actual planner linked the old Alza asking context44800; user gross offer35000 remained separate; cash differences41500/37000, private sale suggested | stage9-browser-trade.json |
| Results and sources | Two cash paths, known fees/loan, signed outlays and source links displayed | docs/stage9-trade-ui.jpg |
| English seller chat after restarting the updated server | 50000 m grounded to 50 km, actual asking median44800, no calibrated adjustment, all eight checks passed | stage9-browser-sell.json; docs/stage9-sell-ui.png |
| English chat switches Sell to Negotiation | Total budget46000 minus complete fees1500 gives bare-price cap/counter44500; asking context44800 stays separate, all five checks passed | stage9-browser-negotiation.json; docs/stage9-negotiation-ui.png |

These are five unique actual model-driven browser turns in total: two buying turns, one Trade-In turn, one seller turn and one negotiation turn. The negotiation export also contains the preceding seller turn; do not count that duplicated history as another execution. All four business areas have a live browser scenario, but not every form/role/error pathway was exercised with a real model. Broader form/tool/result rendering passed offline AppTest/Controller checks. Previous Stage 8 live evidence remains separate.

The final browser rerun initially exposed a stale imported ui_session module in the already-running development server after its public helper changed. Restarting that server loaded the updated module; the final selling/negotiation runs and screenshots are from the restarted process. Restart guidance is in STAGE9_GUIDE_ZH.md. This observed failure is not counted as a successful consultation.

All customer preferences/financial quotes are synthetic teaching inputs. The source-backed asking advertisements are frozen snapshots. The exports record actual tools, observations and checks; they are not fabricated transcripts. These are development acceptance cases, not holdout understanding accuracy, recommendation relevance, market valuation accuracy or transaction success.

## Operating boundaries and remaining work

The server listens on127.0.0.1:8501. One local task runs at a time. Another tab retains its submission in memory without applying facts; the user explicitly chooses Retry, Discard or Reset. Other editing is disabled until that draft is resolved. A free model does not automatically execute a retained draft. Reload/close/server restart may lose temporary state. Stop is between turns, while in-flight model work uses existing request/turn deadlines. Failed or incomplete responses do not populate current verified result panels. Date checks on saved data and live data retrieval remain distinct deferred features, as explicitly agreed by the user.

Further work: independent holdout/system evaluation, teammates reproducing installation on their own computers, data/comparable coverage, report, video, presentation/Q&A and contribution evidence. See REMAINING_WORK_ZH.md. Delivery history is recorded by Git commits; completion of this stage does not establish completion of the whole assignment.
