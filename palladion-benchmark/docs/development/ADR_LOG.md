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

## BADR-0014 — B01 runtime dependencies and additional files

**Status:** ACCEPTED; 2026-10-18.

**Authority:** Owner instruction 2026-10-18 that libraries may be added (BADR-0005), applied by the coordinator inside the B01 task scope; the owner may amend.

**Question:** Which runtime dependencies and extra files does phase B01 add beyond the protocol tree?

**Why:** B01 needs YAML configuration loading, an HTTP client for the Groq entry point, and a secret scan whose negative control the card requires; none of these has a home in the 70-file tree.

**Options:** (a) httpx and PyYAML at runtime, types-PyYAML for typing, plus `benchmark/secret_scan.py`, `tests/test_secret_scan.py` and `benchmark/config.py` (typed configuration loaders kept apart from the contracts so each module has one responsibility); (b) standard-library urllib and a JSON-only config format; (c) skip the scan and rely on `.gitignore`.

**Recommendation:** Option (a). httpx mirrors the client Palladion already uses for the same endpoint, which keeps the transport behavior comparable; PyYAML matches the protocol's `.yaml` config files; the scan is the only mechanism that makes the card's planted-key proof possible. Exact versions are pinned by `uv.lock` and recorded in EVIDENCE_LOG. Contracts use standard-library frozen dataclasses rather than pydantic because the protocol specifies dataclasses and no validation need requires another library.

**What affects what:** B01-T01.01 (files and pins), B01-T02.03 (YAML), B01-T05.01 and B01-T05.02 (httpx); the checker's list of recorded additions; BG-SECURITY.

**My answer (editable):** Accepted in scope under the owner's blanket permission to add libraries; owner may remove or replace any item.

**Verification:** `uv sync --locked` from a clean state, the dependency list in `pyproject.toml` equals this ADR, and the secret scan rejects a planted key and passes a clean tree (B01-T01.01).

## BADR-0015 — Generator model assignment rule and live-call authorization

**Status:** ACCEPTED; 2026-10-18.

**Authority:** Owner answers in chat, 2026-10-18: pre-assign models by quota; and the instruction to finish phase B01 end to end, which includes the real-provider proof in B01-T05.02, after creating `palladion-benchmark/.env`.

**Question:** How does the three-model Groq pool operate, and what live spending is authorized in B01?

**Why:** BADR-0007 says to switch models when rate limited and BADR-0008 says one model per question, chosen before any arm runs. The pre-phase adversary (A8, A2) found that these conflict unless an assignment rule is defined and that live spending needs a recorded authorization.

**Options:** (a) Pre-assign each question's model from configured per-model token budgets; waits at call time are capped and never switch models; (b) automatic failover with the model as a stratum; (c) qwen only.

**Recommendation:** Option (a). Budgets are configuration inputs and stay null until the owner states real limits, in which case every question gets the primary model. Questions are assigned in a seeded random order; the primary model takes questions until its budget is spent, then the next model in order. At call time a classified rate limit waits for the provider's retry-after up to 120 seconds (configurable, recorded), then the call fails and is recorded; it never switches model. When all budgets are exhausted, whole remaining questions are NOT_RUN for every arm. Automatic failover remains available only as an explicit, off-by-default setting whose use marks the question mixed-model.

**What affects what:** B01-T02.03 (config), B01-T05.01, B01-T05.02, B05-T05.01, B07-T08.01; BADR-0007 and BADR-0008 (this elaborates them); risks BR04, BR07, BR13.

**My answer (editable):** Pre-assign by quota (2026-10-18). Live authorization for B01 only: one call per approved model (three), a completion cap of at most 256 tokens, and at most six calls in total including classified retries; the commands use an explicit enable flag and the benchmark-local `.env`. Any further live use needs a new owner instruction.

**Verification:** Unit tests with an injected transport show no switch occurs without the explicit setting and every call records its model; B01-T05.02 records the real calls, models, token counts and quota headers.

