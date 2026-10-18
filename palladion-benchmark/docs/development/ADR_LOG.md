# Benchmark architecture and development decision log

Updated 2026-10-18. This is the canonical owner-answer record for the benchmark. Palladion's own
decision log is separate and is not edited from here. Records marked ACCEPTED rest on an explicit
owner instruction in the 2026-10-18 session or on a coordinator decision inside task scope, and
say which. Records marked PROPOSED are recommendations the owner has not answered; they grant
nothing, and work that depends on them is blocked or proceeds at stated risk.
Acceptance is never proof of behavior.

## How to read and edit decisions

Read Status and Authority, then Question, Why, Options, Recommendation, What affects what,
**My answer (editable)** and Verification. The owner may edit the answer directly. An answer
that begins with OPEN means unanswered. When an answer changes, preserve the previous answer and
date as an amendment line beneath it; do not erase history or silently narrow it.
Statuses: ACCEPTED, PROPOSED, SUPERSEDED, REJECTED. Verification names the evidence that would
show the decision working, and is kept separate from acceptance.

## BADR-0001 — Benchmark location and repository layout

**Status:** ACCEPTED; 2026-10-18.

**Authority:** Owner answer in chat, 2026-10-18: keep the benchmark in this repository as its own uv project.

**Question:** Where does the benchmark code and its development suite live relative to Palladion?

**Why:** The research protocol describes a separate repository, but the owner placed the protocol under `palladion-benchmark/` in the Palladion checkout and wants to push to `main` here.

**Options:** (a) Sibling folder `palladion-benchmark/` in this repository with its own `pyproject.toml`, `uv.lock` and `.venv`; (b) a new standalone git repository now.

**Recommendation:** Option (a), designed so the folder can be extracted into its own repository later without code changes (no imports across the boundary, no shared paths).

**What affects what:** All file paths in the master plan; the shared git checkout hygiene rules (BADR-0004); the isolation rule (BADR-0002); root navigation, which this suite does not edit.

**My answer (editable):** In this repo, own uv project (2026-10-18). Root `README.md` and `AGENTS.md` are not edited by benchmark work because the Palladion contributor has uncommitted changes in them.

**Verification:** Directory inspection and BG-DOC; extractability is checked in B08-T07.01 by confirming no benchmark path refers outside `palladion-benchmark/` except documented links. The documentation checker locates the repository root by a fixed path depth and its constants would need one edit after extraction.

## BADR-0002 — Independence from the system under test

**Status:** ACCEPTED; 2026-10-18.

**Authority:** Owner instruction 2026-10-18 (develop the benchmark, not Palladion) and protocol §7.1 and §7.3.

**Question:** How does the benchmark reach Palladion without contaminating the experiment or colliding with the other contributor?

**Why:** The evaluator alone may see gold; a harness importing the agent could leak labels or couple to internals that change daily.

**Options:** (a) Adapter over Palladion's HTTP interface, no code import, evaluator-only gold in a separate namespace; (b) import Palladion modules directly; (c) copy Palladion code into the benchmark.

**Recommendation:** Option (a). `palladion/` is read-only for this work: read its live source and documentation to learn the interface, never edit it, never stage its files.

**What affects what:** B04-T03.01, B06-T04.01, B07-T04.01; BG-ADAPTER and BG-SECURITY static import check; risk BR01.

**My answer (editable):** Accepted as stated; Palladion is developed by another contributor and changes concurrently. Amendment 2026-10-18 (OQ11): E3, E4 and critic-dependent ablations stay FEATURE_NOT_SUPPORTED until Palladion documents a critic-off switch and a real critic; the benchmark never edits Palladion to obtain one.

**Verification:** A static scan in the adapter tests finds no import of the Palladion package; run artifacts contain no gold fields (BG-ADAPTER, BG-TRACKA).

## BADR-0003 — Subagent policy and model

**Status:** ACCEPTED; 2026-10-18.

**Authority:** Owner instruction 2026-10-18: spawn subagents only as needed and use only Haiku 5.5.

**Question:** When may subagents be used and which model do they run?

**Why:** The owner's global rules limit delegation and name another model for the Palladion project. For this benchmark the owner gave a different, explicit model instruction.

