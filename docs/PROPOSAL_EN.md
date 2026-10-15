# Vehicle Sales and Purchase Consultation Agent System

Status: design proposal, not an implementation report. Lecturer approval of the project plan was confirmed by the user on 13 October 2026. Team size: five. Working submission date: 2 November 2026; submission time remains unspecified.

## Purpose and problem

Vehicle buyers may know their lifestyle needs but struggle to translate them into vehicle specifications. Sellers may also have difficulty interpreting comparable prices and deciding how to respond to offers. This project proposes a local consultation agent that turns natural-language goals into structured requirements, invokes vehicle consultation tools, checks their results, and explains recommendations with traceable evidence.

The system will support three core tasks: lifestyle-based vehicle matching, rule-based vehicle valuation, and negotiation/trade-in advice. It will help users make informed decisions within the supplied dataset. It will not guarantee the highest selling price or execute a vehicle transaction.

## Scope

The initial design focuses on used passenger vehicles in Malaysia and prices in MYR. This is a working domain assumption. Users can describe their budget, passenger requirements, travel habits, and priorities in English. Vehicle information will be stored in a small curated local knowledge base with provenance and observation dates. Availability will refer to the dataset, not a live stock guarantee.

Core functions:

1. **Persona/Lifestyle-Based Matching:** extract hard constraints and preferences, derive requirements through rules, filter eligible vehicles, and rank candidates with weighted feature scores.
2. **Intelligent Valuation Engine:** identify comparable records and apply documented mileage and condition adjustments to produce a reference estimate/range. Insufficient comparables will result in an explicit insufficient-evidence response. Historical trend estimation will only be claimed if suitable dated data becomes available.
3. **Negotiation/Trade-In Advisor:** use a hand-authored decision tree and deterministic calculations to assess offers against valuation evidence, budgets, and user-provided limits; compare trade-in with private-sale scenarios.

Multimodal exterior assessment and trained regression are optional extensions after the core system is validated.

## AI techniques and knowledge representation

The proposed system combines symbolic domain reasoning with a pretrained local language model.

- **NLP/NLU/NLG:** a model served by Ollama extracts intent and slots and generates explanations based on verified tool outputs. The team will use pretrained inference rather than train a language model.
- **Frames:** VehicleFrame, BuyerProfileFrame, and SellerVehicleFrame define slots, types, ranges, unknown values, and selected class/instance inheritance. The frames provide explicit structured domain knowledge.
- **Production Rules and Forward Chaining:** facts activate IF–THEN rules and derive intermediate requirements. For example, a six-person household produces a minimum-seat requirement, which excludes five-seat vehicles. Rule identifiers and derived facts support explanations.
- **Rule-Based Expert System:** the valuation engine combines a knowledge base, inference process, and explanation facility. Rules will distinguish documented evidence from illustrative assumptions.
- **Weighted Multi-Criteria Scoring:** eligible vehicles receive normalized preference scores. This is a transparent ranking method, not a trained ML model or A* search.
- **Hand-authored Decision Tree:** negotiation branches are explicitly defined and testable. The tree is not a trained classification model.

Formal fuzzy inference will only be claimed if membership functions and an inference/aggregation procedure are implemented and evaluated. Regression will only be claimed as a trained technique if a suitable dataset and independent evaluation are available.

## Architecture and agent workflow

The application will use Python, Ollama, a Streamlit interface, a local structured vehicle knowledge base, and schema validation. A single agent controller will manage user requirements, tool selection, tool execution, validation, retries, and stopping conditions.

The agent follows a bounded loop:

1. Interpret the user's goal and update task state.
2. Request essential missing information or select the next allowed tool.
3. Execute the tool through Python.
4. Observe and validate constraints, identifiers, numerical values, and evidence.
5. Continue, clarify, or finish with a grounded explanation.

The agent will support changing requirements across turns. It will not silently relax hard constraints or invent vehicle records. It will display a short decision trace consisting of relevant facts, fired rules, tools used, and validation outcomes.

The confirmed development machine has an RTX 3050 Laptop GPU with 4 GB VRAM and approximately 13.9 GiB system-visible RAM. qwen3:4b is an initial candidate; qwen3:1.7b is a fallback. Selection depends on observed extraction quality, tool use, latency, and memory consumption.

## Data and evaluation

An initial target of 30–50 curated records will support a demonstrable prototype; this is a project planning target, not an official course requirement. Records will distinguish listing asking prices from transaction labels, include source/date information, and represent missing values explicitly. Synthetic fixtures may test calculations but will not validate real market accuracy.

The initial evaluation set will contain 30 scenarios: ten matching, eight valuation, six negotiation/trade-in, and six exceptional/boundary scenarios. The team will measure intent/slot correctness, hard-constraint violations, recommendation relevance, agreement with independently calculated rule fixtures, tool-selection correctness, task completion, error recovery, and response latency. Matching will be compared with a basic filtering baseline. Valuation accuracy against real prices will only be evaluated when independent suitable labels exist.

## Development and deliverables

Development proceeds through specification and data design, isolated domain tools, Ollama integration, agent loop and interface, evaluation, and submission preparation. The final week prioritizes verified core behavior and assessment evidence.

Deliverables include the operational system, report with Introduction/Literature Review/Methodology/Implementation/Conclusion, final demonstration, video, individual contribution justifications, and workload matrix. Actual implementation challenges and results will be recorded during development rather than invented in advance. All members will understand the complete workflow and explain their own contributions.

## References for implementation

Course sources are indexed in `PROJECT_CONTEXT.md` and `source-manifest.json`. Lecturer adaptations are distinguished there from the original chatbot brief.

- Ollama tool calling: https://docs.ollama.com/capabilities/tool-calling
- Ollama structured outputs: https://docs.ollama.com/capabilities/structured-outputs
- Model candidate: https://ollama.com/library/qwen3:4b
- Fallback: https://ollama.com/library/qwen3:1.7b
- Streamlit chat interface: https://docs.streamlit.io/develop/api-reference/chat
- Python SQLite integration: https://docs.python.org/3/library/sqlite3.html

These links are technical references. A full academic literature review and APA reference list will be developed separately.
