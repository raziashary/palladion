# Evidence log

Updated 2026-10-18. Command observations and review receipts, in order. An entry records exact
commands, environment, results, limits and cleanup. A receipt is not behavioral evidence. Entries are
appended; corrections strike the old claim and add a new entry with the mechanism of the error.

## E-B00-001 — Documentation checker, negative self-test and protocol-tree measurement

Task: B00-T01 to B00-T03.01. Gate: BG-DOC. Environment: Windows 11, Python 3.14.7, repository `C:\palladion`, branch `main`.

- Command: `python palladion-benchmark/docs/development/check_docs.py --self-test` (from the repository root, `PYTHONIOENCODING=utf-8`).
  Exit status 0. Observed: PASS 16 Markdown files; 22 sections, 8 hypotheses, 16 ablations, 10 strata, 18 invariants, 19 mutations mapped;
  PASS 87 atomic tasks (8 checked), fields, acyclic dependencies, shared-file writer ordering and ownership of all 70 protocol-tree files;
  PASS 33 in-memory negative checks rejected, repository unchanged. The checker also printed 12 NOTICE lines for cards that wait on open
  decisions or questions (listed in PROGRESS).
- Protocol-tree measurement: a parser over the protocol's repository tree yields 70 file entries, 56 `.py` and 14 other, matching the
  protocol's stated "70 planned files (56 Python and 14 …)". The checker re-derives the count on every run and fails if the stated and parsed
  counts differ.
- Negative controls spot-checked for the intended reason (not merely "some error"): a self-dependency produced "Atomic dependency cycle",
  a dependency on a later phase produced "depends on a later phase", removing a card's file produced "Protocol tree file lacks an atomic owner",
  a proposed ADR with an answer produced "proposed decision must show an OPEN answer", a checked card whose files do not exist produced
  "checked but file does not exist".
- Lint and types: `uv run mypy docs/development/check_docs.py` reported no issues. `uv run ruff check` fixed 16 style findings and left one
  stylistic SIM102 hint (nested `if`), unfixed by choice.
- Limits: the checker validates structure, links, IDs and ownership only. It cannot show that a task is the right size or that a document is
  faithful to the protocol; E-B00-003 is the semantic review. Its repository root is found by fixed path depth.

## E-B00-002 — uv bootstrap

Task: B00-T03.02. Environment: uv 0.13.1, CPython 3.14.7.

- Commands in `palladion-benchmark/`: `uv init --bare --no-workspace --name palladion-benchmark --vcs none`, then `requires-python` edited to
  `>=3.11,<3.15` (BADR-0005), dev group `mypy`, `pytest`, `ruff` added, `uv venv`, `uv sync`, `uv sync --locked`.
- Observed: `.venv` created with CPython 3.14.7; 13 packages installed (ruff 0.17.1, mypy 2.4.0, pytest 9.1.1); `uv sync --locked` resolved 14
  packages and checked 13 with no change; `git check-ignore` confirms `.venv/` is ignored. No runtime dependencies. `uv run pytest` was not run as a
  gate because no `tests/` directory exists yet; running it now would only report that nothing was collected.
- Added dependencies: mypy, pytest, ruff (dev group; purpose: type checks, tests, lint; owning task B00-T03.02).
- Limits: nothing here exercises benchmark code. Clean-clone reproducibility is checked by B01-T01.01.

## E-B00-003 — Independent end-of-phase review (Haiku 5.5)

Task: B00-T04.01. One read-only reviewer requested with model `haiku` (the harness's Haiku tier; the exact model revision is not reported by the
tool and is not verified here). Brief: read the complete protocol and the whole suite, refute fidelity, fairness, dependency logic, consistency
and the checker; no edits, no git, no credentials, no network.

- Coverage claimed by the reviewer: protocol lines 1–1208 in full, master plan 1–1018, all other development documents and `check_docs.py`,
  Palladion suite for format, plus spot reads of Palladion `settings.py`, `api/schemas.py`, `api/routes.py`. It ran the checker read-only.
