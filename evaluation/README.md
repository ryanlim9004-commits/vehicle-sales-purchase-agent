# Independent evaluation handoff

Start with [the full Windows setup/test guide](../TEAM_GUIDE_ZH.md),
[the member record template](../TEAM_TEST_RECORD_TEMPLATE_ZH.md) and
[independent-case instructions in Chinese](INDEPENDENT_CASES_GUIDE_ZH.md).

No independently authored teammate cases have been confirmed in this repository.
The empty template is preparation, not submitted evidence or a contribution log.

1. Each of the other four members can independently write five English cases
   before looking at rankings: everyday buying, contradictory/unknown inputs,
   selling without sufficient comparables, negotiation fees and trade-in loans.
   Twenty cases is a manageable course target, not a guarantee of statistical power.
2. Include the author/date, expected hard constraints, acceptable outcome and
   reasoning/source basis. Unknown must be an acceptable outcome when evidence
   is missing. Freeze a copy/hash before execution. Do not fill results in advance.
3. For buying, present v1 and v2 outputs under shuffled labels to reviewers.
   Score relevance: 0 unsuitable, 1 partly suitable, 2 suitable with supported
   reasons. Count hard-constraint violations separately; a nice explanation
   cannot compensate for violating budget/seats/excluded brands.
4. Check prices/fees/loan arithmetic with an independent hand calculation.
   Check source-year/variant applicability, disclosed unknowns and proper
   abstention. This does not measure real deal completion or transaction accuracy.
5. Record disagreements and include all cases. If these cases are used to tune
   rules, relabel them development cases and obtain new independent cases.
6. Another member follows requirements-lock.txt on a clean Python 3.13 setup,
   downloads the same qwen3:4b model, runs offline tests, starts Streamlit and
   exports one real consultation. Record hardware, versions, result and failures.

Use synthetic financial quotes for tests and label them. Do not submit private
customer/VIN/contact data to the repository. Keep anonymous verified duplicate
groups separate from any restricted raw records when price data becomes available.
