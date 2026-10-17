# Architecture and development decision log

Material decisions are recorded when made. Statuses: `ACCEPTED`, `PROPOSED`, `SUPERSEDED`,
`REJECTED`. Accepted blueprint constraints below are inherited decisions, not evidence
of implementation. Do not turn an unresolved research choice into an accepted default.

New entries use: ID, date, status, decision owner, context/source, what, why, alternatives,
where/how, consequences, validation and reopening condition. Cite blueprint headings,
not line numbers. Append corrections; strike a wrong original claim and explain the error
mechanism in a new entry. Superseding a rule needs the applicable user approval.

## ADR-0001 — Repository and development-document layout

- Date/status/owner: 2026-10-17; ACCEPTED; coordinator interpreting the user's named paths.
- Context: user identifies `palladion/docs/vision/palladion-blueprint-v2.md`, requests the
  suite in that docs tree, and reserves sibling `baseline/`. Actual root is `C:/palladion`.
- Decision: canonical working suite is `palladion/docs/development/`; vision stays in
  `palladion/docs/vision/`. Root AGENTS/README and docs README route readers here.
  The illustrative `evidence-agent/` root in “Concrete prototype repository” maps to
  `palladion/`; retain planned package name `evidence_agent` until explicitly changed.
- Reason/alternatives: reuses the existing project/docs boundary; avoids a second
  nested repository or multiple working-memory folders. No product files created now.
- Consequences: one memory, one plan and one progress authority. New documentation
  does not count toward the blueprint's proposed 74 runtime/support-file manifest.
- Proof/reopen: G-DOC and repository path inspection. Reopen if the user chooses a
  different system/package layout; update links and map together.

## ADR-0002 — System-first scope and deferred external comparisons

- Date/status/owner: 2026-10-17; ACCEPTED; user instruction.
- Context: current task is development suite; user excludes UI and reserves baseline
  systems for later honest comparison. Blueprint “Build plan” prioritizes vertical slices.
- Decision: P00 documents only; P01–P08 describe future system implementation and tests;
  no UI phase. Keep `baseline/` unpopulated in this task. Internal B0–B9 experiments
  test the substrate and additions; X01 later compares distinct external systems.
- Reason/alternatives: immediate full application/UI/comparator scaffolding would
  exceed the requested outcome. Delaying all internal baselines would defeat the science.
- Where/how: MASTER_DEV_PLAN, GOAL, RESEARCH_PROTOCOL and root instructions.
- Consequences: no provider calls, infrastructure installation, application promises or
  performance claims now. External systems need a defined comparison contract later.
- Proof/reopen: G-DOC scope review; reopen comparator scope with a subsequent user task.

## ADR-0003 — Evidence authority and modular ownership

- Date/status/owner: 2026-10-17; ACCEPTED; inherited blueprint “Locked decisions,”
  “Canonical truth, derived indexes, and evidence classes,” “Directory responsibilities.”
- Decision: modular Python 3.11+ monolith; FastAPI transport; SQLite registry/originals
  and scoped memory; Qdrant dense+BM25 discovery; optional separate Neo4j provenance.
  Approved source clauses, typed policy traces and scoped observations warrant claims.
  Retrieval scores, graph paths, memory and either model never create authority.
- Why/alternative: a model-only or index-payload authority path would bypass the trust chain.
- Where/how: `agent → domain tools → storage`; ACL before any evidence text reaches
  model/display, then revalidation at citation/final release boundaries. Policy/gate
  cannot invoke a generative model to establish deterministic business rules.
- Consequences: schema/source hashes, exact spans, manifests and replayable traces are
  required. Cross-store staged publication is not a distributed transaction.
- Validation/reopen: G-SOURCE, G-SECURITY, G-GATE; changes to locked architecture require direction.

## ADR-0004 — Temporal policy and operational boundaries

- Date/status/owner: 2026-10-17; ACCEPTED; inherited “Policy-specific temporal applicability,”
  “Policy evaluation contract,” and “Live operational / BI adapters.”
- Decision: scope + declared trusted time basis + half-open valid interval + explicit
  matching supersession/record cutoff select policy. No revision/similarity tie breaker.
  Safe bounded JSON AST evaluates evidence-linked facts; missing and unavailable are distinct.
  Named read-only adapters preserve observed_at, source_event_at and data_as_of separately.