- Result: 26 findings (7 HIGH, 14 MEDIUM, 5 LOW). The coordinator verified the two load-bearing Palladion claims directly: `critic_max_calls` has
  `ge=1` in Palladion `settings.py:21`, and the `Search` model allows only case, query, mode and `limit` up to 12 with no clock or budget
  (`api/schemas.py`). Both confirmed.
- Dispositions (finding → action → where):
  - F1 seal could precede data → B08-T02.01, T02.02 and the seal now depend on M-tier generation and paraphrase → MASTER_DEV_PLAN.
  - F2 E3/E4 not expressible by configuration → ~~"critic toggled by configuration"~~ corrected; E3/E4 FEATURE_NOT_SUPPORTED without a documented switch; OQ11, BR12; ablation card narrowed.
  - F3 corpus load and native-ingestion unowned → new B04-T03.02; native-ingestion mode added to B04-T04.01 and B08-T04.01.
  - F4 Palladion search cannot honor K=20, budgets or clock → B04-T03.01 changed (harness-side truncation, flags, pinned mode and hops).
  - F5 excluding mixed-model pairs is informative censoring → BADR-0008 recommendation revised to an ITT rule; BR13.
  - F6 generator proof could pass with zero calls → B01-T05.02 proof requires one real response per model.
  - F7 unsupported-directive rate unowned → new B05-T01.02.
  - F8 ablations post-seal and bundled → the sealed list and exploratory labeling added to B08-T03.01 and B08-T05.01; splitting into 16 cards deferred to B08 planning (owner: coordinator at B08 start).
  - F9 unordered shared-file writers → ordering edges added; checker now enforces writer ordering (log files excepted); one self-test added.
  - F10/F11 missing metrics and conditions → added to B03-T03.02, B03-T06.01, B06-T05.01, B07-T05.02, B07-T06.02, B07-T08.01 and new B07-T05.03; RAPTOR/DRIFT remain exploratory without a card (owner B09, not scheduled).
  - F12 partition counts, calibration split, eligibility, effect sizes → B02 and B08 cards extended; OQ06 still gates H4.
  - F13 pilots could read test partition → pilot cards restricted to the smoke partition; validator negative case added in B04-T04.03.
  - F14 R7a mode and hop setting unpinned → pinned in B04-T03.01. Whether Palladion's search uses graph expansion at all is UNCERTAIN until B04.
  - F15 Palladion commit insufficient in a dirty tree → manifest records source-tree digest and dirty list; confirmatory runs refuse a dirty tree.
  - F16 realism checks → added to B02-T06.01 and B08-T01.01. F17 judge independence → B05-T04.02.
  - F18 checker gaps → ownership of development-suite files restricted to the known list; shared-writer ordering; PASS counts computed; notices for waiting cards. Not fixed: fixed-depth repository root (documented), "checked ⇒ evidence" (a checked card is accepted when its files exist; evidence text is reviewed by hand).
  - F19 evidence overstated → this entry and E-B00-001/002 now exist; B00 acceptance text corrected; PROGRESS shows DONE only after E-B00-004.
  - F20 oversized cards → event generation moved to world.py; further splitting left to each phase's pre-adversary (owner: coordinator at phase start).
  - F21 mutation table lacked gold columns → table now states they come from protocol §16.1 and are copied by B07-T07.01; the reviewer's concern about unrestated columns is accepted as a documentation-only choice.
  - F22 traceability overstatement, F25 numeric thresholds → thresholds rule added to TESTING_GATES; per-row wording deferred to each owning phase.
  - F23 mapping inaccuracy and M-tier timing → plan text restated as this plan's own mapping; deviation flagged in BADR-0006. F24 → BADR-0010 lists all six additions. F26 → PROGRESS lists waiting cards.
- Limits: one model review is not independent evidence of correctness; the reviewer did not read Palladion beyond the spot checks and did not read `uv.lock`.

## E-B00-004 — Publication

