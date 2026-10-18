# Requirements traceability

Updated 2026-10-18. Maps the research protocol to owning tasks and gates so no section, hypothesis,
ablation, stratum or methodological rule is orphaned. Source:
[research protocol v1.0](../vision/palladion_retrieval_benchmark_research_protocol.md). A row is a plan
link, not evidence that anything is built or measured. Ownership of the protocol's 70-file tree is
enforced by [check_docs.py](check_docs.py) against the atomic register in the
[master plan](MASTER_DEV_PLAN.md#atomic-execution-register), not duplicated here.

## Protocol sections

| Section | Content | Owner tasks | Gates |
|---|---|---|---|
| §1 | Objectives, hypotheses, decision rules | B08-T03.01, B08-T04.01 | BG-PREREG, BG-REPORT |
| §2 | Comparators: eight retrievers, five systems, exploratory conditions | B04-T01.01, B06-T01.01, B07-T01.01 | BG-ADAPTER |
| §3 | Tracks A/B/C and fairness controls | B04-T04.02, B05-T05.01, B07-T08.01 | BG-FAIR, BG-TRACKA, BG-TRACKB, BG-TRACKC |
| §4 | Synthetic world and corpus | B02-T01.01, B02-T02.01, B02-T02.02 | BG-FIXTURE |
| §5 | Query sets, episodes, partitions, update benchmark | B02-T04.02, B07-T05.01 | BG-GOLD |
| §6 | Ground-truth construction and evidence ontology | B02-T04.01, B02-T07.02 | BG-GOLD |
| §7 | Harness contracts, manifest, staging, traces | B01-T02.01, B01-T03.02, B01-T03.03 | BG-HARNESS, BG-REPRO |
| §8 | Retrieval metrics | B03-T02.01, B03-T03.01, B03-T03.02 | BG-METRIC |
| §9 | Answer, provenance, policy and temporal metrics | B05-T01.01, B05-T02.01 | BG-METRIC |
| §10 | Abstention, selective prediction, calibration, loss | B05-T03.01, B03-T04.01 | BG-METRIC, BG-STATS |
| §11 | Memory, graph, tool and critic metrics | B07-T05.02, B07-T06.01, B07-T06.02, B06-T05.01 | BG-METRIC |
| §12 | Latency, cost, scaling, operational burden | B03-T05.01, B09-T01.01 | BG-METRIC, BG-TRACKA |
| §13 | Scorecards, endpoints, release gates | B03-T06.01, B08-T06.01 | BG-REPORT |
| §14 | Execution stages, sample size, statistics | B03-T04.01, B08-T02.02, B08-T04.01 | BG-STATS, BG-PREREG |
| §15 | Ablation study | B08-T05.01 | BG-ABLATION |
| §16 | Mutation and adversarial experiments | B07-T07.01 | BG-FIXTURE, BG-SECURITY |
| §17 | Worked examples as test seeds | B03-T02.01, B03-T03.02 | BG-METRIC |
| §18 | Repository map and entry points | B00-T03.01, B01-T01.01, B01-T04.02 | BG-DOC, BG-HARNESS |
| §19 | Execution plan, resources, deliverables | B00-T02.01, B08-T07.01 | BG-DOC, BG-REPRO |
| §20 | Threats to validity | B08-T07.01 | BG-REPORT |
| §21 | Source register | B06-T01.01, B07-T03.01, B09-T03.01 | BG-REPRO |
| §22 | Preregistration checklist | B08-T03.01 | BG-PREREG |

## Hypotheses (protocol §1.2)

| ID | Hypothesis and its null | Owner tasks | Gates |
|---|---|---|---|
| H1 | Palladion retrieves complete, applicable evidence better on cross-document, exception and superseded cases; null: no gain over the best strong non-Palladion retriever at matched budget | B04-T05.01, B08-T04.01 | BG-TRACKA, BG-PREREG |
| H2 | Provenance and deterministic policy validation reduce unsupported operational directives; null: no reduction against shared-generator hybrid RAG | B05-T06.01, B08-T04.01 | BG-TRACKB, BG-PREREG |
| H3 | The evidence critic finds genuinely missing prerequisites beyond the deterministic gate; null: no better than Palladion without it | B07-T06.01, B08-T05.01 | BG-TRACKC, BG-ABLATION |
| H4 | The typed graph improves multi-hop evidence recall enough to justify cost; null: no material gain at matched budget | B06-T06.01, B08-T05.01 | BG-TRACKA, BG-ABLATION |
| H5 | The continuity packet reduces case-identity drift and repeated investigation; null: no gain over a bounded rolling summary | B07-T05.02, B08-T05.01 | BG-TRACKC, BG-ABLATION |
| H6 | Policy-specific temporal resolution prevents wrong-vintage decisions; null: no gain over metadata-filtered hybrid RAG | B05-T02.01, B08-T05.01 | BG-METRIC, BG-ABLATION |
| H7 | Extra guardrails lower unsupported claims without unacceptable over-abstention; null: any safety gain is offset by lost coverage | B05-T03.01, B08-T04.01 | BG-METRIC, BG-PREREG |
| H8 | How accuracy, safety, indexing and query cost, and tail latency scale; null: Palladion is dominated by a simpler comparator in the relevant region | B03-T05.01, B08-T06.01 | BG-METRIC, BG-REPORT |

## Ablations (protocol §15)

| ID | Comparison | Owner tasks | Gates |
|---|---|---|---|
| A01 | Dense alone, BM25 alone, hybrid | B08-T05.01, B04-T02.01 | BG-ABLATION |
| A02 | RRF versus weighted RRF versus DBSF | B08-T05.01, B04-T02.01 | BG-ABLATION |
| A03 | Hybrid versus hybrid plus reranker | B08-T05.01, B04-T02.02 | BG-ABLATION |
| A04 | Hybrid with metadata filter versus Palladion without graph | B08-T05.01, B04-T03.01 | BG-ABLATION |
| A05 | Typed graph off, on at depth 1 and depth 2 | B08-T05.01, B06-T04.01 | BG-ABLATION |
| A06 | Exact-ID parser off and on | B08-T05.01, B04-T03.01 | BG-ABLATION |
| A07 | Source-authority checking off and on (failure-mode probe only) | B08-T05.01, B07-T04.01 | BG-ABLATION, BG-SECURITY |
| A08 | Temporal resolver versus naive newest versus static as-of | B08-T05.01, B05-T02.01 | BG-ABLATION |
| A09 | Policy evaluator off and on over the same accessible rules (system ablation) | B08-T05.01, B07-T04.01 | BG-ABLATION |
| A10 | Critic off and on with the same main model and gate | B08-T05.01, B07-T04.01 | BG-ABLATION |
| A11 | Critic countersearch off and on | B08-T05.01, B07-T06.01 | BG-ABLATION |
| A12 | Continuity packet versus summary versus no memory | B08-T05.01, B07-T05.02 | BG-ABLATION |
| A13 | Reference-only hot tier versus raw cached chunks | B08-T05.01, B07-T05.02 | BG-ABLATION |
| A14 | Live adapter versus document-only guesses versus oracle results (system ablation) | B08-T05.01, B02-T05.01 | BG-ABLATION |
| A15 | Evidence gate off and on, fictional fixtures only | B08-T05.01, B07-T04.01 | BG-ABLATION, BG-SECURITY |
| A16 | Full preflight versus no prefetch versus exclusive router | B08-T05.01, B07-T04.01 | BG-ABLATION |

## Question strata (protocol §5.1)

| ID | Stratum | Owner tasks | Gates |
|---|---|---|---|
| Q1 | Exact IDs and rare terms | B02-T04.02, B04-T01.01 | BG-GOLD, BG-TRACKA |
| Q2 | Semantic paraphrase and bilingual retrieval | B02-T04.02, B04-T01.02 | BG-GOLD, BG-TRACKA |
| Q3 | Multi-document and multi-hop | B02-T04.02, B06-T06.01 | BG-GOLD, BG-TRACKA |
| Q4 | Version, supersession and as-of time | B02-T04.02, B05-T02.01 | BG-GOLD, BG-METRIC |
| Q5 | Structured policy exceptions | B02-T04.02, B05-T02.01 | BG-GOLD, BG-METRIC |
| Q6 | Contradictory authoritative sources | B02-T04.02, B07-T07.01 | BG-GOLD, BG-FIXTURE |
| Q7 | Unanswerable or insufficient inventory | B02-T04.02, B05-T03.01 | BG-GOLD, BG-METRIC |
| Q8 | ACL, role, tenant and source trust | B02-T04.02, B02-T03.01 | BG-GOLD, BG-SECURITY |
| Q9 | Live system status and failures (Track C unless a shared fixture is exposed) | B02-T04.02, B07-T09.01 | BG-GOLD, BG-TRACKC |
| Q10 | Global synthesis and long-document structure | B02-T04.02, B06-T02.01 | BG-GOLD, BG-TRACKA |

## Methodological invariants

Rules every task must preserve. Violating one invalidates a result, so each has an owner and a gate.

| ID | Invariant | Owner tasks | Gates |
|---|---|---|---|
| BI01 | Information barrier: only the evaluator sees gold; arms see the published corpus and authorized tool output (§4.4, §7.3) | B02-T03.01, B04-T04.03 | BG-SECURITY, BG-FIXTURE |
| BI02 | Identical source snapshot, principal, ACL and temporal condition for every arm (§3.1 items 1, 2, 6) | B04-T02.01, B04-T04.02 | BG-FAIR |
| BI03 | No oracle labels reach any prompt, embedding, graph build or arm-visible metadata (§3.1 item 7) | B04-T04.03 | BG-FAIR, BG-REPRO |
| BI04 | Tune on dev only, seal the test set, never revisit after seeing numbers (§3.1 item 10, §5.2) | B08-T02.01, B08-T03.01 | BG-PREREG |
| BI05 | Partition by scenario family before paraphrase, by episode for multi-turn (§5.2, §5.3) | B02-T04.02, B07-T05.01 | BG-GOLD |
| BI06 | No phantom native citations; alignment-only mappings are labeled (§7.1) | B03-T01.01 | BG-ADAPTER, BG-METRIC |
| BI07 | Missing, unsupported, invalid and timed-out runs are results, never zeros; report intention-to-treat (§13.4, §14.6) | B01-T02.02, B03-T06.01 | BG-HARNESS, BG-REPORT |
| BI08 | Paired, family-clustered statistics with preregistered pairings and multiplicity control (§14.2) | B03-T04.01, B08-T03.01 | BG-STATS, BG-PREREG |
| BI09 | Zero observed failures give an upper bound, not zero risk (§13.2, §20) | B03-T04.01, B08-T02.02 | BG-STATS, BG-SECURITY |
| BI10 | Gold comes from the deterministic hidden world plus human audit; LLM judges are secondary (§6.3) | B02-T07.02, B05-T04.02 | BG-GOLD, BG-METRIC |
| BI11 | Pin every model, package and comparator; `latest` is rejected in confirmatory runs (§7.2) | B01-T03.02, B01-T02.03 | BG-REPRO, BG-HARNESS |
| BI12 | Account indexing, extraction, storage and update cost, not only query cost (§3.1 item 8, §12.2) | B06-T06.01, B03-T05.01 | BG-FAIR, BG-METRIC |
| BI13 | Preserve official comparator algorithms; record every deviation (§2.1) | B06-T01.01, B06-T02.01, B06-T03.01 | BG-ADAPTER, BG-FAIR |
| BI14 | Retrieval and rerank scores are ranking features, never answer probabilities (§8.5, §10.2) | B03-T04.01, B05-T03.01 | BG-METRIC, BG-STATS |
| BI15 | Fictional data only, marked as such; no real company, customer or transaction identifiers (§4.1) | B02-T01.01, B02-T07.01 | BG-FIXTURE, BG-SECURITY |
| BI16 | Publish negative findings and Pareto views; no single composite as winner (§1.4, §13.1, §19.4) | B03-T06.01, B08-T06.01 | BG-REPORT |
| BI17 | Source authority comes from registry metadata, never from claims inside a document (§9.5) | B02-T02.02, B07-T07.01 | BG-FIXTURE, BG-SECURITY |
| BI18 | Repeat stochastic generation, record model, settings and timestamps, treat provider drift as a factor (§14.4) | B08-T04.01, B01-T05.01 | BG-TRACKB, BG-REPRO |
