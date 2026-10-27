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

**Amendment after the build and the post-phase audit (E-B04-002, E-B04-004), 2026-10-19:** (a) Every benchmark principal maps to one Palladion reader in one case; under C2 the neutral filter is applied to Palladion's output after its ranking, so R7a can return fewer than K candidates, and the number dropped is a ledger flag. (b) Documents are loaded into Palladion as approved (approved, retired, non_normative), approved then revoked (withdrawn) or left as draft (draft, unapproved proposal); approval there means retrievable, not authoritative, and retired and withdrawn states and supersession links are declared gaps. (c) Documents loaded over HTTP get no identifier aliases, so a query naming a code is answered with nothing by Palladion (BR24); this is recorded, not worked around. (d) R7a validity follows Palladion's wall clock (BR22). (e) Dense results with equal scores are ordered by chunk id after asking for ten extra hits, so a rebuild gives the same list. (f) The validator allows exactly one gold-named key, `gold_manifest_sha256`, in a manifest, which is evaluator-side by design. (g) Item 9 reads: Track A runs the smoke or dev split; the pilot measurement uses the smoke split only. (h) Downloads: the embedding model was 252 MB, the reranker 92 MB, Qdrant 33 MB; the owner re-approved after the larger size was stated.

## BADR-0026 — Label audit delegated to the coordinator; dispositions

**Status:** ACCEPTED; 2026-10-19.

**Authority:** Owner message, 2026-10-19: no time to label, "please just label it by yourself and push". The dispositions below are coordinator decisions inside B02-T07.02 and may be amended by the owner.

**Question:** Who reads the 30-item packet when the owner will not, what does that reading count for, and what happens to the defects it finds?

**Why:** BADR-0019 expected an owner reading. Without one the pilot would stay blocked, but a reading by the builder is weaker evidence than a human's.

**Options:** (a) Keep B02-T07.02 open until the owner labels; (b) coordinator labels blind, records the limit, keeps BG-GOLD PARTIAL and asks the owner to relabel or accept before the seal; (c) skip the audit.

**Recommendation:** (b).

**What affects what:** B02-T07.02 closes; B04-T05.01 unblocks after the three-question withdrawal; BG-GOLD stays PARTIAL; B08-T03.01 gains the relabel-or-accept step and the generator correction.

**My answer (editable):** Accepted as (b). The three synthesis questions a-1c1517e1c363, a-29081870dc64 and a-4bcb97ff166b are withdrawn from the pilot by a recorded list, the gold is not edited, and the generator is corrected before the seal (BR29). The reader's one wrong label (a-3e78c6bf81ce) is not a gold defect.

**Verification:** E-B02-006 holds the report, denominators, the item-level reasons and the limits; the exclusion list is tested in B04-T05.01.

## BADR-0027 — Palladion limits: benchmark-side mitigations and the fixes handed to its contributor

**Status:** ACCEPTED; 2026-10-19.

**Authority:** Owner answers in chat, 2026-10-19: register the missing aliases through a benchmark-owned setup step and report it as a second variant beside today's R7a; build per-principal identities later, before B08; write one document that lists what is mitigated and what needs a Palladion fix. The loader change (item 2) is a coordinator decision inside B04 scope that the owner may amend.

**Question:** Which Palladion limits do we mitigate on our side, how, and which are left as requests to its contributor?

**Why:** The pilot (E-B04-005) showed R7a empty on every code-bearing question (BR24) and the risk register held two statements about Palladion that its source contradicts (BR27, BR28). The owner asked for the mitigable ones done and the rest written down properly.

**Options:** (a) Do nothing and only report; (b) mitigate what can be done without touching `palladion/` and document the rest; (c) ask for fixes before any further R7a run.

**Recommendation:** (b), as built.

**What affects what:** (1) An alias setup step (`scripts/palladion_aliases.py` and `scripts/palladion_alias_job.py`) calls Palladion's own `Catalog.add_alias` inside the isolated worktree's environment, after the HTTP load and with the server stopped; it reads only published text, edits nothing under `palladion/` and records itself in the arm's manifest. This departs from "HTTP only" (BADR-0002) for setup, never for searches. R7a is reported as the plain variant (no aliases) and the aliased variant, in separate runs of the same arm id. (2) The HTTP loader approves each version after the one it supersedes and names it, and revokes withdrawn documents last. (3) Per-principal identities (BR27) wait for B08. (4) Palladion fixes PF01 to PF06 are in [PALLADION_FIXES](PALLADION_FIXES.md); nothing is agreed with its contributor.

**My answer (editable):** Accepted as above. Corrections to the register: BR27 and BR28 are restated against the source.

**Verification:** E-B04-006 holds the four re-runs, their validator results and the limits; the tests for the loader and the alias step fail on planted defects.

## BADR-0028 — B05 decisions after the pre-phase adversary

**Status:** ACCEPTED; 2026-10-20.

**Authority:** The owner started B05 ("Start B05: run its pre-phase adversary first, then build it", 2026-10-20) and earlier ruled that no further live provider use is authorized. The items below are coordinator decisions inside B05 scope after E-B05-001; the owner may amend. Live use (item 9) is not decided here.

**Question:** How are Track B answers scored against deterministic gold, run fairly across retrievers, and kept free of leakage, without any live provider call?

**Why:** The adversary (E-B05-001) showed the gold had no closed claim, action or outcome vocabulary, Track B artifacts had no scorer or validator, generator faults were classed as arm faults, prompts were not screened or kept, and the live pilot had no authorization.

**Options:** (a) Extend the question file's schema and regenerate; (b) add an evaluator-only answer-gold file beside it; (c) score claims with a judge.

**Recommendation:** (b), because it leaves the question file and the label-audit digests unchanged and gives deterministic targets.

