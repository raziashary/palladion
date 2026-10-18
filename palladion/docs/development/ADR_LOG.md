# Architecture and development decision log

Updated 2026-10-17. This is the canonical owner-answer record. All twelve Q01–Q12
recommendation directions are accepted by the user's current instruction, with the
explicit override: real Groq `qwen/qwen3.8-27b` instead of a fake-first runtime. Technical
verification is recorded per phase: P01 foundation compatibility/consumers are now tested
(E-P01-001); provider, retrieval and empirical research obligations remain unexecuted.
Approval alone is not proof.

## How to read and edit decisions

Read Authority/Status → Question → Why → Options → Recommendation → What affects what → **My answer
(editable)** → Verification. The owner may edit the answer directly. An empty answer is
OPEN; a recommendation alone is not acceptance. Before affected work, read that field
and the latest user instructions. Preserve the previous answer and date as an amendment
when it changes; do not erase history or silently narrow it. Record authority, status and
verification separately. Statuses: ACCEPTED, PROPOSED, SUPERSEDED, REJECTED. An accepted
direction can have execution state PLANNED, VERIFY_AT_IMPLEMENTATION or DEFERRED.

ADRs 0001–0010 retain their original records as historical evidence beneath the new
editable structure. Later amendments govern current choices; historical wording is not
an instruction to revert those choices. In particular, ADR-0011 replaces optional phase
review with required reviews; ADR-0013 replaces fake-first runtime with uv/Groq. This
is an explicitly approved deviation from blueprint Slice 3's mock-LLM-first suggestion;
the four tools, canonical evidence, mock operational APIs and integrity gates remain.

## ADR-0001 — Repository and development-document layout

**Status:** ACCEPTED; original decision date 2026-10-17; restructured without a new owner vote.

**Authority:** 2026-10-17 user-specified project/docs paths, plus coordinator layout interpretation retained in the historical record.

**Question:** Where do project code and durable working documents live?

**Why:** Preserve the source-grounded scope and trust boundaries in the original record;
its rationale and evidence are retained below rather than replaced by a new claim.

**Options:** Retain the accepted direction or explicitly amend it; the historical record
preserves alternatives considered. Current amendments: ADR-0011 governs GO, ADR format and phase reviews; ADR-0013 governs uv/Groq. Apply them over conflicting historical wording.

**Recommendation:** Keep one system root palladion/ and one development folder; interpret the blueprint tree here.

**What affects what:** AGENTS.md; palladion/docs/development/; planned src/evidence_agent/; navigation and task readers.

**My answer (editable):** Retain the previously accepted decision, subject to the current
amendments above. This records existing authority; it is not a fabricated new owner quote.

**Verification:** Original verification obligations remain planned unless EVIDENCE_LOG
records executed proof. Current documentation conformity is checked by G-DOC/E-DOC-003.

### Historical record for ADR-0001

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

**Status:** ACCEPTED; original decision date 2026-10-17; restructured without a new owner vote.

**Authority:** 2026-10-17 explicit user system-first, no-UI and deferred-comparator instruction; latest user GO hold applies.

**Question:** What is authorized now, and when do UI/comparator implementations start?

**Why:** Preserve the source-grounded scope and trust boundaries in the original record;
its rationale and evidence are retained below rather than replaced by a new claim.

**Options:** Retain the accepted direction or explicitly amend it; the historical record
preserves alternatives considered. Current amendments: ADR-0011 governs GO, ADR format and phase reviews; ADR-0013 governs uv/Groq. Apply them over conflicting historical wording.

**Recommendation:** Documentation and hypothesis-first system plan; no UI; baseline/ is deferred. Current implementation is held for GO.

**What affects what:** GOAL; MASTER_DEV_PLAN; baseline/ boundary; implementation and research readers.

**My answer (editable):** Retain the previously accepted decision, subject to the current
amendments above. This records existing authority; it is not a fabricated new owner quote.

**Verification:** Original verification obligations remain planned unless EVIDENCE_LOG
records executed proof. Current documentation conformity is checked by G-DOC/E-DOC-003.

### Historical record for ADR-0002

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

**Status:** ACCEPTED; original decision date 2026-10-17; restructured without a new owner vote.

**Authority:** Blueprint v0.2 Locked decisions, System architecture and Directory responsibilities; accepted by the original user mandate.

**Question:** Which layer owns evidence authority and system responsibilities?

**Why:** Preserve the source-grounded scope and trust boundaries in the original record;
its rationale and evidence are retained below rather than replaced by a new claim.

**Options:** Retain the accepted direction or explicitly amend it; the historical record
preserves alternatives considered. Current amendments: ADR-0011 governs GO, ADR format and phase reviews; ADR-0013 governs uv/Groq. Apply them over conflicting historical wording.

**Recommendation:** Canonical registry/originals, valid policy traces and scoped observations own authority; derived indexes/models do not.

**What affects what:** Planned core/security/storage/retrieval/policy/live/agent; source and final-gate consumers.

**My answer (editable):** Retain the previously accepted decision, subject to the current
amendments above. This records existing authority; it is not a fabricated new owner quote.

**Verification:** Original verification obligations remain planned unless EVIDENCE_LOG
records executed proof. Current documentation conformity is checked by G-DOC/E-DOC-003.

### Historical record for ADR-0003

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

**Status:** ACCEPTED; original decision date 2026-10-17; restructured without a new owner vote.

**Authority:** Blueprint v0.2 Policy-specific temporal applicability, Policy evaluation contract and Live adapters; accepted blueprint constraint.

**Question:** How are policy time and live operational boundaries enforced?

**Why:** Preserve the source-grounded scope and trust boundaries in the original record;
its rationale and evidence are retained below rather than replaced by a new claim.

**Options:** Retain the accepted direction or explicitly amend it; the historical record
preserves alternatives considered. Current amendments: ADR-0011 governs GO, ADR format and phase reviews; ADR-0013 governs uv/Groq. Apply them over conflicting historical wording.

**Recommendation:** Declared trusted time basis, explicit scoped supersession and safe typed predicates; mock read-only operations preserve all timestamps.

**What affects what:** Planned policy/temporal.py, policy/engine.py, live/gateway.py; final gate and audit readers.

**My answer (editable):** Retain the previously accepted decision, subject to the current
amendments above. This records existing authority; it is not a fabricated new owner quote.

**Verification:** Original verification obligations remain planned unless EVIDENCE_LOG
records executed proof. Current documentation conformity is checked by G-DOC/E-DOC-003.

### Historical record for ADR-0004

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

**Status:** ACCEPTED; original decision date 2026-10-17; restructured without a new owner vote.

**Authority:** Blueprint v0.2 Exact call budget, Four read tools and Final evidence gate; accepted blueprint constraint.

**Question:** How is bounded investigation released safely?

**Why:** Preserve the source-grounded scope and trust boundaries in the original record;
its rationale and evidence are retained below rather than replaced by a new claim.

**Options:** Retain the accepted direction or explicitly amend it; the historical record
preserves alternatives considered. Current amendments: ADR-0011 governs GO, ADR format and phase reviews; ADR-0013 governs uv/Groq. Apply them over conflicting historical wording.

**Recommendation:** Exactly four read tools, five main calls including final, at most three critic calls, independent deterministic final gate.

**What affects what:** Planned agent/loop.py, tools.py, critic.py, gate.py; API response and persisted events.

**My answer (editable):** Retain the previously accepted decision, subject to the current
amendments above. This records existing authority; it is not a fabricated new owner quote.

**Verification:** Original verification obligations remain planned unless EVIDENCE_LOG
records executed proof. Current documentation conformity is checked by G-DOC/E-DOC-003.

### Historical record for ADR-0005

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

**Status:** ACCEPTED; original decision date 2026-10-17; restructured without a new owner vote.

**Authority:** Blueprint v0.2 Continuity packet and SQLite memory; accepted blueprint constraint.

**Question:** What may continuity remember and authorize?

**Why:** Preserve the source-grounded scope and trust boundaries in the original record;
its rationale and evidence are retained below rather than replaced by a new claim.