Task: B00-T04.02. Before commit: checker and self-test passed, secret pattern scan over `palladion-benchmark/` found nothing, `git diff --cached --name-only`
listed 20 files all under `palladion-benchmark/`, `git log origin/main..HEAD` held only the benchmark commit. Commit `5c392f9`
("docs(benchmark): establish benchmark development suite and uv project") was made with a path-scoped `git commit -- palladion-benchmark`, then
`git push origin main` fast-forwarded `64d2066..5c392f9`; afterwards `git status -sb` showed `main...origin/main` with no divergence. Palladion's
uncommitted files were not staged or committed. This entry was added in a follow-up documentation commit.

## E-B01-001 — Pre-phase adversary for B01 (Haiku 5.5, medium effort)

Task: B01 start. One read-only reviewer requested with model `haiku` and effort `medium` (the tool does not report the exact model revision; not verified).
Brief: read the complete protocol, AGENTS, the whole master plan and development records, and Palladion's `llm.py` and `settings.py`; refute the B01 tasks and the
coordinator's intended design; no edits, no git, no `.env`. Coverage claimed: protocol 1–1208 in full, all development documents except EVIDENCE_LOG and PROJECT_MAP.
Result: 24 findings (3 HIGH, 16 MEDIUM, 5 LOW). Dispositions (finding → action → where):

- adv-1 retry vs one-record-per-pair → ledger keyed by run, arm, question and attempt with one final outcome per pair → B01-T04.01.
- adv-2 no recorded spend authorization → BADR-0015 records the owner's instruction, three calls, completion cap 256 and at most six calls → ADR_LOG.
- adv-3 gold barrier by key denylist → allowlist plus value screening in B01-T02.01; subprocess isolation from B04 (owner approved) → BADR-0016.
- adv-4 manifest digest not tamper-evident → digest also recorded in every ledger record, manifest written before the first arm → B01-T03.02.
- adv-5 dirty shared tree cannot be pinned → separate checks, `--no-optional-locks`, pinned worktree rule for B04 → BADR-0016, B01-T03.02.
- adv-6 loader traps → duplicate-key-rejecting loader, pin allowlist, quoted version pins → B01-T02.03.
- adv-7 missing request parameters → all recorded per call, "no provider-exposed revision" stated explicitly → B01-T05.01.
- adv-8 BADR-0007/0008 conflict → owner chose pre-assignment by quota; rule defined in BADR-0015.
- adv-9 stray threads after timeout → arm marked unusable, late results discarded and counted; subprocess later → B01-T04.01, BADR-0016.
- adv-10 mid-case run deadline bias → run-level limits apply between cases only → B01-T04.01.
- adv-11 tests unowned → four test files added to cards → MASTER_DEV_PLAN, checker additions.
- adv-12 dependency omissions → corrected in B01-T05.01 and B01-T05.02.
- adv-13 `native_citation_supported` default → required field with backing rule; owner approved → BADR-0016.
- adv-14 manifest schema gaps → full protocol 7.2 schema → B01-T03.02.
- adv-15 self-reported budgets → two semantics (refuse before dispatch vs unverified self-report) → B01-T03.03; independent source for Palladion calls deferred to B07 (owner: coordinator at B07 start).
- adv-16 key leak on error paths → trust_env false, no redirects, fixed error codes, planted-key test through each path → B01-T05.01.
- adv-17 rerun via new run id → plan-digest registry → B01-T04.01.
- adv-18 mutable frozen fields → deep copy into read-only forms → B01-T02.01.
- adv-19 make/docker absent → static checks only, execution recorded NOT_RUN; port 127.0.0.1:17333; image tag pinned (digest not resolvable without docker) → B01-T01.01.
- adv-20 inf and float-as-int → rejected → B01-T02.01. adv-21 scanner self-trip → fake keys built at runtime, minimum exact-match length → B01-T01.01.
- adv-22 httpx pin → `httpx==0.28.1` → B01-T01.01. adv-23 error origin → added → B01-T02.02. adv-24 UNVERIFIED blocks runs, E3/E4 pinned to OQ11 → B01-T03.01.
- Limits: one model review is not evidence of correctness; the reviewer read neither EVIDENCE_LOG nor `check_docs.py`.