- Why/alternative: latest-upload policy and fresh read-time BI would produce invalid decisions.
- Where/how: policy registry/temporal/engine, live gateway, final gate.
- Consequences: four time bases, conflict/default review, source-linked rule traces and
  mock-first fixtures. Time-basis migration and freshness values remain owner decisions.
- Validation/reopen: G-TEMPORAL, G-POLICY, G-LIVE; no real connector/payment writes authorized.

## ADR-0005 — Bounded investigation, critic and final release

- Date/status/owner: 2026-10-17; ACCEPTED; inherited “Exact call budget,” “Exactly four
  LLM-facing read tools,” “Main agent, critic and evidence gate ordering.”
- Decision: exactly `search_knowledge`, `evaluate_policy`, `lookup_live_data`, `recall_memory`;
  deterministic nonexclusive preflight; ≤5 main calls including finalization, ≤3 critic
  calls normally one. Reserve final main call; failed attempts consume budget. No sixth
  call for invalid final JSON; use safe deterministic rendering.
- Decision continued: mandatory critic for normative/operational drafts during prototype
  evaluation; ≤2 critic counter-searches as initial configured limit. Other starting tool,
  token, graph, passage/time values are explicit tunables, not business truths.
- Why/alternative: single-winner routing, uncounted repairs and critic PASS as authority
  would violate the blueprint. A fake critic during early tests is not substantive review.
- Where/how: runtime counters and deadline, schema validation, ledger and deterministic gate.
- Consequences: five dispositions and useful qualified outcomes; P04 normative outputs
  stay safely limited until P06 review exists. Adaptive critic/planner are later experiments.
- Validation/reopen: G-BUDGET, G-CRITIC, G-GATE; tuning recorded before evaluation, hard caps
  and mandatory-review changes require explicit decision.

## ADR-0006 — Continuity is attributed state

- Date/status/owner: 2026-10-17; ACCEPTED; inherited “Continuity packet and SQLite memory.”
- Decision: application builds packet from typed events; preserve observed/reported/
  hypothesis distinctions and scope. User/owner controls reported-fact validity; live
  freshness follows approved use requirements. Handles must be revalidated under current ACL.
- Why/alternative: model-written recaps as truth and automatic global promotion poison memory.
- Where/how: memory store/packet/hotcache, case events, authorized promotion operations.
- Consequences: no silent TTL, cross-case drift or retained principal grants; sqlite-vec
  remains optional pending evidence. Developer PROJECT_MEMORY is unrelated to runtime memory.
- Validation/reopen: G-MEMORY and G-SECURITY; validity/retention owner choices stay in risk log.

## ADR-0007 — Research discipline and gate meanings

- Date/status/owner: 2026-10-17; ACCEPTED; user asks honest scoring; blueprint “Research
  evaluation,” “Initial acceptance gates,” “Questions deliberately left to experiments.”
- Decision: keep B0–B9 labels; frozen retrieval data, repeated model runs, independent gold
  adjudication, held-out separation and paired critic controls. Report safety, utility,
  abstention, recall, latency and cost separately. No composite leaderboard score now.
- Why/alternative: blanket refusal can lower unsupported claims while destroying usefulness;
  unequal tools/calls/corpora or model self-grading would confound conclusions.
- Where/how: RESEARCH_PROTOCOL, TESTING_GATES, evaluation runner and run manifests later.
- Consequences: fixed integrity gates differ from empirical targets calibrated after B0/B1;
  no success guarantee. Negative/neutral experiments remain publishable evidence.
  Multi-phase gates remain PARTIAL until all obligations are exercised; early phases
  close only their own accepted subset, without claiming later consumer coverage.
- Validation/reopen: G-RESEARCH; numerical targets/splits/repetitions and external capability
  tracks must be frozen in future records before held-out runs.

## ADR-0008 — Development agent model constraint

- Date/status/owner: 2026-10-17; ACCEPTED; direct user instruction.
- Decision: all development subagents use GPT 6 Luna High (`gpt-6-luna`, `high`).
  This constrains development delegation, not Palladion's eventual runtime model choice.
- Why/alternative: user explicitly requested this model/effort for every subagent.
- Where/how: AGENTS, task protocol, explicit model and effort on each dispatch; scoped
  read-only audit tasks where editing is unnecessary. No silent fallback if unavailable.
