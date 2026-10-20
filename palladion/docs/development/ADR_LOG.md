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

## ADR-0045 — P06 structured review and public status consumers

**Status:** ACCEPTED; owner response2026-10-19; implementation not yet verified.
**Authority:** P06 GO; pre-phase adversary findings3/4; Universal Rule4 for shipped contracts.
**Question:** May the existing critic/message contracts gain structured optional review fields and real review statuses?
**Why:** CriticReview currently holds unbound string maps; MessageResponse only accepts UNAVAILABLE_UNTIL_P06. The declared timeline consumer drops review state.
**Options:** Preserve the unavailable boundary (cannot complete P06), or add compatible optional critic fields and additional response status values, with safe persisted/readback metadata.
**Recommendation:** Preserve legacy CriticReview fields/defaults; add typed bounded claim findings (claim, reason, evidence refs, missing slots), verdict/review identity, contradictions and purpose-bearing scoped counter-search proposals. Handler validates all IDs against the actual draft/current ledger. Extend review_status with PASS/CHALLENGE/UNAVAILABLE while retaining UNAVAILABLE_UNTIL_P06 for legacy readers. Expose only safe status/call counts in case timeline; raw prompts/reasons/rejected contents stay protected. Use existing current case/admin rules, no new authority or fifth tool. No schema migration/dependency.
**What affects what:** core/models.py, api/schemas.py, agent/critic.py/loop.py/gate.py, memory/store.py safe release projection, api/routes.py timeline and contract/gate/API/critic compatibility tests. Critic failures count, counter-search uses existing scoped worker/shared budgets, all final evidence revalidates.
**My answer (editable):** Approve compatible review/status extensions (Recommended)
**Amendment history:** Originally PENDING; owner approved via the corresponding async decision card on2026-10-19.
**Verification:** Owner approved; pending  implementation, legacy round trips, strict ID/budget/privacy negatives, actual Groq message/timeline/citation consumers and end audit.

## ADR-0046 — P06 pilot labels and consequential support boundary

**Status:** ACCEPTED; owner response2026-10-19; implementation not yet verified.
**Authority:** P06 GO, pre-phase adversary finding1, accepted ADR0020/0033 and blueprint§10/14.
**Question:** Which outcomes can P06 measure without invented independent human adjudication?
**Why:** No human annotators or escalation assignee are named. A source ID or critic agreement cannot establish semantic sufficiency or general accuracy.
**Options:** Obtain independent human labels/assignment before semantic scores, or run explicitly pilot-only mechanical fixtures now and keep semantic/operational adequacy qualified until those labels exist.
**Recommendation:** Complete all P06 runtime, search, finalization and paired-artifact work. Freeze controlled synthetic drafts and canonical initial ledgers once per case; compare critic off, fixed-context, authorized counter-search and blind-requirements conditions, then run actual end-to-end Groq messages separately. Measure exact missing schema fields, typed observation associations and exact source/exception quote corrections/false objections; retain unsupported objections, changed evidence, failures, withheld-appendix uncertainty and usage costs. Unadjudicated semantic correction/false-veto fields remain unknown, not zero or success. A real exception correction must be visible through the authenticated answer/citation reader. Critic PASS never substitutes for human adequacy: only controlled attributions/typed results may be released, never a payment instruction; consequential free prose stays qualified with the unassigned escalation limitation. Full semantic/hypothesis claims retain P08 independent-label prerequisites. Mandatory normative review remains enabled by default; no adaptive bypass.
**What affects what:** P06-T03 fixture manifest/evaluator/scorer, P06-T02 gate safe templates, RESEARCH_PROTOCOL/TESTING_GATES and actual evidence. This records a pilot limitation rather than a model-quality result or waived runtime requirement.
**My answer (editable):** Approve pilot boundary and full P06 implementation (Recommended)
**Amendment history:** Originally PENDING; owner approved via the corresponding async decision card on2026-10-19.
**Verification:** Owner approved; pending  frozen input hash equality and negative controls, actual provider correction/search/message/citation readback, measured all-condition artifacts and end audit.

## ADR-0047 — Extend the existing budget owner for critic reservations

**Status:** ACCEPTED coordinator detail within P06 bounds;2026-10-19.
**Authority:** Blueprint§11.4, accepted ADR0005, P06-T01.02; no new dependency/authority.
**Question:** Which owner counts critic calls and counter-searches against shared resources?
**Why:** Budget in agent/loop.py already owns main/tool reservations; reporting critic_used=0 is a placeholder.
**Options:** Duplicate counters in a critic (rejected), or add atomic critic/search reservations to Budget.
**Recommendation:** Keep one existing Budget owner. Add critic and search maxima/used counts, reserve before each actual dispatch including failed calls, and reserve a shared tool slot atomically with each authorized critic search. Disallowed fourth review/third search or exhausted tool budget never reaches a model/search; its rejection is logged by the runtime caller. Main final slot is unaffected. Settings remains the validated hard-cap configuration.
**What affects what:** agent/loop.py Budget, P06 critic caller and test_agent_budget.py cap/concurrency/failure controls. No shipped public response field is changed before ADR0045 approval.
**My answer (editable):** Coordinator implements the already-required shared accounting in its existing owner.
**Verification:** Test-first reservations and downstream critic dispatch checks; no runtime critic completion claim yet.

## ADR-0048 — Bind advisory review to current canonical evidence

**Status:** ACCEPTED coordinator implementation detail under ADR0045/0046;2026-10-19.
**Authority:** P06-T01/T02, blueprint§10/11, owner-approved structured review and pilot boundary.
**Question:** What does a completed critic assessment permit the final gate to consume?
**Why:** Known refs and a PASS are insufficient semantic proof; finalization may revise a draft and source state may change.
**Options:** Trust verdict/free prose (rejected), or current-evidence-bound advisory review plus unchanged deterministic ownership.
**Recommendation:** Each independent review records draft and canonical ledger digests. The gate re-reads all evidence and only recognizes a completed structured review if the ledger still matches. Typed observations, exact attributions, canonical missing fields and executed policy trace own support; unsupported critic objections never manufacture conflict or erase a valid typed fact. New counter-search evidence requires a subsequent real review before reserved finalization. Final claims always revalidate; no extra main repair. A literal determined synthetic policy result may render through a controlled decision-support template after current review, never a payment authorization. OPERATIONAL_GUIDANCE remains qualified for unassigned human adequacy; no human signature invented.
**What affects what:** critic.py/loop.py/gate.py, canonical model fields, safe API/timeline metadata and guard tests. Raw reviews stay protected diagnostics, never timeline/evidence prompts. Existing Groq transport uses fresh critic messages and no native tools; only backend-scoped knowledge searches run under shared counters. No new provider/dependency/schema migration.
**My answer (editable):** Coordinator implements the approved authority boundaries in existing owners.
**Verification:** Independent-context, invented-ref, grounded-but-false objection, canonical gap, cap/cancellation/revocation and artifact tests; actual Groq/API/citation correction still required.

## ADR-0049 — Correct the frozen critic treatment before a fresh run

**Status:** ACCEPTED coordinator fixture/prompt correction within ADR0046;2026-10-19.
**Authority:** Actual first P06 pilot source/response inspection; P06-T03 input integrity.
**Question:** Was the supposedly missing appendix already present through another evidence route?
**Why:** First exception fixture added an incomplete PolicyDecision whose canonical clause previews already contained the exception. No new search was necessary. It also elicited inappropriate knowledge searches for live settlement status. Full-runtime smoke then hit400/429 (8000TPM); all original rows remain failures/observations, not a critic win.
**Options:** Claim a search win anyway (rejected), or correct the producing fixture and run a separately identified revision with all prior results retained.
**Recommendation:** Version2 separates exception discovery (initial SOP/live only, no policy trace carrying appendix), valid-fact control, genuine missing-input policy control, and genuinely withheld appendix. Keep all four paired review modes. Ask the reviewer to search for a requested document absent from its inventory; missing live facts remain missing and are not knowledge-search targets. Typed missing-slot fields must come from supplied policy requirements; semantic inquiries remain reasons, never new authority. Use60s inter-condition pacing (within the allowed wait cap), preserve60s per-request deadline and original freshness limits. Full-runtime source/appendix test is separate from frozen inputs and earlier P04/P05 domain checks; no hidden native-tool/model fallback. Capture scoped Git/source/prompt/fixture/index manifests before calls. Preserve first run and exact loaded source snapshot.
**What affects what:** critic prompt/repair hint, evaluate.py setup and manifest, critic_pilot fixture version and falsifying tests. Six P06 tasks and positive actual correction/citation requirement unchanged; no benchmark/graph/default-budget/dependency expansion.
**My answer (editable):** Coordinator fixes a confirmed input-integrity error before relying on the measurement; no research-success inference.
**Verification:** Original report/source sidecar retained. Fresh v2 completed16conditions with equal frozen hashes and source snapshots; raw/scorer2 hashes and failures at E-P06-001. Actual full-message proof remains open.

## ADR-0050 — Separate observed retention loss from a causal critic veto

**Status:** ACCEPTED coordinator measurement correction;2026-10-19.
**Authority:** P06-T03.01/02, ADR0046 unknown semantic judgments and claims discipline.
**Question:** Does loss of a known fact relative to the off arm prove a critic veto?
**Why:** The first scorer named simple output omission mechanical_false_veto_vs_off. A finalizer omission or provider failure can produce that observation without any critic veto. That causal label was unsupported and is retracted; original reports remain byte-for-byte unchanged.
**Options:** Retain a misleading causal label (rejected), or distinguish observable retention loss, structured false objections and unknown causal veto.
**Recommendation:** Scorer version2 reports known_fact_retention_loss_vs_off, measured false objections against controlled valid claims, and null mechanical_false_veto_vs_off pending actual veto attribution. Preserve semantic unknowns. Derive a separately identified summary from saved raw artifacts after the active v2 experiment finishes; never overwrite its launch snapshot, source hashes or original scores. Strict full-exception-quote matching remains strict: a valid shorter excerpt is not relabeled a full-quote success.
**What affects what:** core/evaluation.py, its negative controls, evaluate.py future manifests and derived report; RESEARCH_PROTOCOL/EVIDENCE_LOG. Current active run p06-3202bf9ad06143478590fdedd298fdfb uses its frozen original scorer snapshot, not this subsequent version.
**My answer (editable):** Coordinator corrects an evidenced measurement error; no new hypothesis or acceptance threshold.
**Verification:** Seven scorer controls pass, including omission with/without provider failure; raw-preserving scorer2 derivation verifies all launch hashes, frozen envelopes and original bytes (E-P06-001). Original v1/v2 artifacts unchanged.

## ADR-0051 — Separate a targeted full-message engineering probe from paired experiments

