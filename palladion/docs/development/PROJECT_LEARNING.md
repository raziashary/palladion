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