## E-B01-002 — Tooling, secret scan and clean-copy proof (B01-T01.01)

Environment: Windows 11, CPython 3.14.7, uv 0.13.1, branch `main`. Commands run in `palladion-benchmark/` unless noted.

- Dependencies added (BADR-0014): `httpx==0.28.1` and `PyYAML>=6.0.2,<7` (locked 6.0.3) at runtime; `types-PyYAML>=6,<7` (locked 6.0.12.20260906) for typing; existing dev group mypy 2.4.0, pytest 9.1.1, ruff 0.17.1.
  Purposes: HTTP client for the Groq entry point, YAML configs, strict typing of the YAML loader.
- Files: `pyproject.toml` (pytest `pythonpath`, ruff rules E F I UP B SIM RUF at line length 120, mypy strict), `.env.example` (one variable name, no value), `docker-compose.yml`
  (Qdrant only, `profiles: [qdrant]`, tag `v1.19.2` matching Palladion, bound to `127.0.0.1:17333`), `Makefile` (every recipe is a `uv` command), `benchmark/__init__.py`,
  `benchmark/secret_scan.py`, `tests/test_secret_scan.py` (23 tests).
- Secret scan controls: each of five patterns catches its planted case (fake keys built at runtime); clean text passes; a key planted in a staged file of a temporary repository is caught and a clean index passes;
  the scan reads the index, not the working copy; matches are never printed; the opt-in exact-value scan finds a literal from a local env file that no pattern matches. Positive control on the real file:
  `python -m benchmark.secret_scan --paths .env` reports `env-file-must-not-be-committed` and `groq-key` by rule name only, so the Groq key pattern matches the real key format.
  Exact-value scan of the live-proof records with `--env-file .env`: 0 findings.
- Clean-copy proof: the files `git ls-files -co --exclude-standard` lists (no `.venv`, no `.env`) were copied to a temporary directory; there `uv sync --locked`, `ruff check`, `ruff format --check`, `mypy` (19 files) and `pytest` (327 passed at that moment) all succeeded.
- NOT_RUN: `make` and `docker` are not installed on this machine, so the Makefile targets and `docker compose` were not executed. Static checks only: compose services all behind a profile with pinned image and loopback ports, Makefile recipes all `uv` commands and required targets present.
  The Qdrant image digest could not be resolved without a container runtime; the tag is pinned, the digest is not.

## E-B01-003 — Contracts, configs, registry, manifest, tracing, runner and CLI (B01-T02 to B01-T04)

Totals at this point: `uv run pytest` 328 passed (contracts and registry 85, config 49, manifest 45, budgets and tracing 21, runner 26, CLI 10, generator 69, secret scan 23; a full run takes about 15 to 20 seconds);
`uv run ruff check .` and `ruff format --check benchmark tests` clean; `uv run mypy` strict, no issues in 19 files; docs checker passes.

- Contracts (`benchmark/contracts.py`): frozen dataclasses; naive or malformed timestamps, bool or float where an int is required, NaN and infinity, non-pseudonymous question ids, filter keys outside the allowlist, gold-like keys and gold-like values,
  a native-citation claim without a source version, unknown fields and a SUPPORTED answer carrying an abstention reason are all rejected; null latency and cost stay null; mappings are deep-copied read-only. Failure mapping: six exception types map to one run state and origin with fixed codes.
- Configs (`benchmark/config.py`, four YAML files): duplicate keys, unknown keys, unquoted version-like pins (3.10 would load as 3.1), floating or range pins, unapproved or misordered models, split sizes that do not add to the M tier and a composition that does not sum to 12,000 are rejected;
  exploratory mode accepts UNPINNED, confirmatory mode refuses it; identical files give identical digests. The real files load: 15 arms, K 5/10/20, budgets 4000/8000, split 10/30/60.