## BADR-0016 — Contract strictness, isolation and system-under-test pinning

**Status:** ACCEPTED; 2026-10-18.

**Authority:** Owner answers in chat, 2026-10-18 (required citation field; subprocess isolation from B04); coordinator recommendation for the pinning rule.

**Question:** Where does the harness depart from the protocol's sketches or tighten them, and how are arms isolated and pinned?

**Why:** The protocol's `native_citation_supported: bool = True` makes an uncited arm look cited (BI06); a denylist of gold-like keys cannot keep gold out of arms in a shared process; a dirty shared working tree cannot be a pinned system under test (adversary findings adv-3, adv-5, adv-9 and adv-13).

**Options:** For the citation field, keep the sketch's default or require it; for isolation, in-process threads or subprocesses; for the system under test, the live shared tree or a pinned checkout.

**Recommendation:** Require the field with no default and demand a non-null `source_version_id` when true (a deviation from the sketch, stricter than it). Use an allowlist of arm-visible request fields. From B04 on, run arms and Palladion as separate subprocesses with a restricted input directory so timeouts can kill and gold is physically absent; B01 uses in-process fakes and marks an adapter unusable after a timeout. Confirmatory runs of Palladion use a pinned commit in a separate worktree or image, checked for cleanliness independently of the benchmark tree; read-only git status uses `--no-optional-locks`.

**What affects what:** B01-T02.01, B01-T04.01, B04-T03.01, B06, B07-T04.01, B08-T03.01; BI01, BI03, BI06; risks BR01 and BR02.

**My answer (editable):** Required citation field approved; subprocess isolation from B04 approved (2026-10-18). The pinned-worktree rule is the coordinator's recommendation, accepted in scope and to be confirmed when B04 starts.

**Verification:** Contract tests reject a defaulted or unbacked citation claim and gold-like keys and values; B04 records subprocess isolation evidence; the manifest records both trees' state separately.

## BADR-0017 — No Docker: Qdrant runs as a standalone binary under WSL

**Status:** ACCEPTED; 2026-10-18.

**Authority:** Owner message in chat, 2026-10-18: this machine cannot run Docker; do what Palladion does for Qdrant.

**Question:** How do the benchmark's local services run on a machine without Docker?

**Why:** Palladion runs Qdrant without Docker through a checksum-pinned official static release under WSL Ubuntu with Linux-owned storage, because the native Windows server produced filesystem errors. The benchmark needs its own index service (dense and hybrid arms) that cannot be disturbed by, or disturb, Palladion's store.

**Options:** (a) The same method with the benchmark's own launcher: pinned official release, SHA-256 verified, WSL, separate ports (HTTP 17333, gRPC 17334), separate data directory under `~/.local/share/palladion-benchmark/qdrant/`; (b) share Palladion's running instance; (c) require Docker.

**Recommendation:** Option (a). The launcher (`scripts/qdrant_server.py`, with tests) is built in B04-T04.01 as an addition (listed in BADR-0017, not copied from Palladion code, since the benchmark never imports or edits Palladion). `docker-compose.yml` stays as an optional file for machines with Docker and is not executed here. Neo4j (B06) needs the same treatment and is queued as OQ12.

**What affects what:** B04-T01.02 and later cards that need Qdrant, B04-T04.01, B06-T04.01; risks BR06 and BR11; reproducibility (service version is pinned by release and checksum instead of an image digest).

**My answer (editable):** Do not use Docker; run Qdrant without it, as Palladion does (2026-10-18).

**Verification:** B04-T04.01 starts the pinned release under WSL on port 17333, reads back a collection through the benchmark's own client, confirms Palladion's port 16333 and store are untouched, and stops only the process it started.

## BADR-0018 — B02 test files beyond the protocol tree

**Status:** ACCEPTED; 2026-10-18.

**Authority:** Coordinator decision inside task scope; the owner may amend.

**Question:** Which test files does phase B02 add beyond the eight the protocol lists?

