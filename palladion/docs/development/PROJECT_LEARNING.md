# Project learning and corrections

This records engineering/research learning, not runtime agent memory or company policy.
An observation needs evidence; a conjecture is labeled. Never convert an untested idea
or copied research reference into a Palladion result. Preserve failed experiments.

## L001 — The blueprint is a design, not a generated application

- Date/type: 2026-10-17; verified repository observation.
- Evidence: initial git tree at `9b167a2` contains only the blueprint; blueprint “Concrete
  prototype repository” and “Representative implementation code” explicitly disclaim a
  complete runnable implementation. E-DOC-001 records the inspected baseline.
- Lesson: planned paths must stay labeled until source and consumer behavior exist.
- Applied: PROJECT_MAP separates actual and planned files; every system gate NOT_RUN.

## L002 — Two completeness claims require different instruments

- Date/type: 2026-10-17; inherited design constraint, not experimental discovery.
- Source: blueprint “Ingestion pipeline and source inventory boundary” and “The unsolved
  missing-document problem.”
- Lesson: accepted-source→index reconciliation can be tested; all external company
  documents being supplied requires user/application attestation. Critic agreement cannot
  bridge that boundary.
- Applied/proof planned: separate INDEX_COVERAGE/INVENTORY_ATTESTED and T12/G-RESEARCH.

## L003 — Examples omit safety-critical implementation work

- Date/type: 2026-10-17; blueprint source observation.
- Source: “Bounded orchestration pseudocode” consumes counters after calls in the sketch,
  followed by an explicit warning that failures/timeouts must still consume/reserve slots.
  “A gate invariant” explicitly omits semantic sufficiency and full ACL logic.
- Lesson: copying examples without surrounding warnings can yield extra attempts or
  unsupported conclusions. Implement from the complete contract, not just the snippet.
- Applied/proof planned: G-BUDGET adversarial failures/concurrency; G-GATE actual claim
  support and label-bypass tests. No runtime bug is claimed because no implementation exists.

## L004 — Scientific control differs from build order

- Date/type: 2026-10-17; blueprint cross-reference observation.
- Source: “Explicit experimental arms” lists B3 graph before B4 policy; “Build plan” places
  graph in Slice 6 after memory/critic. These describe treatments and execution order respectively.
- Lesson: preserve slice order while naming parent treatment explicitly. Internal substrate
  baseline is necessary now; external comparator implementations remain later work.
- Applied: MASTER_DEV_PLAN sequence and RESEARCH_PROTOCOL arm table; future results required.

## L005 — Unsupported rate alone rewards silence

- Date/type: 2026-10-17; methodological risk, not measured Palladion behavior.
- Source: blueprint metrics include usefulness, abstention precision/recall and false vetoes;
  user requests honest scoring.
- Lesson: always score usefulness/coverage and cost beside safety. Empty denominators are
  N/A, not perfect performance. No synthetic scalar winner is justified before criteria freeze.
- Applied: RESEARCH_PROTOCOL metric definitions and future X01 tracks.

## L006 — A module-level row is not an atomic execution task

- Date/type: 2026-10-17; user correction and documentation-reference review.
- Prior claim correction: ~~The initial suite's work-package rows provided sufficient
  execution detail.~~ They grouped several files/behaviors; the user requested the finer
  file-specific checkbox format used in Arcana's master development plan.
- Source: Arcana “Every task names its proof,” provider task examples, active consumer
  proofs and companion gate/goal/map records; Palladion blueprint “Every file and its
  responsibility.” Arcana files were read live as a reference, not copied as authority.
- Applied: ADR-0009 preserves parent IDs and adds bounded child cards with exact planned
  files, explicit dependencies, reader and positive/negative proof. Check planned ownership
  without creating a quota of empty modules. E-DOC-002 records coverage and review.

## L007 — Falsify a validator against the real identifier grammar

- Date/type: 2026-10-17; observed checker defect and correction.
- Prior claim correction: ~~The initial checker checked every gate identifier.~~ Its
  alphabetic-only gate expression omitted `G-E2E`; the atomic proof check exposed that
  gap when a card named only this gate. Broadened parsing to include digits and added an
  undefined numeric-gate mutation. The original runtime remains absent, so no product
  defect or tested data leak is inferred from this documentation-parser issue.
- A second self-test rejected the new proof-kind check: an unanchored expression matched
  DOC inside G-DOC, so an absent kind could pass. Anchored the kind to the field start;
  the deliberately missing-kind mutant now fails for that reason.
