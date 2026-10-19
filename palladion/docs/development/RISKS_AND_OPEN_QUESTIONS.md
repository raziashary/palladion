# Risks, accepted answers and verification obligations

Current authority amendment: P05 published f0507e4; user explicitly authorized P06 end-to-end; ADR-0030 separately approves the additive PolicyDecision extension. Earlier implementation hold below is historical; P04 explicit enabled provider commands are authorized.

Updated 2026-10-17. The user read and accepted all recommendation directions, except
fake-first runtime: use Groq `qwen/qwen3.8-27b`. uv and package-selection authority are
explicitly approved. **Additive v3 migration is owner-approved (ADR-0025).**
P05 is explicitly authorized; ADR0039/0040 approve v4/recall and owner/admin scope controls. Later implementation remains phase-scoped. Acceptance does not invent compatibility,
thresholds, fixture values, reviewer availability, completeness or production signoff.

Owner answers live once in [ADR_LOG](ADR_LOG.md); edit **My answer (editable)** there.
This register tracks remaining evidence and deferred scope, not a competing answer inbox.

| ID | Question / accepted direction | Decision and state | Remaining evidence / owning phase |
|---|---|---|---|
| Q01 | Synthetic approval authority | [ADR-0012](ADR_LOG.md#adr-0012--q01--synthetic-approval-authority) ACCEPTED: authenticated administrator events; separate upload/approval grants | P01/P02 implement registry and reject self-approval/unauthorized grants; G-SOURCE/G-SECURITY |
| Q02 | Python packages, environment and model | [ADR-0013](ADR_LOG.md#adr-0013--q02--uv-and-real-groq-runtime-generation) ACCEPTED: uv, app-local uv venv, delegated package choices, actual Groq qwen/qwen3.8-27b; fake-first overridden | Working uv installed separately; user-created ignored app .venv exists (E-DOC-004). P01 verified reuse, package pins/locked sync and installed-wheel smoke (E-P01-001); actual model/tool/schema/quota remains P04 proof. Embeddings remain a measured compatible selection. Actual P04 probes are at E-P04-001. |
| Q03 | Qdrant native RRF/BM25 compatibility | [ADR-0014](ADR_LOG.md#adr-0014--q03--qdrant-hybrid-compatibility) ACCEPTED_DIRECTION; VERIFY_AT_IMPLEMENTATION | P02 real1.19.2/1.19.1 probe and same-point/nativeRRFk60/matched weighting passed (E-P02-001). Broader corpus/language measurements remain P08. |
| Q04 | English/Indonesian processing | [ADR-0015](ADR_LOG.md#adr-0015--q04--english-and-indonesian-retrieval) ACCEPTED_DIRECTION; VERIFY_AT_IMPLEMENTATION | P02 two-profile pilot recorded language mix/per-language metrics (E-P02-001); tied tiny English-source corpus does not select a general winner. P08 broader adjudicated language evidence remains. |
| Q05 | Historical audits and time-basis migrations | [ADR-0016](ADR_LOG.md#adr-0016--q05--historical-audit-and-time-basis-migration) ACCEPTED_DIRECTION: minimal valid/record-time plus knowledge_cutoff, mixed-basis conflict unless explicit precedence | P03 historical/current fixtures, current ACL/admin audit distinction and replay readers implemented and phase-reviewed; no inferred migration or real-business retention rule. |
| Q06 | External inventory attestation/change feed | [ADR-0017](ADR_LOG.md#adr-0017--q06--external-inventory-boundary) ACCEPTED_DIRECTION; external integration DEFERRED | Distinguish INDEX_COVERAGE from INVENTORY_ATTESTED now; later owner-provided attester/scope/change contract. T12 preserves uncertainty. |
| Q07 | Reported validity and live freshness | [ADR-0018](ADR_LOG.md#adr-0018--q07--fact-validity-and-observation-freshness) ACCEPTED_DIRECTION: use-specific owner/config values, separate timestamps, no model expiry | P03 config/ADR-0029 records synthetic owner limits; stale BI/gateway controls implemented; P05 UNSPECIFIED lifetime remains; no numerical company policy invented. |
| Q08 | Labels, targets, splits and repetitions | [ADR-0019](ADR_LOG.md#adr-0019--q08--honest-research-acceptance) ACCEPTED_DIRECTION: two annotators/adjudication, B0/B1 development calibration, freeze before held-out | P02 pilots/P08 preregistration; actual annotator availability, case counts, repetitions and thresholds remain measured/recorded prerequisites to quantitative claims. |
| Q09 | Semantic support and escalation | [ADR-0020](ADR_LOG.md#adr-0020--q09--claim-support-and-human-escalation) ACCEPTED_DIRECTION: independent support/exception rubric, named authorized human escalation, qualify insufficient adequacy | P04 record actual rubric/reviewer assignment and gold support labels; valid citation alone is not proof. No imaginary reviewer/signoff. |
| Q10 | Optional graph/vector/planner/fusion/adaptive review | [ADR-0021](ADR_LOG.md#adr-0021--q10--optional-complexity-needs-controlled-evidence) ACCEPTED_DIRECTION: controlled flags, paired parent ablations, always-on critic labels first | Owning experiments measure incremental value/harm/cost; initially selected Groq model, no silent provider switch or default normative critic bypass. |
| Q11 | External standard RAG/LangChain/provider comparisons | [ADR-0022](ADR_LOG.md#adr-0022--q11--later-external-comparator-systems) ACCEPTED_DIRECTION; implementation DEFERRED to X01 | baseline/ isolated later; exact versions/capability tracks/shared evaluator and cost disclosures remain future evidence. No comparator built. |
| Q12 | Real identity, data privacy and production | [ADR-0023](ADR_LOG.md#adr-0023--q12--real-data-and-production-boundary) ACCEPTED_DIRECTION: synthetic-only until legitimate access/security/retention approvals | Real connectors/deployment DEFERRED; actual signoff required then, prototype test-set success cannot imply production readiness. |

## Owner decision inbox

All twelve recommendation directions are now answered in ADR-0012–ADR-0023. The
current exceptions/explicit choices are Groq runtime, exact model, uv and delegated
package selection. ADR-0011 records the editable answer format, mandatory pre-phase
adversary, single post-phase work auditor, full-vision audit and explicit GO hold.

No repeat approval is required for the accepted directions or compatible packages within
that scope after GO. Record concrete technical choices, fixture assumptions and results
when known. Material departures, new shipped-contract changes or real-data access still
follow universal escalation rules; package authority does not waive those boundaries.

## Credential and environment observation

Root `.env` exists and is ignored by the user's current root `.gitignore`; it was not
read, copied, printed or staged. That `.gitignore` is user-owned/untracked at task start
and is preserved. At that observation it listed `.env` and `venv`; the latter does not
cover `.venv`. User was advised to add `.venv/` before manually running `uv venv` inside
`C:/palladion/palladion`. Recheck ignore behavior at setup; do not relocate/copy secrets.

Current correction (E-DOC-004): the owner updated root ignore rules to `.env` and `.venv/`
and created the app environment. Interpreter existence and git check-ignore are verified;
publish those existing ignore rules unchanged. The earlier observation above is historical,
not a current missing-environment blocker. P01 GO was subsequently given; locked sync
and installed-wheel compatibility now pass at E-P01-001.

## Updating this register

Keep stable Q IDs. When evidence arrives, cite the actual run/test and limits; accepted
recommendation is not completion. New unresolved decisions get a structured ADR with
an empty owner answer; do not silently infer approval. Maintain deferred rows until
that scope is explicitly invoked. Source evidence and current owner answers outrank
historical task wording. P01 is verified complete at E-P01-001; P02 and later
implementation require their own scope authorization.

## Active P04 proof and decisions

Owner-approved ADR-0031/0032/0034 implementations now pass scoped trace/readiness,
cancellable-worker/deadline and canonical provenance/replay/supersession controls.
Actual five dispositions/document/TCP/wheel paths pass; single end review and allthree finding resolutions pass.
Provider400/malformed generation and429 input/output quota failures remain recorded;
none is automatically retried/switched or treated as successful verification. Keep all
engineering reruns separate from future research denominators. The three permitted
models are explicit owner choices (ADR-0036), with model-specific capabilities/proof.
Measured combined8000TPM, Qwen7000input/1000output; header requests counter is1000RPD.
No human escalation assignee or independent semantic gold exists; normative operational
permission remains qualified/unavailable until P06 required review. Full scientific
quality/latency/cost/held-out claims remain P08. Concurrent benchmark is outside this task.

P05 pilot/implementation evidence is E-P05-001. Model400/schema/quota failures and lifecycle reruns are retained; no semantic gold or organization policy authority is inferred. Scope controls are explicit owner decisions, not inferred from team names.

P05 phase-local implementation/audit closes at E-P05-001. No unanswered owner ADR.
The actual pilot has0/3 strict model completions; provider/tool reliability, semantic
usefulness and H04 are unproven. P06/P08 retain every failed condition. Bounded recall
is non-exhaustive even after current scope filters; exact-ID lookup/narrower queries
are available. No tenant/private-row flooding can suppress allowed items before scope.

## Active P06 decisions and proof

P06 DONE at E-P06-001/E-P06-002: all six atomic cards, approved critic/status/pacing
contracts, actual source/installed/API consumers and sole Luna Medium end-review
resolution are verified. Source294PASS plus13 actual-Qdrant cases pass (12 in the sweep,
one isolated after a setup connection-abort) =307 disjoint checks. Installed294 and one
installed real-Qdrant/API case pass as overlapping artifact checks; all50 packaged files
match the final wheel. Ruff, strict mypy59, dependency81+4controls, foundation CLI and
final document gates pass. Original failed/skipped runs remain evidence, not PASS.

Post-fix real20B exact recoveryPASS39.827s (2main/2critic/1search, explicit cap2) and
serialized default-budget MODEL-draft pathPASS37.089s (4main/1critic/2tools) release the
full exception with original citation/timeline readback and no verification errors.
Gate qualifies a changed final proposal or unresolved CHALLENGE while preserving
canonical facts; unchanged current PASS remains eligible for SUPPORTED. Model review
is advisory, not semantic authority or payment permission.

Frozen prompt-version20B matrix cb9e66:16conditions,16/16known-fact retention,
0/4full-exception corrections, one critic validation failure,16main/17critic/4searches,
66117known received tokens (one attempt lacks usage). It precedes ADR0062's gate-only
qualification fix: no model prompt changed; raw outputs are not relabeled post-fix.
No efficacy/H05, semantic accuracy, causal false-veto or completeness claim. Mandatory
review remains enabled; draft-blind first pass sees canonical required slots (§10.1).
P07 graph/P08 adjudicated research/X01 comparators remain deferred; no P07 GO or P06
main push is inferred. No unanswered P06 owner ADR. Owned processes stopped, storage
preserved and ports16333/16334/18080 verified free; foreign benchmark/editor work untouched.


No unanswered P06 owner ADR remains. Exact-ID recovery does not establish semantic
recall, inventory completeness, production readiness or baseline superiority.
