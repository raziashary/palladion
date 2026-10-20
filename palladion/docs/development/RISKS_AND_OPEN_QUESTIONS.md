# Risks, accepted answers and verification obligations

P10 historical host caution: Windows reported98–99% memory use (9–156MiB available)
and CoreCLR failed with0x800705AA. Current parser launch was hardened against the
Windows venv-redirector/job-assignment race; three focused actual-process controls
passed5.41s via a lightweight base interpreter. A subsequent full collection was
interrupted by the coordinator under host exhaustion, not marked PASS. Current
source458PASS, installed91PASS and native PDF1PASS now supersede that hold (E-P10-006).
The single full-blueprint end review found no material defect; E-P10-007 resolves its final evidence-freshness gap. No foreign process is authorized for termination.
The owner asked to retry with other work running; owned Qdrant is stopped with storage
preserved and recorded PID absent; Windows and WSL report no16333/16334/17687listeners.

ADR0096–0098 have explicit answers; no new architecture choice is awaiting approval.
PDF extraction has resource bounds but is not an OS security sandbox or an OCR/layout
guarantee. Lexical controls are developer-authored and do not establish generalization.
Memory history omits old operational/policy claim text and suppressed corrected/revoked
queries; missing context is preferable to resurrecting invalid authority. PF03 remains open.

Current checkpoint 2026-10-20: P10 OPEN under owner GO/ADR0096–0098. Earlier448source and later86focused tests passed in their recorded snapshots; latest hardening still needs current-byte verification. Actual graph/PDF/Groq/reopen attempt3 passed (9invocations/8responses; one cause UNKNOWN). Windows resource exhaustion blocks installed/native/final-review/cleanup closeout. No commit or push; standing main-push approval persists. P09/PF03 remains OPEN. Preserve foreign benchmark/editor work.

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
At the historical P06 checkpoint, P07 graph/P08 adjudicated research/X01 comparators remained deferred; no P07 GO or P06
main push is inferred. No unanswered P06 owner ADR. Owned processes stopped, storage
preserved and ports16333/16334/18080 verified free; foreign benchmark/editor work untouched.


No unanswered P06 owner ADR remains. Exact-ID recovery does not establish semantic
recall, inventory completeness, production readiness or baseline superiority.

## P07 memory promotion risks and accepted boundaries

Owner0066 answers global=private USER-wide, explicit backend sessions, primary deterministic PathA plus lower-influence cosine/loss PathB, and additive v6. No unanswered category/scope/strategy/storage decision remains. Calibration thresholds/weighting/loss are explicit pilot tunables, not measured optimal values. Main must prove privacy under source revocation/closed sessions, chunk-provenance idempotence, uncertain/quoted/injected preference rejection and no procedural-policy escalation. Existing case-wide packet readers are insufficient. No automatic organization promotion, extra Groq classifier, hidden write tool or embedding-store dependency. Unresolved empirical classification/benefit questions remain research limits, not permission to claim success.

### P07 measured boundaries and remaining research (2026-10-19)

Owner0066/0068 profile is frozen, uncalibrated. The deterministic backend path is automatic; local PathB is an explicitly enabled separate process. The nonprototype six-event pilot keeps4mechanically specified boundaries and2unknown semantic labels. It made1embeddingcall/12texts/0provider calls,5.91seconds, no additional promotion. One weak English cue is not eligible under frozen rules; the eligible detailed-example cue abstains on cosine.74109/combined.62822/loss0. Preserve these false-negative possibilities rather than tune after seeing outputs. Generalization/calibration requires P08 independent labels; no new owner decision is needed for the accepted implementation.

Paired actual graph run00c4866d has0incremental exception recoveries because B2 context expansion already supplies the appendix. Default graph remains disabled. Canonical two-hop navigation, positive/negative ACL/tool/API consumer and cost evidence are engineering results; they are not an adjudicated retrieval or answer-quality win. Paths may describe already selected evidence and never count as new recovery. Initial provider-free pilot had slow/degraded worker; first live attempt failed graph seed; these stay in E-P07-002. Successful20B run proves automatic preference reaches real next-session input with old episode absent, not the truth or quality of a preference-based response.