**Why:** The protocol's test files cover temporal gold, ACL isolation, evidence slots and fixture integrity. The world generator, document renderer, live-API mock and generation script would otherwise have no owned test file.

**Options:** (a) Add `tests/test_world.py`, `tests/test_documents.py`, `tests/test_live_api.py` and `tests/test_generate_data.py`; (b) fold those tests into the protocol's files; (c) leave the modules untested.

**Recommendation:** Option (a): one test file per module keeps ownership and failures easy to attribute. All 70 tree files remain owned.

**What affects what:** B02-T01.01, B02-T02.01, B02-T02.02, B02-T05.01, B02-T07.01; the checker's recorded additions.

**My answer (editable):** Accepted in scope under the owner's blanket permission to add files and libraries; owner may remove or merge any of them.

**Verification:** BG-DOC confirms every tree file still has an owner and every addition is listed; each new test file is run by `uv run pytest`.

## BADR-0019 — Pilot label audit design and live-call authorization

**Status:** ACCEPTED; 2026-10-18.

**Authority:** Owner answers in chat, 2026-10-18: authorize the LLM second pass and label the packet personally; also perform a retrieval check on the same sample.

**Question:** How is the B02 pilot label audit run, given that OQ08 leaves the owner as the only human annotator, and what live spending does it need?

**Why:** Protocol 6.3 and 14.5 ask for dual human annotation. The owner is also the author of the hidden world, so is not blind to intended labels, and an LLM pass reads the same template text. The pre-phase adversary (adv-1, adv-4, adv-21) showed that agreement here cannot detect template-induced errors and that the card and four records still said two independent annotators.

**Options:** (a) Owner labels a blinded stratified packet, a blinded LLM pass labels the same packet, and the owner also checks that cited clauses exist and suffice; (b) owner only; (c) defer the audit.

**Recommendation:** Option (a). The packet is about 30 items, drawn with a recorded seed, stratified over the ten strata, shown without gold fields, split names or generator tags. Disagreements are resolved against the hidden-world rules, not by either annotator, and every post-audit gold edit is logged with before and after hashes. The dataset card states that the statistic is owner against LLM, not human against human, and that this is a recorded deviation from protocol 6.3 and 14.5.

**What affects what:** B02-T07.02, BG-GOLD, BR10, B05-T04.01 wording, B04-T05.01 (depends on the audit).

**My answer (editable):** Authorized (2026-10-18). Live authorization for B02-T07.02 only: at most 40 calls in total including classified retries, one call per item, completion cap 256 tokens, the three approved Groq models only, one model per item assigned by the BADR-0015 rule, the benchmark-local `.env`, an explicit enable flag, no key in logs. Any further live use needs a new owner instruction. The owner labels the packet personally and records the retrieval check. Amendment (2026-10-19): the first model pass used 36 of the 40 calls with a prompt that cut documents off before their rule clauses, and agreed with gold on 7 of 30 items. The owner authorised 40 more calls for a second pass, same models and limits (used 37). The owner chose to push B02 with the owner labels outstanding and to label later; B02-T07.02 and BG-GOLD stay PARTIAL until then. Second amendment (2026-10-19): after the post-phase audit changed the fixture, the owner authorised up to 40 more calls for one pass on the final fixture (used 36, prompt excerpt-v1). No further live use is authorised.

**Verification:** Unit tests show the packet carries no gold field and the agreement statistic matches hand-computed cases; B02-T07.02 records the real calls, models, counts and the owner's labels with denominators.

## BADR-0020 — Barrier, determinism and file decisions for B02

**Status:** ACCEPTED; 2026-10-18.

**Authority:** Coordinator decision inside task scope, after the pre-phase adversary (E-B02-001); the owner may amend.

**Question:** Which design rules does B02 adopt to keep gold out of arm-visible data and to make generation reproducible, and which files does it add?

**Why:** The adversary found six barrier holes (query text, filter values, identifiers, titles, file and manifest order, snapshot ids), determinism hazards (hash randomisation, time zone, shared random streams), and proofs without an owner file.