**What affects what:** ten decisions follow, each owned by the card named.
1. **Answer-gold sidecar** (B05-T07.01): claim units with a closed kind, required or forbidden and a slot; a closed action; the policy outcome; applicable version ids. Additive optional fields on `CaseResponse`; answer citation syntax `document@version#clause`.
2. **Accounting** (B05-T01.02): coverage is intention-to-treat (non-completion counts against it); the directive rate is reported conditional on completion and with an intention-to-treat worst-case bound that treats non-completed pairs as unknown. Denominators of the 87 eligible smoke questions are stated with every figure; the pilot is descriptive.
3. **Gate and budget** (B05-T05.01): every cited or used id must come from the delivered bundle; the unit is whitespace words; C2 for all arms with C1 as a sensitivity run; one named R7a variant per run.
4. **Faults and barrier** (B05-T09.01): rate-limit and provider HTTP faults are provider-origin invalid runs, budget and disabled are harness-origin not-run; the total rate-limit wait stays below the case deadline; a cancel flag stops a timed-out worker; every prompt message is screened and the prompt text is kept in the run directory.
5. **Scoring never calls the generator's resolver** (B05-T02.01); the oracle policy-tool condition moves to Track C (B07-T08.01).
6. **Judges** (B05-T04.02): label sources have fixed precedence (deterministic, human, judge); a judge never overwrites a higher source; at least two judges with distinct model ids, family overlap disclosed (the pool has two families); judge prompts stay outside run directories; judge output counts only after agreement with human labels is reported. Judge calls need the owner's authorization.
7. **Loss matrix** (B05-T03.01): event rules fixed here. Correct supported answer: all required claims, none forbidden, every cited id delivered and accessible (0). Useful partial: the status states the missing input for a PARTIAL or conflict question (0.2). Unnecessary abstention: gold ANSWERABLE, response not substantive (1). Minor unsupported descriptive claim: a descriptive claim with no valid delivered citation (2). Inapplicable-SOP interpretation: declared version or outcome differs from the answer-gold on a policy question (5). Unauthorized disclosure: a cited or used id the principal cannot access (20). Unsupported directive: an action outside the gold's allowed actions or a forbidden directive claim (25). Sweep: each weight scaled by 0.5 and 2 one at a time, and all weights jointly low and high; a winner that changes is reported as conditional. AURC is dropped from B05 (no harness-observed confidence score is defined); selective risk and coverage are reported at the decision point.
8. **Stability** is NOT_RUN in B05 (needs two index generations); granularity is reported per arm.
9. **Live use**: B05-T06.01 is BLOCKED until the owner authorizes calls, tokens, models and the quota assumption; it will replay stored Track A candidates so only generator calls are live. The adversary's size estimate (about 261 calls, roughly 1.3 to 1.6 million prompt tokens) is an estimate, not a measurement.
10. **Single model**: with the configured null token budgets every question goes to the primary model; the pilot says so, and the NOT_RUN path is tested with an injected budget.

**My answer (editable):** Accepted as above.

**Verification:** Each item has a test with a negative control in its owning card; E-B05-001 records the dispositions.

### BADR-0028 amendment (2026-10-20): clarifications from the post-phase audit

Dispositions that change or narrow the wording above (E-B05-004): **item 7**: a useful partial answer (0.2) is a correct answer to a PARTIAL question only (a correct report of a conflict is a full correct answer, 0); unauthorized disclosure is a cited source the principal may not read (delivered-but-uncited sources are a retrieval leak and are counted in Track A); each forbidden behaviour costs an event (wrong rule stated: inapplicable SOP; revealed or confirmed source: disclosure; status guessed: minor claim; a final outcome without the input is already a directive); one minor event per claim, not per reason. **Item 2**: the intention-to-treat accounting is for the two co-primary endpoints; coverage of abstentions, selective figures and loss are conditional on completion with the number of pairs that did not complete beside them. **Item 3**: what was delivered is read from the prompt the run kept, and an answer whose recorded delivered ids differ from it is an invalid answer. **Item 4**: the generator's deadline is set inside the Runner's, so a slow provider ends as a timeout from the provider and does not disable the arm; a hang in retrieval still does (BR14). The answer-gold's `as_of_basis` is carried for B07 and the labelling guide and has no scorer yet.

## BADR-0029 — Live generator use for the first Track B pass (B05-T06.01)

**Status:** ACCEPTED; 2026-10-20.

**Authority:** Owner answers in chat, 2026-10-20: "I will authorize bounded live Groq use for the B05 pilot", then 20 calls, the primary model with failover down the approved list on a rate limit, and 700 completion tokens.

**Question:** What may the first live Track B pass spend, on which models, and with what failover?

**Why:** B05-T06.01 was blocked because no live use was authorized after the label audit (BADR-0019). The owner asked for a bounded first pass to measure real tokens, failures and rate limits before spending more.

**Options:** (a) a small first pass of 20 calls; (b) 60 calls; (c) all 174 pairs; for models, the primary only or the explicit three-model chain.

**Recommendation:** (a), with the primary model only; the owner chose the chain instead.