Known downstream concern from the concurrent benchmark owner's publishedb1209f8 receipt: generic HTTP-loaded source metadata does not necessarily create ExactIndex aliases. Current P07 trusted synthetic seed explicitly registers aliases; no general exact-ID upload guarantee is claimed. Owner: future P08/source retrieval follow-up under Rule4 if a shipped lookup contract changes; do not silently change it in this graph/memory phase.


## P07 final phase-local disposition (2026-10-19)

E-P07-002 records all11cards, actual source/installed/CLI/provider and original-reader proof, the sole GPT6LunaMedium end audit and same-reviewer resolution. The reviewer read the full blueprint (§1–§18), I01–I15, graph and memory amendment; three current-facing document contradictions were fixed and rechecked. No confirmed source defect remained. Graph has0incremental recoveries in4paired queries and stays off by default; controlled path recovery proves integration only. PathA automatic promotion and opt-in bounded local PathB retain original ACL/authorityNONE;4mechanical pilot labels pass,2semantic labels remain unknown. Historical failures and intermediate pending statuses above remain dated snapshots, not current scope. No unanswered P07 owner ADR; P08 adjudication, generalization and external comparisons remain excluded.


## P08 measured risks and accepted limits (2026-10-20)

ADR0079 owner-approved freeze precedes44observations;16rowerrors and45HTTP429 among
91model invocations demonstrate free-quota constraints, not model quality. Shared
provider/host contention,2families and a critic run overlapping part of the grid prevent
causal capacity or general quality claims. All targets/failures and unknown semantics
remain in P08_RESULTS. Known received usage54750tokens excludes unknown failed billing.
No independent human panel is available; support/usefulness/false-veto labels stay unknown.

Earlier real Neo4j failures remain in the historical20PASS/4FAIL record. Current
serialized7integration checksPASS217.35s and current24control reconciliationPASS.
VM pauses suggest a resource question, not established query blame or measured capacity.
Owner chose Keep other work running; serialize own checks without deadline expansion.
Preserve foreign benchmark/editor processes. Repeatedly failed gates cannot be silently
waived. No new architectural ADR is pending; if completion requires a new contract,
record and obtain the owner's direction under Rule4. No further main push is authorized.

End-review R4 identified invalid@5/10/20 labels on a final top4 packet. ADR0086 withdraws those labels, preserves raw artifacts and exposes only observed packet metrics. Candidate/fused/reranked-stage metrics remain unavailable for this pilot; a new separately frozen full-stage run is required for new claims, alongside independent semantic labels. This limitation is explicit rather than inferred zero or a claimed retrieval result.

## P09 current owner decisions and retained limits

ADR0087–89 explicitly approved: scoped retrieval contracts, non-admin provisioning and
safe evaluator controls. ADR0090 corrects existing guarantees. Owner rejected ADR0091
closure. ADR0095 opt-in5second audit reuse is implemented, with measured large-case
benefit but small-case overhead/expiry misses; PF03 scaling acceptance stays open. The
owner authorizes only handoff completion notes under the benchmark tree and a scoped
verified main push. Earlier dated push/scope restrictions are historical. Semantic
completeness/assertion accuracy, human labels and general deployment readiness remain
unknown; synthetic demo_auth file-permission/bounds hardening is a separately owned
shared-host deployment suggestion, not a confirmed remote vulnerability.


Historical P09 scope note: new concurrent handoff PF07 (graph-link HTTP administration) appeared during P09
closeout in foreign uncommitted edits. It is not covered by approved PF01–06 contracts.
Owner: project owner plus benchmark contributor; destination: separately scoped task,
pre-adversary and Rule4 graph/schema/API authorization if requested. Preserve its text,
do not implement or label it done under that P09 mechanism checkpoint. The later owner
GO and accepted ADR0096 explicitly authorize P10's separate graph API implementation;
E-P10-006 records its current source/installed gates and earlier actual graph consumer.