**Options:** (a) Haiku 5.5 only, read-only reviewers at phase start and end; (b) the global default model; (c) broader delegation.

**Recommendation:** Option (a). Do not substitute a different model silently; if Haiku 5.5 is unavailable, report that and ask. Reviewers read the complete protocol, get no credentials, and make no git or external changes. The coordinator does research, implementation and tests.

**What affects what:** MASTER_DEV_PLAN delegation section; AGENTS; B00-T04.01 and every later phase review.

**My answer (editable):** Haiku 5.5 only, only when needed (2026-10-18). This overrides the Luna Medium rule for this folder only.

**Verification:** Each review receipt in EVIDENCE_LOG records the model requested; whether the harness honored it is stated as observed, not assumed.

## BADR-0004 — Version control in a shared checkout

**Status:** ACCEPTED; 2026-10-18.

**Authority:** Owner instruction 2026-10-18: pushing to `main` is permitted for this work.

**Question:** How are commits and pushes made while another contributor has uncommitted changes in the same working tree?

**Why:** `git add -A` or an unscoped commit would capture Palladion edits; a push publishes every commit that is ahead of `origin/main`, including ones that are not mine.

**Options:** (a) Path-scoped staging and commits under `palladion-benchmark/`, check `git diff --cached --name-only` and `git log origin/main..HEAD` before pushing; (b) a separate worktree on a branch; (c) wait for the other contributor.

**Recommendation:** Option (a). Never force-push, rewrite published history, tag, or touch git config. If a push is rejected, fetch, report the divergence and ask. If commits that are not mine are ahead of origin, ask before pushing.

**What affects what:** B00-T04.02 and every closeout; AGENTS git section; risk BR02.

**My answer (editable):** Push to main is allowed (2026-10-18). Scope and checks are as recommended.

**Verification:** The commit file list contains only `palladion-benchmark/` paths; the ahead list contains only benchmark commits at push time (recorded in EVIDENCE_LOG).

## BADR-0005 — Python tooling and dependency policy

**Status:** ACCEPTED; 2026-10-18.

**Authority:** Owner instruction 2026-10-18: libraries may be added; use `uv init` and a staged uv environment.

**Question:** How is the Python project created and how are dependencies introduced?

**Why:** The protocol asks for Python 3.11+ with comparators isolated because their requirements differ.

**Options:** (a) uv project with a dev group (pytest, ruff, mypy) now and runtime dependencies added per task; (b) install the full stack up front.

**Recommendation:** Option (a). Each added dependency is recorded (name, purpose, owning task) in the card's evidence. Comparators (HippoRAG, GraphRAG, LightRAG) live in separate pinned environments, subprocesses or containers rather than the harness environment. `requires-python` follows the Palladion pin range so both can share the machine's interpreter.

**What affects what:** pyproject, uv.lock, B01-T01.01 onward; BG-REPRO; risk BR06.

**My answer (editable):** Libraries may be added; use uv init and a staged venv (2026-10-18).

**Verification:** `uv sync --locked` from a clean clone (B01-T01.01); the lockfile is committed.

## BADR-0006 — Phase decomposition B00–B09

**Status:** ACCEPTED; 2026-10-18.

**Authority:** Owner answer in chat, 2026-10-18: approve the B00–B09 breakdown as written, including M-tier generation in B08.

**Question:** Are the ten phases and their order the intended work breakdown?

**Why:** The protocol gives six logical slices and three stages but no task decomposition.

**Options:** (a) The B00–B09 breakdown in the master plan; (b) fewer, coarser phases; (c) follow the protocol slices exactly.

**Recommendation:** Option (a), with one flagged deviation: the protocol generates the 12k corpus before the locked test, while this plan generates it in B08 after all arms exist and pilots on the S tier. It splits slice 1 into harness and fixtures, and slice 2 into evaluation core, retrieval arms and answer-level evaluation, so each phase has one reviewable gate set.

**What affects what:** MASTER_DEV_PLAN, GOAL, PROGRESS phase tables.

**My answer (editable):** Approved as written (2026-10-18).

**Verification:** Owner reads the plan; every protocol section maps to at least one task (BG-DOC traceability check).

## BADR-0007 — Generator model pool

