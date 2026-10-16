# Stage 9 agreed scope

Confirmed by the user on 16 October 2026 after the grilling design round.

1. English chat is primary; forms supplement/update explicit facts. Both use the same Controller grounding, memory, planner, business tools and independent checks.
2. Memory is private to the current browser tab. Reload/close may reset it. A manual JSON evidence download is provided; no automatic chat files or history restoration.
3. Version 1 uses the saved **15 Oct 2026 snapshot** and a fixed reference-check date. A current-date mode is deferred until after version 1 review.
4. **Current-date checks and live search are different features.** Date checks apply freshness rules to saved records; live search would retrieve new records and require separate source ingestion/validation. Neither is added by a date label.
5. Mileage/condition market calibration, photo assessment and additional vehicle criteria remain optional later work. Default valuation shows the actual unadjusted asking reference and explicitly says no mileage/condition adjustment was applied.

## Integration decisions

- `streamlit_app.py` renders English controls, comparisons and source links; `ui_session.py` owns per-tab presentation state, manual exports and request deduplication.
- `form_inputs.py` validates explicitly entered fields on a copy, then creates canonical evidence and a typed TurnPatch. Blank means keep; Unknown means clear; a stated 0 is a known zero only where allowed.
- Forms do not ask a language model to re-extract already structured fields. `AgentController.handle(..., form_patch=...)` skips that extraction phase only. The same grounding, memory rules, actual Ollama planning, tool calls and result checks still run. The trace marks this as form input, not a model extraction.
- Form fields are not prefilled with old cash quotes. Changing a vehicle identity cannot accidentally reconfirm its old quotes through untouched widgets.
- Browsing areas/tabs is read-only. Submitting in another area explicitly switches the task; a user's explicit chat goal can also switch it.
- The UI displays only checked complete responses as current results. Earlier chat is history; incomplete/failed turn output is not presented as verified pricing.
- One mutable Controller per tab; a shared lock serializes local inference across tabs on the 4 GB GPU. This is a local demonstration, not an authenticated multi-user hosting system.
- Running work disables further app submissions. Stop applies between turns; request/turn deadlines remain responsible for in-flight model timeouts.
- If another tab holds the inference lock, keep the unapplied submission in its originating tab with the same request ID. Only explicit Retry runs it; Discard/Reset clears it. New edits wait until it is resolved, preventing an older draft from overwriting newer facts.
- Bind the server to `127.0.0.1`. No cloud publishing or GitHub push is implied by implementing this stage.