**Options:** Retain the accepted direction or explicitly amend it; the historical record
preserves alternatives considered. Current amendments: ADR-0011 governs GO, ADR format and phase reviews; ADR-0013 governs uv/Groq. Apply them over conflicting historical wording.

**Recommendation:** Application-generated attributed state; owner-controlled reported validity; live freshness independently rechecked; no automatic global promotion.

**What affects what:** Planned memory/store.py, packet.py, hotcache.py; next authorized request and canonical resolver.

**My answer (editable):** Retain the previously accepted decision, subject to the current
amendments above. This records existing authority; it is not a fabricated new owner quote.

**Verification:** Original verification obligations remain planned unless EVIDENCE_LOG
records executed proof. Current documentation conformity is checked by G-DOC/E-DOC-003.

### Historical record for ADR-0006

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

**Status:** ACCEPTED; original decision date 2026-10-17; restructured without a new owner vote.

**Authority:** User honest-comparison mandate and blueprint v0.2 Research evaluation; no numerical result inferred.

**Question:** How will evidence quality and research claims be evaluated?

**Why:** Preserve the source-grounded scope and trust boundaries in the original record;
its rationale and evidence are retained below rather than replaced by a new claim.

**Options:** Retain the accepted direction or explicitly amend it; the historical record
preserves alternatives considered. Current amendments: ADR-0011 governs GO, ADR format and phase reviews; ADR-0013 governs uv/Groq. Apply them over conflicting historical wording.

**Recommendation:** Keep frozen controls, independent labels, held-out separation, raw safety/utility/cost metrics and negative results.

**What affects what:** RESEARCH_PROTOCOL; TESTING_GATES; planned scripts/evaluate.py; result and scorer readers.

**My answer (editable):** Retain the previously accepted decision, subject to the current
amendments above. This records existing authority; it is not a fabricated new owner quote.

**Verification:** Original verification obligations remain planned unless EVIDENCE_LOG
records executed proof. Current documentation conformity is checked by G-DOC/E-DOC-003.

### Historical record for ADR-0007

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

**Status:** ACCEPTED; original decision date 2026-10-17; restructured without a new owner vote.

**Authority:** Original user instruction required GPT 6 Luna High; superseding user instruction
2026-10-18 requires GPT 6 Luna Medium for every new dispatch (ADR-0026).

**Question:** Which models may development subagents use?

**Why:** Preserve the source-grounded scope and trust boundaries in the original record;
its rationale and evidence are retained below rather than replaced by a new claim.

**Options:** Retain the accepted direction or explicitly amend it; the historical record
preserves alternatives considered. Current amendments: ADR-0011 governs GO, ADR format and phase reviews; ADR-0013 governs uv/Groq. Apply them over conflicting historical wording.

**Recommendation:** Use GPT 6 Luna Medium for every newly dispatched development subagent; this is separate from Groq runtime generation. The user superseded the original High-effort direction on 2026-10-18.

**What affects what:** All development dispatches; pre-phase adversary and post-phase auditor receipts.

**My answer (editable):** Retain the previously accepted decision, subject to the current
amendments above. This records existing authority; it is not a fabricated new owner quote.

**Verification:** Original verification obligations remain planned unless EVIDENCE_LOG
records executed proof. Current documentation conformity is checked by G-DOC/E-DOC-003.

### Historical record for ADR-0008

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

**Status:** ACCEPTED; original decision date 2026-10-17; restructured without a new owner vote.

**Authority:** Direct user follow-up requesting Arcana-style atomic file-specific tasks; original accepted record retained.

**Question:** What makes a task executable and traceable?

**Why:** Preserve the source-grounded scope and trust boundaries in the original record;
its rationale and evidence are retained below rather than replaced by a new claim.

**Options:** Retain the accepted direction or explicitly amend it; the historical record
preserves alternatives considered. Current amendments: ADR-0011 governs GO, ADR format and phase reviews; ADR-0013 governs uv/Groq. Apply them over conflicting historical wording.

**Recommendation:** Retain stable parent IDs and atomic child cards with exact files, dependencies, reader and falsifiable proof.

**What affects what:** MASTER_DEV_PLAN checkboxes; check_docs.py; PROGRESS summaries and evidence records.

**My answer (editable):** Retain the previously accepted decision, subject to the current
amendments above. This records existing authority; it is not a fabricated new owner quote.

**Verification:** Original verification obligations remain planned unless EVIDENCE_LOG
records executed proof. Current documentation conformity is checked by G-DOC/E-DOC-003.

### Historical record for ADR-0009

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

**Status:** ACCEPTED; original decision date 2026-10-17; restructured without a new owner vote.

**Authority:** Direct user follow-up requesting useful Arcana rules tailored into Palladion AGENTS; amended review rule in ADR-0011.

**Question:** Which Arcana development methods apply to Palladion?

**Why:** Preserve the source-grounded scope and trust boundaries in the original record;
its rationale and evidence are retained below rather than replaced by a new claim.

**Options:** Retain the accepted direction or explicitly amend it; the historical record
preserves alternatives considered. Current amendments: ADR-0011 governs GO, ADR format and phase reviews; ADR-0013 governs uv/Groq. Apply them over conflicting historical wording.

**Recommendation:** Adapt dual grounding, real-consumer proof, meaningful checks, scope/measurement discipline and durable learning; follow ADR-0011 for mandatory reviews.

**What affects what:** AGENTS; task protocol; testing gates, learning and closeout; no Arcana runtime/UI imported.

**My answer (editable):** Retain the previously accepted decision, subject to the current
amendments above. This records existing authority; it is not a fabricated new owner quote.

**Verification:** Original verification obligations remain planned unless EVIDENCE_LOG
records executed proof. Current documentation conformity is checked by G-DOC/E-DOC-003.

### Historical record for ADR-0010

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

## ADR-0011 — Editable decisions, mandatory phase reviews and GO boundary

**Status:** ACCEPTED; authority: user instruction 2026-10-17.

**Authority:** Current explicit user instruction on editable ADRs, mandatory pre/post phase reviews, full-suite vision audits and WAIT_FOR_GO.

**Question:** How should owner answers, phase adversaries, work audits and the current hold be governed?

**Why:** Optional review wording and a flat bullet ADR made decisions hard to edit and did not reflect the new mandate.

**Options:** Keep optional reviews and old format, or adopt the explicitly requested structured answer workflow and mandatory reviews.

**Recommendation:** Use this editable structure; before each phase one GPT 6 Luna Medium adversary refutes tasks against source/vision; after validation/smoke/gates one GPT 6 Luna Medium work auditor audits evidence and consumers. Coordinator resolves findings. For this task both coordinator and that auditor inspect every development doc against the entire blueprint.

**What affects what:** AGENTS and MASTER_DEV_PLAN schedule both independent reviews; TESTING_GATES/EVIDENCE_LOG retain receipts and findings; PROGRESS is WAIT_FOR_GO after docs closure. No implementation/install/venv/model call/push now.

**My answer (editable):** User explicitly requested this structure and review sequence, and said to restructure the docs and wait for GO. The latest user additionally requires coordinator plus subagent whole-development/full-vision audits.

**Verification:** E-DOC-003 completed the original whole-suite review. E-DOC-004 records
the fresh pre/post reviews of the final amendment and the same auditor's resolution
recheck. Documentation review is complete; runtime remains unverified.

**Amendment history (2026-10-17):** The original answer above required docs-only
WAIT_FOR_GO and no push. The user now requires both future review roles to consider the
blueprint, authorizes publishing verified documentation to main, and retains the P01 GO
hold. Apply MASTER_DEV_PLAN “Blueprint review contract for both reviewers”: both read
the complete blueprint and report phase-local coverage/findings. Separately authorized
machine repair and the user-created .venv do not grant product implementation GO.
Original answers/authority remain above; this amendment records the newer instruction.

## ADR-0012 — Q01 — Synthetic approval authority

**Status:** ACCEPTED; authority: user instruction 2026-10-17.

**Authority:** Current user instruction accepts all open-question recommendation directions; ADR-0013 records the explicit uv/Groq exception and package delegation.