- Consequences/proof: dispatch metadata in current session; initial independent blueprint
  auditor used those settings. Runtime provider remains an experimental factor (Q02).
- Reopen: only on user instruction.

## ADR-0009 — File-specific atomic execution register

- Date/status/owner: 2026-10-17; ACCEPTED; user's requested refinement of the development suite.
- Context: the initial master plan's P01–P08 rows bundle several files and behaviors.
  User requests atomic tasks using Arcana's `docs/restructurization/development/` as a
  documentation reference. Inspected its master plan “The document family,” “Every task
  names its proof,” provider/active-phase task examples, and companion gate/goal/map records.
- Decision: preserve existing Pxx-Txx IDs as work-package IDs; append stable child IDs
  `Pxx-Txx.nn` as executable checkbox tasks in the same master plan. Each child names exact
  planned file paths, dependencies, one bounded change, its reader, and falsifiable proof.
  No blind one-task-per-file quota: a behavior can touch its owner, wiring and test together.
- Where/how: master plan atomic register, task-reading/closure protocol, documentation
  validator, gate ownership links, progress/goal/map/memory/learning/evidence records.
  Checkbox task state lives in the plan; PROGRESS summarizes phases and active task.
- Consequences: old group references retain meaning; a group closes only when all children
  and its acceptance pass. Planned file coverage is checked against blueprint §12.2, but
  code presence is never inferred. If implementation consolidates a planned file, record
  its owner/consumer mapping and revise the plan before closing the changed contract.
- Alternatives: replacing/renumbering old IDs breaks traceability; simply appending file
  lists leaves multi-deliverable tasks ambiguous. Copying Arcana's product rules would
  import unrelated architecture, readiness scores and approvals, so those do not transfer.
- Validation: E-DOC-002 and G-DOC cover child metadata, parent/dependency references,
  dependency cycles, blueprint file ownership and deliberate validator failures; independent
  GPT 6 Luna High review checks semantic task size, sequencing and coverage.
- Reopen: if source or owner decisions change a task boundary; keep IDs and dated history.

## ADR-0010 — Adapt Arcana's evidence and development rules for Palladion

- Date/status/owner: 2026-10-17; ACCEPTED; user explicitly requested selection and tailoring
  of useful Arcana master-plan rules into Palladion AGENTS, then continuation.
- Context/source: inspected Arcana “Rules of Development,” “Every task names its proof,”
  “Adversarially verify every phase BEFORE building it,” “Method rules,” “Per-phase workflow,”
  “Dual anchor,” and the “Learnings register,” including false-green and unused-helper examples.
- Decision: add local rules for dual grounding, bounded atomic tasks, pre-build refutation,
  actual consumers, meaningful negative controls, exact measurement/scope, visible review
  resolution, incremental durable delegation, learning/no-stale updates and fresh/populated
  lifecycle proof. Put a complete closeout sequence in AGENTS where every task reads it.
- Why: these methods address Palladion's core risks—citation laundering, incomplete
  evidence, unwired gates, stale memory, budget failures and overstated research claims.
- Where/how: root AGENTS, master-plan task protocol/atomic P00-T04.05, G-DOC content review,
  PROJECT_LEARNING and E-DOC-002. No product code or deployment approval added.
- Boundaries: do not import Arcana's two-auditor minimum, every-finding owner veto, public
  deployment requirement, numeric readiness weights, platform triples, Rust/Tauri scope,
  GO history or destructive-operation examples. Use proportional independent review and
  the user's universal escalation rules. No rule is silently narrowed by this adaptation.
- Consequences/proof: AGENTS must match the atomic plan and preserve current scope,
  synthetic-only operations, Luna High constraint and explicit push permissions. Independent
  review checks for conflict with universal rules; documentation self-tests prove structure.
- Reopen: when a concrete source/behavior conflict or user instruction changes a method.

## Future decision template

```text
ADR-NNNN — title
Date / status / decision owner:
Context and governing source headings:
What / why / alternatives:
Where / how / affected consumers:
Consequences / risks:
Validation and evidence:
Supersedes / reopening condition:
```

Next free ADR number: 0011. Pending choices live in [risks](RISKS_AND_OPEN_QUESTIONS.md), not
as implicitly accepted ADRs. Record implementation-time material choices immediately.