- Applied: checker CLI plus in-memory negative controls, E-DOC-002; original E-DOC-001
  check output remains historical with this explicit qualification, not silently erased.

## L008 — Put useful lessons in the instructions every task actually reads

- Date/type: 2026-10-17; explicit user request and method adaptation.
- Source: Arcana “Method rules,” “Dual anchor,” “Per-phase workflow” and “Learnings
  register,” notably false-green checks and helpers whose real consumer was never wired.
- Applied: ADR-0010 and root AGENTS now require substantial premise refutation,
  consumer/readback proof, meaningful negative controls, exact measurement scope,
  visible findings, durable delegation and complete closeout. Keep Palladion's own
  blueprint/permissions, proportional audits and no-UI/synthetic-only boundaries.
- Limit: adopted methods are instructions, not evidence that a future implementation is
  correct. Independent content review and falsifiable behavior remain required.

## L009 — Name the reader available at the task's actual phase

- Date/type: 2026-10-17; independent plan-audit finding and correction.
- Error: ~~P02's retrieval-audit task could prove authorized API trace consumption.~~
  The API reader is implemented at P04-T04.02. An early producer test could not establish
  that later authorization path, despite the stated proof.
- Correction: P02-T04.02 explicitly proves real append→reopen→internal readback in
  telemetry/audit.py; P04-T04.02 owns role-gated HTTP trace consumption and depends on
  the producer task. Early G-SECURITY evidence stays partial. Also repaired P00's stale
  goal header to include D06 and recorded current checker results.
- Evidence: E-DOC-002; independent review found the mismatch before any application code.

## Current owner-answer refinement

## L010 — Accepting a method does not manufacture its empirical answer

- Date/type: 2026-10-17; user answers and mandatory pre-phase review.
- User accepted all twelve recommendation directions, except fake-first runtime; selected
  uv and Groq qwen/qwen3.8-27b, delegated compatible package choice and requested GO hold.
- Applied: ADR-0011–ADR-0023 and risk register distinguish accepted direction, technical
  verification and deferred scope. No tokenization win, fixture age, sample size, human
  reviewer availability or production signoff is invented. Do not re-ask an answered
  direction merely because its implementation proof has not happened.
- Pre-phase adversary identified stale fake-first, unselected-provider, optional-review
  and completed-phase wording before edits. E-DOC-003 records the receipt and corrections.

## L011 — Decision documents must expose the owner's editable answer

- Date/type: 2026-10-17; explicit user instruction and live reference read.
- Arcana's vision “Cross-cutting architecture” uses The call/Why it matters/Options/
  Couples with/My recommendation/owner decision. Its runtime ADR log uses a different
  format; the user's specified question/impact/editable-answer workflow governs here.
- Applied: all existing decisions restructured with original records preserved, new
  decisions use the same fields, and accepted/empty-answer negative checks added.
  Later owner edits require preserving prior answer/date and updating affected consumers.

## L012 — Real generation and deterministic fault testing are different proof

- Date/type: 2026-10-17; user override with blueprint boundary retained.
- Applied: actual Groq is required for generative end-to-end proof. Typed/error/transport
  fixtures can test budgets and malformed-output guards, but cannot claim a provider call
  or replace failed access/rate proof with fake success. Mock operational data remains
  synthetic and read-only. No account request was made during documentation setup.
- Official listing/quota pages confirm published model/free-plan documentation, not this
  account's access or free/unlimited capacity. Future runs record actual usage and bounds.

## Post-audit corrections

## L013 — Keep negative-control mutations attached to the current document shape

- Date/type: 2026-10-17; full-vision post-audit and executable check.
- After Q/ADR links were added, an old literal mutation no longer changed its fixture.
  The self-test correctly reported failure rather than treating no mutation as success.
  Changed the target to the actual ID; preserved the unchanged-fixture guard and reran.
- Auditor also exposed implicit Authority metadata and venv ignore ownership occurring
  too late. Explicit Authority fields/checks and an ignore-before-create owned-file proof
  now close those gaps. E-DOC-003 preserves findings, earlier red output and resolutions.

## L014 — A stateless reviewer needs the governing source explicitly

- Date/type: 2026-10-17; fresh pre-phase adversary finding and owner instruction.
- Prior wording required reviews against the vision, but reserved the explicit full-read
  requirement for P00. A future stateless reviewer could receive only a phase task card.
- Correction: every pre-adversary and single post-work auditor directly reads the full
  blueprint and reports relevant headings/invariants, tasks, consumers, proof and deferred
  obligations. Explicitly include zero-call nonexclusive preflight, four tools, main/critic/
  tool attempt budgets and draft→critic→finalization→gate ordering. E-DOC-004 records review.