- Registry: 15 arms, each declaring all five capabilities with a source note; UNVERIFIED blocks a run (recorded NOT_RUN), UNSUPPORTED records FEATURE_NOT_SUPPORTED; E3 is FEATURE_NOT_SUPPORTED and E4 NOT_RUN per OQ11; drift against `comparators.yaml` fails.
- Manifest (`benchmark/run_manifest.py`): full protocol section 7.2 fields; exclusive create; the embedded digest catches damage; a rewrite with a recomputed in-file digest passes alone but fails against the external digest (tested); the gold digest is absent from the arm view;
  dirty benchmark or system-under-test trees are refused in confirmatory mode and reported separately; the read-only git capture leaves the index untouched (tested on temporary repositories, including rename, delete, ignored and untracked files).
- Tracing and budgets: 18 stages in protocol order; fixed error codes; absent usage stays null; a sixth main call is refused before dispatch and recorded; self-reported over-budget counts are flagged and not clamped; eight threads cannot oversubscribe a budget of five.
- Runner: pairing, seeded randomized order, an intention-to-treat final record per pair, retries only for the transient type with both outcomes kept, a timeout marks the arm unusable and counts the discarded late result, the run-level limit applies between cases, resume never re-dispatches,
  a second run id on the same plan is refused, manifests must exist first and carry the runner's retry policy.
- CLI: `python -m benchmark.cli capability-matrix` exits 0 with 16 table rows; `--arm R99` exits 2 with the arm named; confirmatory validation exits 1 on UNPINNED entries.
- Mutation controls: for each module, planted defects were applied to a temporary copy and the owning tests had to fail. Contracts 6 of 6 killed; config 5 of 5 meaningful ones killed (a sixth was a redundant duplicate check, which was then removed); manifest 8 of 8 (after adding an untracked-file digest test);
  budgets 6 of 7 (removing the lock is not detectable under the GIL, so the concurrency test shows the contract but not the absence of races); runner 14 of 14 (after adding two tests); CLI 4 of 4;
  generator 18 of 18 after tests for redirects, proxy environment, model approval and usage validation were added.
- Limits: all provider and Palladion behavior in these tests is injected or local; the thread-based timeout cannot stop a runaway arm (subprocess isolation from B04, BADR-0016); Windows only; Python 3.14.7 only although `requires-python` allows 3.11 to 3.14.

## E-B01-004 — Real-provider proof of the generator entry point (B01-T05.02)

Authority: BADR-0015 (owner instruction to finish B01 end to end, with one call per approved model, at most 256 completion tokens and 6 calls). Command from `palladion-benchmark/`:
`uv run python -m benchmark.generator --prove --enable-live --out artifacts/runs/b01-generator-proof/records.jsonl`. Exit status 0.

- Observed: 3 calls, 3 real responses, each `served_model` equal to the requested model (`qwen/qwen3.8-27b`, `openai/gpt-oss-120b`, `openai/gpt-oss-20b`); prompt and completion tokens 36/2, 93/23 and 93/20; latency 666, 592 and 540 ms;
  every response carried a request id; rate-limit headers showed a 1,000 requests limit and an 8,000 tokens limit on each model with 7,767, 7,651 and 7,651 tokens remaining. No retry, wait or failover occurred.
  The records file (gitignored under `artifacts/`) has 3 lines; the exact-value secret scan of it found nothing. The key was never printed.
- This establishes only that the entry point reaches the three models and records what the provider returned on these three calls. It does not establish output quality, throughput, behavior under sustained load or stability of the headers.
  Groq exposes no model revision; the records state `provider_exposes_revision: false`.
- Limits: 8,000 tokens per minute is small for Tracks B and C; the pre-assignment budgets (BADR-0015) stay null until real daily limits are stated.

## E-B01-005 — Post-phase audit for B01 (Haiku 5.5, medium effort) and resolution