**Options:** (a) Adopt the rules below and add the files; (b) leave them to individual tasks; (c) defer to B08.

**Recommendation:** Option (a). (1) Queries are written by LLM-free templates and screened for gold, stratum and answerability vocabulary and for document ids outside the exact-id stratum. (2) Filter values come only from the principal, the case and the arm condition. (3) Question ids are keyed-hash pseudonyms, snapshot ids are content digests, titles and file names carry no family, stratum or split token, and manifest order is shuffled by an independent seed. (4) Each generator component draws from its own named random stream and tier seeds are derived from the base seed and the tier name, so S and M family sets are disjoint. (5) Digests use one canonical encoding (key-sorted compact JSON, UTF-8, explicit UTC timestamps, no wall clock or absolute paths) and are proven across subprocesses with different hash seed, time zone and working directory. (6) Scenario family is a world object (root policy family plus entity cluster); partitions run over the union of all strata. (7) Answerability, negative mechanism and evidence status follow a validated mapping. (8) Live-mock freshness bounds are per-operation constants in the mock, and read times derive from the evaluation time. (9) Additional files: `benchmark/fixtures/entities.py`, `benchmark/fixtures/knowledge.py` and `benchmark/fixtures/phrasebook.py` and `benchmark/fixtures/artifacts.py` (phrase banks and support-artifact generation, kept apart from the renderer), `benchmark/fixtures/operations.py` (the world module would otherwise hold three responsibilities in one file; `world.py` keeps the aggregate and its builder), `benchmark/fixtures/audit.py`, `tests/test_partitions.py`, `tests/test_label_audit.py`.

**What affects what:** B02-T01 to B02-T07, the checker's recorded additions, BG-FIXTURE, BG-GOLD, BG-SECURITY, BG-REPRO.

**My answer (editable):** Accepted in scope under the owner's blanket permission to add files and libraries; owner may amend any rule.

**Verification:** Each rule has a planted-defect test in the owning task; BG-DOC confirms the new files have owners.

## BADR-0021 — Corpus noise and measurement constants

**Status:** ACCEPTED; 2026-10-18.

**Authority:** Coordinator decision inside task scope, recorded before the first measurement that uses the numbers (TESTING_GATES numeric-tolerance rule); the owner may amend before the first confirmatory use.

**Question:** Which constants fix how noise is planted and how its proportions are measured in the S-tier corpus?

**Why:** Protocol 4.5 gives noise ranges but no way to measure them, and the pre-phase adversary (adv-15, adv-16) found that reporting the generator's own tags would restate the configured rate.

**Options:** (a) Plant each kind of noise at the midpoint of its configured range and measure it from the documents with independent methods; (b) report generator tags; (c) plant at the range edges.

**Recommendation:** Option (a). Planted counts are the range midpoint times the tier size (S tier: near-duplicates 120, stale 78, unapproved 36 including drafts, injection 18) plus truncated passages at 3 percent (the protocol names truncation as structural noise without a rate). Measurement: near-duplicates are non-authoritative documents whose word 3-shingle sets have Jaccard similarity of at least 0.75 (shingles shared by more than 60 documents are ignored as boilerplate), counted as redundant members of each group; stale text is a non-authoritative, non-proposal document quoting a policy window that differs from the one in force at the snapshot; unapproved is a registry state of draft or unapproved proposal; injection is a match of a fixed cue list; language is classified from stopword shares (below 0.2 Indonesian is English, above 0.8 is Indonesian, otherwise mixed), with the tagged language reported beside it. Because templates repeat on their own, the planted near-duplicate count is the target minus the natural count measured first. The measured proportion, not the plan, is what the dataset card reports, and a tag/measurement gap is shown.

**What affects what:** B02-T02.02, B02-T06.01 (realism thresholds are a separate ADR), B02-T07.01 (dataset card), BG-FIXTURE.

