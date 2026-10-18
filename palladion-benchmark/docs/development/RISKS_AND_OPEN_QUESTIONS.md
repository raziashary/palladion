# Risks and open questions

Updated 2026-10-18. Risks are things that can invalidate the experiment or block work; open
questions need the owner's answer before the named task. Decisions are recorded in
[ADR_LOG](ADR_LOG.md). A row here is not an approval.

## Open questions (owner decisions)

| ID | Question and why it matters | Needed before | Linked decision | State |
|---|---|---|---|---|
| OQ01 | How will the Groq key reach the benchmark (benchmark-local `.env`, per-command variable)? No provider call happens until this is answered | B01-T05.02 | BADR-0013 | OPEN |
| OQ02 | Failover and pairing rule when a Groq model is rate limited (one model per question across all arms is recommended) | B01-T05.01 | BADR-0008 | OPEN |
| OQ03 | Which Palladion interface does the R7a/E3/E4 adapter call, and is it stable enough to pin? Read Palladion's live source when B04 starts; its API is still changing | B04-T03.01 | BADR-0002 | OPEN |
| OQ04 | Embedding model for R1–R3: use Palladion's pinned embeddings for parity, or an independent model? The protocol asks for parity where possible | B04-T01.02 | BADR-0002 | OPEN |
| OQ05 | Which cross-encoder is the frozen R3 reranker, and may it be downloaded (size and source stated first)? | B04-T02.02 | BADR-0005 | OPEN |
| OQ06 | Graph comparators need LLM extraction. With free-tier quotas, is indexing limited to the S tier, or is a larger budget available? Spending cap and retry ceiling are required by protocol §19.2 | B06-T01.01 | BADR-0007 | OPEN |
| OQ07 | Is Google RAG Engine access (region, allowlist, billing) available for E2? Default is NOT_RUN | B07-T03.01 | BADR-0006 | OPEN |
| OQ08 | Who are the two human annotators for the stratified label audit and the claim-level audits? Automation alone is not independent truth | B02-T07.02 | BADR-0006 | OPEN |
| OQ09 | Dataset license for the synthetic fixtures and the generator code | B08-T07.01 | BADR-0006 | OPEN |
| OQ10 | Primary confirmatory pairings (protocol suggests R7 vs R3 and E4 vs E3), equivalence margin and multiplicity procedure | B08-T03.01 | BADR-0012 | OPEN |
| OQ11 | Palladion's settings cannot turn the critic off (minimum one call), its independent critic is a later phase of its own plan, and it exposes no switch for the gate, preflight, authority check, parser or temporal resolver. Will its contributor add documented switches, or are E3/E4 and most ablations FEATURE_NOT_SUPPORTED? The benchmark does not edit Palladion | B07-T04.01 | BADR-0002 | OPEN |

## Risks

| ID | Risk | Consequence | Mitigation and owner |
|---|---|---|---|
| BR01 | Palladion's interface changes while the other contributor works (it has uncommitted edits and phases open) | Adapter breaks or silently measures a moving target | Read live source at adapter time; record Palladion commit in every run manifest; adapter failure is NOT_RUN. Owner: B04-T03.01 |
| BR02 | Shared checkout: an unscoped `git add`, commit or push captures the other contributor's work or publishes their commits | Mixed history, premature publication | Path-scoped commits, `git diff --cached --name-only` check, ahead-list check before push (BADR-0004). Owner: every closeout |
| BR03 | Researcher advantage: the benchmark author's taxonomy may mirror Palladion's strengths | Biased comparison | C2 gives R3 identical authority metadata; blinded annotation; publish generator; disclose in the report (protocol §20). Owner: B04-T02.01, B08-T07.01 |
| BR04 | Shared-provider generator confound and mixed models within pairs (BADR-0007) | Paired differences reflect model, not retriever | BADR-0008 pairing rule; per-call model record; Stage 3 replication on another family (B09-T02.01) |
| BR05 | Synthetic realism and template artifacts make the world easier than real knowledge | Overstated effect sizes | Realism checks, actual proportions reported, template-first plus audited paraphrase (BADR-0009); limits stated in the dataset card |
| BR06 | Comparator installs are fragile on Windows (HippoRAG, GraphRAG, LightRAG, Neo4j, Qdrant) and need their own Python versions | Arms cannot run, or run with silent substitutions | Isolated pinned environments; official algorithm preserved; NOT_RUN with reason otherwise. Owner: B06 |
| BR07 | Free-tier quota exhaustion mid-run | Truncated runs, silent resampling | Budgets and attempt ceilings recorded; intention-to-treat accounting; resume rather than rerun. Owner: B01-T05.01, B08-T04.01 |
| BR08 | Peeking at locked test annotations during tuning | Invalid confirmatory claims | Namespace separation, no test path in dev commands, seal hashes (B08-T03.01) |
| BR09 | Rare-event endpoints underpowered with 600 test questions | Inconclusive safety results | Power simulation from dev data, targeted security suite sized from the zero-failure bound (B08-T02.02) |
| BR10 | Gold labels circular or wrong | Everything downstream invalid | Hidden world is the source of truth, two-annotator audit, fixture defects fixed before sealing (B02-T07.02) |
| BR12 | Palladion cannot express the primary critic-off challenger E3 or most ablations by configuration (OQ11), and its search interface has no clock, token-budget or K above 12 | H3, H5, H6 and most of A01–A16 untestable; fairness controls fail silently | Mark FEATURE_NOT_SUPPORTED with the reason, enforce budgets harness-side, never relabel E4 as E3 (B04-T03.01, B07-T04.01, B08-T05.01) |
| BR13 | Rate-limit-driven model switching correlates with arm token volume, so excluding mixed-model pairs would be informative censoring | Biased paired comparisons | BADR-0008 revised to an intention-to-treat rule fixed before arms run; log mixed-model fraction |
| BR11 | Docker may be unavailable on this machine (Palladion itself runs Qdrant without Docker) | Compose services cannot start | Services optional behind profiles; use the native launchers where documented; record environment in the manifest |