One read-only auditor requested with model `haiku` and effort `medium` (the exact model revision is not reported by the tool). Brief: read the complete protocol, the whole suite and all code, tests and configs;
look for protocol drift, defects, tests that cannot fail, unconsumed modules, document drift and key leakage; it was allowed one command, the test suite, and forbidden `.env`, `artifacts/`, git, uv and the network.
Coverage claimed: protocol 1–1209, all development documents, all ten source files, four YAML files, build files and all eight test files; it did not open `uv.lock`, `.env` or the live records, and did not run ruff, mypy or the docs checker.
It observed `328 passed in 13.51s`, matching the claim. Result: 22 findings (2 HIGH, 14 MEDIUM, 6 LOW). The coordinator read the code paths for each and dispositioned them as follows (finding → action → where). Findings are labelled adv-N.

- adv-1 the registry was never consulted by the runner → `Runner` takes the registry and `required_capabilities`; a blocked arm records NOT_RUN or FEATURE_NOT_SUPPORTED for every pair with no adapter call; an arm missing from the registry stops the run before any record is written → `benchmark/runner.py`, new tests.
- adv-2 unscannable files passed silently → they are now findings (`unscannable-file`) unless `--allow-unscannable` is given and are still counted; UTF-16 files with a byte-order mark are decoded and scanned → `benchmark/secret_scan.py`.
- adv-3 keyword pattern missed `GROQ_API_KEY` and quoted JSON keys → lookarounds and optional quotes; names that only contain a keyword (tokenizer, max_tokens, secretary) are tested as non-matches.
- adv-4 a gold-carrying object could reach a system arm → `RunnerCase` accepts only `RetrievalRequest` or `CaseRequest`; the system path requires `CaseRequest`.
- adv-5 question ids admitted `test-…` and `lock-…` → the only accepted form is `q-` plus hex; episodes use `ep-` plus hex; negative cases added.
- adv-6 an interrupted retry made resume impossible → the next attempt number comes from the ledger and the first-attempt status is read back; tested with a pre-seeded non-final record.
- adv-7 the unusable-arm mark was lost on restart → rebuilt from TIMEOUT records at start; tested across a restart.
- adv-8 a subset rerun under a new run id was accepted → on the test split no pair another run covered may ever run again, even with a declared repeat; on other splits a repeat of a plan needs an explicit exploratory declaration, because tuning on dev legitimately reruns pairs (protocol 14.1 limits selective reruns to the confirmatory stage).
- adv-9 confirmatory mode was too permissive → arms R7, R7a, R7b, E3 and E4 must pin and record the system under test, and `model_versions` must not be empty. Not changed: a model pin without a revision is accepted because the provider exposes none; the generator records that fact on every call. Limit stated, not hidden.
- adv-10 budget checks and the tracer had no production caller → the runner now runs `check_reported` on a system response, flags `BUDGET_VIOLATION_UNVERIFIED` on the ledger record and keeps the reported counts unclamped. `Tracer` stays unconsumed until adapters emit spans in B04; owner: coordinator at B04 start. The runner does not emit stage spans (no protocol stage fits an arm call).
- adv-11 a null-content reply could pass the proof → PASS needs non-empty text; tested. The earlier live run is unaffected (all three returned text).
- adv-12 the NOT_RUN mapping for unassigned questions did not exist → the card now says `assign_models` returns the unassigned set and the Track B runner (B05-T05.01) records them NOT_RUN; reproducibility.md already deferred wiring to B05.
- adv-13 query text is unscreened → by design, recorded on the card (fixture validation in B02 owns it); filter markers are now substring-based so `gold_answer` is caught.
- adv-14 `retry_timeouts` had no effect → removed from the schema, config, manifest policy and tests.
- adv-15 no-call records stored duration 0.0 → now null. adv-16 manifest split was never compared → refused on mismatch. adv-17 malformed strata key raised a bare error → ConfigError.
- adv-18 to adv-20 document drift (accepted-ADR list, a stray test line in docs/README, missing test files in the BG-HARNESS row) → fixed. adv-21 weak assertions → exact fixed codes asserted and the length escape removed. adv-22 zero limits crashed the proof command → refused with exit 2.
- Mutation control after the fixes: 18 planted defects against the new behavior were each killed by the owning test file; one (`system path accepts any request`) is an equivalent mutant because `RunnerCase` already restricts the type, so the second check cannot be reached with another type.
- Verification after the fixes: `uv run pytest` 358 passed, ruff and strict mypy clean (see the closing entry).
- Limits: one model audit is not proof of correctness; the auditor did not run the linters or the checker and did not inspect the live records, which the coordinator scanned for the key (0 findings).