**Question:** What constitutes trusted approval in the synthetic prototype?

**Why:** Source prose cannot approve itself; authenticated identity and scope must exist outside the document.

**Options:** Authenticated administrator events; simulated signatures; imported document-management attestations.

**Recommendation:** Start with authenticated administrator approval events and separate upload/approval grants; add signature simulation only if a later hypothesis requires it.

**What affects what:** Planned registry/metadata/access code produces approval records read by source resolver, policy registry and final gate; Q01 direction is accepted.

**My answer (editable):** Accept the recommendation, as part of the user's approval of all open-question recommendations.

**Verification:** P01 subset verified at E-P01-001: persisted approval/readers reject
self-approval and unauthorized approvers. Full G-SOURCE/G-SECURITY retain later P02/API/index
obligations and remain PARTIAL.

## ADR-0013 — Q02 — uv and real Groq runtime generation

**Status:** ACCEPTED; authority: user instruction 2026-10-17.

**Authority:** Current user instruction accepts all open-question recommendation directions; ADR-0013 records the explicit uv/Groq exception and package delegation.

**Question:** Which environment, package authority and generative model should implementation use?

**Why:** The user rejects fake-first runtime, supplies a Groq key and selects the exact model; development-agent models must remain distinct.

**Options:** Prior fake-first suggestion (overridden); actual Groq model as selected; any future provider/model change only by an explicit recorded decision.

**Recommendation:** Use uv with uv venv in C:/palladion/palladion, creating the app-local .venv; baseline/ later owns a separate environment. Use Groq qwen/qwen3.8-27b for actual initial runtime generation, including main and critic contexts. Select compatible packages/pins within the blueprint under delegated package authority after GO.

**What affects what:** Planned pyproject.toml/uv.lock, settings and agent/llm.py; actual Groq HTTP/tool/structured-output path and runtime smokes; root .env stays at C:/palladion/.env and is command-locally loaded. Ensure .venv/ is ignored before creating it. Do not copy the key or silently switch model. Groq does not select an embedding model.

**My answer (editable):** User: use Groq, model qwen/qwen3.8-27b, Python via uv/uv venv; free to select/install other packages. Root .env/key and gitignore were user-prepared. User asks documentation only until GO.

**Verification:** VERIFY_AT_IMPLEMENTATION for account access, tool/schema behavior,
quota and actual call. Correction: ~~uv is not on the current shell PATH~~ was the initial
observation. Separate authorized machine repair installed working uv; the user created
the app .venv and E-DOC-004 verifies existence/ignore protection. E-P01-001 now verifies
P01 pins, locked sync and installed-wheel compatibility on Python 3.14.7. Actual model
integration remains P04 proof; deterministic fixtures cannot substitute for it.

## ADR-0014 — Q03 — Qdrant hybrid compatibility

**Status:** ACCEPTED; authority: user instruction 2026-10-17.

**Authority:** Current user instruction accepts all open-question recommendation directions; ADR-0013 records the explicit uv/Groq exception and package delegation.

**Question:** How are native RRF and sparse BM25 made reproducible?

**Why:** Illustrative SDK shapes and vendor defaults cannot establish installed behavior.

**Options:** One compatible pinned native fusion; controlled alternative only as an explicit later experiment.

**Recommendation:** Probe official pinned server/client APIs, use same-point dense/bm25 representations, match ingest/query BM25 mode and tokenizer, and run one native RRF stage with k=60. Select a supported mode at that compatibility task.

**What affects what:** Planned storage/qdrant.py, retrieval/hybrid.py, manifests and benchmark reader; version/mode selection is delegated technical work, not verified now.

**My answer (editable):** Accept the recommendation direction; do not invent a compatibility result.

**Verification:** P02 actual probe passed with Qdrant1.19.2/client1.19.1, same-point
named dense/BM25 and one nativeRRFk60. Explicit English/no-stemming representations
share ingest/query options and IDF handling. E-P02-001 retains actual model/tokenizer
file fingerprints and pilot limits; final work audit remains phase-owned.

## ADR-0015 — Q04 — English and Indonesian retrieval

**Status:** ACCEPTED; authority: user instruction 2026-10-17.

**Authority:** Current user instruction accepts all open-question recommendation directions; ADR-0013 records the explicit uv/Groq exception and package delegation.

**Question:** How should language processing and corpus mix be selected?

**Why:** English-oriented defaults may miss Indonesian clauses; an aggregate can conceal those failures.

**Options:** Unexamined defaults or recorded language variants tested on development labels.

**Recommendation:** Record corpus language distribution, compare stemming/tokenization variants on development data and pin the selected representation; report each language slice.

**What affects what:** Planned chunk/index manifests, retrieval tests and evaluator; gold/held-out split remains independent of tuning.

**My answer (editable):** Accept the recommendation; select details from measured development evidence rather than a claimed language improvement.

**Verification:** E-P02-001 measures English/no-stemming on eight PILOT queries
(7English,1Indonesian targeting English sources). Results tied; retain explicit English
initial profile without claiming a language-wide winner. General Indonesian-document
quality and human adjudication remain future evidence.

## ADR-0016 — Q05 — Historical audit and time-basis migration

**Status:** ACCEPTED; authority: user instruction 2026-10-17.

**Authority:** Current user instruction accepts all open-question recommendation directions; ADR-0013 records the explicit uv/Groq exception and package delegation.

**Question:** What historical reconstruction and migration semantics are allowed?

**Why:** Current supersession cannot erase past applicability; mixed time bases cannot be silently ranked together.

**Options:** Minimal knowledge-cutoff audit plus explicit migration rules, or a full temporal database (not required).

**Recommendation:** Use declared bases, valid/record time and knowledge_cutoff fixtures; incompatible bases remain conflict unless an approved migration/precedence is supplied. Retain reconstructible decision traces; do not build a full temporal database.

**What affects what:** Planned policy/registry.py, temporal.py and audit traces; current guidance and authorized historical audit readers stay distinct. Concrete business migrations are not invented.

**My answer (editable):** Accept the minimal audit and conflict-by-default recommendation.

**Verification:** PLANNED; G-TEMPORAL boundary/overlap/cutoff tests; concrete retention/fixture choices recorded at owning task.

## ADR-0017 — Q06 — External inventory boundary

**Status:** ACCEPTED; authority: user instruction 2026-10-17.

**Authority:** Current user instruction accepts all open-question recommendation directions; ADR-0013 records the explicit uv/Groq exception and package delegation.

**Question:** Who attests external document completeness?

**Why:** Internal accepted-source reconciliation does not establish that every company document was supplied.

**Options:** Application/user inventory attestation, or unsupported model inference (rejected).

**Recommendation:** Keep supplied-source INDEX_COVERAGE separate from external INVENTORY_ATTESTED. Later define attester/scope/time/change-feed interface when an external owner provides it.

**What affects what:** Ingest manifests and coverage/gate responses; no source of external authority is fabricated. The future manifest integration remains deferred.

**My answer (editable):** Accept the separation and defer the external interface until its actual owner and scope exist.

**Verification:** DEFERRED; T12 withheld-appendix test must preserve scoped uncertainty.

## ADR-0018 — Q07 — Fact validity and observation freshness

**Status:** ACCEPTED; authority: user instruction 2026-10-17.

**Authority:** Current user instruction accepts all open-question recommendation directions; ADR-0013 records the explicit uv/Groq exception and package delegation.

**Question:** How are reported validity and intended-use observation freshness configured?

**Why:** A fresh read timestamp cannot make an old BI snapshot current; models cannot invent fact expiry.

**Options:** Per-policy/adapter owner values with provenance, or universal/model-generated TTL (rejected).

**Recommendation:** Use explicit use-specific synthetic fixture limits with declared owner/rule; preserve observed_at, source_event_at and data_as_of. User-reported unspecified validity remains UNSPECIFIED. Record numerical fixture values during implementation, never as real-company rules.

**What affects what:** Planned live/contracts.py, gateway.py, adapters.yaml, policy input validation and memory validity; current decision and historical observation readers use different checks.

