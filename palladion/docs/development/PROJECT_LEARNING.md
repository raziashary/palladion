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

## Future learning entry

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