**Status:** ACCEPTED coordinator verification detail;2026-10-19.
**Authority:** P06-T02.02 actual message proof and owner-approved explicit GPT-OSS20B alternative (ADR0036).
**Question:** How will the remaining full-entry-point correction be checked after the v2 pilot's full-message HTTP400?
**Why:** Frozen pairs showed actual appendix discovery and final exact attributed excerpts, but the separate full message did not counter-search and recorded a provider failure. It cannot close the real runtime gate.
**Options:** Hide the failed message (rejected), or retain it and run a separately named, bounded explicit engineering scenario.
**Recommendation:** Add critic scenario to existing validate_agent.py: one SOP search/draft requested, overall question explicitly requests the missing approved appendix. Use explicit openai/gpt-oss-20b after the active120B experiment ends. Require actual critic counter-search and subsequent review, appendix-backed final citation, authenticated citation GET and matching persisted timeline counts, with no verification failures. Existing request deadline, call limits, gate and transport remain unchanged. Each invocation is one separately retained engineering receipt, never a selective replacement for paired measurements or a reliability estimate.
**What affects what:** scripts/validate_agent.py, P06-T02.02 ownership/evidence and final smoke. No runtime fallback, new dependency or gate relaxation. Earlier provider failures and strict full-quote misses remain visible.
**My answer (editable):** Coordinator implements required entry-point proof through the existing explicit smoke command.
**Verification:** Actual20B invocation exited1 with two critic schema failures and final429; original/extracted receipts retained at E-P06-001. Separate120B r3 also failed400/429. Positive full-message proof remains open; no successful condition substituted.

## ADR-0052 — Give the bounded critic repair a safe actionable cause

**Status:** ACCEPTED in-scope owning-layer correction;2026-10-19.
**Authority:** Blueprint11.5 one bounded corrected schema repair; P06-T01/T02 verification.
**Question:** Can a boolean repair flag correct repeated grounding/schema errors?
**Why:** Explicit20B full-message probe failed both critic validations and then hit8000TPM (used6445/requested1961). Raw rejected output was intentionally absent; the caller supplied only a boolean repair flag, so no specific validation correction reached the next review. No success is inferred from this failure.
**Options:** Retry blindly (rejected), or pass a bounded allowlisted validator cause to the one existing repair and retain it only in protected diagnostics.
**Recommendation:** Reuse existing validation owner and attempt cap. Controlled known grounding errors become repair hints; Pydantic schema failures use a fixed schema hint. Never reflect arbitrary exception/provider/model prose into instructions or public readers. Add a falsifying unknown-required-slot repair control. Preserve original v1/v2 artifacts. The next separately retained engineering smoke asks for a single SOP candidate (existing tool limit1) to avoid unnecessary context; record explicit model/query/source versions and do not change runtime defaults or budgets.
**What affects what:** critic.py context/error diagnostics, test_critic.py and validate_agent.py engineering question. No new tools, retries, authority, dependency or shipped contract.
**My answer (editable):** Coordinator fixes unambiguous missing repair context and improves safe observability at the owning validator.
**Verification:** Focused39PASS8.32s, source274PASS42.97s, rebuilt exact50file artifact and installed35focusedPASS12.69s. Separate120B r3 failed400/429 without critic validation errors; it does not prove positive full-message correction. Original20B failure retained.

## ADR-0053 — Optional shared model-call pacing under the existing deadline

**Status:** ACCEPTED; owner async reply2026-10-19: Approve opt-in call pacing (Recommended). Implementation/proof remains required.
**Authority:** Actual P06 free-quota failures; Rule4 transport/configuration contract escalation.
**Question:** May explicitly enabled live checks space main/critic calls, initially10seconds, while preserving the existing60second deadline and attempt caps?
**Why:** Full-message20B and120B probes consumed the shared8000TPM before reserved finalization. The latter also made extra investigator calls and provider400; pacing cannot itself prove that separate model-output failure is fixed. Immediate bursts do not establish required positive full-runtime proof.
**Options:** Opt-in shared transport pacing; preserve unchanged transport; another owner-selected approach. Higher quota or a hidden model fallback is not assumed.
**Recommendation:** Add explicit configurable pacing, default0, shared across main and critic on the same model boundary. Waiting is cancellable and included in the existing request deadline; no failed HTTP request retry, call-limit increase or automatic model switch. Record actual timing/configuration. Start at10seconds as a separately identified engineering condition, retaining every prior failure and making no reliability inference.
**What affects what:** If approved, agent/llm.py explicit transport configuration, existing enabled serve/validate/evaluate consumers as scoped, cancellation/concurrency tests and actual live proof. P06 full-message gate remains open; no phase closeout or main push implied.
**My answer (editable):** Approve opt-in call pacing (Recommended)
**Amendment history:** Previously PENDING; owner approved the async question on2026-10-19.
**Verification:** Approved, not yet verified. Transport spacing is shared by main/critic; an existing caller-owned before-send validation callback will recheck authorization/evidence after any wait. No abandoned future reservations, retry, default pacing or deadline widening. End audit waits for complete checks.

## ADR-0054 — Prove critic discovery from canonical pre-review inventory

**Status:** ACCEPTED coordinator proof/diagnostic correction;2026-10-19.
**Authority:** P06-T02.02, ADR0049 confound prevention and existing protected diagnostics.
**Question:** Does a final appendix citation plus a critic search prove that the critic found previously absent evidence?
**Why:** The investigator may already have retrieved another chunk of that appendix. The existing smoke predicate did not distinguish this route. Per-attempt provider codes were also lost when a later quota error replaced the transport's last failure, obstructing diagnosis of400.
**Options:** Infer discovery from counters (rejected), or retain protected canonical inventory bindings and test the actual transition.
**Recommendation:** Record each critic input's evidence IDs/kinds/revision IDs and digest in existing DIAGNOSTIC events. The smoke requires no appendix revision in the first critic inventory and a later reviewed appendix revision, plus final canonical citation readback. Never expose these diagnostics in timeline/recall/evidence views. Preserve safe provider error code per counted model attempt, without provider prose. Add negative controls for pre-supplied appendix, no subsequent review and repair-prose privacy.
**What affects what:** critic.py/loop.py internal events, validate_agent.py proof reader and focused tests; the existing main prompt now explicitly describes initial draft → independent exception review → finalization, without restricting any of the four tools; no authority, public API, dependency or fifth tool. Pacing approval ADR0053 is independent; old receipts remain unchanged.
**My answer (editable):** Coordinator closes a confirmed measurement gap and keeps failure diagnosis at the existing owner.
**Verification:** Pending positive/negative controls and actual paced entry-point proof.

## ADR-0055 — Supplement default-budget proof with bounded main-exhaustion recovery

**Status:** ACCEPTED coordinator test configuration within existing Settings;2026-10-19.
**Authority:** P06-T02.02 actual counter-search proof; existing validated lower main-call caps and safe draft exhaustion path.
**Question:** How can the remaining critic-discovery path be exercised when the investigator already fetched the requested appendix?
**Why:** Paced20B completes the default-budget native investigator → generated draft → independent review → reserved final → gate/API path without verification failures, but correctly fails the discovery predicate because the appendix was already present. This is a measurement condition mismatch, not evidence that the critic found it. The complete three-model grid is retained.
**Options:** Call a main discovery a critic win (rejected), or supplement the default-budget run with an explicitly lower existing main-call cap and report that narrower condition honestly.
**Recommendation:** Expose existing Settings.main_max_calls through the synthetic smoke CLI, default5 unchanged. A separate recovery scenario uses cap2: one real native investigator call, existing safe-draft exhaustion, independent real critic discovery/review and the reserved real finalization call, inside the same60s and shared tool limits. No fake model, injected tool output or new runtime path. This recovery probe supplements, rather than replaces, the default-budget real generated-draft proof and frozen paired measurements. Record source/settings/model, initial inventory, new appendix evidence, final exact quote, current citation GET and timeline counts. No natural main-model error rate or research superiority claim.
**What affects what:** scripts/validate_agent.py explicit CLI settings/report, P06-T02.02 evidence; runtime, shipped defaults, four tools and authority remain unchanged. Full-scope end reviewer must assess both default and recovery evidence before phase closure.
**My answer (editable):** Coordinator selects an existing supported test configuration; no new architectural decision or owner quota change.
**Verification:** Default20B52.9s noverificationfailures; three-model grid retained. Separate actual recovery proof pending; no completion inferred from intent.

## ADR-0056 — Make the critic's admissible slot set explicit

**Status:** ACCEPTED coordinator prompt/schema alignment;2026-10-19.
**Authority:** Existing typed-slot validation, ADR0049/0052 and actual lower-cap120B errors.
**Question:** Why did the reviewer repeat Unknown critic requirement after a repair hint?
**Why:** The lower-cap120B probe proposed schema slots even though its supplied requirements list was empty. Both attempts were rejected, and finalization later returned400/json_validate_failed. The valid-JSON structured allowlist needs to be explicit; no source/slot authority is being broadened.
**Options:** Relax validation (rejected), or state the already-enforced admissible names directly in the model context.
**Recommendation:** Supply allowed_missing_slots from the same canonical requirement producer. Explicitly require all missing_slots arrays empty when that list is empty, and claim_reviews empty for an empty initial draft. Missing-document counter-search remains available. Existing unsupported-ID/slot rejection, one repair/caps and deterministic authority stay unchanged. Record the failed120B recovery and a separately identified20B check; no hidden retry or success claim.
**What affects what:** critic prompt/context, existing guard assertions and subsequent actual proof. Earlier frozen measurements retain their exact launch-version prompts; they are not measurements of this subsequent revision.
**My answer (editable):** Coordinator clarifies existing strict constraints without weakening acceptance or claiming semantic accuracy.
**Verification:** Pending guard/current-profile live checks. Original lower-cap120B failure retained in runtime/evaluation/p06-message-120b-recovery.json.

## ADR-0057 — Ground requested-source gaps and the intended clause in the live probe

**Status:** ACCEPTED coordinator input/proof correction;2026-10-19.
**Authority:** P06 critic question/inventory context, existing ExactIndex and deterministic nonexclusive preflight principles.
**Question:** Did the recovery reviewer receive the intended reversal clause, and can it identify a concrete unrepresented request?
**Why:** Actual20B recovery has no verification errors but returns vacuous PASS/NOT_ESTABLISHED without search. Its only initial document is the introductory SOP chunk: source-ID exact union plus limit1 is not clause selection. Frozen v2 explicitly used the reversal clause. A source-ID string in a long untrusted question is also not an explicit coverage observation.
**Options:** Infer clause coverage from whole-source ID (rejected), relax search success criteria (rejected), or correct the probe and expose bounded scoped coverage hints using the existing exact reader.
**Recommendation:** The live recovery question targets exact S26-REVERSAL, not whole-SOP limit1. Critic context carries at most8 requested identifiers from ExactIndex.identifiers and whether each matches an already admitted inventory ID through the current authorized exact reader. False means not represented in this supplied ledger, never nonexistent/known outside scope. Unknown and inaccessible references remain indistinguishable. Prompt an empty draft to investigate concrete unrepresented document requests rather than treating no claims as question completion. Four tools, validator and gate stay unchanged; no automatic search or new authority.
**What affects what:** critic context/prompt, validate_agent.py synthetic query and bounded/privacy controls. Default generated-draft proof and all prior failed recovery receipts remain separate; source/prompt versions are explicit.
**My answer (editable):** Coordinator fixes the demonstrated producer gap using existing canonical readers, without redefining success.
**Verification:** Pending positive/negative controls and separately identified actual recovery. Original20Bcap2 run23.467s had no errors but no search/correction; it remains a failed discovery check.

## ADR-0058 — Own finalization instructions in the trusted role