- Correction (2026-10-18, after the post-phase audit): the NOT_RUN line above says `make` and `docker` are "not installed". For Docker that is incomplete: the owner stated Docker cannot run on this machine at all, so the compose file is optional and
  Qdrant runs as a pinned standalone binary under WSL (BADR-0017). `make` is simply not installed.

## E-B01-006 — Resolution check, closing validation and publication preparation

The same auditor (Haiku 5.5, medium effort) re-read the fixes and reported a status for each finding, plus eight new points (adv-23 to adv-30). It disclosed that it ran one read-only `git status`, which is outside the commands it was allowed and changed nothing.
It observed `358 passed`, the expected count at that moment.

- Resolved as verified by the auditor: adv-2, adv-3, adv-4, adv-5, adv-7, adv-11, adv-14 to adv-17, adv-18 to adv-22. Accepted as stated: adv-8 (dev reruns are allowed), adv-13 (query text is screened in B02).
- adv-1 (partial) → accepted: `required_capabilities` is chosen by the caller because only the arm's track and metadata condition know what a run depends on; B04-T02.01 sets it per condition. The blocking mechanism itself is tested end to end.
- adv-6 (partial) and new adv-23 → fixed: the no-call final record now uses the next attempt number and keeps the true first status; tested with an interrupted attempt followed by a blocked arm.
- adv-9 (partial) → fixed for lexical arms (new adv-27): R0 uses no model, so a confirmatory R0 run may have empty `model_versions`; every other arm must name its models. Nullable container and method digests stay allowed with a stated reason.
- adv-10 (partial) → fixed in part: `RunSummary.flag_counts` now counts flagged records, so a flagged OK is visible in the summary. A flagged record keeps status OK on purpose and the flag is the failure marker; B03 scorers must read flags.
  `Tracer` stays unconsumed until adapters emit spans (B04). adv-12 (partial) → accepted: `assign_models` has no production caller until B05-T05.01, and the card text says so.
- New adv-24 → refuted: the registry compares the product of arms and questions, so a run that adds a different arm for already-covered questions is not refused; the auditor's example would repeat R0 pairs only if R0 were in both runs. A test now shows the allowed case.
- New adv-25 → fixed: `gold` must be a whole word, so `gold_answer` and `gold-slots` are refused while `Goldman`, `goldstar` and `marigold` pass. New adv-26 → documented in the README (binary and oversized files fail `--staged` unless `--allow-unscannable`).
  New adv-28 → accepted: the plan registry has no versioned entries because no registry file exists outside tests yet. New adv-29 → fixed: the hardware test checks the field set instead of searching for the user name.
  New adv-30 → fixed: Docker wording in `reproducibility.md`, the secret-scan test comment and the plan evidence line now says Docker cannot run here (BADR-0017); this entry also appends a correction to E-B01-002.
- Mutation controls on the new behavior: four planted defects (attempt restart, substring `gold`, removed R0 exemption, dropped flag counts) were each killed.
- Closing validation (from `palladion-benchmark/`): `uv run pytest` 371 passed; `uv run ruff check .` and `ruff format --check benchmark tests` clean; `uv run mypy` strict, no issues in 19 files;
  docs checker and its 33 negative self-tests pass. The live-proof records were scanned for the key with the opt-in exact-value scan (0 findings).
- Limits: two model reviews are not proof of correctness; `make` was never executed and Docker cannot run here; every Palladion and provider behavior beyond the three recorded live calls is untested; Windows and CPython 3.14.7 only.