**My answer (editable):** Accepted in scope; these are fixture-design constants, not thresholds on any system under test.

**Verification:** `tests/test_documents.py` measures the built corpus, checks each proportion against the configured range, and plants a tag/text mismatch that the measurement must expose.

## BADR-0022 — Fixture realism thresholds and independent gold-support check

**Status:** ACCEPTED; 2026-10-19.

**Authority:** Coordinator decision inside task scope, recorded before the first realism measurement (TESTING_GATES numeric-tolerance rule; pre-phase adversary adv-4, adv-6, adv-16); the owner may amend before the first confirmatory use.

**Question:** Which numbers decide that the S-tier fixture is not trivially solvable, not over-regular and not answered by version order, and how is gold-support checked without reusing the renderer?

**Why:** B02-T06.01 must catch fixtures whose gold is circular or whose answers are searchable by accident. A check with no number cannot fail.

**Options:** (a) Fix the floors and ceilings below now and fix the fixture, never the number, if a measurement misses them; (b) measure first and then choose; (c) skip realism checks.

**Recommendation:** Option (a). (1) Identifier-free lexical solvability: a BM25 ranking (k1 1.5, b 0.75, over the documents visible to the principal) of the question text with every token that contains a digit removed must put a gold document first for at most 0.60 of the answerable questions in strata Q2 to Q5. (2) Sentence-length variation: the coefficient of variation of sentence length over non-authoritative documents must be at least 0.25. (3) Skeleton diversity: after replacing digits and identifiers, distinct sentences divided by all sentences over non-authoritative documents must be at least 0.10. (4) Version order: in Q4, choosing the newest in-force version of the cited family must be right for at most 0.30 of the questions, and choosing the oldest for at most 0.60. (5) Gold-support is read from the rendered text of the cited spans by an extractor that shares no code with the renderer (digits and unit words only): every number in a required claim, once identifiers are removed, must appear in the cited spans or equal the sum of two numbers in them. These are sanity floors for a template-first fixture, not proof of realism; the dataset card states that limit.

**What affects what:** B02-T06.01, B02-T07.01 (dataset card), BG-FIXTURE, BG-GOLD, risk BR05.

**My answer (editable):** Accepted in scope; the numbers are fixture-design constants, not thresholds on any system under test.

**Verification:** `tests/test_fixture_integrity.py` runs every check on the clean S-tier fixture and plants a defect for each one, including an over-regular corpus and a trivially searchable query set.

## BADR-0023 — Decisions taken at the B02 post-phase audit

**Status:** ACCEPTED; 2026-10-19.

**Authority:** Coordinator decisions inside task scope after the post-phase audit (E-B02-004); the owner may amend any of them.

**Question:** Which design changes does B02 adopt in answer to the post-phase audit, and which file does it add?

**Why:** The audit found unplanned policy conflicts, enumerable question identifiers, announcements that singled out planted histories, a label audit that could not be reproduced or protected from stale labels, and a 1,200-line module that mixed the gold schema with ten generators.

**Options:** (a) Fix them in B02 and record what stays open; (b) defer all of it to B08.

**Recommendation:** Option (a). (1) Policy precedence follows scope specificity (a tenant-specific policy outranks a class-specific one, which outranks neither) and only planted conflicts use a higher value, so overlapping policies never tie by accident; a validation check reports any unplanned conflict. (2) Question identifiers are keyed by an id secret; the pilot uses the empty default and says so, and the locked split must use a private secret before the seal. (3) Announcements are drawn from any family with a later version. Policy ids in support-document titles stay: they are public identifiers, not split or family labels (this narrows BADR-0020 rule 3 to question ids, split, stratum and scenario labels). (4) The label audit stores a gold digest with every owner label and refuses labels made against changed gold, stores a prompt version and digest with every model label, refuses to overwrite a recorded pass, and counts calls cumulatively across passes. (5) Live reads give an outsider the same answer for a missing subject as for another tenant's. (6) Regeneration with overwrite clears the previous published tree and keeps the audit folder. (7) `benchmark/fixtures/question_gen.py` holds the ten stratum generators and the builder; `questions.py` keeps the schema, screening and partition helpers. (8) Deferred with owners: unindexed-source questions (B04, which has an index to omit), user-supplied validity policy on reported facts (B07-T05.01), injection variants beyond plain instructions (B07-T07.01), partition tests at the M-tier shape and a larger scope vocabulary (B08-T01.01), `knowledge.py` split (B08), audit constants as configuration (B04).