**What affects what:** at most 20 generator calls in total, counting every dispatch including a call refused by a rate limit and every failover attempt; models `qwen/qwen3.8-27b`, then `openai/gpt-oss-120b` if it is rate limited, then `openai/gpt-oss-20b`, in that order only (an explicit, recorded failover: BADR-0008's switch rule, `allow_automatic_failover` for this run only); a question whose arms ran on different models is flagged, never dropped (BR13); completion cap 700 tokens; R2 and R3 only; a seeded subset of the eligible questions small enough that every pair can finish inside the cap (8 questions, 16 pairs, 4 calls of headroom); calls are paced so the observed 8,000 tokens per minute is not hit by design; the benchmark-local `.env`, an explicit enable flag, no key in any output. No judge call is authorized. The estimate of 5,000 to 6,000 prompt tokens per call is mine and unmeasured. Any further live use needs a new owner instruction.

**My answer (editable):** Authorized as above for one pass; the results are single-run and descriptive.

**Verification:** the run directory holds one generation record per dispatched call (cap check), every prompt, and the models used; E-B05-005 records the counts, failures and rate-limit events.

**Outcome (2026-10-20):** the pass used 16 of the 20 calls, all on the primary model with no rate limit and no failover; 15 pairs were valid, 1 answer was invalid; see E-B05-005. R7a was not run: the owner's limits named R2 and R3 only, so the card's original R7a scope needs a new instruction.

## BADR-0030 — Owner items stay deferred, each pinned to its phase (2026-10-20)

**Status:** ACCEPTED; 2026-10-20.

**Authority:** Owner answers in chat, 2026-10-20: no further live Groq use before B06; "none now" for OQ09, OQ10 and the label-audit stance, "put all three each respectively in their appropriate phase in the MDP and other dev suite".

**Question:** Which owner items are settled before B06, and where do the rest wait?

**Why:** None of the three blocks B06 or B07. Each blocks only a later card, and a deferred item that is not a dependency on its card is easy to miss.

**Options:** settle them now; defer them with a tracked dependency; defer without one.

**Recommendation:** defer with a tracked dependency (chosen).

**What affects what:** OQ10 (confirmatory pairings) and the new OQ13 (the owner relabels the 30-item pilot packet or accepts the delegated labels in writing, BADR-0026) are dependencies of B08-T03.01 and block the seal; OQ09 (license) is a dependency of B08-T07.01. The checker prints each as a waiting notice. No further live use is authorized: BADR-0029 is spent at 16 of 20 calls, and the next Track B pass needs a new instruction.

**My answer (editable):** Deferred as above.

**Verification:** `check_docs.py` lists B08-T03.01 on OQ10 and OQ13 and B08-T07.01 on OQ09.

## BADR-0031 — Scope of B06 after the pre-phase adversary (2026-10-20)

**Status:** ACCEPTED; 2026-10-20.

**Authority:** Owner answers in chat, 2026-10-20: "build offline, run on a subset"; R7b "FEATURE_NOT_SUPPORTED + request PF07"; shared contracts "Yes, additive only"; isolation "Yes, worker plus proxy"; subagents "Yes, implementers for B06 only".

**Question:** How is B06 scoped given E-B06-001 (the S tier needs about 4 million tokens and about 8 hours per comparator at the measured 8,000 tokens a minute, the machine has 7.4 GB and no GPU, and R7b has no graph over HTTP at the pin)?

**Why:** Running R4 to R6 over all 1,200 documents on the free tier is not feasible, and an HTTP-only R7b has zero edges. The protocol asks for the official pipelines, cold-state cost accounting and no hidden spend.

**Options:** (a) build everything offline and run live extraction on a matched subset (chosen); (b) build offline only; (c) defer the comparators. For R7b: declare it unsupported and request PF07 (chosen) or only declare it. For contracts: additive extension (chosen) or side files. For isolation: worker plus counting proxy (chosen) or in-process.

**Recommendation:** as chosen.

**What affects what:** (1) B06 gains three foundation cards (B06-T00.01 contracts, B06-T00.02 worker and proxy, B06-T00.03 pins and approved downloads) and loses GraphRAG Global and DRIFT, which are exploratory and not built here. (2) R7b is FEATURE_NOT_SUPPORTED at 6444345 and PF07 is added to PALLADION_FIXES.md; Neo4j (OQ12) is not needed until PF07 lands. (3) The Track A manifest, arm list, offline cost record and candidate record gain optional fields and new arm ids only; every existing run and test stays valid. (4) This reverses BADR-0025 item 8 (subprocess isolation deferred to B08): isolation is built in B06, in this order. (5) The cold-state run is a pilot on a matched subset of about 100 documents with R0 to R3 and R7a re-run on the same subset; no ranking claim. (6) **Delegation for B06 only** (supersedes BADR-0003 for this phase, owner-requested): after the coordinator builds and tests the shared contracts, worker and proxy, up to three Haiku 5.5 (medium effort) implementer agents may each write one adapter (R4, R5, R6) with its own test file in disjoint paths, offline only, with no credentials, no network and no git; the coordinator reviews every diff, runs every test and owns integration, task state and records. The adversary at the start and the auditor at the end stay. The rule reverts to the start-and-end-only limit when B06 closes. (7) No download and no live call happens until OQ14 is answered for that artifact or run.

**My answer (editable):** Accepted as above.

**Verification:** E-B06-001 holds the adversary receipt and dispositions; the plan, gates and checker reflect the new cards; each later B06 card closes only with its own proof.

## BADR-0032 — Live extraction for the graph comparators' cold-state pilot (B06-T06.01)

**Status:** ACCEPTED; 2026-10-20.

**Authority:** Owner answers in chat, 2026-10-20: subset "60 documents, 12 questions"; comparators "All three, one after another"; limits "300 calls, 900k tokens, 20 s pace".

**Question:** What may the live cold-state run of R4, R5 and R6 spend, and on what?

**Why:** E-B06-001 showed the full tier does not fit the free tier. The owner chose a matched subset and stated limits so the pilot measures real extraction cost and failures without a runaway.

**Options:** a smaller or larger subset (36 or 100 documents); LightRAG alone first; other call and token limits.

**Recommendation:** the options chosen.

**What affects what:** per comparator, in the order R6, R4, R5: at most 300 provider calls and 900,000 tokens (prompt plus completion as the provider reports them), at least 20 seconds between calls, completion capped at 700 tokens, model `qwen/qwen3.8-27b` only (the proxy refuses any other and has no failover), no judge call, no retry beyond what counts against the call cap (a rate-limited and a failed call each use a call). Enforced outside the comparator by the counting proxy; the proxy refuses everything once a cap is reached and a comparator that cannot finish indexing inside its cap is reported as FAILED with its spend, never extended. Embeddings are local and spend nothing. The subset is `artifacts/fixtures/Ssub60`: 12 questions, 60 documents, 103 chunks (BADR-0031 rule, seed 7). Any further live use, a larger subset or a second attempt needs a new owner instruction.

**My answer (editable):** Authorized as above for one run per comparator.

**Verification:** each run directory holds `proxy.jsonl` (one row per call) and `spend.json` (calls, tokens, refusals against the limits); E-B06-004 records the counts and failures.

## BADR-0033 — Resume the R6 pilot on gpt-oss after a per-minute output-token wall (B06-T06.01)

**Status:** ACCEPTED; 2026-10-20.

**Authority:** Owner answers in chat, 2026-10-20: "look cant we just resume this? and is the rate limit only to qwen models? you know it is fine if we switch models as well"; model "gpt oss 120B, if it hits the same problem then GPT OSS 20B"; cap "300 calls, 900k tokens".

**Question:** The first full R6 attempt (run directory now `artifacts/runs/g-r6-qwen-stopped`, qwen) stopped by me at 243 calls: 80 OK, 163 rate-limited (HTTP 429), about 211,000 tokens, the provider's answer being a per-minute output-token limit of 1,000 for that model. How is R6 finished?

**Why:** Calls that were rate-limited counted against BADR-0032's cap and bought nothing; Groq limits are per model; LightRAG keeps its finished extractions on disk, so the work already paid for need not be repeated.

**Options:** record R6 as failed; wait and retry on qwen; resume on a different approved model; restart cold.

**Recommendation:** the option chosen.

**What affects what:** a new run `g-r6-b` copies the comparator state of `g-r6` (`--resume-from`; `g-r6-qwen-stopped` stays as it was) and finishes extraction on `openai/gpt-oss-120b`; only if that model also hits a wall, one further resumed run on `openai/gpt-oss-20b`. One model per run (the proxy still refuses any other and has no failover). Each run has its own authorization of at most 300 calls, 900,000 tokens, at least 20 s between calls, completion capped at 700, no judge call; rate-limited calls count. The index therefore mixes models (qwen for the first 80 calls, then gpt-oss) and the retrieval-time keyword calls use the resumed model; this is a recorded deviation and the result is a pilot, not a like-for-like score. Combined spend is reported across `g-r6-qwen-stopped` and the resumed runs. R4 and R5 keep their own 300/900k authorization each and are not yet run. Any further attempt needs a new owner instruction.

**My answer (editable):** Authorized as above.

**Verification:** each run directory holds `proxy.jsonl` and `spend.json` (with `resumed_from`); E-B06-004 reports both segments.

## BADR-0034 — R6 resumed on qwen at a 60 s pace after the gpt-oss attempt failed (B06-T06.01)

**Status:** ACCEPTED; 2026-10-20.

**Authority:** Owner answer in chat, 2026-10-20: "Resume on qwen, 60 s pace".

**Question:** The `g-r6-b` run (BADR-0033, `openai/gpt-oss-120b`) made 13 calls and every one was cut off at the 700-token completion cap with empty content (about 698 reasoning tokens each), so the build FAILED. How is R6 continued?

**Why:** gpt-oss models spend the whole completion budget on hidden reasoning, so they cannot answer inside the owner's 700 cap; qwen answered 80 calls; its wall was 1,000 output tokens per minute, and with each call reserving up to 700, one call per 60 s stays under it.

**Options:** resume on qwen at 60 s; raise the cap to 2000 on gpt-oss; stop and record R6 as failed.

**Recommendation:** the option chosen.

**What affects what:** run `g-r6-c` copies the comparator state of `g-r6-b` (a superset of the qwen run's finished extractions) and finishes on `qwen/qwen3.8-27b`, at most 300 calls, 900,000 tokens, 60 s between calls, completion capped at 700, no failover, rate-limited calls count. The gpt-oss-20b fallback of BADR-0033 is withdrawn (same reasoning behavior). Spend across `g-r6-qwen-stopped` (243 calls), `g-r6-b` (13) and `g-r6-c` is reported together. Any further attempt needs a new owner instruction.

**My answer (editable):** Authorized as above. Owner, 2026-10-20: the "300 calls, 900k tokens" of BADR-0032 means per run; the 410 calls of the six R6 runs are accepted as within it.

**Verification:** `proxy.jsonl` and `spend.json` in each run directory; E-B06-004.

**Amendment, 2026-10-20 (BADR-0034):** run `g-r6-c` made no provider call and failed to build: the upstream skips failed documents when a stored id is inserted again, so nothing was reprocessed (a defect of the benchmark's LightRAG worker, not of the provider). The worker now marks this corpus's failed documents pending, drops the duplicate records, inserts only ids not yet stored, and runs LightRAG with one model call and one insert at a time (the proxy dispatches one call at a time, and parallel writers collided on Windows with "access denied" in the first run). Tested with a provider that truncates, then a provider that answers, over one working directory. The same authorization (300 calls, 900,000 tokens, 60 s pace, qwen) is used once more as run `g-r6-d`, resumed from `g-r6-c`; no call was spent by `g-r6-c`.

## BADR-0035 — R6 resumed on gpt-oss-120b with a 2,000-token completion cap after qwen's daily limit (B06-T06.01)

**Status:** ACCEPTED; 2026-10-20.

**Authority:** Owner answer in chat, 2026-10-20: "Allow gpt-oss with 2000 cap".

**Question:** Run `g-r6-d` (qwen, 60 s pace) made 31 provider calls (the book has 43 rows, 12 of them local embeddings), 3 answered and the rest rejected by Groq's limit of 200,000 tokens per day for that model, which the earlier attempts had used up. How does the R6 pilot continue?

**Why:** R6 has 36 of 103 chunks indexed. qwen has no quota left today; gpt-oss models have their own quota but spend the 700-token cap on hidden reasoning (BADR-0034), so they need a larger completion cap.

**Options:** wait for the quota; record the pilot as quota-blocked; gpt-oss with a larger cap.

**Recommendation:** the option chosen (the owner's).

**What affects what:** run `g-r6-e` is resumed from `g-r6-d` and uses `openai/gpt-oss-120b` only, with the completion cap raised from 700 to 2,000 for this run (the owner's explicit change), at most 300 calls and 900,000 tokens (unchanged), 30 s between calls (above the 20 s minimum), no failover, rate-limited calls counted. The index mixes models and cap settings (qwen for the first part; gpt-oss after), a recorded deviation: this is a pilot, not a like-for-like score. Spend across all R6 runs (`g-r6-qwen-stopped`, `g-r6-b`, `g-r6-d`, `g-r6-e`) is reported together. R4 and R5 are not run on this authorization. A further attempt needs a new owner instruction.

**My answer (editable):** Authorized as above.

**Verification:** `proxy.jsonl` and `spend.json` of each run; E-B06-004.

## BADR-0036 — R6 resumed on gpt-oss-20b after gpt-oss-120b's daily limit (B06-T06.01)

**Status:** ACCEPTED; 2026-10-20.

**Authority:** Owner answer in chat, 2026-10-20: "Finish on gpt-oss-20b".

**Question:** Run `g-r6-e` (gpt-oss-120b, completion cap 2,000, 30 s pace) made about 80 provider calls and about 251,000 tokens (65 answered, the rest rejected) before Groq's limit of 200,000 tokens per day for that model stopped it; R6 had 58 of 103 chunks indexed. How is R6 finished?

**Why:** Each model has its own daily quota; gpt-oss-20b is the owner-approved smaller model (ADR-0036 of the system project) and has not been used today.

**Options:** gpt-oss-20b; record the pilot and run later; wait for the quota window.

**Recommendation:** the option chosen (the owner's).

**What affects what:** run `g-r6-f` is resumed from `g-r6-e` and uses `openai/gpt-oss-20b` only, completion cap 2,000, at most 300 calls and 900,000 tokens, 30 s between calls, no failover, rate-limited calls counted. The R6 index now mixes three models (qwen, gpt-oss-120b, gpt-oss-20b), a recorded deviation; the result remains a pilot, not a like-for-like score. If this model also reaches a limit the run is stopped and R6 is reported as partial. R4 and R5 are not run on this authorization. A further attempt needs a new owner instruction.

**My answer (editable):** Authorized as above.

**Verification:** `proxy.jsonl` and `spend.json` of each R6 run; E-B06-004.

## BADR-0037 — The benchmark is the owner's private experiment, scoped to the free tier (standing posture)

**Status:** ACCEPTED; 2026-10-20.

**Authority:** Owner message in chat, 2026-10-20: "it is fine doing switching models for testing, or even using your own subagents or even stopping some of the work. Palladion is simply an experiment of mine and palladion-benchmark is my own way of seeing did my hypothesis work, I will not claim it publicly this is a proper research paper ... the benchmark can be suited and tailored as per what we have and as per the constraints (I'm not buying API keys for side projects)."

**Question:** How strict is the benchmark's scope, given a private experiment on free-tier quotas?

**Why:** Free-tier daily token limits (200,000 per model per day) stopped three consecutive R6 attempts; the owner does not intend a public research claim.

**Options:** keep the full-protocol scope and wait for quota; or tailor the scope to what the free tier allows.

**Recommendation:** the second (the owner's).

**What affects what:** (1) Switching among the three approved Groq models for live runs is allowed without asking each time, recorded per run (which model, which cap), never hidden. (2) Live comparator runs are best-effort pilots: a comparator that cannot finish within the free quota is reported as partial or quota-blocked with its spend, not extended with new money and not waited on; stopping a run early is allowed. (3) The matched subset, caps and pacing may be tailored to the quota. (4) Subagents may be used beyond the adversary and auditor where useful (the model rule for them is unchanged: Haiku 5.5). (5) Unchanged: no fabricated, imputed or silently dropped result; failures and partial runs are results; no secret in a repository or a subagent; no purchase of keys; the information barrier; claims stay descriptive and private (no "best RAG", no public research claim). Wording that promises seal-grade or publishable rigor in the README and report (B08-T07.01) is to be written as a private experiment with its limits.

**My answer (editable):** Accepted as above.

**Verification:** E-B06-004 reports each R6 segment with its model; B08 documents carry the private-experiment framing.

**Closure, 2026-10-20 (BADR-0037):** owner chose "Accept partial, close B06": B06-T06.01 is closed with its limits written in E-B06-004 and E-B06-005 (R6 63 of 103 chunks, no query answered; R4 and R5 not attempted; R7a not run on the subset). Completing the live graph runs stays optional (BR39).

## BADR-0038 — The benchmark may change Palladion where a card needs it (supersedes the edit ban of BADR-0002 for B07 onward)

**Status:** ACCEPTED; 2026-10-21.

**Authority:** Owner message in chat, 2026-10-21: "for context the other guy has stopped working on @palladion so from this point on forward you may change palladion if it is necessary".

**Question:** BADR-0002 forbade editing or staging anything under `palladion/` because another contributor owned it. That contributor has stopped. What may the benchmark work now do to Palladion?

**Why:** B07 needs E3 and E4 over Palladion's message interface, and OQ11/PF06 left the critic-off arm reachable only through Palladion's own Python evaluator, not through HTTP; a model client that talks only to the provider also bypasses the counting proxy.

**Options:** keep the ban and mark E3/E4 FEATURE_NOT_SUPPORTED; edit Palladion freely; edit Palladion only where a benchmark card cannot be built or proven otherwise.

**Recommendation:** the third.

**What affects what:** (1) A change under `palladion/` is made only when a named B07 card cannot be built or proven without it, it is the smallest change that does so, and it is justified in this log before it is made. (2) Palladion's own rules apply to such a change (root `AGENTS.md`: ADR in `palladion/docs/development/ADR_LOG.md`, tests, evidence, its locked decisions and its "no serving bypass" rule unchanged; graph stays off by default). (3) Benchmark code still reaches Palladion only over HTTP and never imports it (BADR-0002's second half stands); a server-side wiring change in Palladion's launcher is allowed because it is configuration of the system under test, not an import. (4) Because Palladion then moves, R7a and any later arm are re-pinned to the new commit; recorded results keep the pin they were produced under. (5) Commits touching `palladion/` are separate from benchmark commits, and pushing them needs the owner's approval (root `AGENTS.md`), asked before the first such push.

**My answer (editable):** Accepted as above.

**Verification:** each Palladion change is listed with its card, its Palladion ADR and its tests in E-B07 evidence; `git diff --name-only` for a benchmark commit shows no `palladion/` path.

## BADR-0039 — B07 scope: how E3 and E4 are defined, what Palladion gets, and what is not observed

**Status:** ACCEPTED; 2026-10-21.

**Authority:** Owner answers in chat, 2026-10-21 (AskUserQuestion after the B07 adversary, E-B07-001): "Yes, evaluator-only flag"; "Approve the list"; "Principal + case per episode"; "Defer to B08 as NOT_RUN". The owner's instruction to finish B07 end to end and BADR-0038 give the rest.

**Question:** The adversary showed E4 is already Palladion's default serving path but E3 (critic removed) has no HTTP path, that Palladion's model client cannot be counted by the benchmark, that its policy and operational claims cannot be released without the critic's review, that private memory crosses cases by principal, and that the oracle policy tool would be circular. How is B07 scoped?

**Why:** Fairness controls (protocol 3.1) need every model call counted and capped outside the system, a frozen clock, and one version of the system; Track C needs isolation between independent episodes.

**Options:** E3 FEATURE_NOT_SUPPORTED; an evaluator-only launcher option; a request-level switch (rejected: it would be a serving bypass).

**Recommendation:** the evaluator-only launcher option, with the narrowest set of Palladion changes.

**What affects what:** (1) **E4** is Palladion's default serving path at the new pin. **E3** is Palladion's own evaluator control B5 (critic removed, final gate kept), started by a launcher flag that needs an explicit acknowledgement; it is a distinct, disclosed treatment: because the gate releases policy results, rule requirements and operational guidance only after a review, E3 reports those as unavailable, and its numbers are not read as 'the architecture without the critic' on those strata. E3 is never labelled E4. (2) **Palladion changes** (BADR-0038, each with a Palladion ADR first, tests, default serving byte-identical, 'no serving bypass' unchanged): B07-T00.01 loopback-only model base URL, key from a named environment variable, completion cap and request deadline as launcher parameters, a settings-file argument; B07-T00.02 evaluator mode with a response evaluator block; B07-T00.03 an injected evaluation clock; no other Palladion change without a new entry. (3) **One pin** for R7a, E3 and E4 (B07-T00.04); results already recorded keep 6444345. (4) **Observation:** token and call counts come from the counting proxy's book; Palladion's own counts are kept as self-reported with a divergence flag; a metric that needs data no interface returns (memory contents, tool arguments) is NOT_OBSERVABLE, never zero or estimated. (5) **Episodes:** one provisioned principal and case per independent episode (the episode's token registered by the evaluator-mode launcher), so private memory does not cross episodes; no state reset inside an episode; the reload cost is measured and reported. (6) **Oracle policy-tool condition (protocol 9.4):** NOT_RUN in B07 with its reason (the generator's resolver built the gold, so a tool built from it is circular); an independent policy evaluator is a B08 task. (7) **Not built for Palladion at this pin:** M07 and M15 (graph is off, Neo4j is OQ12); mutations that need server state no interface sets (M08, M11, M12 if the clock option proves insufficient) are recorded NOT_RUN or FEATURE_NOT_SUPPORTED per system. (8) **Approved quotes:** a verbatim quote of an approved document that is non-normative or an injection text is released as 'Approved source states'; it is scored as an authority-confusion candidate, not as a verified fact (BR43). (9) **Models:** each Palladion server runs one model (BADR-0008 amended for these arms: the model used is recorded per run and the pilot uses one model for all arms of a question); one completion cap for all arms is set with the pilot limits. (10) **Live use:** none until the owner states limits for B07-T09.01 (BADR-0030 stands); downloads of LangChain, LangGraph and Google ADK need the owner's approval by name (OQ14, B07-T00.05); no Google access probe without approval (OQ07).

**My answer (editable):** Accepted as above.

**Verification:** E-B07-001 holds the adversary receipt and dispositions; each Palladion change lists its Palladion ADR, tests and evidence; the plan, gates and checker reflect the new cards.

## BADR-0040 — Downloads for B07: the LangChain and LangGraph environment and one Palladion wheel

**Status:** ACCEPTED; 2026-10-21.

**Authority:** Owner answers in chat, 2026-10-21: "Yes, install (Recommended)" for langchain-core, langchain-text-splitters, langgraph and langchain-openai with dependencies into an isolated Python 3.12 environment; and "Yes, that wheel only (Recommended)" for the one Palladion dependency missing from the local cache.

**Question:** E0 and E1 need LangChain and LangGraph; the isolated Palladion at its new commit needs its locked environment. What may be downloaded?

**Why:** OQ14 and BADR-0031 item 7: nothing is downloaded before the owner approves that artifact.

**Options:** install the packages; mark E0 and E1 NOT_RUN; reuse another environment (they conflict on pydantic and openai versions).

**Recommendation:** the first.

**What affects what:** (1) `artifacts/comparators/env-langchain` (gitignored) on uv-managed CPython 3.12.15 holds `langchain-core` 1.6.7, `langchain-text-splitters` 1.1.3, `langchain-openai` 1.6.7, `langgraph` 1.2.14 and `openai` 3.26.0, installed with `uv pip install --exclude-newer 2026-10-07` (the latest releases at least two weeks old); measured size 45 MB; `scripts/comparators.py framework E1` verifies exactly these versions and records the lock digest `4ac56681ff6c...` (first 12 characters). Google ADK (E2) is recorded and not installed. (2) For the isolated Palladion at `4af66d6` (`artifacts/palladion-4af66d6/palladion/.venv`) `uv sync --frozen` fetched what the local cache lacked, starting with `pytz` 2026.5; the lock file's hashes are checked by uv. Later syncs use `--offline` so the launcher never downloads without approval again. No other download in B07 is approved; a model download for any framework would need its own approval.

**My answer (editable):** Approved as above.

**Verification:** `scripts/comparators.py framework E0|E1` output; tests in `tests/test_comparators.py`; E-B07-002.

**Addendum, 2026-10-21 (BADR-0040):** `numpy` 2.5.3 was added to `env-langchain` on the owner's approval ("Yes, install numpy"): `InMemoryVectorStore` needs it to compute cosine similarity and langchain-core lists it only as an optional extra. The environment is 99 MB after it. The framework pin now names it; the lock digest changes accordingly.


## BADR-0041 — Palladion episodes are isolated by principal and session in the corpus case; the pin moves to `eec4ba5` (amends BADR-0039)

**Status:** ACCEPTED; 2026-10-21.

**Authority:** Owner answer in chat, 2026-10-21: "Principal per episode, shared case (Recommended)". The pin move is the consequence of BADR-0038 (a Palladion change committed apart from benchmark work).

**Question:** BADR-0039 chose one provisioned principal and one case per independent episode. Can Palladion's cases hold the corpus?

**Why:** Measured on the isolated runtime: a principal provisioned through `POST /v1/admin/principals`, `/v1/admin/cases` and a membership of a new case `case-ep-1` searches that case with HTTP 200 and **0 passages**, while the same search in `case-42` (where the corpus was uploaded) returns passages. Sources belong to the case they were uploaded under, so a case per episode would need the 1,200-document corpus uploaded again for every episode and arm.

**Amended 2026-10-22 (audit):** BADR-0039 item 5 and BR41 still say "principal and case per episode"; BADR-0041 supersedes that to principal and session per episode in the corpus case. Mutation cases ask as one further principal that no episode uses (`mutation-cases`).

**Options:** (a) one principal per episode and heat, a member of the corpus case, with a fresh session per episode; (b) a case per episode with a copy of the corpus; (c) reset the runtime between episodes.

**Recommendation:** (a): the smallest change, no re-upload, and the cross-episode leakage measure (`benchmark/eval/memory.py`) counts any residue instead of assuming there is none.

**What affects what:** (1) `scripts/run_track_c.py` provisions `usr_…` principals with the grants `source:read` and `case:read`, adds each to `case-42`, writes a token for each into the runtime's operator-owned `demo_auth.json` and only then starts the evaluator servers. (2) Private (USER) memory is keyed by principal and the session is new per episode, but case-scoped records (policy decisions, case events of the case) stay shared; a fact that crosses episodes through them shows up as leakage. A hot repeat (same episode, same principal) is the only condition that keeps memory. (3) E3 and E4 share one Palladion state, so a mutation made for one is visible to the other; the entry point refuses both arms with mutation cases in one run and the pilot runs them one at a time on a freshly prepared runtime (the added documents are revoked after each case, and a revoked base document is reported as not restorable). (4) The pin in `configs/comparators.yaml`, `scripts/palladion_runtime.py` and `tests/test_config_loader.py` moves from `4af66d6` to `eec4ba5` (Palladion commit "make the application own the injected evaluation clock"); results recorded at `6444345` keep their pin.

**My answer (editable):** Approved: principal per episode, shared case.

**Verification:** probe output in E-B07-002; `tests/test_track_c.py` (isolation, leakage control); the smoke runs `c-smoke`, `c-smoke-fw`, `c-dry`.

## BADR-0042 — Limits for the live Track C pilot (B07-T09.01; OQ14)

**Status:** ACCEPTED; 2026-10-21.

**Authority:** Owner answer in chat, 2026-10-21: "Palladion arms only, ~1 day (Recommended)": E3 and E4, two episodes of four turns and four mutation cases (M01, M09, M13, M14); per arm 250 calls, 150,000 tokens, 700 completion tokens, 20 s pace. E0 and E1 stay offline-proven and are run on a later day only if the owner asks.

**Question:** Which live limits apply to the first Track C pilot?

**Why:** BADR-0030 and BADR-0032: no live use until the owner states limits for the run; the free tier gives about 200,000 tokens per day per model.

**Options:** Palladion arms only; all four arms over two or three days; no live pilot.

**Recommendation:** the first: the dry-run estimate (`c-dry`) is 36,648 prompt tokens and at most 21,000 completion tokens for E3, 66,854 and 33,600 for E4, inside the caps; E0 and E1 add embedding work and baseline conditions that the day's quota would not cover.

**What affects what:** (1) One model, `qwen/qwen3.8-27b`, for every call of a run (BADR-0039); no failover. (2) The caps are per arm and enforced by that arm's counting proxy (`--call-cap 250 --token-cap 150000 --pace-seconds 20 --max-completion-tokens 700`; the pace was later raised to 45 s, see the addendum). A run-wide tool-call cap (episodes x 6 x 8 + cases x 16 = 160 for the pilot) is set by the script, is not an owner limit, and only ever lowers what an arm may do. (3) E3 and E4 run in two invocations, each on a freshly prepared runtime (BADR-0041). (4) A cap, a daily-limit stop or a failed call is recorded in the ledger and the summary; nothing is retried by hand and nothing is dropped. (5) The estimate and the measurement are reported side by side. (6) No confirmatory claim.

**My answer (editable):** Approved as above.

**Verification:** `artifacts/runs/c-live-e3`, `artifacts/runs/c-live-e4` (`summary.json`, `ledger.jsonl`, `proxy-*.jsonl`), E-B07-003.

**Addendum, 2026-10-21 (BADR-0042):** the first live attempt, `artifacts/runs/c-live-e3`, was a harness fault and is kept as a result, not rerun silently. Palladion's connection used the adapter's 60 s client timeout while a message takes several paced model calls (20 s apart), so 7 of 8 turns and 3 of 4 mutation asks ended as TIMEOUT on the client side while the server went on spending: the proxy's saved book shows 31 calls (the run's totals said 32), 70,774 prompt and 5,923 completion tokens (76,697 of the day's ~200,000) for answers nobody read, 8 of them rate-limited (HTTP 429 per minute) and one 413. Corrected: the connection timeout is now Palladion's own request deadline plus 30 s (`PalladionArm(timeout=)`), and the pace is 45 s instead of 20 s, which is a slower rate inside the owner's limits (it can only lower calls per minute); the call, token and completion caps are unchanged. Because the day's quota is partly spent, E3 runs now and E4 on a later day, each on a freshly prepared runtime (BADR-0041).

**Addendum, 2026-10-22 (BADR-0041, end-of-phase audit):** (1) The entry point now refuses `--arms E3,E4` in one invocation whether or not mutation cases are requested: both servers would run on one database with the same principals, and private memory is keyed by principal. (2) Each run's limits (caps, pace, completion cap, timeouts) are written into its manifest, and a live run must name the call cap, token cap and pace. (3) The audit also found, and I fixed in Palladion (commit `dd70c0e`, ADR-0101 second addendum), a wall-clock read in memory recall and a launcher path that could send the root `.env` key to a custom model address. The pin stays `eec4ba5`: the live pilot ran there, and the next live run re-pins to the commit that has these two fixes.


## BADR-0043 — B08 re-plan: a descriptive comparison of Palladion against the other systems under the free tier (OQ10, OQ13, OQ14)

**Status:** ACCEPTED; 2026-10-22.

**Authority:** Owner answers in chat, 2026-10-22: "Descriptive comparison, not sealed"; Track B "spread over several days"; systems "all, as much as possible with the limit" (R0 to R3 with R7a, E0/E1 against E3/E4 on Track C, the graph comparators R4 to R6, and a re-pin of Palladion to `dd70c0e` first); OQ10 and OQ13 "use defaults, label as exploratory". The owner's end goal for B08: at least a report of what Palladion scores against the other systems, on the protocol's measures, with every constraint applied, the cost constraints included.

**Question:** What does B08 deliver when the sealed confirmatory run (600 test questions, 100 episodes, three repetitions, all arms, both tracks) cannot be afforded on the free tier?

**Why:** B04 to B07 produced arms and one partial live pilot each; no system arm has a measured result that supports a ranking (PROGRESS). A sealed run needs the M tier, OQ10 and OQ13 answered, and quota the free tier cannot give in one go (about 200,000 tokens a day per model; a Palladion turn cost a mean of 14,204 prompt tokens, and a graph comparator index about 4 million tokens per system on the S tier). The owner wants a comparison now, with the limits stated.

**Options:** (a) B08 as written (seal, then confirm), blocked on quota, OQ10 and OQ13; (b) a descriptive comparison on the S tier, retrieval first, then answer-level and system-level on matched subsets over several days, labelled exploratory; (c) retrieval only.

**Recommendation:** (b), in the order that spends nothing first.

**What affects what:** (1) **Claim level.** Every result is exploratory and descriptive: no seal, no confirmatory claim, no "best RAG", no composite winner (protocol §19.4; B08-T06.01 unchanged). Pairings are the defaults of OQ10 (R7 against R3, E4 against E3, Holm) and the delegated labels of OQ13 are accepted for now and flagged, so BG-GOLD stays PARTIAL and BG-PREREG stays NOT_RUN. (2) **B08 cards.** B08-T01 (M tier), T02 (tuning, power, security-suite sizing), T03 (seal), T04 (confirmatory run) and T05 (ablations) are not run on this path; they stay open, not closed, and their dependency on OQ10 and OQ13 is untouched. The new cards B08-T08.01 to T08.06 deliver the comparison; B08-T06.01 and T07.01 report from them. (3) **Order.** Re-pin Palladion to `dd70c0e` and re-run the gates; then Track A on the full S tier for R0 to R3, R7a and R7b (no model, no quota; conditions C1 and C2); then Track B on one matched, fixed question subset over several days; then Track C for E3, E4, E0 and E1 on a matched episode subset; then the graph comparators R4 to R6 as quota allows, resumed across days. (4) **Matching.** Every system answers the same question and episode lists, fixed before the first spend and recorded in the manifest; a system that cannot finish its list reports how far it got, and the report states the common subset and each system's own coverage; nothing is dropped (BADR-0037). (5) **Limits per live day and arm** are those of BADR-0042 (250 calls, 150,000 tokens, 700 completion tokens, a pace of at least 45 s for Palladion), one model per run, no hidden failover (BADR-0008); a daily limit or a cap ends that day's run and is recorded. The owner states other numbers by telling me. The graph indexes keep their own limits from BADR-0032 to BADR-0036. (6) **Cost axis.** Every system is reported with the calls, prompt and completion tokens, wall time and daily-limit stops measured by its counting proxy, beside the quality measures; the estimate and the measurement are never mixed. (7) **Downloads** still need the owner's approval by name (OQ14); none is planned. (8) **Systems that cannot be compared** stay NOT_RUN or FEATURE_NOT_SUPPORTED with the reason (E2: no access; M09 on Palladion). (9) **Palladion changes.** None planned; one found necessary follows BADR-0038.

**My answer (editable):** Approved by the owner's chat answers above.

**Verification:** `check_docs.py`; the matched lists and limits in each run's manifest; one evidence entry per card as it closes.


## BADR-0044 — B08 comparison: quota horizon, model policy, quota-blocked outcome, fairness repairs and sizes (adversary E-B08-001)

**Status:** ACCEPTED; 2026-10-27.

**Authority:** Owner answers in chat, 2026-10-27, to the pre-phase adversary's four questions: "About 4 days, 3 models"; "Per-question assignment, one equal cap"; "Yes, record and resume next day"; "Restart R6 cold on qwen, R4/R5 if quota remains". The other points below follow from the adversary's confirmed findings and are inside BADR-0043; I decided them and the owner may overrule any.

**Question:** How is the comparison sized and run so that it is fair, honest about the free tier, and finishable?

**Why:** The adversary (E-B08-001) confirmed that a full matched comparison needs about 5 to 7 million tokens (25 to 37 model-days on one model) against 200,000 tokens a day per model; that a provider's daily refusal is written as a final INVALID_RUN and can never be retried; that "one model per run" contradicts the one-model-per-question rule (BADR-0008); that R7a is filtered after ranking, sent no `as_of`, and mapped to one reader; and that the pairing, Holm, harm-metric and report code the cards presuppose is not wired.

**Options:** as asked in chat; the rest were decided on the evidence.

**Recommendation:** as accepted.

**What affects what:** (1) **Horizon.** About four days of quota on three models (about 2.4 million tokens). The day count is a horizon, not a promise: work is ordered by priority (Track A, which costs nothing; Track B; Track C; graph arms) and whatever is unfinished when the quota or the horizon ends is reported with its coverage, never extended or bought (BADR-0037). (2) **Sizes (fixed before the first spend in a frozen matched list).** Track A: all 97 scoreable S-tier questions of the single split that exists (`smoke`; S has no dev or test annotations, `annotations_test` is empty), under C1 and C2. Track B: a seeded, stratum-balanced list of 40 of the 87 Track-B-eligible questions for each of R0 to R3 and R7a (200 pairs, about 0.6 million tokens). Track C: 2 episodes for each of E0, E1, E3, E4 (four turns each) and three mutation cases (M01, M13, M14) for E3 and E4 only. Graph arms: R6 cold, then R4, R5 with leftover quota, on the 60-document subset, with R0 to R3 and R7a also run on that subset for a matched comparison. The 8 questions of the earlier live pass (`b-live-1`, other settings) stay history and are not merged. (3) **Model policy.** Track B: each question is assigned one of the three approved models before any arm runs (`assign_models`, BADR-0008), the same model for every arm on that question, one completion cap of 2,000 tokens for every call (so no arm has a different budget), the assignment recorded in the plan digest and each call's model recorded; results are reported pooled and by model. Track C: all four systems on one model, qwen (Palladion's validated model); a Palladion arm and its control never differ in model. Graph arms: one model per arm build (BADR-0033 to BADR-0036 stand). (4) **Quota-blocked outcome.** A provider refusal whose window is a day (`TOKENS_DAILY`, `REQUESTS_DAILY`) is no longer a final INVALID_RUN: the call is recorded as `QUOTA_BLOCKED` (a NOT_RUN kind, harness-attributed), the pair stays pending, the run stops starting new calls, and the same run directory is resumed after the quota resets. Both attempts stay in the ledger; reports count quota-blocked pairs apart and never score them as an arm's failure or as zero. Per-minute refusals keep their retry and final handling. (5) **Fairness repairs for R7a before it is measured:** one Palladion reader per benchmark principal (PF05 provisioning, as Track C already does), `as_of` set to the case's evaluation time (PF01), and the neutral C2 filter applied inside the candidate pool, not after truncation; an arm or stratum that cannot be made equal is reported as a capability difference and excluded from the paired claim. R7a stays the plain HTTP path (no benchmark alias script). (6) **Pairing.** R7 (the full retriever) is unpinned and not built, so the primary retrieval pairing is R7a against R3; the primary system pairing is E4 against E3 (BADR-0043 defaults); everything else is exploratory, Holm-adjusted, with intervals clustered by scenario family; strata with too few clusters are marked descriptive. (7) **Harm metrics** are reported over every eligible pair (a pair that did not complete is a "not completed" count, never a harm and never a zero) beside the conditional rate. (8) **Cross-run guard.** The plan digest includes the system-under-test commit, K, budget, condition and model assignment; a report refuses to pool runs that differ in any of them. Results at earlier pins (`6444345`, `eec4ba5`) are history and never pooled with `dd70c0e` results. (9) **Systems that cannot be compared:** E0 and E1 mutation cases are NOT_RUN (no live-status tool), and live-status turns are a capability difference for them; R7b is FEATURE_NOT_SUPPORTED (a link route exists, but no graph store, OQ12, and no link-selection rule, BR34); E2 NOT_RUN; ablations A01 to A16 are not run except where an arm contrast is the ablation (A01 and A03 appear as R0 to R3 contrasts, stated as such). (10) **Cost axis.** Query-time calls, tokens and wall time come from the counting proxies; offline build cost is reported apart; local arms' tokens are NOT_OBSERVABLE, not zero; Palladion's coverage-check setting (PF03) is recorded. (11) **No repetitions:** every generative result is a single run at temperature 0 and is labelled so (protocol §14.4 asks for three; not affordable). (12) **Subagents:** Haiku 5.5, medium, start adversary and end reviewer only (BADR-0003).

**My answer (editable):** Approved by the owner's chat answers above for items 1 to 4; items 5 to 12 are the coordinator's decisions on the adversary's evidence.

**Verification:** E-B08-001; tests and run directories named in each card.

**Addendum, 2026-10-27 (B08-T08.08):** item 5 said the neutral filter would be applied inside the candidate pool. Reading Palladion's source showed a better equivalent: Palladion enforces a per-document `allowed_principal_ids` list in its index filter before ranking, and PF05 lets the benchmark provision a reader per principal. Under C2 the arm therefore gives each principal a reader and uploads each restricted document with the readers the neutral rule allows, and it no longer masks Palladion's output; a returned document the neutral rule would refuse is counted as `acl_leaked` and stays in the output, so any disagreement is scored as exposure. The same three guarantees hold (access before ranking, same rule, no hidden filter), and the check that it works is read back through Palladion (`verify_acl`). The cost is that one Palladion corpus load serves one condition. `as_of` is the case's evaluation time (PF01). Verification: E-B08-004.

**Addendum, 2026-10-27 (B08-T08.09):** (1) Track A asks all 100 questions of the one split S has and scores 97 (the three withdrawn questions stay in the ledger, BADR-0026); item 2 said 97. (2) The Track B model assignment is owned by the frozen matched list, not recomputed from `configs/benchmark.yaml`: the shipped default keeps its null budgets (the earlier pilots and 16 tests depend on them), `scripts/freeze_matched.py` takes the per-model shares on its command line, and `run_track_b.py --matched-list` uses the frozen assignment and refuses a list whose questions are not exactly the ones asked. Verification: E-B08-005.

**Addendum, 2026-10-27 (B08-T08.03, owner answers in chat):** (1) The per-model daily token cap of BADR-0042 is raised from 150,000 to 190,000 tokens for the rest of this comparison ("Raise to 190,000"); the provider's own limit (200,000) is unchanged and still stops a call. The first Track B day measured 1,750 to 2,400 tokens a call and stopped both gpt-oss models at 150,000 with 21 pairs pending. (2) Track C is shrunk to one episode and two mutation cases per arm ("Shrink to 1 episode + 2 cases"), because the measured cost (about 15,000 tokens a turn for E3 and about 27,000 for E4) put the frozen list at about 600,000 tokens; the Track C list is frozen again in its own file before the first Track C spend, and the Track B and Track A lists are untouched. Verification: E-B08-008.

## BADR-0045 — Licenses for the fixtures and the code (OQ09)

**Status:** ACCEPTED; 2026-10-27.

**Authority:** Owner answer in chat, 2026-10-27: "MIT code + CC BY 4.0 data".

**Question:** Under which licenses are the synthetic fixtures and the benchmark and generator code published?

**Why:** Protocol 19.3 asks for an explicit dataset license, and B08-T07.01 cannot close without one.

**Options:** MIT code with CC BY 4.0 data; Apache-2.0 code with CC BY 4.0 data; no license yet.

**Recommendation:** the first: permissive, common for a benchmark, and attribution for the data.

**What affects what:** `docs/dataset_card.md`, `docs/reproducibility.md`, the README and a `LICENSE` file name the licenses; the dataset card keeps its statement that every document is fictional and not an authentic procedure; the licenses cover this repository's benchmark code and generated data only, not Palladion, the comparators, or the models, each under its own terms. Any change to the benchmark code that includes a third party's work keeps that work's license.

**My answer (editable):** MIT for the code and the generator; CC BY 4.0 for the generated fictional corpus, questions, gold and annotations.

**Verification:** `LICENSE` and the dataset card name the licenses (B08-T07.01).

**Addendum, 2026-10-27 (B08-T08.04, schedule from the measured costs):** the first Track C day (E0 and E1, qwen, 190,000-token day shared by two arms) measured 2,300 prompt tokens a turn for E0 (35,405 tokens for 15 answered turns, 1 turn stopped by the cap) and 13,800 for E1 (its first turn used its whole ceiling of five model calls and four tool calls and is INVALID_RUN, ARM; the second hit a per-minute limit and exhausted its retries; the other 14 turns were stopped by the arm's share of the day, `QUOTA_BLOCKED`). With qwen's day recovering on a rolling 24 hours (the books show 190,000 free at about 12:30 UTC on 2026-10-28), the remaining Track C work is run one arm group per day, each with the whole day: E4 (about 160,000 tokens), then E3 (about 90,000) with the single E0 condition that was stopped, then E1 in two halves of two memory baselines each (`none` and `scoped_episodic` first; `last_n` and `rolling_summary` only if the days allow). E1's missing baselines, if any, are reported as not run for lack of quota, never as a result of E1. The graph comparators are not started: R6 alone needs about 1.1 million qwen tokens (about six days of the model), R4 and R5 are unmeasured, and the four-day horizon of the owner's answer is used by Tracks B and C (priority order of BADR-0044 item 1); the pilot of B06 stands as their only result. Verification: the evidence entry of B08-T08.04 when the card closes.