**My answer (editable):** Accept owner-defined validity/freshness semantics; no particular numerical age was supplied or approved by this answer.

**Verification:** PLANNED; G-LIVE/G-MEMORY stale-BI, changed-state and unspecified-expiry tests.

## ADR-0019 — Q08 — Honest research acceptance

**Status:** ACCEPTED; authority: user instruction 2026-10-17.

**Authority:** Current user instruction accepts all open-question recommendation directions; ADR-0013 records the explicit uv/Groq exception and package delegation.

**Question:** How are labels, targets, splits, repetitions and tradeoffs fixed?

**Why:** Invented targets, self-grading and held-out tuning would undermine the hypothesis.

**Options:** Development-calibrated preregistration with independent labels, or post-hoc thresholds/self-grading (rejected).

**Recommendation:** Use two independent annotators plus adjudication for meaningful research; pilot-only if unavailable. Calibrate B0/B1 development data, then freeze family-disjoint splits, repetitions, uncertainty, numerical targets and cost/latency tradeoffs before held-out runs.

**What affects what:** RESEARCH_PROTOCOL, gold labels, evaluator manifests and result readers; empirical values are pending measurements, not unanswered owner recommendations.

**My answer (editable):** Accept the recommendation, including honest pilot limits and no invented numerical target.

**Verification:** VERIFY_AT_IMPLEMENTATION; annotator availability and actual sample/threshold choices remain evidence obligations.

## ADR-0020 — Q09 — Claim support and human escalation

**Status:** ACCEPTED; authority: user instruction 2026-10-17.

**Authority:** Current user instruction accepts all open-question recommendation directions; ADR-0013 records the explicit uv/Groq exception and package delegation.

**Question:** What happens when deterministic eligibility does not establish semantic adequacy?

**Why:** A valid citation/hash is not proof that a passage supports the claim or contains every exception.

**Options:** Gold-reviewed support rubric and designated human review, or treating necessary checks as complete proof (rejected).

**Recommendation:** Use independently reviewed support/exception labels and a named authorized human escalation boundary; insufficient adequacy stays qualified or blocked. Record the concrete rubric and reviewer assignment at the owning task, not an imaginary signoff.

**What affects what:** Planned gold annotations, agent/gate.py, critic reviews and safe renderer; no consequential supported claim is released merely because refs exist.

**My answer (editable):** Accept the rubric/escalation recommendation; the actual reviewer assignment and support labels must still be evidenced.

**Verification:** PLANNED; G-GATE must reject irrelevant-but-valid references and unresolved critical challenges.

## ADR-0021 — Q10 — Optional complexity needs controlled evidence

**Status:** ACCEPTED; authority: user instruction 2026-10-17.

**Authority:** Current user instruction accepts all open-question recommendation directions; ADR-0013 records the explicit uv/Groq exception and package delegation.

**Question:** When should graph, vector memory, planner, fusion or adaptive critic be retained?

**Why:** Capability presence and architectural appeal do not establish incremental value.

**Options:** Controlled disabled-by-default treatments with paired evidence, or unconditional activation (rejected).

**Recommendation:** Use explicit treatment flags and paired parent controls; collect always-on critic labels before adaptive review; measure harms, recall/utility and total cost before retention. Initial generative treatments use the selected Groq model; any different model is a separate recorded treatment.

**What affects what:** Planned graph/memory/retrieval/agent feature branches and B3/B7/B8/B9 reports; the default normative critic rule remains mandatory.

**My answer (editable):** Accept experiment-first retention; package selection is delegated within this approved direction, not evidence that a feature helps.

**Verification:** PLANNED; G-RESEARCH preserves null/adverse results and complete per-treatment costs.

## ADR-0022 — Q11 — Later external comparator systems

**Status:** ACCEPTED; authority: user instruction 2026-10-17.

**Authority:** Current user instruction accepts all open-question recommendation directions; ADR-0013 records the explicit uv/Groq exception and package delegation.

**Question:** How are standard RAG, LangChain and provider systems compared fairly?

**Why:** Library labels, unequal tools/data and hidden extra calls can manufacture a winner.

**Options:** Capability/resource-matched and disclosed native tracks, or an unexplained scalar ranking (rejected).

**Recommendation:** Keep baseline/ deferred. Later define exact versions/capabilities/shared evaluator, same supplied corpus/scopes/questions where possible, disclose differences and keep raw safety/utility/latency/cost dimensions.

**What affects what:** Future baseline/ environments and adapters; current system architecture and no-UI scope unchanged.

**My answer (editable):** Accept the honest comparison recommendation and its deferred timing.

**Verification:** DEFERRED; no comparator dependency or result exists.

## ADR-0023 — Q12 — Real data and production boundary

**Status:** ACCEPTED; authority: user instruction 2026-10-17.

**Authority:** Current user instruction accepts all open-question recommendation directions; ADR-0013 records the explicit uv/Groq exception and package delegation.

**Question:** When can the prototype connect actual enterprise data or claim production readiness?

**Why:** Synthetic success and append-only SQLite logs do not establish privacy, identity or tamper-evidence guarantees.

**Options:** Synthetic-only until legitimate integration/security/retention signoff, or assume dev success authorizes production (rejected).

**Recommendation:** Remain synthetic with read-only mock operational systems. Require actual owner access, enterprise identity/approval controls, privacy/retention decisions and security review before real connectors; do not label the prototype production-ready.

**What affects what:** Future deployment and live connectors only; Groq runtime selection changes generation, not the mock operational-data boundary.

**My answer (editable):** Accept the synthetic-only recommendation and defer actual deployment approval.

**Verification:** DEFERRED; no real business data or connector has been used.

## Sources and verification notes

Reference decision format: Arcana vision master plan “Cross-cutting architecture,” which
uses The call, Why it matters, Options, Couples with, My recommendation and the owner's
editable decision. Its runtime ADR log has a different historical format; the user's
requested question/answer structure governs Palladion.