- Limit: review coverage is process evidence, not proof of unbuilt runtime behavior.

The final checker first rejected root README/.gitignore task ownership: its allowlist
recognized AGENTS only despite these being existing repository navigation/protection
artifacts. Narrowly permit those two files for P00 only, preserving all other ownership
bounds; negative controls reject unrelated root files and runtime ownership of root README.

## L015 — P01 integration needs a production reader and failing negative controls

- Pre-phase audit found no concrete fixture/registry consumer or exact catalog completeness
  guard. Added offline CLI using real stored authorization/approval/bytes after reopen;
  no P02 ingestion/API shortcut. Multi-phase G-SOURCE/G-SECURITY remain PARTIAL.
- Integration checks caught evidence/policy status vocabulary drift, naive/lexical timestamp
  handling and idempotent metadata aliases. Aligned blueprint enums and UTC metadata;
  source ACL and grant/membership revocation are read from actual stored state.
- Initial fixtures failed because BI data_as_of is an envelope timestamp, not a data
  payload field; later split metadata/source models briefly failed typed bundle assembly.
  Worker corrected source-vs-envelope validation and constructed computed typed sources.
  T01/T02 now distinguish current event time from historical event/current handling.
- SQLite rejection initially enabled WAL before establishing DB ownership. Preflight now
  rejects foreign/newer/incomplete DBs first; byte hashes and no-sidecar tests verify this.
- Windows UTF-8 reads are explicit. Ruff exposed one pre-existing checker blank-line issue;
  corrected without changing checker semantics, and expanded navigation read to app README.
- Latest phase suite: 75 tests pass; no claim of human-annotated gold, model quality or
  future temporal/gate/graph behavior is inferred. E-P01-001 retains observations and limits.

## L016 — Count and label checks do not establish semantic consistency

The single P01 work auditor found that two approved-candidate labels did not prove
policy overlap, and individually valid evidence/source enums could disagree. Fixture
validation must check applicability relationships and trusted instants; evidence envelopes
must bind their kind to the source reference kind. Positive controls must still accept
the four intended pairs and the deliberately injected overlapping policy fixture.
E-P01-001 records fixes, deliberate failing mutations and final resolution evidence.
Two stale GO statements also demonstrated why current status needs a full document sweep.
Final staging exposed a Windows autocrlf risk for hashed source originals. App attributes
now preserve those bytes; a fresh index checkout must pass actual fixture/CLI reads.

## L017 — Real retrieval proof exposes environment and consumer gaps

P02 pre-adversary found missing search/revocation producers and persistent representation
metadata. Owner approved additive v3 before schema changes. Source-preserving parsing,
exact manifests and current canonical readers are distinct from an index acknowledging a
write. A→B→A configuration reindex must read the active generation, not newest-created.
Empty source ACL means authorized case members, requiring a scoped OR in discovery;
boolean payloads need a BOOL index. Repeated collection checks validate existing schema
and create only missing indexes.

Docker became unusable; preserve its install directory. Official glibc build exceeded
Ubuntu's libc; verified musl build works. Native Windows actual writes failed on filesystem
access, so supported standalone execution uses WSL Linux storage. Version output alone
was not proof. Fresh HTTP upload→approval→search→citation and revoke→deny pass against
that real server. Test cleanup needed explicit Qdrant close (no context-manager API).

Metric tests falsified an incorrect expected nDCG calculation. Empty denominators remain
null. A failed measurement stage must make a pilot incomplete; raw run history is kept.
P02 pilots cannot establish full B0/B1/B2 answer-system or general multilingual quality.
User changed future subagents to Luna Medium; preserve earlier High receipts, update
standing instructions and use Medium for all new dispatches. E-P02-001 retains proof.

## New learning entry template

```text
LNNN — title
Date / type: observed | measured | hypothesis | correction
Question and prior belief:
Source / task / gate / run artifact:
Exact observation, negative cases, scope and limitations:
What changed in our understanding:
Action and affected records:
Revisit condition:
```

For a retraction: keep and strike the original false claim, add a new entry with why it
was wrong and which evidence falsified it, and link any ADR/status corrections. Never
erase failed runs or rename a post-hoc threshold as the original goal.

## L018 — Exercise bounds through the real consumer