**What affects what:** B02-T01 to B02-T07, B03 (gold digest, ids), B04-T05 (needs the audit), B08-T03.01 (private id secret), BG-FIXTURE, BG-GOLD, BG-SECURITY.

**My answer (editable):** Accepted in scope; the owner may amend any item.

**Verification:** Each item has a regression test and a planted-defect mutant in E-B02-003.

## BADR-0024 — B03 decisions after the pre-phase adversary

**Status:** ACCEPTED; 2026-10-19.

**Authority:** Owner answers in chat, 2026-10-19: binary slot-match relevance; add an optional document id to the candidate contract. Remaining items are coordinator decisions inside task scope after E-B03-001; the owner may amend.

**Question:** How does the scorer define relevance, identity, units, denominators and the intention-to-treat rule, and which fixture and contract fields does B03 add?

**Why:** The adversary (E-B03-001) showed that the gold has no graded relevance, that most documents have no identifier a candidate can carry, that overlap credit could hide authority confusion, and that nothing consumed a run end to end.

**Options:** (a) Fix the rules now, before the first measurement, and add the missing fields; (b) leave them to each metric.

**Recommendation:** Option (a). (1) Relevance is binary: a candidate is relevant only when it matches an alternative of a required slot of the record. (2) `EvidenceCandidate` gains optional `source_document_id` and `source_sha256` (default none); a candidate can then be matched to any published document by identity. (3) Headline coverage and completeness count identity matches only; text overlap gives separately labelled alignment credit. (4) Locator grammar and overlap rule: text is NFC-normalised with whitespace folded; a candidate maps to a clause when its text is contained in the clause span or contains it, or when at least 0.8 of the candidate's words lie inside the clause span; these numbers are fixed here before the first measurement. (5) Unit of evaluation: one gold clause or one whole document for non-clause sources; duplicate candidates for the same unit count once; a list shorter than K is scored over what was returned with K reported; a record with no relevant unit gives not-applicable for ranking metrics. (6) CompleteSet and SlotCoverage apply to records with satisfiable slots only; others return not-applicable. (7) Intention to treat: non-completed pairs count as failures on binary endpoints in the primary table; the conditional table uses the commonly completed set and counts exclusions; pairs censored by the same run deadline are excluded and counted. (8) Bootstrap: percentile cluster bootstrap by scenario family, a recorded seed, and below 8 clusters the interval is labelled descriptive; the zero-failure bound is computed exactly from n. (9) Latency quantiles use linear interpolation between order statistics; timed-out calls are reported beside and treated as at least the deadline. (10) `GoldRecord` gets a reader that checks the gold digest; the manifest gains the recorded interval and the gold a history-allowed flag (B03-T03.02). (11) Noise slope, paraphrase stability and rank sensitivity move to B07-T07.01, B08-T01.02 and B09-T01.01; marginal-update cost moves to B07-T05.01. (12) New files: `benchmark/eval/score_run.py`, `tests/test_score_run.py`, `tests/test_evidence_metrics.py`, `tests/test_retrieval_metrics.py`.

**What affects what:** B03-T01.01 to B03-T07.01, B04-T01 (candidates carry document ids), B05-T01, B08-T02, BG-METRIC, BG-STATS, BG-REPORT.

**My answer (editable):** Items 1 and 2 accepted by the owner (2026-10-19). Items 3 to 12 accepted in scope under the owner's blanket permission; the owner may amend before the first measurement.