Official references checked 2026-10-17 without account credentials or model requests:
[Groq model listing](https://console.groq.com/docs/model/qwen/qwen3.8-27b),
[Groq rate limits](https://console.groq.com/docs/rate-limits), and
[uv environments](https://docs.astral.sh/uv/pip/environments/).
The model is publicly listed; free-plan limits exist and account quotas may differ.
Free-tier intent is not unlimited/guaranteed-zero-cost capacity. Before any enabled run,
verify account/model access and quotas, bound calls/tokens/time and record actual usage;
never auto-upgrade billing or silently substitute a model. No live access checked here.

## ADR-0024 — P01 deterministic foundation implementation

**Status:** ACCEPTED; implementation details within explicit P01 GO.
**Authority:** User delegates compatible packages and P01 implementation; blueprint permits Pydantic/SQLite and plan requires lifecycle/consumer proof.
**Question:** How will P01 contracts, persistence and authorization be testable?
**Why:** Pre-adversary found helper-only proof and missing lifecycle/catalog cases.
**Options:** Pydantic versioned models and stdlib SQLite, or handwritten validation/custom persistence layers.
**Recommendation:** Pydantic v2, safe PyYAML config, pytest/Ruff/mypy/build, uv locked dependencies and existing Python 3.14 if compatible. SQLite user_version and explicit transactional forward migrations, never reset/downgrade. Offline CLI consumes real registry/authorization/original methods.
**What affects what:** P01 models/settings/storage/fixtures/CLI; no new agent tool, network model call, retrieval or HTTP API. Trusted stored profiles/memberships own access. Separate uploader/approver actors and grants; prose cannot approve itself. uv.lock records resolved pins.
**My answer (editable):** Coordinator applies delegated compatible-package and P01 authority; no additional owner architectural choice inferred.
**Verification:** E-P01-001 records 75 passing tests, strict typing/lint and offline
consumer proof. Python 3.14.7 compatibility is observed; uv.lock pins runtime/dev tools,
Hatchling 1.32.4 pins the builder. Corrected artifact and same-auditor resolution pass;
P01 is complete. Explicit kind/source matching and T03 applicability consistency were
added after review with failing negative controls; no new owner ADR decision is needed.

**Amendment history:** Current explicit user GO authorizes P01 implementation and package
setup; earlier P00 hold remains historical. Typed schema corrections align exact evidence,
policy and live status vocabularies with blueprint contracts; no generic incomplete/unavailable
collapse. Tool/time starting limits are explicit prototype config, not measured business policy.
Final staged review found core.autocrlf=true; app .gitattributes marks original fixture
Markdown as -text so Git preserves exact hashes/spans across checkout. This implements
the existing immutable-source invariant, without changing global/repository git config.
Sources: [Pydantic strict mode](https://docs.pydantic.dev/latest/concepts/strict_mode/),
[uv locked sync](https://docs.astral.sh/uv/concepts/projects/sync/) and Python SQLite docs.
All provider-specific compatibility remains deferred to enabled P04 proof.

## ADR-0025 — P02 additive retrieval catalog and verified substrate

**Status:** ACCEPTED; schema extension explicitly approved by owner 2026-10-17.
**Authority:** P02 GO, compatible package delegation, and owner async answer approving additive v3 migration.
**Question:** How can P02 persist exact publication IDs and model/tokenizer identity without losing P01 data?
**Why:** Pre-adversary found v2 manifest lacks reproducibility fields and P02 ownership omitted migrations.
**Options:** Additive transactional v3 catalog, or keep v2 and introduce a competing sidecar authority.
**Recommendation:** Add v3 tables for chunk spans/generation records/exact aliases/manifests bound to immutable source IDs and representation fingerprints. Preserve v2 tables/behavior; verify fresh/populated/failed upgrades. Explicit search and audited source revocation supply missing consumers/producers. Shared typed ingestion/index contracts retain canonical resolution ownership.
**What affects what:** storage schema/sqlite/catalog/registry, ingestion, index adapters, canonical resolver, authenticated API and tests. Qdrant discovery never supplies canonical quote authority. P02 pilots measure retrieval only, not full B0/B1/B2 answer arms.
**My answer (editable):** User: Approve additive v3 migration (Recommended).
**Verification:** VERIFIED at E-P02-001: additive fresh/populated/rollback preservation, real exact-manifest publication and HTTP consumers pass within final115-test suite; single audit findings resolved.

## ADR-0026 — Standing subagent effort and Docker-free execution amendment

**Status:** ACCEPTED; direct owner instructions 2026-10-18.
**Authority:** User: from now on only use GPT 6 Luna Medium; Docker cannot work, implement an alternative.
**Question:** Which development-agent effort and local Qdrant path govern remaining work?
**Why:** Owner changes the standing model preference and requires a working Docker alternative.
**Options:** Luna Medium for future dispatches and checksum-pinned Qdrant in WSL, or retain superseded High/Docker requirements (rejected).
**Recommendation:** Every new subagent uses gpt-6-luna/medium. Preserve completed High receipts as historical evidence. Run official pinned Qdrant1.19.2 in WSL with Linux-owned storage; keep optional Compose for other machines, no production-readiness claim.
**What affects what:** Global AGENTS section12, project AGENTS, master review protocol, gates, memory and future reviewer dispatch. Runtime Groq model/critic budgets are unchanged. The in-flight High evaluator was interrupted; any new dispatch uses Medium.
**My answer (editable):** User: from now on only use gpt 6 luna medium; Docker alternative requested.
**Verification:** Standing rules updated in global/project instructions. WSL launcher starts real Qdrant; recorded PID3046 stop succeeds with storage preserved. Final115-test suite, isolated wheel HTTP smoke and same-auditor resolution verified at E-P02-001.

## ADR-0027 — Direct dependency and interface completion audit

**Status:** ACCEPTED; user follow-up 2026-10-18.
**Authority:** User requests inspection/fix of apparent incomplete functions, missing direct dependencies and similar gaps, then commit/push; P03 remains on hold.
**Question:** How should direct imports and Protocol method declarations be validated before publication?
**Why:** P02 imports huggingface_hub and dynamically imports onnxruntime but declared them only transitively. Existing tests/install smokes did not detect this manifest ownership gap.
**Options:** Keep transitive reliance, or declare each directly used distribution and validate import ownership.
**Recommendation:** Use uv add to promote already-locked huggingface-hub1.33.0, onnxruntime1.31.0 and starlette1.8.0 to direct dependencies without upgrading the resolved environment. Add a standard-library import/manifest checker with negative controls. Clarify Protocol docstrings and verify concrete implementations with existing typing and real retrieval tests.
**What affects what:** pyproject.toml/uv.lock, src interface documentation, scripts/check_dependencies.py and regression controls, packaging and consumer verification. Also correct the owning catalog active-generation publication check and CLI reader; no schema, API shape or P03 changes.
**My answer (editable):** User: check the other as well; once all clear commit and push, wait for Phase3 GO.
**Verification:** VERIFIED at E-P02-002: direct-import checker47 files/four negative controls,117 actual-server tests, typing/lint/build/installed-wheel smoke and source review passed. Prior closeout missed direct dependency completeness; correction retained there.

## ADR-0028 — Limit delegation to start/end review

**Status:** ACCEPTED; direct user instruction 2026-10-18.
**Authority:** User limits subagents to the adversary at the start and review at the end, model gpt6luna medium, citing usage cost.
**Question:** When may a subagent be dispatched?
**Why:** Intermediate research/implementation/test agents consume more usage than the owner wants.
**Options:** Earlier proactive delegation, or start adversary/end reviewer only.
**Recommendation:** Only those two roles, gpt-6-luna/medium. Coordinator performs all intermediate work; reuse end reviewer for resolution checks. Preserve historical evidence.
**What affects what:** Global AGENTS Rule12/14/16, project AGENTS, master task protocol, gates, working memory and future dispatches. Does not alter system runtime models or authorize P03.
**My answer (editable):** User: only use subagents for the adversary at the start and the review at the end; Model is gpt 6 luna medium.
**Verification:** Standing instructions updated; no new intermediate dispatches after this instruction.

## ADR-0029 — P03 authority, history and synthetic operation bounds

**Status:** ACCEPTED within existing P03/ADR-0016/0018 scope; core change separately owner-approved in ADR-0030.
**Authority:** Owner P03 GO; accepted historical-audit and synthetic owner-defined freshness directions.
**Question:** How will P03 preserve trusted facts/history without new infrastructure or schema?
**Why:** Pre-adversary found missing policy producers, target binding, historical state and replay consumers.
**Options:** Use existing policy/source tables plus append-only typed case/audit events, or add competing stores/migrations.
**Recommendation:** Existing stores, current ACL recheck, independent admin policy registration/approval tied to immutable clauses. Explicit admin audit mode replays cutoff approval/revocation; it never grants current operational authority. Trusted case scope is admin-registered; case opening is canonical cases.created_at, domain event is a named registered event, transaction time comes from persisted gateway evidence, evaluation time from backend clock. Undefined mixed bases stay conflict. Main implementation adds no dependency.
**What affects what:** policy/live modules, existing access/audit facilities,10 P03 cards/tests, smoke/replay reader. Policy gate consumption remains P04. Synthetic owner palladion-fixture-owner config: transaction/settlement/incident observation age300s; merchant snapshot age900s; timeout1000ms,2 attempts,10ms backoff,16KiB response,20 calls/minute and4 concurrent/16 pending reads. These are test assumptions, not company policy or performance measurements. Retain append-only local traces without automatic purge; production retention deferred.
**My answer (editable):** Inherits owner's accepted synthetic fixture/minimal audit directions and P03 GO. Core PolicyDecision extension is separately approved in ADR-0030; this record did not grant that approval.
**Verification:** PASS for P03 scope at E-P03-001: four bases, current/audit distinction, source/target denial, concurrency/deadline, provenance and reopened replay controls executed; single work review complete. P04 gate consumer remains deferred.

## ADR-0030 — Additive executed PolicyDecision fields

**Status:** ACCEPTED; explicit owner async approval 2026-10-18.
**Authority:** Owner answer: Approve additive PolicyDecision extension (Recommended).
**Question:** May P03 add outcome, normalized inputs/selection trace and support determined zero-input policies without fake evidence?
**Why:** Shipped P01 shape lacked executed outcome and required input refs even for no-input policies.
**Options:** Add optional compatible fields and precise zero-input validation, or keep the incomplete shape.
**Recommendation:** Optional outcome/normalized_inputs/required_fields/selection_trace/evaluated_at plus explicit audit mode/cutoff. Existing valid payloads retain defaults; zero-input outcome is explicit, no invented evidence refs.
**What affects what:** core/models.PolicyDecision, policy engine/replay reader, compatibility and zero-input controls. No schema change or new generative tools.
**My answer (editable):** User: Approve additive PolicyDecision extension (Recommended).
**Verification:** PASS at E-P03-001: legacy compatible payload roundtrip and executed zero-input policy tests passed, including focused independent end-review checks. Approval remains the owner answer above.

## ADR-0031 — P04 trace authorization and readiness

**Status:** ACCEPTED; explicit owner reply2026-10-18 supersedes pending answer below. Owner: Approve scoped admin traces and expanded readiness (Recommended). Implementation and tests remain required.
**Authority:** P04 GO; Rule4 for new authorization/readiness contract.
**Question:** Who reads traces and which dependencies determine readiness?
**Why:** Start review found no developer grant and index-only readiness.
**Options:** Current admin plus current case membership with redacted metadata, or traces disabled; SQLite/Qdrant/configuration readiness without provider calls.
**Recommendation:** Existing admin AND current case membership; no raw prompts/rejected text or other cases. Check SQLite, Qdrant and explicit agent configuration; keep liveness independent.
**What affects what:** api/routes.py, main lifecycle, telemetry/audit.py, security/HTTP tests; no new grant/schema.
**My answer (editable):** User: Approve scoped admin traces and expanded readiness (Recommended). Supersedes prior pending answer2026-10-18.
**Verification:** E-P04-001: current-admin AND current-case allow/deny/revocation/canary tests pass; actual correlated retrieval/HTTP trace reader passes. SQLite read-only, Qdrant outage and explicit model-boundary checks pass without provider calls; real TCP health/ready pass. End audit pending.

## ADR-0032 — P04 cancellable search boundary

**Status:** ACCEPTED; explicit owner reply2026-10-18 supersedes pending answer below. Owner: Approve cancellable local search worker (Recommended). Implementation and strict cancellation proof remain required.
**Authority:** P04 global deadline/cancellation requirement; existing P02 owned-process precedent.
**Question:** How can cancellation stop synchronous Qdrant/model search?
**Why:** asyncio timeout cannot stop synchronous code and abandoning a thread leaves work running.
**Options:** Owned local subprocess using existing readers, or another owner-selected approach.
**Recommendation:** Bounded credential-free search process; terminate and join on deadline/cancellation; no new package/service.
**What affects what:** agent tools/services, P04-T01.03/P04-T02.03 cards and process/cancellation tests. Direct synchronous search does not meet strict cancellation proof.
**My answer (editable):** User: Approve cancellable local search worker (Recommended). Supersedes prior pending answer2026-10-18.
**Verification:** E-P04-001: real blocked-process cancellation/deadline/credential/IPC controls, actual message deadline→persisted tool cancellation, real Qdrant four-domain readback and isolated exact-wheel consumers pass. No detached thread/process fallback; Windows pipe cleanup verified without unraisable warnings.

## ADR-0033 — P04 support rubric and unassigned human escalation

**Status:** ACCEPTED implementation boundary within ADR-0020 and P04 phase exit.
**Authority:** Owner-accepted ADR-0020; P04-T03.04 conditional adequacy rule; P06 owns critic.
**Question:** What can be established without invented human labels or reviewer assignment?
**Why:** A valid citation does not prove free-text entailment or complete exceptions.
**Options:** Bounded attribution/typed facts and qualified consequential claims, or invented signoff (rejected).
**Recommendation:** SOURCE_QUOTE must exactly match an authorized current passage and renders only as attribution. OBSERVED_FACT must match a typed fresh field/value and renders through a controlled template. RULE_REQUIREMENT must name an approved schema field. POLICY_RESULT never releases operational permission before P06. Unknown refs, mismatched/irrelevant associations and unrecognized free prose are blocked; hypotheses are explicitly unverified and non-authorizing. Model labels cannot suppress checks. Exact quotes overlapping registered policy-clause spans are independently recognized from backend metadata and require policy context/mandatory review even when labeled INFORMATIONAL.
**What affects what:** draft/gate, evidence/coverage readers, gate/security tests and unchanged PILOT gold catalog. Human support/exception annotators and escalation assignee remain UNASSIGNED; consequential adequacy stays qualified. The development reviewer is not a human research annotator.
**My answer (editable):** Inherits accepted ADR-0020/P04 conditional scope; coordinator supplies no human assignment or semantic gold approval.
**Verification:** IN_PROGRESS E-P04-001; actual typed-information Groq/HTTP/citation path and action rejection tested. Human semantic adequacy remains deferred.

## ADR-0034 — Canonical temporal-input provenance for non-determined decisions

**Status:** ACCEPTED; explicit owner reply2026-10-18 supersedes pending answer below. Owner: Approve canonical temporal-input provenance extension (Recommended). Implementation and regression proof remain required.
**Authority:** P04 consumer regression; shipped PolicyDecision/PolicyEngine contract requires owner approval under Rule4.
**Question:** May the canonical decision add optional temporal_input_refs, populated by the owning PolicyEngine from authenticated persisted observations?
**Why:** P03 conflict decisions have no normalized fact refs, so the current P04 reader cannot reconstruct the time-source selection. Historical replay alone must not assert a fresh conflict after supersession.
**Options:** Add compatible canonical temporal-input provenance and tests, or another owner-selected contract. A duplicate authority log in P04 is rejected.
**Recommendation:** Optional tuple default empty in core/models.py, produced in policy/engine.py after actual observation validation; current readers use canonical time-source refs. Preserve backward reading of stored old payloads and normalized fact refs; no schema migration. Older strict binaries may reject newly extended JSON, so forward compatibility is not promised. No public raw PolicyDecision endpoint existed before P04. Record failed observations as attempts without implying valid facts. Prove conflict current-read, later supersession invalidation and legacy roundtrip.
**What affects what:** core/models.py, policy/engine.py, retrieval/evidence.py, tests/test_contracts.py, test_policy_engine.py and test_gate.py. Canonical implementation and local consumer proof now pass; full P04-T03.02 integration remains open.
**My answer (editable):** User: Approve canonical temporal-input provenance extension (Recommended). Supersedes prior pending answer2026-10-18.
**Verification:** Original reproduced FAIL is retained at E-P04-001. Approved owning producer now persists temporal_input_refs after scoped observation reads; replay rechecks their access, runtime reselects current policy. Legacy empty default and conflict/reopen/explicit-supersession tests pass;213 non-server tests, Ruff and strict mypy55PASS. No second authority log/schema migration. Full P04 live integration remains open.

## ADR-0035 — Separate Groq output quota from combined TPM

**Status:** ACCEPTED bounded P04 implementation choice;2026-10-18.
**Authority:** Owner keeps free quota/current model and supplied rate-limit screenshot; P04-T01.01 bounded transport.
**Question:** Why does8K TPM reject a tiny request with a1K limit?
**Why:** Actual headers report8000 combined TPM. Cap1200 fails with output-minute limit1000/requested1151; cap64 succeeds with22prompt/6completion tokens. Earlier combined-TPM diagnosis omitted direction and is retracted.
**Options:** Bound unshipped completion allowance and pace separate engineering checks, or change quota/model.
**Recommendation:** Keep Qwen; cap768 below observed output-minute limit and distinguish input/output diagnostics. Subsequent calls can still exhaust remaining output capacity. Preserve counted429 and one attempt per invocation; no hidden retry or deadline-breaking sleep.
**What affects what:** agent/llm.py, tests/test_llm_transport.py and live-check scheduling. No dependency, public API or shipped-default change. Full scenarios still need actual proof.
**My answer (editable):** Coordinator implementation within existing P04 authority; no owner phase signoff inferred.
**Verification:** E-P04-001: live cap64 success/cap1200 rejection, cap768 native four-tool and JSON success, actual allowlisted header readback;21 focused budget/transport tests and strict typing pass. Full runtime scenarios remain open.

## ADR-0036 — Explicit selection among three owner-approved Groq models

**Status:** ACCEPTED; direct owner direction2026-10-18.
**Authority:** Owner: if Qwen does not make it, switch to openai/gpt-oss-120b or openai/gpt-oss-20b; use either of these three.
**Question:** Which models may P04 use when actual Qwen walkthroughs fail?
**Why:** Cap768 native/JSON probes pass, but actual document walkthrough still hits429 after successful search; different model quotas/capabilities must be measured, not assumed interchangeable.
**Options:** Explicit per-run selection among approved three, or silently substitute providers/models (rejected).
**Recommendation:** Keep Qwen default; allow explicit --model in serve/validate_agent and validated Settings/transport allowlist. Try GPT-OSS120B for remaining engineering walkthroughs. GPT-OSS uses low reasoning and parallel_tool_calls false; Qwen keeps none/parallel true. All retain same four local tools, one-attempt transport, budgets, gate and evidence rules. Built-in web/code tools stay unexposed.
**What affects what:** settings.py, agent/llm.py, scripts/serve.py, scripts/validate_agent.py and transport/model compatibility tests. No new package/provider. Every receipt names its model; no model switch inside a failed attempt or research comparison.
**My answer (editable):** User explicitly authorizes Qwen3.8-27B, GPT-OSS120B or GPT-OSS20B as alternatives. Approval is not successful live-model proof.
**Verification:** E-P04-001: explicit allowlist/capability guards pass; actual native/JSON and five-disposition/document proof across the three named models is recorded, including expected failures. Source/wheel/TCP consumers pass. Official capability references are retained; no comparative model-quality claim.

## ADR-0037 — Distinguish expected negative smoke outcomes from unexpected failures

**Status:** ACCEPTED coordinator correction within P04-T04.03;2026-10-18.
**Authority:** Existing HybridSearch exact-ID behavior, four-tool handler and five-disposition smoke requirements.
**Question:** Can a healthy exact miss or deliberately unavailable adapter ever pass the original smoke predicate?
**Why:** Exact unknown identifiers intentionally returnDEGRADED/EXACT_IDENTIFIER_NOT_FOUND with auditfailureNONE. Deliberately unavailable live adapters intentionally appendLIVE_UNAVAILABLE. The original assertions requiredsearchOK and zero failures respectively, making both intended negative controls impossible.
**Options:** Preserve impossible assertions, weaken all failures (rejected), or check only the precise expected negative condition and reject every unexpected failure.
**Recommendation:** Accept exact miss only with successful persisted tool result, sole exact-miss warning, matching retrieval trace and auditNONE. Unavailable scenario requires exactlyLIVE_UNAVAILABLE, no claims, unavailable/timeout adapter status and VERIFICATION_UNAVAILABLE. Provider400/429, malformed drafts, cancellation and unrelated failures still fail. Keep old failed receipts.
**What affects what:** agent/tools.py persists safe retrieval warning/trace metadata; scripts/validate_agent.py reads it. Runtime release checks and model behavior are not relaxed. Expected domain-fault success is evidence of safe abstention, not dependency reliability.
**My answer (editable):** Coordinator fixes unambiguous smoke-contract bugs under Rules5/7; no owner phase signoff inferred.
**Verification:** Actual20B exact miss nowstrictPASS (3main/1tool,no unexpectedfailures). Unavailable corrected predicate still rejects earlier120B provider400 result. Actual20B unavailable strictPASS with exactlyLIVE_UNAVAILABLE/no claims and no unexpected failures; mandatory end review remains open.

## ADR-0038 — Close alternate prompt reads and report executed search scope

**Status:** ACCEPTED in-scope correctness/privacy fixes under ADR-0031 and P04 integrity requirements;2026-10-19.
**Authority:** Sole end reviewer findings and existing case/user scope, redacted diagnostics and honest absence rules.
**Question:** Can case-event evidence bypass redacted timeline/trace, or a no-tool reply imply a search?
**Why:** REQUEST payload projection retained raw queries; timeline event IDs made another member's question retrievable through evidence/recall. Gate used a constant searched-scope label even without search. Root README still described implemented agent features as future.
**Options:** Preserve those defects, remove continuity, or separate safe event metadata from owner-scoped unverified reported-input hydration and derive scope from actual tool execution.
**Recommendation:** Public event/recall projections whitelist metadata for every event kind. Packet hydration reads only the current authenticated operator's own bounded prior reports, tagged unverified, from the same canonical event store. No new store/contract. Search text distinguishes none, failed/incomplete and completed scoped retrieval; it never attests full inventory. Correct stale public docs.
**What affects what:** memory/store.py and packet.py, gate.py, owner/cross-member API/recall/packet canaries, no-tool search-scope tests and root README. All changes remain P04; P05 full memory is deferred.
**My answer (editable):** Coordinator fixes confirmed in-scope findings; no shipped schema or public contract extension, no governance exception inferred.
**Verification:** E-P04-001 retains initial failing controls and wrong-column correction. Source229PASS, updated exact-wheel30PASS; real model scope readback observed with both strict scenario failures preserved. Same LunaMedium reviewer resolves R1/R2/R3 with20targetedPASS. No full memory or model reliability claim.

Current P04 closeout (2026-10-19): ADR-0031/0032/0034/0036/0037/0038 implementation and phase-local consumers verified at E-P04-001; mandatory end review/resolution complete. Earlier IN_PROGRESS verification text above is historical, not a current hold. Provider failures remain recorded; P05+ requires GO.

## ADR-0039 — P05 additive memory schema and recall contract

**Status:** ACCEPTED; explicit owner reply2026-10-19; implementation/proof required.
**Authority:** P05 seven atomic tasks and blueprint §9; Rule4 shipped schema/tool contracts.
**Question:** May P05 add a forward-only v4 migration for memory owner/validity/history metadata, explicit team memberships and FTS5, plus optional recall query/category selectors?
**Why:** v3 memory_entries cannot represent all required provenance/validity fields; team membership and FTS are absent. Existing recall accepts only limit.
**Options:** Add compatible v4/optional selectors preserving existing rows/default readers, or owner-selected alternative. Hiding permissions/history in free prose is rejected.
**Recommendation:** Add columns/tables/indexes transactionally, preserve old rows without inventing owner or verification, test fresh install/populated v3 upgrade/rollback/foreign-schema preservation. Retain recall limit/default and add bounded optional query/exact memory ID/category; no identity/scope override and no fifth tool. Existing packet fields suffice; any measured bounds metadata can remain local, without changing the core packet contract.
**What affects what:** storage/sqlite.py/schema validation, memory/store.py (or focused local memory contracts), security/access.py, agent/tools.py, readiness uses actual Database.SCHEMA_VERSION, storage/memory/security/transport tests, plan ownership and docs. No new dependency/vector store or actual persistent runtime migration during tests; isolated synthetic DBs only.
**My answer (editable):** User: Approve additive v4 and recall extension (Recommended). Supersedes pending proposal2026-10-19.
**Verification:** E-P05-001 verifies fresh/populated/rollback/backup and compatible default/exact/FTS readers, final installed wheel and single review/resolution.

## ADR-0040 — P05 scope, promotion and owner controls

**Status:** ACCEPTED; explicit owner reply2026-10-19; implementation/proof required.
**Authority:** Blueprint §9.1/9.3/9.5; no shipped team/promotion precedent; Rule4 authorization decision.
**Question:** Who may read/write/promote scoped memories and control validity?
**Why:** Same tenant alone cannot imply team membership or permission to expose another private case; models have four read tools only.
**Options:** Explicit persisted team membership plus existing tenant/case/role/grant checks, or owner-selected policy. Inferring teams from names or broadening scope on repetition is rejected.
**Recommendation:** USER owner-only; CASE current case members; TEAM explicit current team members; ORGANIZATION same tenant with explicit administrator promotion. Every case-derived item additionally requires current membership in its originating case and current source ACL; promotion never removes those restrictions or creates company-policy authority. Writes/validity/corrections require original owner or existing admin with case:read and document:approve; team administration/promotion require that admin authority and current origin-case membership. General shared items are explicitly created by that authorized admin without a private-case source. Model/runtime guesses never auto-promote; model cannot invoke writes. Validity rule defaults UNSPECIFIED, never model expiry; immutable actor/time/event history. Trusted application Python operations (and an explicit local CLI for operator edits) own writes; do not add enterprise/UI or LLM write tools. Case-close/correction/source revocation invalidate cache/packet; historical evidence remains historical, freshness rechecked independently.
**What affects what:** security/access.py plus memory owner/control methods, v4 membership metadata, memory/store.py/packet.py/hotcache.py, runtime consumers and owner/team/cross-case/tenant/revocation canaries. Source evidence remains canonical and mandatory critic remains unavailable until P06.
**My answer (editable):** User: Approve scoped owner/admin controls (Recommended). Supersedes pending proposal2026-10-19.
**Verification:** E-P05-001 source/member/team/promotion/validity controls, actual follow-up and source-backed API revocation pass; no new authority inferred.

## ADR-0041 — P05 packet producers, cache proof and pilot measurements

**Status:** ACCEPTED coordinator execution detail within P05;2026-10-19.
**Authority:** P05 start adversary/full blueprint §9/§14, owner GO and ADR-0039/0040.
**Question:** Which actual producers and measurements prove continuity?
**Why:** Existing packets omit open questions/hypotheses/observations; retrieval metrics cannot measure memory.
**Options:** Explicit typed producer/readers and pilot-only paired outputs, or infer coverage from the skeleton (rejected).
**Recommendation:** Generate historical observation reminders from scoped canonical live events with RECHECK_FOR_CURRENT_DECISION, typed reported items from owner-controlled memory, hypotheses from non-authorizing releases, policy gaps from persisted gate releases; never elevate context into evidence. Preserve last critical unresolved gaps independently of recent chatter and report compression omissions. Cache exact passages only, with canonical revalidation on every use, principal/grant/case/source hash/generation/time and correction/close state keys; bounded ephemeral entries, no speed claim. Measure a fixed synthetic long-session B4 parent (same B2/policy/live configuration, memory withheld by explicit continuity_enabled=false evaluator setting, default true) against B5 normal/compressed packet_max_chars (6000/1500) using the same runtime. These validated Settings fields are isolated experimental controls; default runtime retains continuity, all four read tools and unchanged gate. Save actual model/API outputs, packets, raw usage/errors, tokens/calls/latency and exact required-slot/stale-claim controls for every condition; no retries selecting successes, no full semantic score/hypothesis success. Critic/vector/graph remain disabled. Test scorer by deliberately omitting settlement and inserting a stale observed value.
**What affects what:** memory/store.py/packet.py/hotcache.py, security/access.py/storage registry/sqlite migration, agent services/preflight/loop/tools, evaluation functions/CLI and tests. Add exact owning files to P05 cards, source/storage compatibility tests and doc records; existing packet contract remains unchanged.
**My answer (editable):** Coordinator specifies falsifiable implementation/measurement under existing mandate; owner approvals remain separately recorded in ADR-0039/0040.
**Verification:** E-P05-001 source/installed/API/real Groq follow-up and sole audit/resolution verified. Pilot0/3 strict completions retained; no P08 research closure.

## ADR-0042 — Preserve persistent state before forward migration

**Status:** ACCEPTED coordinator safeguard required by Rule13;2026-10-19.
**Authority:** Owner-approved additivev4 and universal backup-before-schema-change rule.
**Question:** How can existing stores be opened without losing a restorable v3 state?
**Why:** Startup and trusted local CLI use Database.open; tests use temporary stores but real prototype stores must not be treated as disposable.
**Options:** Require a manual backup before every open, or create a checked SQLite backup before forward migration. Never reset/overwrite a store.
**Recommendation:** After recognizing the old schema and before WAL/schema writes, create an exclusive same-directory .pre-v4-UUID.sqlite backup using SQLite backup API; integrity_check must pass. Expose its path on the Database owner for CLI/doc evidence; never in public HTTP diagnostics. Unknown schemas remain untouched. No migration is run against user demo storage in this task.
**What affects what:** storage/sqlite.py and isolated upgrade/rollback tests; runtime backups remain ignored. No schema downgrade or deleting prior backups.
**My answer (editable):** Coordinator fulfills required preservation under approved migration; no destructive authority inferred.
**Verification:** E-P05-001 populated upgrade/rollback, checked backup reopen/old-version/legacy byte controls pass; no real demo migration.

## ADR-0043 — Apply memory scope before bounded recall windows

**Status:** ACCEPTED in-scope correctness fix;2026-10-19.
**Authority:** Sole end reviewer finding R1; P05 authorized known-fact recall/security contract.
**Question:** Can inaccessible tenant memories crowd out an older authorized match?
**Why:** The first query bounded all tenant candidates before scope checks; 501 private matches could suppress an authorized one.
**Options:** Unbounded scanning (rejected), or current scope/active validity/supersession/revocation filters before the candidate bound, followed by canonical per-item checks.
**Recommendation:** Push current USER/CASE/TEAM/ORGANIZATION and original-case membership plus validity/revision eligibility into SQL before limit. Preserve full canonical source checks after selection; source eligibility is never inferred from SQL alone. Inspect501 candidates and process at most500; recall tool explicitly reports incomplete candidate window and non-exhaustive scope. Exact-ID lookup remains available. Prove >500 denied newer matches cannot suppress authorized results, without exposing denied contents.
**What affects what:** memory/store.py, agent/tools.py and memory regression/coverage controls, scoped recall documentation. No permission expansion or public schema change.
**My answer (editable):** Coordinator fixes confirmed owning-code defect under Rules5/7; owner-approved scope rules unchanged.
**Verification:** E-P05-001 legacy-query starvation control, actual scope/FTS/packet recovery and coverage tests pass; same reviewer resolves R1/R2 with15memoryPASS; final246source and updated wheel65 overlapping checks pass after ADR0044 correction.

## ADR-0044 — Preserve unresolved questions across failed replies

**Status:** ACCEPTED in-scope owning-code correction;2026-10-19.
**Authority:** Main final completion audit, P05 packet/resume requirements and blueprint §9/§11.
**Question:** Does a later empty gap list resolve a previously missing settlement input?
**Why:** The initial packet reader used only the latest RELEASE. After a model/tool failure with empty gaps, the next packet forgot a real unresolved question without new evidence.
**Options:** Treat every empty reply as resolution (rejected), or reconstruct state from decisive canonical policy events and explicit case continuity.
**Recommendation:** Re-read latest authorized current INCOMPLETE_INPUT/DETERMINED decision per family. Incomplete fields stay open; only a later executed determined/updated incomplete result can resolve them. Failed/unverified attempts and empty release lists do not resolve. For case questions without a decisive policy trace, preserve latest nonempty trusted gap record until explicit case closure. Preserve role/source rechecks and bounded packet questions; no old policy result becomes current permission. No final-gate/API contract change.
**What affects what:** memory/store.py/packet.py and third-turn/incomplete→failure→fresh-settlement→determined regressions, source/installed consumers and same-reviewer resolution. Pilot output failures remain unchanged.
**My answer (editable):** Coordinator fixes confirmed packet producer/reader bug under existing P05 authority; no new source of policy authority.
**Verification:** E-P05-001: two controls first fail for erased settlement_state, then17memory/246nonserver/65installed overlapping tests pass; exact rebuilt artifact and same-reviewer code/documentation resolution verified. No new model success inferred.

## Future decision template

```text
ADR-NNNN — title
Status / date:
Authority:
Question:
Why:
Options:
Recommendation:
What affects what: exact files, producers/readers, affected invariants and tradeoffs
My answer (editable):
Verification: planned proof, result, evidence and execution/deferred state
Amendment history: old answer/date/reason and superseding decision
```

Next free ADR number: 0045. Accepted directions do not grant implementation GO.
