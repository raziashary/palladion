# Operational research protocol

Updated 2026-10-18. The [research protocol v1.0](../vision/palladion_retrieval_benchmark_research_protocol.md)
is the vision and stays unedited. This document turns it into the working rules, registries and lock
procedure used by the plan. If the two ever conflict, the vision governs and the conflict is raised, not
patched silently. Nothing here reports a result: no comparative measurement exists.

## Claim under test

Palladion gives more complete, applicable evidence and fewer unsupported operational directives than strong
baselines, at an acceptable cost in coverage, latency and complexity. This is not "best RAG". Primary
challengers: R3 (hybrid plus reranker) for retrieval and E3 (Palladion without critic) for the critic.

## Arm registry (protocol §2)

Eligibility is by track. A method that cannot support a capability is recorded as unsupported, not scored zero.

| Arm | Description | Track and role |
|---|---|---|
| R0 | BM25 over the shared chunks | Track A; lexical control |
| R1 | Dense retrieval, same embedding model, HNSW | Track A; dense control |
| R2 | Hybrid R0+R1 with reciprocal-rank fusion; exact-key channel reported separately | Track A/B; primary practical baseline |
| R3 | R2 plus a fixed cross-encoder reranker | Track A/B; primary challenger |
| R4 | HippoRAG 2, official pipeline | Track A; research comparator |
| R5 | Microsoft GraphRAG Local, official query mode | Track A; graph comparator; Global and DRIFT are separate exploratory modes |
| R6 | LightRAG, official hybrid mode, pinned commit | Track A; efficiency comparator |
| R7 | Palladion retriever; R7a without graph, R7b with bounded graph expansion | Track A/B; candidate system |
| R7a | Palladion retriever without Neo4j | Ablation base and primary candidate |
| R7b | Palladion retriever with bounded Neo4j expansion | Graph treatment; NOT_RUN if the feature is absent |
| E0 | Plain LangChain two-step | Track C; reference stack |
| E1 | LangChain/LangGraph bounded agentic loop | Track C; agentic reference |
| E2 | Google ADK with RAG Engine | Track C; conditional, NOT_RUN without access |
| E3 | Palladion without critic | Track C; primary critic challenger |
| E4 | Full Palladion with critic | Track C; complete system |

Exploratory conditions (not counted in the eight): GraphRAG Global on corpus-wide synthesis only, optional DRIFT and
RAPTOR, and public enterprise benchmarks run through their own harnesses.

## Tracks and conditions

Track A is retrieval only, no answer model. Track B gives every retriever the same generator, prompt family,
answer format, evidence token budget and runtime gate. Track C runs E0–E4 natively under a defined maximum
cost, call and time budget. Metadata conditions: C1 text-only, C2 evidence-governed (equivalent authenticated
metadata for every arm where feasible). Evidence budgets: 4k and 8k tokens, K in 5, 10, 20. Differences
the wrapper cannot remove are reported as capability differences, not ranking superiority.

## Lifecycle stages (protocol §14.1)

| Stage | Data | Allowed | Forbidden |
|---|---|---|---|
| 0 pilot | S tier, 100 questions | Validate parsers, indexes, span mapping, gold coverage, budgets, costs | Held-out claims |
| 1 development | M tier, 300 dev questions | Tune K, pools, reranker cutoff, graph depth, critic activation, thresholds, one lever at a time | Reading locked-test annotations |
| 2 confirmatory | 600 locked questions, 100 episodes | Run all eligible arms once under predeclared retry rules | Retuning, selective reruns |
| 3 replication | Second generator family, new seed, held-out templates, L tier | Replicate | Tuning on replication results |

## Lock procedure (executed in B08-T03.01)

1. Complete the protocol §22 checklist and record each answer; unresolved items block the seal.
2. Freeze code, configs, prompts, seeds, pins and the generator failover rule (BADR-0008).
3. Fix primary pairings (suggested R7 vs R3, E4 vs E3), the equivalence margin, the multiplicity procedure for
   exploratory pairs (Holm or a labeled false-discovery procedure), minimum meaningful effects and the calibration plan.
4. Seal `corpus_manifest`, the locked-test question manifest and annotations by SHA-256; store the hashes in the
   evaluation config and the manifest of every confirmatory run.
5. After sealing, any change to a sealed item is logged and every later result that depends on it is labeled exploratory.

## Run records

Every run has an immutable manifest (protocol §7.2): digests of the source, question and evaluator-only gold manifests,
code commit, Palladion commit, container or environment digest, method versions, exact model and revision,
retrieval configuration, hardware, pricing snapshot, seed, cache condition and start time. Record request IDs,
retries, throttles and cached versus uncached responses. Generation records add the model id used for each call.
Initial and post-retry outcomes are both retained. Prices come from a dated vendor sheet captured at run time;
free-tier runs still report tokens, compute and wall time.

## Analysis rules

Paired differences on question IDs; bootstrap clustered by scenario family; exact McNemar or permutation for
binary outcomes; confidence interval overlapping zero means inconclusive, not equivalent; equivalence needs a stated
margin. For harmful events the improvement direction is reversed in tables. Report effect sizes and raw denominators.
Report conditional-on-completion and end-to-end success separately. Report Pareto views (unsupported-directive rate
against cost, complete-set recall against p95 latency, selective risk against coverage) and say plainly when
Palladion is dominated. The generator model is reported as a factor in every Track B and C table.

## Threats to validity (summary of protocol §20)

Synthetic realism, researcher advantage, implementation inequality, LLM-judge bias, parametric-knowledge contamination,
data leakage across splits, provider capability asymmetry, rare-event limits, benchmark overfitting and licensing. The
mitigation owners are listed in [RISKS_AND_OPEN_QUESTIONS](RISKS_AND_OPEN_QUESTIONS.md) and in the gate catalog.