**Status:** ACCEPTED; 2026-10-18.

**Authority:** Owner answer in chat, 2026-10-18: work around Groq `qwen/qwen3.8-27b`, `openai/gpt-oss-120b` and `openai/gpt-oss-20b` because of free-tier rate limits.

**Question:** Which generator model serves Tracks B and C?

**Why:** The protocol requires a fixed shared generator with exact model revision recorded, but the free tier throttles any single model.

**Options:** (a) A pool of the three named models with qwen as primary; (b) one model only; (c) a paid provider.

**Recommendation:** Option (a), with BADR-0008 controlling how failover interacts with paired comparisons. The model identity is a recorded experimental factor, not a hidden implementation detail. gpt-oss-20b is a weaker model, so its use must be visible in every result.

**What affects what:** B01-T05.01, B01-T05.02, B05-T05.01, B07, B09-T02.01; protocol §3.1 item 3 and §14.4; risk BR04.

**My answer (editable):** Use qwen 3.8 27B, gpt-oss-120B or gpt-oss-20B, switching when a rate limit is hit (2026-10-18).

**Verification:** Every generation record carries its model id, attempt and token counts (BG-HARNESS); real calls to each model recorded in B01-T05.02.

## BADR-0008 — Failover and pairing policy for the generator pool

**Status:** ACCEPTED; 2026-10-18.

**Authority:** Owner answer in chat, 2026-10-18, accepting the coordinator's recommendation (derived from protocol §3.1 and §14.2).

**Question:** When a rate limit forces a model switch, how do we keep paired arm comparisons valid?

**Why:** A paired comparison between two retrievers is confounded if one ran on qwen and the other on gpt-oss-20b.

**Options:** (a) Pause and resume on the same model; fall back only for a whole generator-homogeneous block and report results per model; (b) switch per call and treat the model as a covariate; (c) pick one model per question across all arms.

**Recommendation:** Option (c) layered on (a): for each question, every arm uses the same model, chosen once per question by a rule fixed and recorded before any arm runs (not after a rate limit is observed). Do not exclude mixed-model pairs from the primary analysis: rate limits track an arm's token volume, so exclusion would be informative censoring that conflicts with protocol §14.6. If a mixed pair still occurs, keep it in the intention-to-treat analysis, treat the model as a stratum, and report the mixed fraction. Apply the same rule to Track C. Confirmatory sealing (B08-T03.01) must fix it. Revised after the Haiku review (E-B00-003).

**What affects what:** B01-T05.01, B05-T05.01, B08-T03.01; statistics clustering; risk BR04; question OQ02.

**My answer (editable):** One model per question across all arms, chosen before any arm runs (2026-10-18). Mixed-model pairs, if they still occur, stay in the analysis with the model as a stratum; none are excluded.

**Verification:** Track B and C tests show a mixed-model pair is flagged and retained, with the model recorded as a stratum (BG-TRACKB, BG-TRACKC, BG-FAIR).

## BADR-0009 — Corpus rendering: template first, LLM paraphrase later

**Status:** ACCEPTED; 2026-10-18.

**Authority:** Owner answer in chat, 2026-10-18.

**Question:** May the corpus generator use LLM rewriting from the start?

**Why:** Template rendering keeps labels tied to the hidden world; LLM rewriting can drift critical facts and spends scarce quota.

**Options:** (a) Template-only for the S tier, add gated LLM paraphrase with an equivalence validator before the M tier; (b) LLM rewriting from the start.

**Recommendation:** Option (a), implemented in B08-T01.02 behind a check that rejects any rewrite changing IDs, dates, thresholds or negations.

**What affects what:** B02-T02.01, B02-T02.02, B08-T01.02; realism of the dataset (risk BR05).

**My answer (editable):** Template-first, LLM paraphrase later (2026-10-18).

**Verification:** B02 renders with no model call; B08-T01.02 has a negative control that rejects a dropped negation.

## BADR-0010 — Additions to the protocol's file tree

**Status:** ACCEPTED; 2026-10-18.

**Authority:** Coordinator decision inside task scope; the owner may amend.

**Question:** May the plan add files that the protocol's 70-file tree does not list?

