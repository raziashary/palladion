# Research and later comparison protocol

Status: **P02 retrieval-only pilot in progress; no full answer-system experiments executed**. Governing source: blueprint “Research
evaluation,” “Questions deliberately left to experiments,” “Prototype environment.”
Research records follow [ADR-0007](ADR_LOG.md#adr-0007--research-discipline-and-gate-meanings).
No metric below is a measured Palladion result.

## Question and falsifiable hypotheses

Can this bounded evidence-first harness reduce unsupported answers over simpler RAG
without unacceptable latency, cost, excessive abstention or lost investigation usefulness?

| Hypothesis | Treatment / control | Evidence against the hypothesis |
|---|---|---|
| H01: hybrid discovery helps | B1 vs B0, fixed corpus/model/scope | Recall or downstream support unchanged/worse, or costs exceed frozen tradeoff target |
| H02: context/reranking finds exceptions | B2 vs B1 | Exception recall/support unchanged or valid sources displaced |
| H03: time-aware policy prevents invalid directives | B4 vs declared B2 or B3 parent, otherwise fixed | Temporal failures/unsupported actions persist or false vetoes erase useful decisions |
| H04: structured continuity preserves state safely | B5 vs B4 on multi-turn cases | Omission, stale evidence, scope leakage or anchoring increases; task completion does not improve |
| H05: critic corrects additional errors | B6 vs B5 using same saved draft and initial ledger | No incremental corrections, unsupported challenges/false vetoes, or disproportionate cost |
| H06: graph earns its complexity | B3 vs B2 fixed retrieval queries | No incremental gold-clause recovery, identity contamination, or maintenance/cost outweigh gain |
| H07: adaptive review can retain critical detection | B7 vs always-on B6 after risk labels collected | Important false skips, worse action support or savings below frozen target |
| H08: planner/fusion/vector memory are worth adding | B8/B9 and isolated memory-vector arm vs exact declared parent | No measurable benefit after accounting for added work and reliability risks |

The Q08 method is accepted in ADR-0019; actual numerical targets and sampling require
development evidence. Derive effect sizes and budgets from B0/B1
development data, then preregister numerical criteria before held-out runs. Until then,
these hypotheses have direction and instruments but no invented success threshold.

## Selected runtime and approved setup

ADR-0013 selects uv (`uv venv` in `C:/palladion/palladion`, app-local `.venv`, pinned
`uv.lock`) and real Groq `qwen/qwen3.8-27b` for initial generative runs. Main and critic
use separate contexts; a shared provider/model is not independent truth. Runtime choice
does not constrain development subagents, which remain GPT 6 Luna Medium, or prescribe
an embedding model. Actual embedding/tokenizer selection follows the compatibility task.

P01 package setup is authorized and deterministic foundation fixtures are validated;
no model experiment or research result exists. The corpus remains PILOT without two
independent human annotators/adjudication. P01 makes no provider request.
After GO, run enabled provider experiments under explicit quotas/call/token/time budgets,
record actual model ID and structured/tool behavior, and load only the existing root
`.env` for the specific command. No fake runtime result may replace failed model proof.
Deterministic scorer/guard input fixtures remain distinct from actual model outputs.

The [Groq model page](https://console.groq.com/docs/model/qwen/qwen3.8-27b) lists the
selected model, and [free-plan rate limits](https://console.groq.com/docs/rate-limits)
are documented (checked 2026-10-17). This does not verify account access or unlimited
capacity. Report actual billing if any, zero billed only when evidenced, and separately
estimated list-price resource cost if useful; never assume all inference is cost-free.

## Internal treatments B0–B9

| Arm | Definition from blueprint | Control and caution |
|---|---|---|
| B0 | BM25 + exact identifiers + one LLM | Lexical reference; same canonical corpus/ACL |
| B1 | Dense ANN + BM25 native RRF + exact + one LLM | B0, same generation model and question set |
| B2 | B1 + reranker + parent context | B1; record actual rerank/expanded passage budgets |
| B3 | B2 + bounded Neo4j source expansion | B2; record extraction/review and query cost |
| B4 | B2 **or** B3 + deterministic time-aware policy | Declare chosen parent for each run; never pool the two silently |
| B5 | B4 + typed scoped memory and continuity | Same multi-turn script, corrections and evolving observations |
| B6 | B5 + always-on critic | Saved-draft paired and full end-to-end analyses separately |
| B7 | B5 + risk-triggered critic | Later experimental treatment; not default normative release path |
| B8 | B5/B6 + optional small-model nonexclusive planner | Declare parent; planner call counted (up to 9 calls per blueprint variant) |
| B9 | Fixed B2 data, native RRF vs controlled alternative fusion | Exactly one dense/sparse fusion stage per treatment |

P02 records retrieval-only lexical/hybrid/reranked-context substrate pilots, not full
B0/B1/B2 arms (those include generation). No answer-quality conclusion is possible at
P02. Preserve language/time/ACL slices and index-state disclosures. Full treatments mature later. B3's label
does not require implementing graph before policy/memory/critic; follow the build slices.
Vector memory compares structured/FTS-only against vector augmentation as a separately
named treatment, not an undisclosed change to B5.

Comparative runs with critic disabled or deterministic safeguards ablated execute in an
isolated synthetic evaluator. Their raw answers are scored as experimental artifacts,
not released as supported operational guidance. If a common safety wrapper is imposed,
retain and score both raw and wrapped results; disclose its effect rather than giving
baselines hidden Palladion capabilities. Never disable real authorization for a benchmark.

## Recorded P02 substrate pilot

E-P02-001 records the actual eight-case/two-profile run, raw artifact hash and metric
denominators. Both BM25 profiles tied here; lexical MRR0.9, hybrid/reranked/context MRR1.0,
Recall@5=1.0 on the scored tiny cases. Reranking showed no added quality on this pilot.
These are descriptive pilot measurements, not full B0/B1/B2 answers or a general winner.
The corpus is English; one of eight queries is Indonesian. Human adjudication, meaningful
sample size, held-out results and overall hypothesis conclusions remain unexecuted.

## Corpus, splits and labeling

Use synthetic internally consistent SOPs, versions, exception appendices, drafts, policies,
roles/cases, timestamps and mock observations. Preserve T01–T24 and source inventory tests.
Separate intentionally absent external inventory from accepted-but-unindexed sources and
from inaccessible sources; they test different failure mechanisms.

Before a meaningful research claim:

1. Define corpus/version hash, case-family IDs, language/time/ACL/difficulty strata and
   annotation schema. Every golden identifies admissible exact clauses, applicable rule
   version/time basis, required facts, expected outcome/disposition, forbidden actions,
   allowed hypotheses and evaluator notes.
2. Have at least two annotators review gold labels; log disagreement, adjudicator,
   rationale and remaining ambiguity. LLM agreement is not a substitute. If independent
   human labels are unavailable, report pilot-only evidence and keep the limitation visible.
3. Split development/calibration/held-out by case/document family to prevent near-duplicate
   policy revisions or reworded cases leaking across splits. Freeze split manifest and seed.
4. Decide sample size, repeated generations, randomization, uncertainty method and numerical
   targets using development observations. Record them before held-out execution.
5. Freeze a deterministic retrieval benchmark and repeat stochastic generation per plan.
   Persist actual responses/tool traces; a seed alone may not reproduce a hosted model.

Do not tune prompts, thresholds, chunking or risk rules on the final held-out cases. A
post-result fix requires a new version/run and fresh held-out evidence for a fresh claim.

## Metric definitions and honest denominators

| Dimension | Required measurement |
|---|---|
| Retrieval | Gold admissible clause Recall@5/10/20; nDCG@K with declared relevance grades; MRR; exact-ID hit rate; exception recall; ANN-vs-exact dense neighbor recall. Report candidate, fused, reranked and expanded stages and actual HNSW/exact index state. |
| Authority | Resolvable exact-span citations / all emitted citations; support precision = semantically supported cited claim associations / adjudicated cited associations; approved/applicable source rate; temporal version accuracy; completed provenance chains. |
| Answer integrity | Unsupported material claims / adjudicated material claims; answers with any unsupported material claim / scored answers; unsupported operational actions / adjudicated action claims, plus count of cases with any unsupported action. Hallucinated citation counts/rate. |
| Qualification | Expected-disposition accuracy; abstention precision/recall against gold answerability; required missing-slot recall; contradiction detection; safely labeled hypotheses / hypothesis statements; false vetoes of gold-supported claims/answers. |
| Utility | Human-rated investigation usefulness using a frozen rubric; supported answer coverage on answerable cases; task completion and omission across continuations. A refusal-only system cannot win on unsupported rate alone. |
| Operations | p50/p95 end-to-end and component latency with sample size; main/critic/planner calls, initial/counter searches, tools, retries, tokens, cache hits, exhausted budgets and wall time; actual or explicitly estimated cost. |
| Safety | Attempt counts and observed leaks/side effects for tenant/case/role/graph/memory/tool injection tests; source freshness/schema errors; index lag; graph fan-out and identity failures. |

Zero denominator is `N/A` with numerator/denominator, not 0% or 100%. Report raw counts,
missing/failed runs, case-level paired differences and uncertainty intervals appropriate to
the preregistered design. Cluster repeated outputs by case when estimating uncertainty;
repetitions are not independent new cases. Include language, temporal, ACL, difficulty and
question-type breakdowns so an aggregate does not hide an exception failure.

Model/scorer identity, prompts and limitations must be disclosed for any auxiliary LLM
judge. Deterministic checks and independent annotations own integrity/support labels;
the answering model never grades itself as sole truth.

## Critic-specific controls

Freeze question, draft and initial evidence ledger. Evaluate reviewer off/on on that pair.
Separate (a) same-context review, (b) review with independently authorized counter-search,
and (c) optional blind-requirements prepass. Count corrections, false objections/vetoes,
misses, changed evidence, extra calls/tokens/time and useful next steps. Then run the
full live orchestration as a different experiment; different end-to-end traces alone
cannot isolate the critic's contribution. Test the withheld-appendix shared blind spot.

## Future external comparisons in baseline/

X01 remains deferred. Define exact standard RAG pipeline, LangChain-based pipeline and
named provider system/version before implementation; LangChain is a library, not a
single retrieval architecture. Keep each adapter and dependencies isolated under the
reserved sibling directory. Do not assume provider systems expose policy, live state,
memory, citations, or equal control over model/budgets.

Use a shared evaluator input/output contract that includes case/scope, supplied corpus,
observations, query, result claims/citations/disposition where available, timing and
resource ledger. This contract is planned, not an existing API. Reject unsupported
feature assumptions; capability differences are recorded before scoring.

Run two clearly labeled tracks when needed:

- **Matched capability/resource track:** same eligible documents, principal scopes,
  model/prompt where possible, comparable retrieval/passages/tools/call/time budget,
  common scenario and fixed synthetic observations. Compare only supported capabilities.
- **Native configured system track:** each system's documented configuration and actual
  abilities, with all differences/costs reported. Do not attribute the full difference
  solely to the harness architecture or hide additional tools/data/model calls.

Include document-only tasks where all systems can compete. For policy/live/continuity
tasks, report capability gaps and safety of handling them rather than penalizing a
document-only baseline for not possessing hidden inputs. `N/A` differs from incorrect.
Freeze tuning effort and corpus access, randomize execution order, declare warm/cold
caches, concurrency and hardware. Include ingest/index/model hosting and maintenance
cost separately from per-query cost; critic searches are never free or hidden.

No overall scalar score now. If later requested, preregister dimensions/weights and show
raw metrics and sensitivity to weights. Preserve neutral and negative results. Do not
pick only best-of-N runs or omit failed/provider-timeout cases from denominators.

## Required run artifact and report

Each future run records: run ID/UTC date; git revision plus dirty patch hash; treatment
and parent; corpus/gold/split hashes and annotators; principal scope digest; pinned model,
embedding/tokenizer, dependencies, prompts and schema versions; configs/budgets/flags;
source/index generations; hardware/concurrency/cache state; randomness/repetition plan;
actual outputs, evidence handles and sanitized traces; raw counts, costs, latency samples
and failed runs; scorer/version/rubric; exclusions and reasons; conclusions and limitations.

Keep small redacted manifests/summaries and their artifact hashes/paths referenced from
EVIDENCE_LOG. Large raw outputs stay outside commits in a declared artifact location;
do not commit secrets, private data or giant generated reports. A report without accessible
underlying artifacts is an evidence gap. Label the failure-owning stage: ingestion,
candidates, ranking, source resolver, tool selection, policy inputs, critic, gate or scoring.