**Status:** ACCEPTED coordinator wiring fix within P06-T02.02;2026-10-19.
**Authority:** Blueprint draft → advisory review/new evidence → reserved finalization; protected rejected-claim diagnostics.
**Question:** Where does the backend instruct the reserved finalizer to use the revised ledger?
**Why:** The finalization action was a field inside the user-data payload, while the system prompt treats user text as data. Actual clause-recovery20B discovers/reviews the new appendix with no errors (31.014s,2main/2critic/1search) but final output has no claims. This identifies an instruction-ownership defect; it does not prove the cause of every model omission.
**Options:** Treat user/source data as instructions (rejected), or place the backend phase instruction in the trusted system role.
**Recommendation:** Reuse the existing draft schema/safety rules plus a trusted explicit finalization phase instruction: build a substantive evidence-bound draft from current ledger even when the initial draft is empty; include supported exception and preserve valid observations; no more tools, payment permission or completeness claim. Remove the backend instruction field from untrusted data. Retain bounded initial/final proposed claims in existing protected DIAGNOSTIC events, including MODEL versus SAFE_TEMPLATE origin; public readers must reject those handles. Future evaluator manifests hash the finalization prompt separately. No extra model call or changed gate.
**What affects what:** draft.py/loop.py, evaluate.py prompt manifest, synthetic smoke diagnostics and privacy/role tests. Existing budget/deadline/provider/defaults remain unchanged; prior failed runs stay intact.
**My answer (editable):** Coordinator fixes trusted instruction placement at its owning layer and completes the planned protected proposal diagnostics.
**Verification:** Pending guard/API negative controls and separately identified actual recovery. Prior clause-recovery report remains failed because no final appendix citation was released.

## ADR-0059 — Ask for the exact exception clause without conflicting output constraints

**Status:** ACCEPTED coordinator smoke-fixture correction;2026-10-19.
**Authority:** P06-T02.02/T10 exact exception and citation proof; source/alias inspection.
**Question:** Did the live question request an unambiguous final output and retrieve the intended exception span?
**Why:** The prior question said an initial draft should contain only S26 while later asking for an appendix quote. Source-ID EX-2026-04 lookup also returned introductory/boundary chunks rather than EX-SETTLEMENT-DELAY. After the trusted-finalizer fix, actual20B31–34s runs discover/review appendix and emit a valid SOP quote but omit the requested exception. They remain failed full-correction checks.
**Options:** Count any appendix presence as the full exception (rejected), or name the intended clause and remove the conflicting only-S26 output wording.
**Recommendation:** A clear question starts with exact S26-REVERSAL/limit1 and asks the final answer for separate exact S26-REVERSAL and EX-SETTLEMENT-DELAY attributions. The critic must still choose/execute its scoped search; no evidence is injected. Tighten the smoke predicate to require the complete canonical exception clause in released claims, actual new revision/review, citation GET and timeline counts. This is exact-ID mechanical integration evidence, not semantic ANN discovery, natural model-error correction or research accuracy. Frozen semantic search results retain their original versioned measurements.
**What affects what:** validate_agent.py question/strict expected quote and receipts only. Production runtime, budgets, model roles and gate unchanged. Default-budget generated-draft proof remains separately required on final source.
**My answer (editable):** Coordinator fixes known producer ambiguity and strengthens observable acceptance without hiding failed rows.
**Verification:** Pending explicit20Bcap2/10s exact-clause recovery and final default-budget document smoke. Prior source snapshots and failures retained.

## ADR-0060 — Distinguish correct normal review from discovery recovery

**Status:** ACCEPTED coordinator verification detail;2026-10-19.
**Authority:** P06-T02.02 full-flow evidence and ADR0055's supplemental recovery boundary.
**Question:** Should a normal message fail simply because its investigator already found the requested exception?
**Why:** The strict critic scenario rightly requires a new appendix revision. Normal default-budget messages can already contain it, so that predicate cannot demonstrate their correct generated-draft/review/final behavior. The final-source20B document check separately hit60s after seven reservations at10s spacing; the limit held and its failure stays visible.
**Options:** Weaken discovery acceptance (rejected), or use separate explicit predicates for the two required paths.
**Recommendation:** Keep critic scenario strict unchanged. Add reviewed_exception using the same exact-clause question, requiring a nonempty MODEL-origin initial draft, actual current review, full final exception quote, canonical citations and matching timeline with zero verification errors. Use default maincap5. Explicit8s pacing is a separately recorded configuration within approved0–60s range; it is based on the observed seven-call10s deadline, not a shipped-default change. The existing cap2 critic recovery already strictly passes and remains separate. No failed condition is replaced or counted as research success.
**What affects what:** validate_agent.py verification scenario/report and final normal-path live check. Runtime/policy/gate/default budgets/model selection remain unchanged.
**My answer (editable):** Coordinator separates complementary observable outcomes rather than requiring a redundant critic search when coverage already exists.
**Verification:** Strict cap2 exact recoveryPASS31.076s; final-source default normal proofPASS47.949s,4main/1critic,MODEL draft/full clause/readback/noerrors. Failed document/deadline receipt retained.

## ADR-0061 — Refresh paired evidence on the final source version

**Status:** ACCEPTED coordinator verification correction;2026-10-19.
**Authority:** Source-version fidelity, P06-T03 and no-stale/completion audit.
**Question:** Can the earlier120B pilot alone measure the final critic/context/finalizer revision?
**Why:** It accurately measures its launch version, but subsequent allowed-slot hints, exact coverage and trusted finalization changed the prompts. Treating its statistics as final-build measurements would be unsupported.
**Options:** Relabel old results as current (rejected), or retain them and run the complete matrix on final source.
**Recommendation:** Reopen T03.01/02 proof pending a fresh full four-case/four-mode run on explicitly selected owner-approved GPT-OSS20B. Keep all16conditions,60s external pacing, original source freshness/global deadline, and intra-model pacing0 as in the original frozen comparison. Capture source/prompts/fixture/configuration before provider calls. Preserve every failure and unknown semantic/causal score. This is not a cross-model quality comparison or best-of-N success selection; final positive default and exact-recovery consumers are already separate engineering proofs.
**What affects what:** Research receipts/current task status only; source/runtime/fixture/defaults unchanged and frozen during execution. Single end reviewer follows completed final checks.
**My answer (editable):** Coordinator corrects the evidence-version boundary before claiming completion.
**Verification:** Final-source default20B reviewed_exceptionPASS47.949s,4main/1critic/2tools, MODEL initial draft/full exception/two citations/timeline/noerrors. Full final-source20B matrix complete16conditions:16/16known-fact retention,0/4full-clause correction, one validation failure. Raw/scorer2 summary recorded at E-P06-001. Older120B results remain version-specific.

## ADR-0062 — Qualify changed proposals and unresolved advisory challenges

**Status:** ACCEPTED coordinator in-scope gate correction;2026-10-19.
**Authority:** P06-T02, blueprint §10.5 no unresolved challenge for SUPPORTED; sole end review R1.
**Question:** Can evidence-bound review alone certify a changed final proposal or an unresolved CHALLENGE?
**Why:** The stored draft digest was not consumed by the release gate. A completed CHALLENGE was treated identically to PASS for disposition, despite canonical claims still needing honest review coverage.
**Options:** Add post-finalizer model calls/change budgets (rejected), or conservatively qualify final output using existing review/draft bindings.
**Recommendation:** When a current review's draft digest differs from the final draft, add revised_draft_requires_review. A current CHALLENGE adds unresolved_critic_challenge. Preserve independently canonical facts/attributions, never infer conflict or semantic falsity; such output is PARTIALLY_SUPPORTED, not SUPPORTED. Exact unchanged PASS remains eligible. No prompt, tool, dependency, authorization, schema or budget change.
**What affects what:** agent/gate.py consumes existing ReviewResult.draft_sha256; test_critic.py proves changed policy/fact and unresolved challenge controls. Public missing_requirements already carries bounded qualification strings. Model experiment prompts/frozen ledger and mechanical quote/fact scores are unchanged; previous raw run remains its launch gate version, not retroactively current output. Final gate checks and live entry points must be verified after correction.
**My answer (editable):** Coordinator implements the verified in-scope review finding; no semantic veto authority or new model stage is introduced.
**Verification:** Source294PASS, installed294PASS, actual-Qdrant13PASS and installed1overlap, post-fix real20B recovery39.827s/default-budget37.089sPASS, same-reviewer R1 resolution and final cleanup verified at E-P06-002. R2 blind arm objection withdrawn against §10.1; docs clarify draft-blind, supplied canonical requirements, no independent unsupplied-requirement discovery claim.

## ADR-0063 — P07 canonical provenance and graph publication contracts

**Status:** ACCEPTED owner decision;2026-10-19.
**Authority:** P07 GO; Rule4 still requires approval for shipped schema/publication/configuration contracts.
**Question:** May P07 add canonical graph attestations and compatible explicit graph treatment contracts?
**Why:** Identity hashes prove no attestation. SQLite owns authority; Neo4j is derived. Catalog currently rejects graph-enabled publication/non-Qdrant reconciliation, and the real search worker reconstructs no graph configuration.
**Options:** Keep P07 blocked, or add v5 graph attestations/review/merge records and explicit optional graph contracts.
**Recommendation:** Add v5 immutable source-backed identity attestations, relation reviews and merge decisions with reviewer/time and before/after history; preserve existing rows/APIs and default graph-off. Reuse existing backend manifests, include graph mode in generation identity, and require exact Neo4j ID/hash acknowledgment before graph-required READY. Optional traversal outage explicitly degrades to hybrid; required-relation verification fails unavailable. Wire the real search_knowledge worker. Bounded path metadata is navigation, never authority. No fifth tool or user-registry migration without backup.
**What affects what:** graph registry/identity, SQLite/graph_schema, Catalog/ingest, Settings/HybridSearch/main/API/services/search_worker/audit/scripts. Tests: fresh creation, populated upgrade/rollback preservation, graph publication/outage/cancellation and actual-tool readback.
**My answer (editable):** Approve additive v5 and graph contracts — explicit async answer2026-10-19.
**Initial verification snapshot:** Proposed; no implementation claimed. E-P07-001 records source and pre-adversary findings.

**Verification:** Final2026-10-19: E-P07-002 source/migration/real-store/installed/CLI/provider consumer gates and sole end-review resolution verified. Accepted owner answers remain unchanged. Graph negative-result disable decision and unadjudicated memory semantic limits retained.

## ADR-0064 — P07 identity attestation and reviewed-merge authority

**Status:** ACCEPTED owner decision;2026-10-19.
**Authority:** Rule4 new authorization/authority contract; blueprint §6.
**Question:** Who may attest stable identity, review relations and approve equivalence merges?
**Why:** An external-ID string, document self-label or model extraction cannot establish verified identity. Private provenance must survive merges; names are not keys.
**Options:** Extracted labels grant verification (rejected), or explicit current scoped-admin approval with durable source evidence.
**Recommendation:** Require an existing current admin with document:approve, case membership and current access to every referenced approved source. Persist exact spans, reviewer/time, reason and accepted/rejected before/after merge decisions. Preserve EXTRACTED_UNREVIEWED for unreviewed relations. Models get no write/review/merge tool. Recheck all original case/source permissions before exposing any path. No merge merely from matching names or metadata.
**What affects what:** graph registry, identity, relations, trusted local operator/fixture producer, canonical attestation reader and Neo4j projection; revoked source/role/membership, duplicate race, distinct-ID and merge replay tests.
**My answer (editable):** Approve scoped admin attestation controls — explicit async answer2026-10-19.
**Initial verification snapshot:** Proposed; no invented independent human review.

**Verification:** Final2026-10-19: E-P07-002 source/migration/real-store/installed/CLI/provider consumer gates and sole end-review resolution verified. Accepted owner answers remain unchanged. Graph negative-result disable decision and unadjudicated memory semantic limits retained.