P02's single work audit found a producer/consumer budget mismatch: discovery allowed40 candidates and reranking allowed30. A real HTTP regression first reproduced400, then passed with a declared ranker budget consumed before ranking. Apply chunk bounds to individual Unicode blocks and exception groups, including separators; preserving exact spans does not require unbounded groups. Normalize expected asset/inference backend failures at the adapter boundary so optional reranking can degrade explicitly. Keep fixture-setup failures separate from the intended negative control. E-P02-001 records resolution and final measurements.

## L019 — Import success is not manifest completeness

The P02 closeout missed three direct dependencies because the installed transitive graph
satisfied imports. Promote directly imported packages with uv add, preserve locked versions,
and check import ownership explicitly, including literal dynamic imports. Protocol ellipses
are interface declarations: trace concrete implementers before calling them unfinished.
A canonical active-generation invariant must also be consumed by maintenance CLIs and
checked transactionally at publication; the follow-up found both gaps. E-P02-002 retains
negative controls, setup mistakes, final test evidence and review scope. New user rule
limits delegation to start adversary/end reviewer, GPT6LunaMedium; coordinator owns the rest.

## L020 — Authority needs producers, readers and an atomic snapshot

P03's pre-adversary found that enum values and tables did not supply trusted times,
authenticated policy approval or fact provenance. Implemented real case/server/event/live
producers; policy inputs resolve persisted gateway IDs, not caller verification labels.
An explicit admin historical mode reconstructs registry knowledge without restoring past
ACLs or granting current permission. Core shape needed an owner-approved extension for
executed outcomes and honest zero-input decisions. Reopened trace readers recompute rows.

54 focused P03 tests and the installed-wheel smoke exercise the domain. Full regressions
initially exposed coordinator startup sequencing (connection refused), then an independent
Windows/WSL TCP abort in an existing P02 setup. Retained failed runs, confirmed same-server
health, verified the exact affected case, then passed disjoint163 domain/contract and8
real-Qdrant groups. No assertion/default weakened or infrastructure fix claimed. Await an
actual listener before dependent checks; keep transport limitations separate from code proof.

## L021 — Probe transport combinations and preserve existing tests

P04 confirmed native Groq tools and plain JSON separately, then falsified assumed combined
JSON-object/native-tool support (HTTP400). Keep capabilities separate until actual proof.
Quota failures remain failed attempts, not schema repairs. Assert actual expected smoke
outcomes and do not infer success when cleanup obscures a result.
An Add File operation replaced an existing security test file. Diff review caught it;
original functions restored and extended before regression. Verify file existence first.
Memory readback must not replay old released text around later source revocation.

## L022 — Revalidate a conflict from canonical provenance

A historical policy replay can reconstruct rule rows yet still lack the time-source IDs
needed to establish a current conflict. The P04 reader exposed that gap. Avoid a second
log as an authority workaround: fix the original producer under explicit contract approval.
The canonical change is owner-approved and implemented in ADR-0034; the original failing regression is retained in evidence, not hidden
with a skip or weakened assertion. Backward read compatibility does not imply older strict
binaries can parse new fields. Clause-bound risk also comes from backend source-span
bindings, not a model's INFORMATIONAL label; its isolated bypass guard passes.


## L023 — Quota direction and header units matter

A1000 limit in error prose was initially mistaken for combined TPM. Actual headers
reported8000TPM/1000RPD; subsequent failures distinguish7000input/1000output minute
limits. Preserve direction, remaining/reset counters and numeric retry hints. A smaller
cap is not proof an entire multi-call request fits; never silently retry/switch a failed
model. Actual provider errors remain engineering failures, not research observations to drop.

## L024 — Own native dispatch and process lifetime

Transport carries native calls; loop validates shape/types/unique IDs and reserves
budgets; Tools.execute owns scoped dispatch and returns matching name/id results.
Reject malformed argument types before .encode/hash operations. Cancellation must persist
the attempted tool and terminate/join its local search process. Windows pipes also need
closing/draining after termination; an exited child alone did not prevent a resource warning.

## L025 — Negative controls need precise expected outcomes

Healthy exact-ID absence is intentionallyDEGRADED; dependency failure is not the same
condition. Verify the actual warning plus correlated auditNONE. An intentionally failing
adapter must recordLIVE_UNAVAILABLE while safe abstention passes its negative control;
provider400/429 or malformed-model failures remain disallowed. Preserve original failed
assertions/runs, document their mechanism, and prove the corrected consumer reads the record.


## L026 — Follow alternate readers and verify the schema before querying

