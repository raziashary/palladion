# Architecture and development decision log

Updated 2026-10-17. This is the canonical owner-answer record. All twelve Q01–Q12
recommendation directions are accepted by the user's current instruction, with the
explicit override: real Groq `qwen/qwen3.8-27b` instead of a fake-first runtime. Technical
verification, measured values and deferred work remain unexecuted; approval is not proof.

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

**Authority:** Direct user instruction: every development subagent GPT 6 Luna High.

**Question:** Which models may development subagents use?

**Why:** Preserve the source-grounded scope and trust boundaries in the original record;
its rationale and evidence are retained below rather than replaced by a new claim.

**Options:** Retain the accepted direction or explicitly amend it; the historical record
preserves alternatives considered. Current amendments: ADR-0011 governs GO, ADR format and phase reviews; ADR-0013 governs uv/Groq. Apply them over conflicting historical wording.

**Recommendation:** Use GPT 6 Luna High for every development subagent; this is separate from Groq runtime generation.

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

**Recommendation:** Use this editable structure; before each phase one GPT 6 Luna High adversary refutes tasks against source/vision; after validation/smoke/gates one GPT 6 Luna High work auditor audits evidence and consumers. Coordinator resolves findings. For this task both coordinator and that auditor inspect every development doc against the entire blueprint.

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

**Verification:** PLANNED; G-SOURCE/G-SECURITY must reject self-approval and unauthorized approvers.

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
the app .venv and E-DOC-004 verifies existence/ignore protection. Pins/locked sync remain
P01 proof. Deterministic fixtures do not substitute for real-model integration.

## ADR-0014 — Q03 — Qdrant hybrid compatibility

**Status:** ACCEPTED; authority: user instruction 2026-10-17.

**Authority:** Current user instruction accepts all open-question recommendation directions; ADR-0013 records the explicit uv/Groq exception and package delegation.

**Question:** How are native RRF and sparse BM25 made reproducible?

**Why:** Illustrative SDK shapes and vendor defaults cannot establish installed behavior.

**Options:** One compatible pinned native fusion; controlled alternative only as an explicit later experiment.

**Recommendation:** Probe official pinned server/client APIs, use same-point dense/bm25 representations, match ingest/query BM25 mode and tokenizer, and run one native RRF stage with k=60. Select a supported mode at that compatibility task.

**What affects what:** Planned storage/qdrant.py, retrieval/hybrid.py, manifests and benchmark reader; version/mode selection is delegated technical work, not verified now.

**My answer (editable):** Accept the recommendation direction; do not invent a compatibility result.

**Verification:** VERIFY_AT_IMPLEMENTATION; G-RETRIEVAL integration probe must pass before dependent indexing.

## ADR-0015 — Q04 — English and Indonesian retrieval

**Status:** ACCEPTED; authority: user instruction 2026-10-17.

**Authority:** Current user instruction accepts all open-question recommendation directions; ADR-0013 records the explicit uv/Groq exception and package delegation.

**Question:** How should language processing and corpus mix be selected?

**Why:** English-oriented defaults may miss Indonesian clauses; an aggregate can conceal those failures.

**Options:** Unexamined defaults or recorded language variants tested on development labels.

**Recommendation:** Record corpus language distribution, compare stemming/tokenization variants on development data and pin the selected representation; report each language slice.

**What affects what:** Planned chunk/index manifests, retrieval tests and evaluator; gold/held-out split remains independent of tuning.

**My answer (editable):** Accept the recommendation; select details from measured development evidence rather than a claimed language improvement.

**Verification:** VERIFY_AT_IMPLEMENTATION; no selected tokenizer variant or recall measurement yet.

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

Next free ADR number: 0024. Accepted directions do not grant implementation GO.