**Why:** The tree is an implementation specification, but it has no home for the shared generator client (protocol §3.1 item 3), its tests, or the dataset card the protocol requires in §19.3.

**Options:** (a) Add `benchmark/generator.py`, `tests/test_generator_pool.py` and `docs/dataset_card.md` and record the deviation; (b) fold the generator into an existing module; (c) skip them.

**Recommendation:** Option (a). All 70 tree files are still owned by a card; the additions are `benchmark/generator.py`, `tests/test_generator_pool.py` and `docs/dataset_card.md` (owned by B01-T05.01 and B02-T07.01) plus the suite's own `README.md`, `AGENTS.md` and `docs/README.md` (B00-T02.02), which sit outside the protocol tree.

**What affects what:** B01-T05.01, B02-T07.01; the checker's tree-ownership check.

**My answer (editable):** Accepted as a coordinator decision in scope; owner may remove or move them.

**Verification:** BG-DOC checks that all 70 tree files have an owner; the additions are listed in PROJECT_MAP.

## BADR-0011 — Identifier namespaces and separate agent instructions

**Status:** ACCEPTED; 2026-10-18.

**Authority:** Coordinator decision inside task scope.

**Question:** How are benchmark IDs and instructions kept apart from Palladion's?

**Why:** Palladion uses P, G-, ADR-, T and Q identifiers and a root `AGENTS.md` that governs its contributor.

**Options:** (a) Distinct prefixes (B phases, BG gates, BADR, BI invariants, BR risks, OQ questions, E-B evidence) and a benchmark-local `AGENTS.md`; (b) reuse Palladion's identifiers.

**Recommendation:** Option (a). Hypotheses H1–H8, ablations A01–A16, strata Q1–Q10, arms R0–R7b and E0–E4 keep the protocol's own names; mutation cases are M01–M19 and metamorphic invariants MT01–MT07.

**What affects what:** The checker's reference scan; every cross-reference in this suite.

**My answer (editable):** Accepted in scope; owner may rename.

**Verification:** `check_docs.py` resolves every ID in this suite and its self-test rejects an undefined one.

## BADR-0012 — Protocol numbers are provisional until sealed

**Status:** ACCEPTED; 2026-10-18.

**Authority:** Protocol §13.2 and §14.3 (starting values, revise only before the test lock).

**Question:** Are the protocol's sizes, thresholds and loss weights fixed now?

**Why:** The protocol calls them starting proposals and says power must be estimated from pilot and dev data.

**Options:** (a) Treat them as provisional configuration defaults, frozen only at the B08-T03.01 seal; (b) freeze now.

**Recommendation:** Option (a). Config files carry them as defaults; changes before the seal are logged; after the seal any change marks later results exploratory.

**What affects what:** configs, B08-T02.01, B08-T02.02, B08-T03.01; question OQ10.

**My answer (editable):** Accepted as stated in the protocol.

**Verification:** The seal check in B08-T03.01 compares file hashes; edits after the seal are detected.

## BADR-0013 — Provider credentials for the benchmark

**Status:** ACCEPTED; 2026-10-18.

**Authority:** Owner answer in chat, 2026-10-18: the owner created the gitignored palladion-benchmark/.env.

**Question:** Where does the benchmark read its Groq credential from, and when may it call the provider?

**Why:** Palladion keeps its key in the repository-root `.env`; copying a secret between projects for convenience is a leak risk, and a credential's presence must never trigger spending.

**Options:** (a) A benchmark-local, gitignored `palladion-benchmark/.env` that the owner fills in, loaded only by an explicitly enabled command; (b) read Palladion's root `.env`; (c) environment variables set per command.

**Recommendation:** Option (a) or (c); do not read or copy Palladion's `.env`. Live calls need an explicit enable flag, a recorded budget and the model name in the command.

**What affects what:** B01-T01.01 (`.env.example` names only), B01-T05.01, B01-T05.02; question OQ01.

**My answer (editable):** Benchmark-local gitignored .env, created by the owner (2026-10-18). Loaded only by an explicitly enabled command; Palladion's root .env is never read or copied. The coordinator verified only that the file exists and is ignored by git, not its contents.

**Verification:** The secret scan negative control in B01-T01.01; live-call tests refuse to run without the flag.