**Verification:** Each rule has a hand-computed test and a planted-defect control in the owning B03 task.

**Amendment after the post-phase audit (E-B03-004), 2026-10-19:** (a) A `doc` locator, or none, names the document only: it credits the document unit and the clauses the candidate's text reproduces. (b) Text alignment is computed for every candidate and kept apart from identity credit; a claimed `live:` id is no claim. (c) A candidate leaks when it names a document the principal may not see, or reproduces at least 0.3 of the phrases of such a document that no visible document also contains. (d) Precision counts every relevant candidate; MRR, nDCG, MAP and gain count a slot once. (e) Harm metrics (exposure, authority confusion, wrong vintage) have no intention-to-treat value and are summarised over completed pairs; benefit metrics give a non-completed pair zero when the gold says the metric applies, for non-binary metrics too (an extension of item 7). (f) "Applies" is decided by scoring an empty return, so applicability follows the gold. (g) Entity-disambiguation error is dropped from B03 (no fixture gold carries it). (h) Spend on a failed call counts; a call with no report is missing. Owner may amend before the first measurement.


## BADR-0025 — B04 decisions after the pre-phase adversary

**Status:** ACCEPTED; 2026-10-19.

**Authority:** Owner answers in chat, 2026-10-19: provision an isolated Palladion runtime; harness provenance counts as headline identity; approve the embedding model, the reranker and the Qdrant binary downloads; neutral harness ACL filter. The remaining items are coordinator decisions inside task scope after E-B04-001; the owner may amend.

**Question:** How are the Track A arms built, fed, filtered, budgeted and recorded, and how does R7a run without touching Palladion's live state?

**Why:** The adversary (E-B04-001) showed that no card owned the chunker or tokenizer, that R0 to R3 have no access control or clock, that Palladion's runtime, principals and tokens come only from its own seed, and that the pilot's isolation, budget and K were unrecorded.

**Options:** (a) Build the shared harness first and give every arm the same chunks, filter and budget; (b) let each arm do its own parsing, filtering and truncation.

**Recommendation:** Option (a). (1) Arms read the published namespace and an index directory only. (2) Chunks tile each document, carry document id, clause ids and offsets, and arrive as harness-attributed provenance that earns headline identity, labelled in every table; text-only arms get alignment credit only. (3) Counted tokens are whitespace words, characters also reported; two bundles at one budget may differ by at most one chunk. (4) A neutral filter by the principal's tenant and role (condition C2) is applied to every arm and a no-filter run (C1) is reported beside it. (5) R0 is a standard-library BM25; R1 uses Palladion's pinned embedding model (OQ04) through fastembed and a Qdrant HNSW collection on the benchmark's own server (127.0.0.1:17333, WSL, checksum-pinned); R3 uses Palladion's reranker (OQ05); fusion is reciprocal-rank with a pinned constant. (6) R7a runs from a detached worktree of Palladion at a recorded commit with its own root, collection and port, seeded by Palladion's own seed code; it is labelled native-ingestion in the common-chunk comparison; unavailable or degraded responses are run states, never empty lists. (7) Native-ingestion mode for the other arms is deferred to a later phase. (8) Arm isolation targets accidental leakage; subprocess isolation stays at B08. (9) The pilot runs the smoke partition only; the runner refuses the test split without a recorded seal and records which annotation file it read.

**What affects what:** B04-T01.01 to B04-T05.01, B05 (R3 and R7a feed Track B), B06 (graph arms reuse the harness), B08 (seal, isolation), BG-ADAPTER, BG-FAIR, BG-TRACKA, BG-REPRO, BG-SECURITY.

**My answer (editable):** Items 1 to 4, 6 and the downloads accepted by the owner (2026-10-19). Items 5, 7 to 9 accepted in scope under the owner's blanket permission; the owner may amend before the first measurement.

**Verification:** Each rule has a test with a negative control in its owning B04 task; the pilot records every pin, digest, K, budget and condition.