## ADR-0065 — P07 Docker-free local Neo4j execution

**Status:** ACCEPTED owner decision;2026-10-19.
**Authority:** User Docker alternative instruction and package delegation within the blueprint; local security boundary requires explicit direction.
**Question:** May P07 tests use a pinned project-owned portable WSL Neo4j instance?
**Why:** WSL Ubuntu works but Java is absent; fake stores cannot prove real Neo4j concurrency. Available WSL RAM is about3.6GiB.
**Options:** Portable local synthetic instance, or require an externally managed Neo4j service.
**Recommendation:** Pin neo4j Python driver6.4.1 with uv, Neo4j Community2026.09.0 and checksum-verified portable Java21 under ignored runtime storage. Add explicit setup/start/stop, bounded memory, project-owned storage and loopback-only Bolt17687 with HTTP disabled. For this synthetic-only local instance, disable database auth so the cancellable worker remains credential-free; forbid remote URI/real data. No system service, boot-start or global Java change. Preserve storage on stop; tests clean only newly created UUID partitions. Graph-off needs no Neo4j connection. Retain an optional Compose pin for other machines.
**What affects what:** pyproject/uv.lock, compose, scripts/neo4j_server.py, README and real-store tests. Official references: [driver installation](https://neo4j.com/docs/python-manual/current/install/), [Linux tarball](https://neo4j.com/docs/operations-manual/current/installation/linux/tarball/). PyPI metadata confirms6.4.1/Python>=3.10; official docs list Java21 support.
**My answer (editable):** Approve isolated synthetic WSL setup — explicit async answer2026-10-19.
**Initial verification snapshot:** WSL x86_64/curl present, Java absent. No setup/download performed pending boundary choice; actual compatibility remains to prove.

**Verification:** Final2026-10-19: E-P07-002 source/migration/real-store/installed/CLI/provider consumer gates and sole end-review resolution verified. Accepted owner answers remain unchanged. Graph negative-result disable decision and unadjudicated memory semantic limits retained.

## ADR-0066 — P07 expanded automatic memory promotion mandate

**Status:** ACCEPTED owner scope/category/session direction; classifier amended by owner2026-10-19. Additive v6 storage explicitly APPROVED by owner async reply2026-10-19.
**Authority:** User explicitly adds automatic chunked memory promotion to P07; blueprint §9 and Rule4 govern scope, approval and runtime contracts.
**Question:** How should automatic episodic/semantic/procedural categorization interact with user scope, sessions, provenance and call budgets?
**Why:** Current backend persists events automatically, but categorized memory is operator-written. Category is not access scope: global preferences must not leak private case data or become organization policy. Current message API has no session ID, and extraction cannot silently add a sixth main call or bypass approved procedure ownership.
**Options:** Deterministic bounded promotion now, a separately enabled bounded classifier worker, or consume the existing bounded main response with validated promotion proposals.
**Recommendation:** Semantic means durable USER memory across that user's sessions, not cross-user organization sharing. Promote only explicit user-stated preferences into this durable lane; case facts stay case-scoped and all source ACLs survive. Procedural means observed tool/workflow experience or explicitly owned plans, always unapproved context until an authorized workflow approval; model/execution success is not company-policy approval. Everything else remains episodic in its owning session. Chunk deterministically by event and bounded text spans, retaining event IDs/offsets and immutable promotion decisions. Add backend-owned explicit session IDs/lifecycle with compatible defaults, preserve canonical case evidence outside conversational memory, and consume bounded classifier proposals under a separately explicit measured budget if owner selects that option. Idempotent promotion/correction/revocation and cross-session/user/case privacy must be tested through real readers.
**What affects what:** P07 extra memory task cards; CaseStore/MemoryStore/packet, schema/migration, session API, runtime and extraction/budget owner, FTS recall, CLI/tests/evaluator. Main performs implementation; reuse same start adversary to review new premises, then one end reviewer covers graph plus memory. No embedding/vector dependency is implied.
**My answer (editable):** Owner approved private USER-wide semantic preferences, preserving original case/source ACL, and explicit backend session IDs/lifecycle. Owner overrides the Groq-first recommendation: PathA deterministic rules is primary; PathB cosine similarity plus a loss function is fallback/additional evidence, with greater emphasis on deterministic rules. Add all work to the development suite. Prior options remain above as history; no extra Groq classifier calls are authorized by this answer.
**Amendment2026-10-19:** Implement deterministic event/span chunking and an auditable PathA result first. Optional PathB uses the existing pinned local dense encoder and labeled category examples, a recorded cosine margin loss and deterministic-dominant weighting. Loss is a comparison/abstention measure, not a claim of trained/calibrated accuracy. Hard privacy/type/eligibility checks cannot be overridden by either score. Uncertain chunks remain episodic. Add v6 session/event-span/promotion-decision provenance, preserving operator memory and v5 graph rows; test fresh creation, populated upgrade and transaction rollback. Keep observed procedural experience explicitly unapproved/authorityNONE, distinct from canonical approved workflows. No vector database or new LLM tool is introduced.
**Initial verification snapshot:** Current MemorySpec defaults SEMANTIC but has no classifier; runtime has no write tool or session contract. Graph work remains independently authorized under0063–65.

**Verification:** Final2026-10-19: E-P07-002 source/migration/real-store/installed/CLI/provider consumer gates and sole end-review resolution verified. Accepted owner answers remain unchanged. Graph negative-result disable decision and unadjudicated memory semantic limits retained.

## ADR-0067 — Freeze complete graph projection expectations before publication

**Status:** ACCEPTED coordinator implementation detail within approved0063;2026-10-19.
**Authority:** Existing exact backend-manifest reconciliation and P07 graph source-integrity gate.
**Question:** Does confirming only Neo4j chunk presence prove that expected relations were indexed?
**Why:** No. A relation extractor could write nothing while chunks report healthy. Graph publication must cover the relation producer and its actual reader.
**Options:** Chunk-only acknowledgment (rejected), or a frozen per-generation graph projection manifest including chunk and canonical relation IDs/hashes.
**Recommendation:** Add index_graph_expectations to unshipped approved v5. Snapshot canonical graph projection before write, incorporate its hash into graph-enabled generation identity, and acknowledge exact chunk+relation readback. Keep graph-off generation identity/backends unchanged. No real registry migration occurs without existing backup discipline. New attestations/reviews need reindex/reconciliation for the changed projection; every runtime edge/source is still revalidated canonically. All inferred paths stay navigation-only.
**What affects what:** graph_schema.sql/GraphRegistry/extractor/projection, Catalog/ingest and Neo4j adapter readback; missing/extra/tampered relation and interrupted/idempotent retry tests. No authority moves to Neo4j.
**My answer (editable):** Coordinator grounds graph acknowledgment in the existing exact-manifest pattern instead of treating a healthy producer as proof of consumer coverage.
**Initial verification snapshot:** Real Neo4j physical projection/alias controls2PASS4.21s, canonical race/graph-off5PASS1.59s. Readback recomputes mentions and physical FROM/TO adjacency; source changes invalidate graph READY. Atomic merge validates canonical sources through Catalog plus OriginalStore, avoiding nested Registry.read_source transactions. Graph runtime/baseline experiment still open.

**Verification:** Final2026-10-19: E-P07-002 source/migration/real-store/installed/CLI/provider consumer gates and sole end-review resolution verified. Accepted owner answers remain unchanged. Graph negative-result disable decision and unadjudicated memory semantic limits retained.

## ADR-0068 — Deterministic-primary promotion profile and transactional write ownership

**Status:** ACCEPTED coordinator implementation profile within owner0066;2026-10-19.
**Authority:** Owner PathA/PathB amendment, explicit session/USER scope and additivev6 approval.
**Question:** How do optional similarities supplement rules without granting authority or leaving partially written memory?
**Why:** A cosine ranking/loss is not semantic truth or trained accuracy. An automatic entry without its session/source-span link could escape the intended reader guard if a write fails halfway.
**Options:** Unbounded classifier/independent writes (rejected), or deterministic eligibility plus bounded optional local supplement and enlisted atomic persistence.
**Recommendation:** Freeze promotion-1 prototypes/config before pilot: PathA explicit self-stated preferences, observed allowlisted tool experience, else episodic. Hard quote/attribution/case/authority rejection is final. Only ambiguous eligible personal-style cues enter optional PathB; primary weight0.8, cosine threshold0.75, margin0.1, combined threshold0.65. Loss=max(0,margin-(top-second)); defaults are uncalibrated pilot tunables, not probabilities or training results. Default automatic PathA enabled, local PathB explicitly enabled; no Groq classifier. Backend commits chunk/decision/MemoryStore entry/link atomically using an explicit owner-validated enlisted connection. Preserve the committed runtime event even if promotion fails; expose safe failure metadata rather than pretend stored. Category/scopes stay separate; procedural experience is reported unapproved context, never approved procedure. Session-only episodic readers are distinct from canonical case/source audits/evidence.
**What affects what:** memory/classification,promotion,sessions, MemoryStore writer/reader, runtime/API/packet, bounded local embedding worker/CLI and tests. Source/migration/unit negatives and actual producer→reopened reader/provider proofs required. Existing statement/source validity and originalcase ACL remain intact.
**My answer (editable):** Coordinator selects explicit falsifiable defaults and transaction ownership within the accepted direction; owner may edit future calibration choices.
**Initial verification snapshot:** Classification/session modules are partial; no automatic writer or PathB efficacy claimed until owning consumers and gates execute.

**Verification:** Final2026-10-19: E-P07-002 source/migration/real-store/installed/CLI/provider consumer gates and sole end-review resolution verified. Accepted owner answers remain unchanged. Graph negative-result disable decision and unadjudicated memory semantic limits retained.

## ADR-0069 — Promotion consumer boundaries and explicit local job ownership

**Status:** ACCEPTED coordinator implementation detail;2026-10-19.
**Authority:** Accepted owner ADR0066/0068; existing four-tool runtime, redacted case audit and cancellable local worker patterns.
**Question:** Where do session isolation, procedural experience and optional similarity execute?
**Why:** The redacted audit timeline is case-wide, whereas model episodic continuity must be session-only. A new procedural packet shape must reach the actual loop consumer. Optional local embeddings must not block or expand answer budgets.
**Options:** Change audit visibility/run embeddings inline (rejected), or retain canonical audit readers and separately bound model continuity and opt-in local jobs.
**Recommendation:** Message APIs accept/return compatible optional session IDs, with owner-only start/close. CaseStore/recalled episodic rows and packet releases/reports filter session. Canonical redacted case timeline remains case-wide. Unapproved procedural experience uses the existing previous_attempts payload and is explicitly consumed with authorityNONE. Private preferences reserve packet slots before repetitive events. PathB runs only via scripts/promote_memory.py --enable-path-b in a credential-free subprocess, max8events/64chunks/30seconds with kill/join; no provider calls. Record model/prototype/config/scores/loss and failure/timeout, retry via immutable idempotent ledger. No new dependency or service. Explicit correction/revocation beats later automatic jobs. Unscoped historical episodic rows remain audit/control data rather than model recall.
**What affects what:** memory/store,packet,promotion,promotion_worker; agent/services,loop,tools; api/routes,schemas; scripts/promote_memory.py; owning tests. No source authority or operational write capability changes.
**My answer (editable):** Coordinator chooses existing consumer shapes and a separate explicitly enabled local job within approved scope.
**Initial verification snapshot:** runtime/p07-memory-runtime-r2.log66PASS; runtime/p07-memory-model-controls.log25PASS including actual child encoder and timeout guard. Broader P07/generative proof remains pending.

**Verification:** Final2026-10-19: E-P07-002 source/migration/real-store/installed/CLI/provider consumer gates and sole end-review resolution verified. Accepted owner answers remain unchanged. Graph negative-result disable decision and unadjudicated memory semantic limits retained.

## ADR-0070 — Distinguish graph navigation proof from incremental recovery

**Status:** ACCEPTED coordinator implementation correction;2026-10-19.
**Authority:** P07 graph contracts0063/0067, canonical-path and consumer proof gates.
**Question:** How should a graph path to an already selected passage be represented and measured?
**Why:** Skipping every visited target suppressed valid navigation metadata when ordinary retrieval already found both endpoints. Counting such a path as a novel recovery would inflate graph benefit. Early live runs also hit real Neo4j transaction deadlines and cannot be marked successful.
**Options:** Hide existing-endpoint paths/count them as recovery (rejected), or validate paths separately from admitting new passages and preserve failures.
**Recommendation:** Validate each unique bounded edge and its source proofs even when its target was already selected; only unseen targets enter the traversal frontier. Return paths only when their explicit target_chunk_id survives selection. Keep navigation_only=true and infer no authority. Add graph path counts and GRAPH_UNAVAILABLE to redacted existing telemetry. Per-query remaining time constrains Neo4j execution; runtime process cancellation remains the outer deadline. Keep default graph off and timeout2seconds unchanged; pilot positive controls explicitly configure10seconds. No retry or silent timeout expansion. Retain r1/r2 failures and compare frozen B2/B3 outputs, not path count alone.
**What affects what:** graph/relations, retrieval/graph_expand,hybrid, storage/neo4j, agent/tools, telemetry/audit; actual subprocess/API/Groq and bounded/poisoned/revoked graph controls. Pilot script remains scripts/evaluate_graph.py to avoid a cross-script import layer; task ownership includes this explicit CLI.
**My answer (editable):** Coordinator separates validated navigation from new evidence and retains measured failures within approved graph scope.
**Initial verification snapshot:** Controlled actual Neo4j two-hop positive passed27.23s across multiple traversals after explicit10second operation budgets; early2second/10second transaction failures retained. First paired pilot1308125b:0incremental exception recoveries, B2 already has context link; worker65.19s/degraded is a failure, not passed runtime proof. WSL logs show VM pauses and TransactionTimedOutClientConfiguration; source/cause inference remains bounded. Refreshed successful consumer proof still required.

**Verification:** Final2026-10-19: E-P07-002 source/migration/real-store/installed/CLI/provider consumer gates and sole end-review resolution verified. Accepted owner answers remain unchanged. Graph negative-result disable decision and unadjudicated memory semantic limits retained.

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

Next free ADR number: 0087. Accepted directions do not grant implementation GO.

## ADR-0075 — Development pilot launch configuration and resource accounting

**Status:** ACCEPTED coordinator fixture/configuration within ADR-0019/0071/0072/0074, 2026-10-19.
**Authority:** Full P08 GO, approved stochastic transport and isolated experiments; final evaluation protocol still needs an owner-approved freeze after calibration.
**Question:** What actual development data and bounds precede the frozen evaluation?
**Why:** Existing T01–T24 and P02 data are inspected regression/substrate evidence, not fresh generated-answer calibration or independent human truth.
**Options:** Reuse inspected corpus as confirmatory data (rejected), or supply separate fictional document/case families to development and evaluation stores.
**Recommendation:** `p08_study.json` declares two development and two evaluation families, English/Indonesian, two repeated generations, shuffled order seed1719, selected GPT-OSS20B/temperature0.2. Development executes B0/B1 only. Supply only each case's own original, approve through real registry, index and resolve canonical spans. Fictional zero-input routing policies exercise approved execution/time; required-fact/conflict/temporal rigor remains the separate full T01–T24 matrix. No new enterprise fact or action authority. Development/evaluation have different immutable run IDs; all raw responses, source snapshots, manifests, calls and failures persist in ignored runtime storage. No source/collection deletion.
**What affects what:** evaluation/study.py lifecycle and existing evaluate.py CLI; source snapshots include untracked implementation bytes. Per-phase hard caps200model attempts,160000conservatively estimated token allowance and7200seconds; per-request60seconds, main≤5/critic≤3/planner≤1/tools≤8. Failed calls count; no retry. Actual provider usage and estimates stay separate; missing usage/billing stays unknown. New B9 fixed candidates feed the same canonical rerank/context owner without an extra native fusion; gold IDs derive from canonical original chunks before retrieval, never from returned hits.
**My answer (editable):** Coordinator launch detail under accepted directions. Final targets/tradeoffs and the separate evaluation freeze await actual B0/B1 observations and owner review; no confirmatory claim authorized.
**Verification:** Source/type/guard checks in progress; no development/evaluation provider result claimed before execution.

## ADR-0073 — Frozen experimental mechanics and sidecar ownership

**Status:** ACCEPTED coordinator implementation within approved ADR-0072, 2026-10-19.
**Authority:** Owner-approved isolated controls and sqlite-vec sidecar; existing typed runtime and reader contracts.
**Question:** Which inspectable mechanics implement the approved experiments?
**Why:** Treatment identity must disclose actual work rather than imply a native ANN index or an empirically calibrated risk classifier.
**Options:** Implicit/default switches (rejected), or explicit evaluator objects with frozen mechanics and preserved serving defaults.
**Recommendation:** Use `ExperimentControls` only from the synthetic evaluator. B7 flags typed OPERATIONAL_GUIDANCE/POLICY_RESULT or the recorded policy/action vocabulary; measure euphemism false skips without post-result tuning. B8 adds at most one separately logged same-model planner suggestion call; all four tools remain available after failure. Compare k60 RRF against min-max CombSUM on identical raw candidate lists, with deterministic ties by ID. Vector sidecar stores only IDs, scope metadata, model/content hashes and embeddings; exact sqlite-vec cosine over at most512owner-scoped rows, canonical reader before distance/content return. It is not ANN. Baseline structured/FTS recall remains first; vector augmentation is explicit.
**What affects what:** agent/experiments.py, loop/tools optional hooks, memory/vector.py, core/evaluation.py, redacted planner-role telemetry and owning tests. No registry migration, default bypass, training/calibration claim or source of new authority.
**My answer (editable):** Coordinator detail under accepted ADR-0072; owner approval preserved there.
**Verification:** uv installed sqlite-vec0.1.9; actual in-memory extension reports SQLite3.50.4/vecv0.1.9 and orthogonal cosine distance1. Sidecar reopen/owner isolation/revocation/load-disabled guard passes. Runtime controls and full reader/evaluation proof remain in progress.

## ADR-0074 — Explicit hosted sampling for repeated evaluation

**Status:** ACCEPTED; explicit owner async answer, 2026-10-19.
**Authority:** Rule4 for an additive transport configuration contract; P08 repeated stochastic generations.
**Question:** May the existing Groq transport accept an optional validated temperature, default0, with the study explicitly selecting0.2?
**Why:** Transport currently hardcodes temperature0. Repeating that is useful engineering evidence but cannot be mislabeled a deliberately stochastic sampling treatment.
**Options:** Retain temperature0 and report that limit, or add an optional bounded sampling parameter while preserving every existing caller/default.
**Recommendation:** Optional finite temperature in[0,1], default0; only explicitly enabled P08 study selects0.2 for both development calibration and evaluation. Same selected GPT-OSS20B throughout, no model fallback. Record repetitions, shuffled order/seed, unknown provider seed reproducibility, actual attempts/tokens/failures. Freeze separate run-wide attempt/token/time caps before calls; no retry or per-request deadline expansion.
**What affects what:** agent/llm.py constructor/from_env_file and payload, evaluator CLI/manifest and transport guard tests. No credential, tool, model choice, release or default sampling change.
**My answer (editable):** Approve optional temperature; study uses 0.2 (Recommended).

**Verification:** Current source hardcodes temperature0. Owner approved before the additive implementation; stochastic study proof remains pending.

## ADR-0071 — P08 calibration order and pilot evidence boundary

**Status:** ACCEPTED coordinator implementation within ADR-0019/0021, 2026-10-19.
**Authority:** Explicit P08 GO and the verified start-adversary sequencing finding.
**Question:** How do calibration and frozen evaluation remain distinct without invented independent labels?
**Why:** P02 measured retrieval only; existing T01–T24 cases have already been inspected. No independent semantic annotations or usefulness ratings are evidenced.
**Options:** Reuse inspected cases as confirmatory held-out evidence (rejected), or retain them as regression/development and create disjoint synthetic development/evaluation families with immutable artifacts.
**Recommendation:** Persist actual generated-answer B0/B1 development runs first. Derive and record empirical targets/tradeoffs, freeze the owner-approved protocol and family/source hashes, then execute the declared evaluation grid. Semantic support/usefulness/generalization remain unknown without independent humans. Existing T01–T24 remain the complete regression/fault matrix, not unseen held-out data. New evaluation remains a frozen synthetic pilot.
**What affects what:** P08-T01.01/.02 sequencing, fixture/manifests/scorer/CLI, tests and research/gate status; no release-default change.
**My answer (editable):** Inherits ADR-0019's accepted pilot-only method and P08 GO. The concrete final protocol and targets must be reviewable before evaluation execution.
**Verification:** Start adversary read the complete blueprint and identified the absent calibration boundary; implementation pending.

## ADR-0072 — Isolated experimental controls and derived vector index

**Status:** ACCEPTED; explicit owner async answer, 2026-10-19.
**Authority:** Rule 4 and P08-T02.03–06 for optional interaction contracts and extension installation.
**Question:** May P08 add explicit evaluator-only treatment configuration and a pinned sqlite-vec sidecar with bounded optional recall integration?
**Why:** B7/B8/B9/vector controls are absent. Ablation controls must not weaken ordinary mandatory review; vector hits must retain canonical memory authorization and validity.
**Options:** Leave these experiments pending direction, or implement isolated controls and an explicitly enabled derived index. Changing serving defaults or adding a fifth tool is rejected.
**Recommendation:** Add synthetic evaluator controls: B7 frozen risk-triggered advisory review with false-skip controls against paired B6; B8 nonexclusive planner using the same selected Groq model, separately charged (main ≤5, critic ≤3, planner ≤1, total ≤9); B9 one alternative fusion over identical frozen dense/sparse candidates, without native fusion when the alternative owns combination. Pin sqlite-vec 0.1.9 using uv, in a separate derived SQLite sidecar; load only the packaged extension and immediately disable further extension loading. Revalidate vector hits through current MemoryStore owner/scope/session/source/validity readers. No registry schema migration or existing-data rewrite; optional internal hooks default absent. Ordinary HTTP/runtime mandatory review stays unchanged.
**What affects what:** Evaluator/treatment and memory-vector owners, compatible optional internal hooks if required, pyproject/uv.lock, explicit CLI/config, tests/gates. No write privilege, hidden model fallback or implicit enablement. Require fresh/populated sidecar/readback, stale/revoked/cross-scope and extension-failure controls.
**My answer (editable):** Approve isolated controls and sqlite-vec sidecar (Recommended).

**Verification:** Owner approved; implementation and compatibility proof pending. Official Python example demonstrates loading the packaged extension and disabling loading afterward; PyPI lists 0.1.9. Installed Windows/Python compatibility remains unproven. Final fusion choice is recorded before measurements. Sources: [sqlite-vec Python example](https://github.com/asg017/sqlite-vec/blob/main/examples/simple-python/demo.py), [package metadata](https://pypi.org/project/sqlite-vec/), [Qdrant hybrid queries](https://qdrant.tech/documentation/search/hybrid-queries/).


## P07 final phase-local disposition (2026-10-19)

E-P07-002 records all11cards, actual source/installed/CLI/provider and original-reader proof, the sole GPT6LunaMedium end audit and same-reviewer resolution. The reviewer read the full blueprint (§1–§18), I01–I15, graph and memory amendment; three current-facing document contradictions were fixed and rechecked. No confirmed source defect remained. Graph has0incremental recoveries in4paired queries and stays off by default; controlled path recovery proves integration only. PathA automatic promotion and opt-in bounded local PathB retain original ACL/authorityNONE;4mechanical pilot labels pass,2semantic labels remain unknown. Historical failures and intermediate pending statuses above remain dated snapshots, not current scope. No unanswered P07 owner ADR; P08 adjudication, generalization and external comparisons remain excluded.


## ADR-0076 — Correct the one-call baseline capability contract before freeze

**Status:** ACCEPTED in-scope experimental defect correction,2026-10-19.
**Authority:** P08 B0–B3 one-LLM document-only definitions; universal Rule5.
**Question:** Why do no-tool baseline prompts ask for four tools and a critic?
**Why:** Development launch0/r1 reused DRAFT_INSTRUCTIONS, which explicitly asks for native tool investigation and later critic. R1 recorded four Indonesian provider400/tool_use_failed while all four English calls returned. This is a concrete prompt/capability contradiction, not evidence that a language or model is universally defective. R1 all8observations/4failures remain intact.
**Options:** Ignore provider errors or insert fake outputs (rejected), or fix the baseline prompt owner and launch a separately versioned complete development run before final targets/evaluation freeze.
**Recommendation:** Dedicated one-call no-tool JSON Draft prompt derived from the actual Draft schema; no tools/critic instructions, no new provider/model/corpus/sampling choice. Retain actual raw draft plus common-gate response separately, disclose baseline policy/critic capability gaps instead of attributing wrapper-induced qualification to raw semantic error. Mark actual retrieval status in the ledger so common rendering does not claim no search occurred. Preserve all original runs and prompts; no threshold tuning on evaluation data.
**What affects what:** evaluation/study.py baseline prompt, prompt hash and search attribution, prompt guard and development artifacts. Ordinary runtime/gate/transport unchanged.
**My answer (editable):** Coordinator correction of the owning experimental consumer, supported by the already authorized arm definition.
**Verification:** R1 safe provider diagnostics show tool_use_failed; the mechanism is plausible but the corrected actual-run result is still required. No claim that it fixes every provider failure.

## ADR-0077 — Complete source-state calibration and physical-index disclosure

**Status:** ACCEPTED coordinator correction within P08,2026-10-19.
**Authority:** Blueprint current-source/approval/ACL invariants and P08 calibration/manifests; no serving contract change.
**Question:** Does a single-current-document calibration establish behavior with competing source states or a physical HNSW index?
**Why:** It does neither. R2 received8/8responses but recovered the exact quote in4/8; its original one-source artifacts remain intact. Tiny collections may use a scan despite an ANN query request.
**Options:** Overstate the original pilot (rejected), or retain it and run a separately versioned final development calibration before owner freeze.
**Recommendation:** Add family-local retired, unapproved draft and restricted source fixtures to both predeclared folds. Bind every supplied document into split/corpus hashes. Current source gold remains unchanged; do not tune expected outcomes to observed answers. Record actual collection point/indexed-vector counts and pinned reranker manifest/fingerprint. Label physical-index absence and do not infer HNSW performance. B7 compares B6, vector augmentation compares B5; replay computes case-clustered paired cost differences from all attempts.
**What affects what:** p08_study.json, evaluation/study.py, core split guards, final development manifests and research report. No source-authority, release, serving default or new dependency change.
**My answer (editable):** Coordinator implementation detail under P08 and accepted ADR0071–75. Concrete evaluation targets and freeze still require owner review after final development observations.
**Verification:** R2 raw run p08_b13ffe65a8d7435a94a07d4f4a7049d4 preserves8calls/8responses,4exact quote recoveries and0wrapped SUPPORTED results. Rich-source calibration and physical index readback remain pending.

## ADR-0078 — Isolate canonical history across experimental observations

**Status:** ACCEPTED coordinator defect correction before evaluation,2026-10-19.
**Authority:** P08 paired ablations, scope isolation and fixed-input requirements.
**Question:** Are separate sessions sufficient to isolate repeated treatment observations?
**Why:** No: USER semantic preferences and canonical case history deliberately survive sessions. Reusing one case database could contaminate a later arm with another arm's generated history. Development B0/B1 did not persist runtime answers, but full runtime arms would.
**Options:** Rely on session changes (rejected), or clone the same source-only canonical snapshot for each observation before any runtime event.
**Recommendation:** SQLite backup to a new observation-owned database plus exact originals copy, preserving source IDs, approvals, generations and private ACL. Never rewrite the source snapshot. Seed the same prior preference event for B4–B8/vector, with B4 continuity disabled; B4's workload no longer omits the history that its paired B5 receives. Setup cloning stays outside measured request latency and is disclosed separately.
**What affects what:** evaluation/study.py only; canonical serving/session/memory contracts unchanged. No new dependency or source-authority store; unique derived observation resources remain retained.
**My answer (editable):** Coordinator correction within explicitly approved isolated P08 experiments.
**Verification:** Source trace confirms USER memory is cross-session; full evaluation has not begun. Actual clone/reopen/isolation guard and final measurement remain required.

## ADR-0079 — Owner-approved final pilot freeze and token ceiling

**Status:** ACCEPTED; explicit owner async answer,2026-10-19.
**Authority:** P08-T01.01 owner-approved final protocol; accepted ADR0071/74/75.
**Question:** May the concrete44observation protocol and conservative token ceiling be frozen after development?
**Why:** Development now records real generated answers, source-state competition, failures and calibrated mechanical targets. The160000estimated-token cap could prevent meaningful coverage of all11arms.
**Options:** Keep160000and record budget-limited observations, or raise only this ceiling to2000000while retaining200calls/7200seconds and request limits.
**Recommendation:** Freeze evidence/P08_PROTOCOL_FREEZE.md:2cases×11arms×2repetitions,20Btemperature0.2,seed1719,10secondspacing,no retry/fallback. Targets≥0.5exactquote recovery,1.0releasedcitationresolvability,0restrictedcanaryleakage and no budget overrun. Preserve all failure denominators; semantic accuracy/usefulness/causal conclusions remain unknown.
**What affects what:** Study config/guard, immutable machine protocol/calibration hashes, evaluator/report. No serving default, call count, request deadline or model change.
**My answer (editable):** Approve protocol and estimated-token ceiling (Recommended).
**Verification:** Owner approved before evaluation. Machine freeze and grid execution still require actual artifacts; approval is not evidence of targets passing.

## ADR-0080 — Explicit application assets for the installed evaluator

**Status:** ACCEPTED in-scope packaging defect correction,2026-10-19.
**Authority:** P08 entry-point/installed consumer proof; existing script-owned application root pattern.
**Question:** Can the installed study module infer the repository fixture folder from its package file location?
**Why:** A wheel lives under site-packages, so parents[3]/data is not the application fixture directory. The existing scripts already own the correct application root; moving evaluator logic into a package must preserve that consumer input.
**Options:** Rely on a source checkout location (rejected), or pass the script's existing application root into the study and its setup/observation owners.
**Recommendation:** Optional explicit app root on the evaluator, supplied by scripts/evaluate.py; helpers receive it for fixtures/config/cache/runtime. Preserve source defaults and existing study semantics. No global-path mutation or extra package copies. The currently executing grid uses its frozen source snapshot and unchanged correct source-root behavior; this repair affects installed path discovery, not its treatment/corpus/model.
**What affects what:** evaluation/study.py, scripts/evaluate.py and installed entry-point proof. No provider, serving, data schema or frozen fixture change.
**My answer (editable):** Coordinator owning-consumer repair under P08 and Rule5.
**Verification:** Source trace proves file-location inference differs between checkout and site-packages. Current installed CLI root/override guard passes; installed44row replay and HTTP smoke pass (E-P08-002).

## ADR-0081 — Preserve typed degradation for native search timeouts

**Status:** ACCEPTED small owning-layer defect correction,2026-10-20.
**Authority:** Existing DependencyUnavailable contract and P08 partial-outage/failure-accounting tasks; Rule5.
**Question:** Why does a real Qdrant HTTP408 bypass the existing dependency-unavailable handling?
**Why:** The frozen-critic continuation encountered a native408. The adapter normalizes transport exceptions and HTTP5xx, but lets HTTP408/429 escape as UnexpectedResponse, defeating existing typed degradation. This is distinct from fixing service slowness or retrying a failed call.
**Options:** Treat native timeout/throttle as unhandled errors (rejected), or normalize them in the existing Qdrant call owner while preserving validation/auth error behavior.
**Recommendation:** Map408/429 alongside5xx to existing DependencyUnavailable; preserve400/401/403 and no retries. Add native library response guards and actual search smoke. Do not rewrite graph queries: later graph failures also hit MERGE/cleanup, and VM pause evidence does not establish a query-code root cause.
**What affects what:** storage/qdrant.py and tests/test_retrieval.py; existing downstream typed unavailable handling is reused. No new response schema, dependency, default deadline, retry or authorization grant.
**My answer (editable):** Coordinator in-scope correction of promised timeout degradation, not a new contract or architecture.
**Verification:** Real408 traceback retained runtime/p08-frozen-critic-r1.log. Native408/429/503 versus400/403 mapping group17PASS; final source/wheel/HTTP controls pass (E-P08-002). Original grid is complete and remains bound to its unchanged source snapshot.

## ADR-0082 — Retain known usage within partially failed observations

**Status:** ACCEPTED in-scope scoring defect correction,2026-10-20.
**Authority:** P08 all-attempt cost accounting and unknown-is-not-zero rule.
**Question:** Should a later failed call erase earlier known token usage from the same observation's arm total?
**Why:** Raw calls retain every received usage, but the row-level aggregate is empty when any invocation lacks usage. The first arm scorer consequently undercounts known partial usage even though the global attempt reader is correct.
**Options:** Use only complete-row usage (rejected), or join immutable attempt usage by each row's recorded call numbers during replay.
**Recommendation:** Preserve raw rows unchanged. Enrich scorer inputs with per-attempt usage from the bound call artifact; sum all known received tokens while reporting missing attempts and incomplete runs separately. Public mechanical receipt carries those same usage inputs and must reproduce raw-replay metrics exactly. No failed usage is assigned zero or inferred billing.
**What affects what:** core/evaluation.py, evaluation/study.py replay, scorer guard and derived report export only; no provider calls, frozen treatment, runtime output or original artifact mutation.
**My answer (editable):** Coordinator correction of the owning report reader under existing accounting requirements.
**Verification:** Raw91attempts preserve54750knownreceivedtokens; mixed successful/unknown scorer group18PASS. Raw replay and bounded public receipt metrics match; known arm totals equal54750 (E-P08-002).

## ADR-0083 — Propagate vector candidate-window incompleteness

**Status:** ACCEPTED correction to the new opt-in P08 consumer,2026-10-20.
**Authority:** Approved ADR0072 bounded vector augmentation and existing recall coverage semantics.
**Question:** Does the recall handler disclose truncation in both its baseline and vector candidate windows?
**Why:** VectorMemory records its512candidate truncation flag, but the handler currently reports only the structured/FTS reader's flag. The existing exhaustive=false remains truthful, yet the specific incompleteness field can be wrong.
**Options:** Leave the producer flag unread (rejected), or combine it with baseline incompleteness only when vector recall actually runs.
**Recommendation:** OR the current vector last_truncated into the existing recall coverage flag. Exact-ID/no-query/default paths do not inherit stale vector flags. Use an actual513derived-row guard with canonical denial and the real tool consumer.
**What affects what:** agent/tools.py optional vector branch and tests/test_memory.py; no new tool, field, default or authority change.
**My answer (editable):** Coordinator local producer-to-reader correction inside the approved new experiment.
**Verification:** Actual513derived-row window → canonical denial → real recall handler guard1PASS39.29s; no-query/default branch does not inherit stale flags. Final source/wheel controls pass (E-P08-002).


## ADR-0084 — Explicit alternate model for a separate continuity control

**Status:** ACCEPTED in-scope model selection under owner-approved ADR0036,2026-10-20.
**Authority:** Owner authorizes Groq Qwen/120B/20B selection with explicit recording, no hidden fallback.
**Question:** Which approved model should execute the fresh, separate continuity control after the20B frozen critic run?
**Why:** Actual20B response headers report daily token quota199674/200000 and HTTP429. The frozen grid and in-progress critic observations must retain their selected model and failures.
**Options:** Attempt another20B control under near-exhausted daily quota, or explicitly select the already-approved120B for a separate versioned continuity pilot.
**Recommendation:** Finish recording the20B critic conditions unchanged, then execute one explicitly enabled memory pilot using Groq openai/gpt-oss-120b with10secondspacing and existing request/call limits. No failed call retry, cross-model pooled metric or replacement of the frozen grid.
**What affects what:** Only the next explicit scripts/evaluate.py --memory command and its separate run manifest/report; no source, dependency, serving default or frozen treatment change.
**My answer (editable):** Coordinator selects an already owner-approved model for this distinct control, not hidden fallback.
**Verification:** Live20B quota diagnostic preserved in p06-57815987982f4322997fc434305ebe83.json. Separate120B run p05-b55c4c1197d646f299746de55263886f completed all3conditions,32859known tokens; failures/omission retained, not pooled with20B (E-P08-002).


## ADR-0085 — Correct legacy continuity report after mandatory critic integration

**Status:** ACCEPTED owning report defect correction,2026-10-20.
**Authority:** Rule5 comment/report behavior mismatch; P08 per-attempt accounting.
**Question:** Does the existing memory pilot still run without a critic as its report says?
**Why:** run_memory constructs the current default AgentRuntime through configure_agent. Since P06 that runtime always invokes independent review; the old report's critic=false is stale. Received-usage lists alone also omit failed attempts.
**Options:** Disable the mandatory reviewer to match an old label (rejected), or report the actual constant reviewer and persist redacted per-attempt records.
**Recommendation:** Label critic=true/held constant across continuity arms; retain initial and per-condition role/stage/status/attempt/usage/error_code records from the canonical attempt events. Do not alter runtime, source fixtures, model budget or continuity comparison.
**What affects what:** scripts/evaluate.py run_memory report only. Earlier reports remain unchanged; frozen P08 grid and active critic source snapshot remain immutable.
**My answer (editable):** Coordinator corrects the actual report producer before its fresh consumer proof.
**Verification:** Live source trace run_memory → configure_agent → AgentRuntime default review; Installed120B pilot completed all3conditions and records22startedcalls/failed/schema/cancelled attempts, with critic=true/heldconstant; exact script hash matches retained snapshot (E-P08-002).


## ADR-0086 — Withdraw unobserved retrieval cutoffs after top-four truncation

**Status:** ACCEPTED owning measurement defect correction,2026-10-20.
**Authority:** End-review R4; P08 unknown-is-not-zero/retained-failure rules and approved pilot boundary ADR0071/0079.
**Question:** Can the final top-four model packet measure candidate Recall@5/10/20 and full-ranking MRR?
**Why:** _observe scores only HybridSearch result.passages after limit4, while score_ranked_references defaults to5/10/20. These labels cannot observe ranks5–20 and are not valid candidate-stage measurements. The frozen raw run retained this defect; no higher-stage quality claim is supported.
**Options:** Rerun a new separately frozen experiment with full-stage capture for new claims, or withdraw the invalid higher-cutoff labels now and expose only actually observed packet metrics.
**Recommendation:** Preserve frozen inputs/source/rows/calls/completion unchanged. Future evaluator scoring names final-packet @4/packet-MRR and leaves unobserved candidate/stage @5/10/20/full-MRR unknown. Replay/report explicitly withdraw legacy top-four scores mislabeled as larger cutoffs. No new metric values are inferred from missing ranks, no source/model/treatment tuning or provider rerun. Higher-stage performance remains unmeasured.
**What affects what:** core/evaluation.py bounded packet scorer, evaluation/study.py scorer/replay notice, tests and derived reports only. Serving result cap and frozen44observations stay unchanged; no schema/dependency/API contract change.
**My answer (editable):** Coordinator corrects a newly authored report producer/reader; this withdraws an invalid claim rather than inventing missing evidence or narrowing a required metric.
**Verification:** Reviewer traced limit4 → default5/10/20. Final20installed guards distinguish rank5/rank10 from top4 and prove the canonical evaluator keeps exactly4model evidence IDs. Installed44row replay and65/65wheel byte proof pass; same LunaMedium reviewer confirms R4 resolved. No fresh candidate-quality result claimed (E-P08-003).


P08 final verification index2026-10-20: approved ADR0071–0079 directions executed in
versioned calibration/freeze/grid artifacts; ADR0080–0085 owning fixes have actual
source/installed/consumer evidence at E-P08-002. ADR0086 metric withdrawal and sole
reviewer resolution verified at E-P08-003. Acceptance never means positive hypothesis
or availability of missing stage/semantic measurements. Initial pending verification
statements in dated entries describe their decision-time state; this index records
completed engineering proof and retained research limits.

## ADR-0087 — Scoped retrieval handoff contracts (PF01–PF04)

**Status:** ACCEPTED by owner, 2026-10-20; verification pending.
**Authority:** Owner requests Part B handoff fixes; Rule4 requires concrete contract approval.
**Question:** May search expose historical document cutoffs, approval-owned identifiers, batched physical coverage and optional larger/token-budgeted HTTP results?
**Why:** HTTP loses existing core as_of; normal uploads lack aliases; coverage stops at100 sources and performs one backend read per source; callers cannot request a measured evidence budget.
**Options:** Keep current limits; add scoped optional contracts; or weaken canonical checks (rejected).
**Recommendation:** Optional timezone-aware document as_of with matching citation readback, preserving current approval/ACL/revocation checks. Approval owner registers bounded family/revision/identifier aliases. Reconcile coverage in bounded physical batches with explicit truncation/outage status. HTTP default12/max40, tool max12 unchanged. Optional whole-passage budget uses the pinned retrieval tokenizer with truncation disabled, exposes identity/count and preserves exact source spans; declare already-installed tokenizers0.23.3 as direct dependency if used. No provider-token/billing equivalence, schema migration or default tokenizer work.
**What affects what:** api/schemas.py, api/routes.py, storage/catalog.py, storage/exact.py, storage/qdrant.py, retrieval/coverage.py, retrieval/hybrid.py, retrieval/embeddings.py, ingestion approval consumer, pyproject.toml/uv.lock and owning API/ingest/retrieval tests. Four tools and trusted policy event-time selection unchanged.
**My answer (editable):** Owner explicitly approved the recommendation, 2026-10-20.
**Verification:** Before closure: HTTP historical/current/naive/revocation controls, upload→approve→exact-search→citation proof, physical missing/hash/outage/truncation controls beyond100sources, measured batch comparison, default/40/budget/tokenizer/span controls. Not verified yet.

## ADR-0088 — Admin-owned synthetic provisioning (PF05)

**Status:** ACCEPTED by owner, 2026-10-20; verification pending.
**Authority:** Rule4 new authorization and API contracts.
**Question:** May existing tenant admins create non-admin principals, cases and case memberships through authenticated APIs?
**Why:** Trusted seed helpers are not a public provisioning contract; benchmark needs isolated nonprivileged actors without direct SQLite mutation.
**Options:** Continue operator-only fixture provisioning; add bounded scoped admin operations; expose bootstrap helpers directly (rejected).
**Recommendation:** Existing current tenant admins only, current authorization rechecked in the write transaction. New principals non-admin, grants allowlisted and bounded by issuer grants. Case membership writes require current admin membership in the case. No tenant creation, bearer-token minting or role escalation. Existing conflicting identity returns409; idempotent repeats never restore revoked grants/memberships. Original source ACL remains independently required.
**What affects what:** storage/registry.py, api/schemas.py, api/routes.py and authorization/API tests; existing storage tables, no migration or credential dispatch.
**My answer (editable):** Owner explicitly approved the recommendation, 2026-10-20.
**Verification:** Positive scoped creation and reopen/readback; cross-tenant/non-admin/stale actor/overgrant/collision/revocation-negative controls; no token values in response/audit. Not verified yet.

## ADR-0089 — Preserve serving invariants in ablation handoff (PF06)

**Status:** ACCEPTED by owner, 2026-10-20; verification pending.
**Authority:** Blueprint locked decisions, four tools and deterministic canonical authority.
**Question:** Should PF06 expose only safe existing evaluator controls, rather than serving flags that remove integrity boundaries?
**Why:** The handoff predates the implemented critic. B4/B5 already omit critic in isolated experiments but retain the final gate. Generic switches disabling gate/parser/source/time/preflight would contradict the vision.
**Options:** Document supported isolated controls and explicit unsupported ablations; or separately design a raw non-serving research harness after further approval.
**Recommendation:** First option. Publish capability matrix and configuration/status evidence for actual evaluator switches; no general serving bypasses. Mark unsupported dangerous ablations FEATURE_NOT_SUPPORTED, never pretend they ran. Main/critic/model/attempt accounting remains explicit.
**What affects what:** agent/experiments.py, evaluation/study.py, evaluator tests and Palladion documentation. No benchmark edits, new tool or serving default change.
**My answer (editable):** Owner explicitly approved the recommendation, 2026-10-20.
**Verification:** Default gate/authority/preflight behavior unchanged, supported controls consumed by actual isolated runner, unsupported controls explicitly rejected. Not verified yet.

## ADR-0090 — Correct gate and evaluation proof gaps from independent reaudit

**Status:** ACCEPTED owning defect corrections, 2026-10-20; implementation/proof pending.
**Authority:** Existing mandatory critic, hard deadline, reproducibility and honest-measurement contracts; Rule5.
**Question:** Can existing guarantees be marked complete with missing conjunction tests, a constant completeness flag and call-only deadline checks?
**Why:** Five-agent reaudit identified a normative requirement bypass, whole-run deadline gap, missing consumed configuration snapshot and incomplete T01/T12 consumer proof.
**Options:** Preserve historical artifacts while fixing owning producers/readers and adding defining controls; or overclaim from the old green suite (rejected).
**Recommendation:** Requirements remain visible canonical facts, but absent/stale/unavailable critic forces qualified release. Add whole-lifecycle cancellation/accounting and exact consumed configuration binding for future studies. Keep frozen artifacts unchanged with explicit legacy limitations. Add old-SOP/current-policy/final-gate and final completeness-canary controls. Withdraw semantic completeness inference from inventory_attested=false; semantic accuracy stays unknown.
**What affects what:** agent/gate.py, evaluation/study.py, core/evaluation.py, evaluation runner, test_gate.py/test_evaluation.py/test_end_to_end.py, p08_integrity_controls.json and derived public evidence/docs. No new model call or source authority.
**My answer (editable):** Coordinator fixes violations of existing documented promises; any necessary new shipped interaction contract is escalated before implementation.
**Verification:** Baseline362PASS/28SKIP does not cover these conjunctions. Defining negative controls must fail before fixes and pass after; valid reviewed policy and scoped uncertainty stay valid. Pending.

P09 implementation detail for ADR0090: evaluation/process_owner.py owns a Windows
kill-on-close Job Object (POSIX private process group on other systems). A start event
prevents the study worker spawning descendants before assignment. Parent closes the
owned tree and joins on deadline/interruption; STARTED rows without FINISHED remain
unknown in a separate termination.json, not fabricated provider responses. Windows
nested-child termination and successful-worker positive controls pass. New study readers
consume copied bound_inputs config/fixtures; source_snapshot retains their exactUTF8bytes
and hashes. No credentials enter that snapshot, no raw legacy artifact is rewritten.

## ADR-0091 — Report measured coverage scaling without hiding physical drift

**Status:** OWNER REJECTS CLOSURE, 2026-10-20; further performance work authorized.
**Authority:** PF03 proof target and Rule4 prohibition on silently narrowing acceptance.
**Question:** May PF03 close with measured bounded linear reconciliation, retaining its unmet small-multiple scaling target as a disclosed limitation?
**Why:** Current real local Qdrant measurements:10sources single0.160861s/10requests versus batch0.0130005s/1request;1000sources single10.511018s/1000requests versus batch0.556804s/16requests. Full physical coverage passes without truncation/degradation. Batch1000 is18.9times faster than single1000, but42.8times batch10, so the proposed small-multiple scaling target is not met. One observation per condition with other local work running is not a latency distribution or capacity result.
**Options:** Accept this measured linear-cost contract now; or design further freshness/caching/async reconciliation semantics and their stale-drift risks before PF03 closure.
**Recommendation:** Accept bounded linear verification with explicit measurements and retained limitation. Avoid inventing constant-cost coverage, disabling integrity checks or claiming the original latency target passed. Further architecture needs a separate approved task.
**What affects what:** PF03 handoff status, P09-T02.03 acceptance/evidence and performance claims only; current authorized batch implementation, physical drift checks and defaults unchanged.
**My answer (editable):** Owner: keep PF03 open, explore faster processing, including lossless gzip or other evidenced options. Original closure proposal rejected; do not waive the target.
**Verification:** runtime/p09-coverage-measure.json and full log; synthetic deterministic3D encoder, real Qdrant transport, identical canonical sources, fresh UUID collection removed in finally. Await owner disposition; no target silently waived.

## ADR-0092 — Close the provisioning identity-existence oracle

**Status:** ACCEPTED by explicit owner answer, 2026-10-20; implementation/proof pending.
**Authority:** P09 reviewer confirms cross-tenant identifier existence disclosure; Rule4 identity/API contract.
**Question:** May PF05 treat the submitted principal_id as a tenant-local subject key and return a deterministic tenant-bound opaque canonical principal_id?
**Why:** The approved prototype accepts globally keyed caller IDs. A tenant admin distinguishes another tenant's existing ID (409) from an unused ID (successful create). The error body cannot remove that oracle; this reveals identifier existence, not target data or grants.
**Options:** Accept that limited synthetic-pilot disclosure; or derive a new non-admin canonical ID from SHA256(tenant_id plus unambiguous delimiter plus submitted local key), returning it for memberships/source ACLs/operator token mapping. Existing bootstrap IDs and authentication stay unchanged.
**Recommendation:** Derive tenant-bound opaque IDs. The same tenant/key remains idempotent, another tenant gets a different ID, and callers use the returned canonical ID for subsequent operations. Preserve grant/role/issuer/current-case/revocation controls and conflicting same-subject grant-request409. No schema migration, stored alias map, token minting or admin creation.
**What affects what:** New PF05 provision_principal request semantics/returned ID, registry handler, API/provisioning/ACL tests and documentation; existing principal IDs, readers and bearer mapping contract unchanged.
**My answer (editable):** Owner approves tenant-bound opaque IDs, 2026-10-20.
**Verification:** Reviewer traced global get_principal to409 versus creation200. Add same-local-key/different-tenant separation, existing foreign-ID string as local key, returned-ID memberships/ACL and revocation/idempotence controls. Do not claim fixed before approval and execution.

P09 owning correction under ADR0087: newly automatic family aliases expose the existing
unbounded exact-discovery reader at scale. Keep direct Catalog.lookup_alias compatibility,
but give the search lane an explicit100candidate window plus sentinel, current ACL before
cut and EXACT_CANDIDATES_TRUNCATED disclosure. This reuses the existing100candidate
investigation boundary rather than claiming exhaustive discovery. Canonical source/time
resolution remains mandatory. Defining101alias and authorized-after-private controls
are required before closure; no unknown-code fuzzy substitution.

## ADR-0093 — Recheck exact-alias write authority inside its transaction

**Status:** ACCEPTED owning authorization-race correction, 2026-10-20.
**Authority:** Existing current-admin document:approve alias contract; Rule5 in-scope defect.
**Question:** Can alias insertion use an authorization check completed before its write transaction starts?
**Why:** Catalog.add_alias previously checked source/approval/role/grants before BEGIN; revocation between that check and the write could persist a discovery alias under stale authority. Canonical readers still prevent source-content disclosure, but the metadata writer violates its current-authority promise.
**Options:** Keep the race (rejected); move existing checks into the owning SQLite transaction.
**Recommendation:** Recheck current actor, case, source approval/ACL and chunk existence within the write transaction. Automatic registration validates all bounded alias plans before its first write, so a later deterministic chunk/identifier bound cannot leave a partial alias set. Transient write failures remain idempotently retryable.
**What affects what:** storage/catalog.py add_alias, storage/exact.py approval planner and focused test_pipeline guard. No new authorization rule, API/default/schema/dependency or authority bypass.
**My answer (editable):** Coordinator corrects existing promised current authorization at its owning writer.
**Verification:** Add a deterministic revocation at transaction entry; prior writer must insert incorrectly, corrected writer must deny with zero alias rows; valid approval/readback continues to pass. Pending.


## ADR-0094 — Remove repeated canonical coverage authorization queries

**Status:** ACCEPTED bounded owning optimization, 2026-10-20; target still open.
**Authority:** Owner request to keep PF03 open and explore faster lossless processing; approved bounded batching ADR0087.
**Question:** Which measured cost can be reduced while retaining physical drift detection and current canonical authorization?
**Why:** Profiled1000-source REST identity/gzip samples execute7006 SQLite statements. Gzip reduces wire bytes from5438862 to1698216, but does not eliminate per-source manifest authorization queries. Three-repeat REST/gRPC medians1000 are0.6165/0.5763s, insufficient evidence for changing transport defaults.
**Options:** Batch existing canonical manifest reads; change transport; add stale caches or omit physical vectors (not authorized).
**Recommendation:** Batch canonical manifests in their Catalog owner, with current principal/case/source ACL revalidation after physical readback and exact generation matching. Use existing short SQLite transaction and bounded64-source SQL batches; no network under the transaction. Keep physical batch/page bounds, compression negotiation and serving defaults unchanged. Measure paired10/1000 sources before judging the unchanged target.
**What affects what:** Catalog and source_coverage internal reader, focused SQL-count/drift/revocation tests, P09-T02.05 and retained measurement evidence. No schema, dependency, public API, permission rule, transport setting or cache.
**My answer (editable):** Coordinator implements an internal optimization of the approved batch reader; any new architecture or acceptance change still needs owner direction.
**Verification:** Pending defining controls and repeated real-Qdrant measurements. PF03 stays open until its original performance obligation is resolved.


## ADR-0095 — Optional bounded physical-audit reuse, pending owner direction

**Status:** ACCEPTED by owner, 2026-10-20; implementation and benefit proof pending.
**Authority:** Rule4 interaction/freshness contract; owner rejected ADR0091 closure.
**Question:** May an explicitly opted-in mode reuse a physical audit for up to5seconds while strict fresh readback remains default?
**Why:** Lossless gzip already operates by default. SQL batching removes repeated authorization queries but full vector transfer/validation still scales with physical contents. Larger batches and gRPC do not prove the original small-multiple target.
**Options:** Keep strict fresh validation and PF03 open; or approve bounded explicitly enabled reuse with a disclosed5second physical-corruption detection window.
**Recommendation:** Preserve strict default. If reuse is chosen, first specify bounded derived storage, exact tenant/case/generation/representation/canonical-manifest keys, current per-request ACL/approval/validity checks, expiry/invalidation and visible physical verification timestamps/cache status. Benchmark must name the opted-in mode. No cache implementation or target success follows from this proposal alone.
**What affects what:** Potential coverage reader and response metadata, derived storage lifecycle, concurrent readers and benchmark interpretation; no source or gate authority bypass. Exact implementation cards/proof must precede dependent work after approval.
**My answer (editable):** Owner: do the5second audit cache, but if it worsens things leave PF03 open. Explicit approval received before implementation.
**Verification:** Future implementation must prove cache hit/expiry/changed generation/revocation/corruption window/bounds and consumer disclosure, then repeated paired scale measurements. Current PF03 remains open.


ADR0095 concrete implementation contract: HTTP reuse_physical_audit defaultsfalse;
HybridSearch and source_coverage pass the explicit flag; four domain tools have no
cache flag. Separate .coverage-cache.sqlite sidecar contains only SHA256keys and
wall/monotonic timestamps, at most32records and1MiB database (SQLite journal separately
bounded by database size). Key binds tenant/principal/case/backend endpoint/collection/
representation plus exact current canonical manifests. Current canonical checks run
before lookup and after physical/cache read; mismatch fails healthy coverage. Only
complete healthy physical audits finishing within5seconds of their start are reused;
hits never extend expiry. Both wall and monotonic ages must be0..5seconds. Busy,
malformed, oversized or unsupported caches fall back to fresh validation with visible
UNAVAILABLE. Responses expose physical_audit_mode, physical_verified_at and cache status.
No source text/vectors/secrets stored; no registry migration. Canonical/physical aggregate
100000chunk bounds apply. Timing improvement must be measured, not presumed.


P09 verification update (E-P09-003/004): ADR0087/0088/0089 approved mechanisms and
ADR0090/0092/0093 owning corrections have current source and isolated installed/HTTP
proof. ADR0094 SQL count improvement is measured, elapsed improvement not established.
ADR0095 bounded opt-in cache guards and actual HTTP/real-Qdrant consumer proof pass;
large-case benefit and small-case overhead are both retained. ADR0091 original PF03
acceptance remains OPEN in P09-T02.07, with no owner waiver. These dated updates
supersede earlier pending verification prose without deleting the original chronology.
