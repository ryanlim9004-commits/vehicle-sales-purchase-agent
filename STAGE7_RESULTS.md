# Stage 7 results — 15 October 2026

Implemented explicit NegotiationFrame / TradeInFrame, a hand-authored buyer/seller decision tree, a deterministic cash calculator, and manual-fixture CLI actions `--negotiate` / `--trade-in`.

- Full regression: **94 test methods passed**, including **27 new methods** in test_negotiation.py, some with subtests and invariant grids.
- `evaluate_negotiation.py`: **8 acceptance cases passed**, using five actual CLI runs and three direct tool scenarios. Full inputs, outputs, rule traces and expected values are retained in stage7-results.json.
- Buyer example: vehicle quote46000 + fees1500 > budget46000; suggested vehicle counter44500.
- Seller example: bid40000 - fees1000 - settlement5000 = net34000 < minimum38000; floor44000; linked asking median yields counter44800.
- Trade-in example: additional cash41500 versus private-sale37000; private-sale cash advantage4500.
- Distinct replacement package prices can reverse the result: trade-in replacement60000 produces additional cash36500, advantage500 over private sale.
- Unknown or partial fees withhold the affected total and overall financial comparison. Time/effort comparisons require user estimates. Cash limits override preference selection.

Consultation quotes and time/effort estimates are synthetic teaching fixtures. Linked valuation uses the actual valuation tool and existing real-source listing snapshots; asking-price references do not establish fair transaction values. No new Ollama extraction, dynamic Agent Loop, UI, executed transaction or market-success evaluation was implemented or claimed.

No new dependencies. Changes remain local; no automatic commit/push. Beginner instructions: STAGE7_GUIDE_ZH.md.