A redacted timeline/trace did not protect raw request payloads retrievable through its
event IDs. Trace every evidence/recall reader; test canary absence for both the owner
and another case member. Preserve only owner-scoped unverified prior reports internally.
The first correction guessed principal_id where the existing schema uses actor_id;
that caused16 focused failures. Reading the actual schema fixed it, and34 focused
checks then passed. Search scope must likewise come from an executed tool result,
not a constant label attached to every response. E-P04-001 retains both red controls
and the failed first implementation.


## L027 — Memory scope and validity need a canonical owner

Use explicit persisted team membership, owner/admin controls and immutable fact revisions;
repetition is never promotion. Unknown lifetime staysUNSPECIFIED. Legacy unowned rows
are preserved but never silently assigned to a reader. Back up recognized persistent
schemas before forward migration and reopen the backup to prove restoration state.

## L028 — A packet can remember correctly while an answer still omits a gap

The actual P05 pilot retained settlement_state in both B5 packets, but the compressed
answer omitted it after a provider tool-generation failure. Report packet and answer
omissions separately; allthree conditions had strict completionfalse. A CLI that saves
all observations is not evidence that the model completed every task. Old observations
remain RECHECK_FOR_CURRENT_DECISION and require new material reads. Same-source cache
hits still validate current ACL/time/bytes; no performance benefit is inferred.

## L029 — SQLite context managers do not close connections

The first P05 pilot produced allthree response rows, then Windows cleanup failed because
native sqlite3 context managers only commit/rollback. Use contextlib.closing for owned
backup/clone connections. Preserve the failed lifecycle receipt and verify the corrected
CLI completes cleanup; never swallow permission errors or invent a successful smoke.


## L030 — Scope filtering must precede bounded recall ranking

Filtering only after LIMIT500 allowed501newer private memories to crowd out an older
permitted item. The legacy query reproduces the omission; the corrected structured,
FTS and packet readers recover the authorized item without private canaries. Scope,
current membership, active validity and revision state now filter before the window;
canonical source ACL/bytes/time still revalidate afterward. The model receives explicit
non-exhaustive/incomplete-window metadata; a bounded search never proves full absence.
Sole end reviewer resolves both this defect and stale authorization text.

## L031 — Absence of a gap is not evidence that it was resolved

Latest-answer-only state dropped an unresolved settlement question when a later failed
reply had an empty missing-input list. A second-message pilot could not detect this
third-turn defect. Preserve unresolved state from authorized decisive canonical policy
traces and retain generic nonempty case questions; only an executed resolving result
can clear a policy requirement. Prove both persistence after failure and resolution
after real policy execution. Main retracted premature closure openly before commit,
kept the red regressions, rebuilt the artifact and reused the same end reviewer.

## L032 — Freeze every route that can carry the supposedly missing evidence

The first critic discovery fixture already carried appendix clause previews through
its policy decision. Freezing a draft and standalone document IDs did not remove that
confound. Inspect the complete canonical model view before claiming an evidence gap;
version the fixture and preserve the original measured rows and loaded source snapshot.

## L033 — Output omission does not identify the cause of a veto

A supported fact absent from a final answer is an observable retention loss. It can
come from finalization, quota failure or review; naming it a critic veto invents a
causal result. Report retention and known-control false objections separately, leave
causal/semantic judgments unknown, and derive corrected summaries without modifying
original artifacts. A shorter correct exception excerpt is also not the full-clause
match required by a preregistered strict scorer.

## L034 — Trusted phases, exact clauses and final-source evidence

Finalization instructions belong in the trusted system phase, not an untrusted data key.
A document ID can retrieve an introduction rather than the required clause: prove full
canonical clause recovery, later review and final readback. Prompt changes invalidate
claims that an earlier experiment measures final source. Preserve old receipts and repeat
the complete matrix. Final20B16conditions retain all known facts but0/4full-clause
corrections and one validation failure; targeted positive engineering checks cannot
supersede neutral research results. E-P06-001 and ADR0058–0061 preserve both boundaries.

## L035 — Completed review is not final-proposal review

End auditor R1 found a stored draft digest with no gate consumer. Compare the actual
final proposal to that digest and qualify changed proposals; likewise qualify unresolved
CHALLENGE. Keep canonical facts visible without inventing conflict or semantic veto.
Unchanged PASS positive controls must still work. Source/installed tests plus both actual
Groq consumers verify the fix (ADR0062/E-P06-002). R2 was refuted by reading exact §10.1:
the permitted blind first pass withholds the draft, not canonical policy requirements.

A suite exit0 can mean SKIPPED: check enable flags and counts before reporting PASS.
Concurrent model/index tests also confound latency: retain connection-abort/deadline
failures and run missing checks serially rather than changing timeouts or model budgets.
