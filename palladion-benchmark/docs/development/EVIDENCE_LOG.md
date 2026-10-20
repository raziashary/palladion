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

## E-B02-001 — Pre-phase adversary for B02 (Haiku 5.5, medium effort) and dispositions

One read-only reviewer requested with model `haiku` and effort `medium` (the exact revision is not reported by the tool). It was told to read the complete protocol, the development documents, `configs/` and the two contract modules, and was forbidden `.env`, `artifacts/`, git, uv and the network.
Coverage claimed: protocol (1,209 lines, two reads), the master plan, AGENTS, testing gates, ADR log, risks, progress, goal, traceability, learning, three config files, `contracts.py` and `config.py`. Not opened: `comparators.yaml`, memory, map, evidence log, `check_docs.py`, existing tests. It reported 29 findings (6 HIGH, 17 MEDIUM, 6 LOW) and listed what it found sound.
The coordinator verified each against the cards and protocol and dispositioned them (finding → action → where). Findings are labelled adv-N.

- adv-1 (T07.02 not achievable as written) → accepted: the owner chose an owner-labelled packet plus a blinded LLM pass and a retrieval check; BADR-0019 records the deviation from protocol 6.3 and 14.5, the live budget (40 calls), the non-independence limit and the disagreement rule; the card, BG-GOLD, BR10 and B05-T04.01 wording were changed. B02 stays open until the owner has labelled.
- adv-2 (empty alternatives is ambiguous) and adv-3 (schema omits fields) and adv-26 (taxonomies overlap) → fixed in the T04.01 card: every protocol 6.1 field, explicit slot states, a validated answerability/mechanism mapping, existence-disclosure claims, track eligibility. Per-metadata-condition answerability was refuted: C1 and C2 change what arms see (protocol 3.2), not what is answerable; the C1 header schema is added to T02.02.
- adv-4 (circular gold-support) → fixed in T06.01 and T07.02: gold-support runs on rendered text with an extractor the renderer does not use; the owner's retrieval check is part of the audit.
- adv-5 (query text unscreened), adv-7 (filter values), adv-8 (identifiers), adv-9 (titles and order) → fixed as BADR-0020 rules 1 to 3 and in the T02.01, T03.01 and T04.02 cards.
- adv-6 (version labels correlate with applicability) → fixed in T06.01: naive-newest and naive-highest-id baselines must score below a ceiling recorded in an ADR before measurement, and the applicable version must often be an older one.
- adv-10 (family undefined) and adv-20 (exact counts, language shares) → fixed in T04.02: family is a world object, partitions run over the union of strata, counts and shares have proofs and a rounding rule.
- adv-11 (shared seed across tiers) and adv-12 (determinism) → fixed in BADR-0020 rules 4 and 5 and the T07.01 proof (subprocess runs under different hash seed, time zone and directory).
- adv-13 (ambiguity list incomplete) and adv-28 (FAQs, API notes, postmortems) → fixed in T02.01 and T02.02.
- adv-14 (proofs overclaim) → accepted: T03.01 now says metadata visibility is proven here and enforcement by a retriever in B04; T05.01 checks the operation allowlist.
- adv-15 (noise measured from tags) and adv-16 (realism checks without thresholds) → fixed in T02.02 and T06.01; the numeric thresholds are fixed in an ADR before the first measurement that uses them.
- adv-17 (track eligibility) → fixed in T04.01 (per-stratum eligibility field).
- adv-18 (decision tables) → refuted as a gap: T01.02 now names the rule fields, precedence and deterministic evaluator; the oracle tool of protocol 9.4 stays with its later owner.
- adv-19 (cycle constructor vs mutation) → fixed in T01.02: construction is permissive, a separate validator rejects cycles.
- adv-21 (document drift) → fixed in the same step as adv-1.
- adv-22 (spans without offsets) → fixed: T04.01 now depends on T02.01 and the renderer emits clause ids and offsets.
- adv-23 (proofs without owner files) → fixed: `tests/test_partitions.py`, `benchmark/fixtures/audit.py` and `tests/test_label_audit.py` are added (BADR-0020); T01.03 tests live in `tests/test_world.py`.
- adv-24 (stale mode has no bound) → fixed in T05.01 and BADR-0020 rule 8. adv-25 (vocabulary) → noted: the protocol uses archived and retired for the same state; the fixtures use retired. adv-27 (S config check) → fixed in the T07.01 proof. adv-29 (a merchant named Gold) → noted: no fixture vocabulary contains the word, and a test confirms the screen does not trip on the world's names.
- Not verified by the reviewer: whether `fixtures/world.py` was early B02 code (it is: T01.01 had just been started when it ran). It did not open `check_docs.py` or run the checker.
- Limits: one model review is not proof of correctness; findings that concern code not yet written (determinism, leakage, realism) are design-level and are proven by the owning tasks.

## E-B02-002 — B02 build, validation and entry-point smoke

All commands run from `palladion-benchmark/` on Windows, CPython 3.14.7, uv 0.13.1, on 2026-10-19.

- `uv run pytest`: 654 passed in 127 s. `uv run ruff check .` clean; `uv run ruff format --check benchmark tests scripts` 45 files formatted; `uv run mypy` strict, no issues in 45 files.
- Entry point: `uv run python scripts/generate_data.py --tier S --out artifacts/fixtures/S --audit-packet --write-card` exited 0 and printed corpus manifest SHA-256 `104d5baa…a2267`, questions SHA-256 `b7a52980…5d7a7`, snapshot `snap-b491d64cb7a4665a`, 1,200 documents and 100 questions. The script validates the fixture before writing and reads the written tree back before reporting (hash check, barrier scan with every question id). Validation findings: 0.
- Reproducibility: `tests/test_generate_data.py` runs the script in two subprocesses under different `PYTHONHASHSEED`, time zone and working directory and compares stdout and manifest bytes (identical); seed 9 gives different digests.
- Measured from the documents (not the generator tags): near-duplicates 9.5% (114), stale 6.5% (78), unapproved 3.0% (36, from registry state), injection 1.5% (18), language 58.6/27.8/13.6 measured against 55/30/15 tagged (87.7% per-document agreement). Realism: identifier-free BM25 solves 0.15 of Q2 to Q5 (ceiling 0.60), sentence-length variation 0.48 (floor 0.25), skeleton diversity 0.16 (floor 0.10), newest-version rule 0.00 (ceiling 0.30), oldest-version rule 0.50 (ceiling 0.60).
- Not run: `make`; any Palladion or comparator call. The gates cover the benchmark's own fixture, not any system.
- Limits: template-first text; about 20 independent policy families (effective sample size); base seed 8 is refused by the generator (too few usable version questions); the vocabulary cannot yet express the M tier (240 policy scopes).

## E-B02-003 — Mutation sweeps over the B02 modules

A defect was planted one at a time in a temporary copy and the owning test files were required to fail. First sweep, 24 mutants across entities, knowledge, documents, artifacts, manifest, live API, questions, validation, audit and the script: 22 killed, 2 survived. The survivors were fixed, not waived: the negated-state counter in the equivalence check never decided a result (the same flip already failed the extracted state fact), so it was removed; the query screen had no integration test, so one was added that builds questions from a leaking template.
Second sweep, 14 mutants for the survivors and the behaviour added after the post-phase audit (id secret, ticketed live subjects, twin pairing, unplanned conflicts, clause numbers, precedence by specificity, live existence, stale regeneration, gold digest on labels, cumulative call budget, overwrite refusal, readback gate, announcements): all killed, one of them (unplanned-conflict report) after retargeting its anchor by hand because the formatter had reflowed the code.
Limits: mutants were chosen by the coordinator; an unlisted defect can survive.

## E-B02-004 — Post-phase audit for B02 (Haiku 5.5, medium effort) and dispositions

One read-only auditor requested with model `haiku` and effort `medium`. It read the complete protocol, the development documents, all of `benchmark/fixtures/`, the script, the card and the eleven B02 test files, and ran only the test suite (639 passed at that time). It reported 31 findings (aud-1 to aud-31: 5 HIGH, 16 MEDIUM, 10 LOW) and listed nine claims it could not refute. Dispositions (finding → action):

- aud-1 (question ids recomputable from the public seed) → fixed in part: ids are keyed by an id secret (BADR-0023); the pilot uses the empty default and the card says so; the locked split must use a private secret before the seal (B08-T03.01). The same finding was raised by the B03 adversary (adv-4).
- aud-2 (manifest lists restricted titles) → refuted as a defect, recorded as a limit: the manifest is the ingest list an indexer sees; access is enforced at retrieval and scored by stratum Q8.
- aud-3 (announcements only for planted histories, family ids in titles) → fixed: announcements draw from any family with a later version; policy ids in support titles are public identifiers (BADR-0023 narrows BADR-0020 rule 3).
- aud-4 (no closure records) → fixed by this entry, the plan state, PROGRESS and GOAL.
- aud-5 (model passes not reproducible, overwrite, budget) → fixed in part: prompt version and digest stored per label, a recorded pass is never overwritten, calls are counted across passes, owner labels carry a gold digest. The two earlier prompts (600 and 900 character prefixes) are not reproducible from the repository and the card says so.
- aud-6 (twins not on the same topic) → fixed: twins share the transaction type and template. aud-7 (unplanned conflicts) → confirmed by execution (4 to 6 of 150 scopes); fixed by precedence from scope specificity plus a validation check. aud-8 (live existence) → fixed. aud-9 (tickets reveal verified states) → fixed for live questions (ticketed transactions are excluded); the ticket text itself stays and is stated as a limit. aud-10 (clause numbers read as claim numbers) → fixed; cross-slot sums remain a stated limit. aud-11 (no readback gate, constant findings count) → fixed. aud-13 (stale files on regeneration) → fixed. aud-14 (labels after gold edits) → fixed with the gold digest.
- aud-12 (barrier test used dummy tokens) → accepted in part: the tests now scan with every real question id; family ids are public policy ids, not barrier tokens. aud-15 (tests use a raw seed) → partly refuted: `generate()` validates the world the card reports, and the card test compares against it. aud-16 (partition tests at the M shape) → deferred to B08-T01.01 with the scope vocabulary. aud-17 → (a) schema presence tests kept by design with a rejection test, (b) relabelled, (d) narrowed to `WorldError`. aud-18 (injection variants) → deferred to B07-T07.01 (M14). aud-19 (unindexed source) → deferred to B04, which has an index to omit. aud-20 → corrected: the naive highest-id rule equals the newest-version rule because ids are chronological, and the template-share check is replaced by the skeleton-diversity floor. aud-21 (user-supplied validity policy) → deferred to B07-T05.01. aud-22 (duplicate markers) → fixed: prefixes and suffixes vary. aud-23 (dead code) → removed (unused banks, `Voice.sample`, `doc_id` parameter, negation counter); `Verification.INFERRED` stays for mutation M07. aud-24 → one snapshot constant. aud-25 → card labels corrected. aud-26 → test added that no world name trips the screen; the "per-case snapshots" wording is read as per-case failure modes. aud-27 → documented. aud-28 → `question_gen.py` split off (BADR-0023); `knowledge.py` split deferred to B08. aud-29 → audit constants stay in code with their ADR; configuration deferred to B04. aud-30 → accepted. aud-31 → guard added.
- Limits: one model audit is not proof of correctness; the auditor did not run ruff, mypy or the checker; the coordinator re-verified aud-7 by execution and the rest by reading the code.

## E-B02-005 — Pilot label audit status (B02-T07.02 stays open; closed by E-B02-006)

Owner-approved design and spending are in BADR-0019. Two blinded model passes were run on an earlier build of the fixture: pass 1 used 36 calls and agreed with gold on 7 of 30 items; pass 2 used 37 calls and agreed on 12 of 30. Cause of the low figure: the prompt showed fixed-length document prefixes and the gold's cited documents were among the model's documents for only 2 of 23 questions with cited evidence (the model agreed on both). The model cannot search the corpus, so the figures do not measure the gold's validity.
The post-phase audit then changed the world and the generator, so those labels no longer belong to the shipped questions and were archived locally (`artifacts/archive/`), not reused. 73 of 80 authorised calls are spent; the packet for the final fixture exists (30 items, `worksheet.md`, a blank `owner_labels.jsonl` carrying gold digests). Pass 3 (2026-10-19, owner authorised up to 40 calls): 36 calls (30 OK, 6 rate-limited retries on gpt-oss-120b), prompt `excerpt-v1`, all three approved models, 10 items each, 30 of 30 valid labels, 17 of 30 (57%) agree with gold. For 22 of the 23 questions with cited evidence the cited documents were not among the model's top documents (the model cannot search), so the 13 disagreements are mostly what the model was shown, not shown gold defects; the labels and call records are under `artifacts/fixtures/S/generator/audit/` (untracked). ~~Open: the owner's labels and retrieval check. Until then BG-GOLD stays PARTIAL and B04-T05.01 is blocked.~~ Superseded 2026-10-19: the labels were made under delegation (E-B02-006, BADR-0026); BG-GOLD stays PARTIAL.

## E-B03-001 — Pre-phase adversary for B03 (Haiku 5.5, medium effort) and dispositions

One read-only reviewer requested with model `haiku` and effort `medium`. It read the complete protocol, the development documents, the contracts, runner, manifest and config modules, `configs/evaluation.yaml` and the B02 gold, document and manifest modules; it grep-read the tracing, registry and knowledge modules. It reported 27 findings (adv-1 to adv-27: 9 HIGH, 13 MEDIUM, 5 LOW) and ten claims it could not refute. Dispositions (finding → action):

- adv-1 (no card owns the consumer) → new card B03-T07.01 (score-run driver with control arms through the real runner); the exit depends on it; adv-20 (control arms cannot be registered) → the same card injects a registry. adv-27 (missing Depends) → fixed in the cards.
- adv-2 (CompleteSet on partial and empty gold) and adv-19 (controls coincide) → not-applicable rule and per-stratum controls (BADR-0024 items 6, B03-T07.01). adv-3 (no graded relevance) → owner chose binary slot match. adv-5 (no identity for unversioned documents) → owner chose optional `source_document_id` and `source_sha256`. adv-6 (overlap inflates) → identity-only headline metrics. adv-7 (locator grammar) → fixed in the ADR before the first measurement.
- adv-4 (question ids recomputable) → fixed in B02 (E-B02-004, aud-1). adv-22 (basis alternatives include superseded versions) → fixed in B02: the basis slot cites the applicable version only.
- adv-8 (no cost record) → B03-T05.01 uses ledger durations, system-reported usage and the B04 index record; marginal-update costs move to B07-T05.01. adv-9 (TIMEOUT latency) and adv-10 (intention to treat) → rules in the card and ADR. adv-11 and adv-12 (bootstrap method, exact bound) → fixed in the ADR and card; the config change lands with B03-T04.01.
- adv-13 (recorded interval, history allowed) and adv-14 (slot kinds) → fields and a name-to-kind table in B03-T03.02. adv-15 and adv-16 (metrics without inputs, no formulas) → three metrics moved, formulas and denominators go to evaluation.yaml with a test that every metric has one group. adv-17 (K and budget not recorded) → B04's Track A writer records them; the scorer takes K explicitly. adv-18 (no gold reader) → in B03-T01.01.
- adv-21 (two owners of one test file) → separate test files. adv-23 (unit, duplicates, zero denominators) → ADR item 5. adv-24 (live citations) → excluded by track eligibility. adv-25 (reading list) → plan header extended. adv-26 (equivalence testing) → TOST in B03-T04.01.
- Limits: one model review is not proof; the reviewer read code and documents, ran nothing, and did not open the tracing or registry modules in full.

## E-B03-002 — B03 build, validation and entry-point evidence

All commands run from `palladion-benchmark/` on Windows, CPython 3.14.7, uv 0.13.1, on 2026-10-19.

- `uv run pytest`: 790 passed in 297 s. `uv run ruff check .` clean; `uv run ruff format --check benchmark tests scripts` 62 files formatted; `uv run mypy` strict, no issues in 62 files.
- New code: `benchmark/eval/{normalize,evidence_sets,retrieval,statistics,cost_latency,score_run}.py`, `benchmark/analysis/tables.py`, and the contract, gold-reader, manifest and config additions of BADR-0024. New tests: `test_span_alignment`, `test_evidence_metrics`, `test_retrieval_metrics`, `test_statistics`, `test_cost_latency`, `test_score_run`, `test_tables` (about 135 tests) over the real S-tier fixture, with `tests/support.py` builders.
- Actual path: `tests/test_score_run.py` runs the perfect, empty and shuffled controls through the real `Runner` (real ledger, manifests, plan registry) with an injected registry, then scores the ledger from disk. Perfect scores CompleteSet 1 and empty 0 on every question that owes evidence; shuffled sits between; on questions with no citable evidence the controls give identical metrics and the scorer reports zero questions for those strata (`control_separation`). A ledger hole, a gold file that differs from the manifests' digest, a manifest for another arm, a ledger that does not match its manifest, an edited published document and a manifest written against another corpus each stop the scorer.
- The fixture and dataset card were regenerated because `history_allowed` and `recorded_from` changed the digests: corpus manifest `4d14dfc4…bd818ce`, questions `216045d3…030cd5` (E-B02-002 keeps its historical digests). The blank owner-label template was regenerated with the new gold digests; no label was lost (none had been entered).
- Not run: any Palladion or comparator call; no scoring command-line entry point exists yet (B04-T04.02 writes Track A runs and owns it). Statistics functions without a production caller (Holm, equivalence, power, calibration, McNemar) are exercised by tests only; their consumers are B05, B06 and B08.
- Limits: the statistics are checked by simulation at fixed seeds, not proven; a scorer that separates controls does not show the metrics match what a reader would call relevant.

## E-B03-003 — Mutation sweeps over the B03 modules

A defect was planted one at a time in a temporary copy and the owning tests were required to fail. First sweep, 35 mutants across normalize, evidence sets, ranking, provenance, statistics, cost, the driver and the tables: 30 killed, 5 survived (overlap threshold on spans, text-alignment threshold, gold-listed inaccessible sources, one retargeted anchor, severe failures counted over non-completed pairs). Each survivor got a test or a corrected anchor, not a waiver. After the audit fixes (E-B03-004) a second sweep added 8 mutants (leak rule for near-duplicates, document locator crediting every clause, published-corpus tampering, failed-call spend, live ids as claims, spanning chunks, precision by novelty, source digest) and retargeted six whose code had moved; two survived (near-copy collapse for long passages, ACL in valid-source recall) and were killed after tests were added. Final run: no survivors.
Limits: mutants were chosen by the coordinator; an unlisted defect can survive.

## E-B03-004 — Post-phase audit for B03 (Haiku 5.5, medium effort) and dispositions

One read-only auditor requested with model `haiku` and effort `medium` (the first attempt was cut off by a usage limit and resumed). It read the complete protocol, the development documents, the B03 modules and tests, ran the statistics, cost and table tests and ruff and mypy, and reported 20 findings (aud-1 to aud-20: 2 HIGH, 10 MEDIUM, 8 LOW) and sixteen claims it could not refute. Dispositions (finding → action):

- aud-1 (exposure ignored partial text) → fixed and verified by execution: every candidate lists the documents whose phrases it reproduces (share at least 0.3); it leaks when it names a forbidden document or reproduces forbidden text that no visible document also contains (near-duplicates of authorised text are not leaks). aud-2 (a bare document id credited every clause) → fixed: a document locator credits the document unit only plus the clauses its text reproduces; the old test that asserted the opposite was rewritten.
- aud-3 (corpus not verified) → fixed: the scorer runs `verify_published` and compares each manifest's source digest. aud-5 (identity hid alignment) → fixed: text alignment is computed for every candidate and reported separately. aud-6 (spanning chunk) → fixed: a clause is credited when the candidate lies in it or it lies in the candidate. aud-7 (precision by novelty) → fixed: precision counts every relevant candidate; gain-based metrics still count a repeat once. aud-8 (failed-call cost) → fixed: spend on a failed call counts and a call without a report is missing. aud-9 (no per-stratum control report) → fixed: `control_separation`. aud-10 (live citations in the locator denominator) → fixed: a `live:` id is no claim.
- aud-4 (`non_normative` documents are not authority confusion) → kept as a stated limit (BR18): runbooks and API notes are legitimate evidence; the metric counts draft, unapproved and withdrawn documents that are not required by the gold. aud-11 (dropped obligations) → noise slope, paraphrase stability, rank sensitivity and marginal-update cost are recorded in BADR-0024 item 11 and now in the target cards' risk entry (BR19); entity-disambiguation error is dropped from B03 because no fixture gold carries it (BADR-0024 amendment, BR19). aud-12 → tests added for partial-text exposure, spanning chunks, live ids, a stale version ranked first and short repeated passages. aud-13 (no scoring entry point) → deferred to B04-T04.02 (BR20); the real-Runner integration test is the consumer evidence for now. aud-14 (ITT zero on non-binary benefit metrics) → accepted as a documented extension of BADR-0024 item 7.
- aud-15 (unused config keys) → `quantile_method` now has a test tying the config to the implemented method; `loss_matrix`, `provisional_gates`, `multiplicity`, `cluster_by` and `sealed` are B01 keys consumed by B05 and B08 (named owners). aud-16 (duplication, dead code) → removed the duplicate metric list, the test-only helper and an unused test function; `completion_tables` stays as the tested statement of the accounting rule. aud-17 (short passages) → fixed. aud-18 (duplicate clause numbers) → refused with an error. aud-19 (clause candidates credit the document unit) → accepted: a document-level gold alternative is satisfied by evidence from that document. aud-20 (circular gold digest) → the redundant read-time check was removed; the manifests' digest is the check.
- Limits: one model audit is not proof of correctness; the auditor read the statistics and driver code and ran a subset of tests; the coordinator verified aud-1, aud-2, aud-5, aud-6 and aud-8 by probes before fixing.

## E-B04-001 — Pre-phase adversary for B04 (Haiku 5.5, medium effort) and dispositions

One read-only reviewer requested with model `haiku` and effort `medium`. It read the complete protocol, the development documents, the B03 scorer and Palladion's live API, settings, retrieval, storage and seed code (read only), ran nothing and used no network. It reported 24 findings (adv-1 to adv-24: 12 HIGH, 9 MEDIUM, 3 LOW), twelve owner decisions and six claims it could not refute. Dispositions (finding → action):

- adv-1, adv-20 (Palladion's default root, port and collection belong to the other contributor; its worktree is dirty) → new card B04-T03.03: a detached worktree at a recorded commit, a dedicated root, collection and port, and a before-and-after check that the defaults are untouched. Owner approved provisioning (BADR-0025).
- adv-2 (principals, cases and tokens exist only in Palladion's seed and a demo token file) → B04-T03.03 seeds the isolated root with Palladion's own seed code; the tokens are read only inside the adapter process and never logged; owner approved reading them.
- adv-3, adv-4 (`/ready` needs the live-model flag, which loads the root `.env`; reranked mode returns unreranked order when the reranker is off; outages and exact-identifier misses return HTTP 200 with an empty list) → B04-T03.01 maps UNAVAILABLE and DEGRADED bodies to run states, refuses a reranked request against a server without the reranker, and tests an empty-but-OK versus unavailable pair; readiness is probed with `/health` and a real search, not `/ready`.
- adv-5, adv-6 (runner threads share a process with gold; nothing records reads; the validator cannot see reads) → threat model stated as accidental leakage, not an adversarial arm (BR21): arms receive only the published and index directories (B04-T01.03 refuses a path holding annotation namespaces), the runner records which annotation file it read, refuses the test split without a seal (B04-T04.02) and the validator checks that record (B04-T04.03). Subprocess isolation of arms stays deferred with its owner at B08.
- adv-7 (identity credit for non-native arms) → owner chose that harness-attributed provenance counts as headline identity, labelled in every table; the revision-to-document table for R7a is written at upload (B04-T03.01).
- adv-8 (no owner for parser, chunker or tokenizer; R7 is native-ingestion) → new card B04-T01.03; R7a is reported as native-ingestion in the common-chunk comparison and labelled.
- adv-9 (tokens undefined, no tolerance) → counted tokens are whitespace words with characters also reported (the B03 precedent); tolerance is one chunk (BADR-0025).
- adv-10 (R0 and R1 have no ACL or time filter) → owner chose a neutral harness filter identical for every arm (C2) with a no-filter run (C1) also reported; temporal filtering by the harness is declared out of scope for B04 (arms get the evaluation time but the pilot does not claim as-of correctness for R0 to R3).
- adv-11 (R7a validity follows the wall clock) → recorded as a capability difference in the adapter; R7a results on strata that depend on the as-of rule are reported as such (BR22).
- adv-12 (downloads) → owner approved all three downloads (embedding model, reranker, Qdrant binary); sizes are verified before each download and the digest is pinned. The reranker is English-trained; the language caveat is recorded.
- adv-13 to adv-19 → card order and dependencies fixed (launcher moved ahead as B04-T01.05; pins and recording as B04-T01.04; K recorded in the manifest and checked by the scorer); BADR-0017's negative controls added to the launcher proof; file lists completed; score entry point added to B04-T04.02 (BR20).
- adv-21 (no exact-key index; Palladion's exact lane is always on) → R2's exact-key channel is the lexical arm's identifier tokens, reported separately; Palladion's lane cannot be separated and is declared. adv-22 (candidate metadata not screened) → B04-T04.03 scans artifacts. adv-23 (authority rule decision has no owner) → B05-T01.01. adv-24 (timeouts) → bounded client timeouts and concurrency in B04-T03.01.
- Limits: one model review is not proof; the reviewer did not see the generated corpus (so the size limits in adv-16 are checked at build time) and ran nothing.

## E-B04-002 — B04 build, validation and entry-point evidence

All commands run from `palladion-benchmark/` on Windows with WSL Ubuntu, CPython 3.14.7, uv 0.13.1, on 2026-10-19.

- `uv run pytest`: 981 passed. `uv run ruff check .` clean; `uv run ruff format --check benchmark tests scripts` formatted; `uv run mypy` strict, no issues in 87 files; docs checker and its self-test pass (92 atomic tasks).
- Downloads (owner approved each): embedding model `Qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q` at `faf4aa42…` (252 MB, Apache-2.0; I had quoted about 120 MB and asked again before downloading), reranker `Xenova/ms-marco-MiniLM-L-6-v2` at `a0914435…` (92 MB, license not stated on the Hub page), Qdrant 1.19.2 Linux binary (33 MB, SHA-256 `50b25324…`). File digests are in `configs/comparators.yaml`. Palladion's pins read from its own source equal these, and its seed computes identical file digests.
- Entry-point smokes on the real S-tier fixture (engineering evidence, not the pilot; no ranking claim): `run_track_a.py` for R0 to R3 with the pinned models ran 400 of 400 pairs (11 minutes) and passed `validate_results.py`; R7a over the isolated Palladion with the full corpus loaded ran 100 of 100 pairs and passed the validator, twice (a second time after a reset and a fresh load). Load: 1,200 uploaded, 1,164 approved (9 of them then revoked), 36 left as draft; sampled titles reachable 10 of 23; searches took a median of about 1.1 s and at most 10.6 s. The dense index recorded ANN recall 1.0 over 25 queries at K=10 (mean and minimum), Qdrant 1.19.2.
- Observations only: on this fixture at K=10 the lexical arm scored above the dense arm (recall 0.28 against 0.03); R7a scored 0.06. The fixture is noise-heavy by construction (near-duplicates, stale copies, unapproved notes), the scores have wide intervals, and 22 of R7a's 100 answers were empty because Palladion answers a query that names a code with nothing (BR24). These are not findings about any system.
- Not run: the pilot measurement (B04-T05.01, which first needs the three-question withdrawal of E-B02-006); native-ingestion mode (deferred); any generator call. WSL, Qdrant and model tests skip when those are missing; they ran here.
- Limits: smokes validate the machinery, not the quality of any arm; R7a runs under a harness filter and Palladion's wall clock (BR22, BR27).

## E-B04-003 — Mutation sweeps over the B04 modules

A defect was planted one at a time in a temporary copy and the owning tests were required to fail. First sweep, 26 mutants across the harness, BM25, model pins, fusion, the Palladion adapter, the validator and the Track A library: 22 killed, 2 survived by anchor and 2 survived for real (the passage integrity check had two halves, each masked by the other, so a test for each half was added). Second sweep after the audit fixes: 13 mutants (arm notes, unknown statuses and warnings, character boundaries, identifier shape, download bound and verification, manifest reuse, escaped gold text, model copy verification, outage as proof, exit status on changed defaults, the launcher's HTTP port); one anchor moved and was retargeted; all killed. Final state: no survivors.
Limits: mutants were chosen by the coordinator; an unlisted defect can survive.

## E-B04-004 — Post-phase audit for B04 (Haiku 5.5, medium effort) and dispositions

One read-only auditor requested with model `haiku` and effort `medium`. It read the complete protocol, the development documents, all B04 modules, scripts and tests, and ran ruff, mypy and the four fast test files; it could not read Palladion, run servers or run the integration tests. It reported 29 findings (aud-1 to aud-29: 2 HIGH, 11 MEDIUM, 16 LOW) and eleven claims it could not refute. Dispositions (finding → action):

- aud-1 (a degraded response with no passages became an empty list) → fixed: only the two warnings that describe a normal answer (`COVERAGE_SCOPE_TRUNCATED`, `EXACT_IDENTIFIER_NOT_FOUND`) pass; any other status or warning is a transient fault. Note: at more than 100 sources Palladion marks every search DEGRADED with the first warning, which is why the adapter cannot treat DEGRADED itself as a fault.
- aud-2 and aud-11 (states approved in Palladion; R0 to R3 index drafts that R7a cannot retrieve) → declared, not changed: approval in Palladion means retrievable, not authoritative; retired, withdrawn and supersession cannot be expressed through its API; the arm's description and BADR-0025 say so, and authority confusion is scored from the published registry state (BR28).
- aud-3 and aud-10 (filter after ranking; notes never reached an artifact) → fixed: arms report notes through `call_flags()`, the runner keeps them as ledger flags (budget truncation, filtered-after-ranking counts, exact-key chunk counts, Palladion warnings), and the summary counts them; the filter-after-ranking difference is declared (BR27).
- aud-4 (BM25 statistics include hidden documents) → accepted limit (BR25): a score is a function of corpus statistics, as in Palladion's own BM25; no text of a hidden document is returned.
- aud-5 (demo-removal proof passed on an unavailable index), aud-6 (model copy unverified), aud-7 (changed defaults exit 0), aud-8 (R7a setup outside intention to treat), aud-9 (read-back not wired) → fixed: the proof needs an answering Palladion; models are verified before and after the copy; `prepare` fails when the contributor's defaults changed; an R7a setup failure leaves R7a in the run as not run with its reason; `verify_load` runs after a load and now fails when none of the sampled documents can be found (found by the second smoke: a stale revision table after a runtime reset).
- aud-12 and aud-13 (ANN recall and the Qdrant binary not recorded) → fixed: the index stats record a measured ANN recall and the server version, the build refuses a server that is not the pinned version, and the manifests list the binary and its digest.
- aud-14 (escaped JSON) → fixed: gold text is also searched in its JSON-escaped form. aud-15 (the read digest is computed from the file it checks) → accepted: the scorer and validator compare the manifests' digests with the file on disk; `test_namespace_read` is false by construction. aud-16 (identifiers need no digit) → fixed. aud-17 (`tables_lost` literal) → the basis is recorded beside it. aud-18 → unchanged by design. aud-19 (launcher accepts 18080) → refused now. aud-20 (collection names) → keyed by model, condition and chunk digest. aud-21 (manifest reuse) → refused when K, budget or condition differ. aud-22 (`fetch` unbounded) → bounded by the Hub's reported size and verified after download; the citation of this entry fixed. aud-23 (secrets optional) → a note says only patterns were scanned. aud-24 (vector cache) → sealed with a digest. aud-25 (offset inside a character) → a contract error. aud-26 (tests) → the disjunctive oracle in the cross-lingual test is deliberate; the worktree creation by a test is documented here.
- aud-27, aud-28, aud-29 (stale documents, card text, smoke only) → this update; BADR-0025 item 9 now says Track A runs smoke or dev and the pilot measurement uses smoke only.
- Limits: one model audit is not proof; the auditor did not run the integration tests or read Palladion; the coordinator reproduced aud-1, aud-5 and aud-8 by reading the code before fixing.

## E-B02-006 — Pilot label audit result (B02-T07.02)

On 2026-10-19 the owner declined to label the packet (no time) and asked the coordinator to do it (BADR-0026). So the "owner" labels below are the coordinator's reading, not an independent human's. Procedure: the 30 questions were labelled from `worksheet.md` and the published corpus only, before `key.json` was opened (the model labels and `audit_report.json` were not opened until after the report was run); then each cited clause was read in the published document and compared with the listed claims. Sources of truth used: document status, validity dates, scope, ACL and the clauses in `published/`; no generator file other than the worksheet and, after labelling, the key.

- Report (`uv run python -m benchmark.fixtures.audit report --root artifacts/fixtures/S`, status COMPLETE, 30 of 30 labelled, 0 invalid model labels): reader against gold 29 of 30 (97%, kappa 0.94); model against gold 17 of 30 (57%); reader against model 17 of 30 (57%, kappa 0.36). Evidence checks: 21 sufficient, 3 partial, 0 insufficient, 6 items cite nothing.
- Disagreement with the gold, 1 item: a-3e78c6bf81ce ("How long does a Retail merchant have to ask for a chargeback?", principal at Harborline). Reader said BLOCKED_BY_ACL (the Retail extension EXC-010 is shown as hidden); gold says UNANSWERABLE. Settled against the world's rules: every chargeback policy in the corpus is scoped to Northwave (POL-010, EXC-010) or Kestrel (POL-020); none applies to Harborline, so no document answers this principal's tenant and the hidden ones are not the cause. The gold stands; the reader's label was the wrong one. The generator's wording (no tenant in the question) is a limit, not a gold defect.
- Defect found, 3 items (a-1c1517e1c363, a-29081870dc64, a-4bcb97ff166b; all in the smoke partition; evidence check "partial"): the synthesis questions ask for "all current policies visible to Northwave Bank support" at or under 336, 168 and 120 hours, but `_make_q10` takes its matches from `ctx.clean_pool()` only. Approved policies readable by Northwave support are missing from the cited lists: POL-009, POL-013, POL-016, POL-019, POL-021, POL-022, POL-025 and POL-026 for the 336 and 168 hour questions (eight policies), and POL-013, POL-016, POL-021, POL-025 and POL-026 for the 120 hour question (five). A system that lists every matching policy would be scored wrong. Disposition: withdraw those three questions from the pilot through a recorded exclusion list (card B04-T05.01); the permanent correction (all matching families, or wording limited to the reference set) goes to the generator before the seal (B08-T03.01). The gold file is not edited, so no hash changes.
- Other observations: items with two approved, equal-authority documents on one scope (a-05b502407120, a-39caaeb20270, a-486f830e70e0) are conflicts by construction and the gold marks them CONFLICT; instruction-like text inside tickets and FAQs (item 12 and item 17) was treated as data.
- Limits: one reader who built the pipeline and knows its templates; same model family as the second pass; agreement with the gold is not independence. BG-GOLD stays PARTIAL. The labels are in `artifacts/fixtures/S/generator/audit/owner_labels.jsonl` (untracked); the owner may relabel at any time with the guide and the report would be re-run.

## E-B04-005 — Track A pilot measurement (B04-T05.01)

Commands (from `palladion-benchmark/`, 2026-10-19; benchmark Qdrant 1.19.2 started by hand and stopped afterwards, Palladion runtime at 6444345, no generator call):

- `uv run python scripts/run_track_a.py --root artifacts/fixtures/S --split smoke --out artifacts/runs/pilot-c2 --run-id pilot-c2 --k 10 --budget 4000 --condition C2 --palladion --load-palladion` (fresh corpus load), then the same with `--condition C1 --run-id pilot-c1 --out artifacts/runs/pilot-c1 --index-dir artifacts/runs/pilot-c2/index` (no load). Both: 5 arms, 100 questions, 500 of 500 pairs OK, exit 0.
- `scripts/validate_results.py` PASS for both (secret values were not supplied, so only patterns were scanned). `scripts/score_track_a.py ... --k 10 --reference R0` PASS: 485 pairs each, which is 97 questions, because the three questions withdrawn in E-B02-006 (`configs/withdrawn_questions.json`) are left out and named at the head of each scorecard. The test split stayed unread.
- Tests for the exclusion list: full suite 974 passed with 10 errors, all from a launcher bug the run exposed (a recorded PID reused by a process whose executable cannot be read crashed the start); fixed with a test that fails on the old code, then the 10 and the launcher tests pass (10 and 25); two scorer tests and one CLI test were added; a planted defect (removing the filter) fails the owning test.

Observations only (C2; mean over the 72 questions where recall applies; intervals and all other metrics are in `artifacts/runs/pilot-c2/scorecard.md`, untracked). Recall at 10: R0 0.29, R1 0.04, R2 0.14, R3 0.19, R7a 0.06. Median latency: R0 11 ms, R1 33 ms, R2 45 ms, R3 1.9 s, R7a 1.1 s (maximum 7.0 s and 4.9 s). Forbidden-source exposure under C2 is 0 for every arm. Authority-confusion returns: R0 60, R1 32, R2 32, R3 44, R7a 0; wrong-vintage returns: R0 42, R1 7, R2 36, R3 33, R7a 0. Under C1 (no filter) recall falls to R0 0.24, R1 0.03, R2 0.13, R3 0.17, R7a 0.06 and forbidden exposures appear: R0 142, R1 204, R2 185, R3 159, R7a 159.

Hand inspection of failures: R7a returned nothing for 22 of 97 questions; 10 are Q1 and 2 are Q7 questions that name a policy or error code (all seven read name a code, the known BR24 behaviour) and 10 are Q9 live-status questions that have no document evidence. R7a's zero authority confusion and zero wrong vintages exist because only approved documents could be loaded into Palladion (BR28), not because it ranks better. R7a's C1 exposures follow from its single mapped reader (BR22): Palladion has no way to express the 17 benchmark principals, so without the harness filter it returns hidden documents; that is a property of the adapter mapping, not a measured Palladion defect. The dense arm's low recall is on a fixture whose queries mostly name policy and error identifiers, which a lexical arm matches exactly; the multilingual MiniLM model is small, and the result says nothing about dense retrieval in general.

Limits: one fixture, one seed, one pass (no repetitions, so no run-to-run variance); 72 questions with defined recall and small strata (7 to 10 per stratum), so the intervals are wide; the S tier is noise-heavy by construction; the gold was audited by one non-independent reader (E-B02-006); K=10 and a 4000-word budget only; R7a latency includes Palladion's coverage check (BR26); pilot results are excluded from held-out claims and support no superiority claim. BG-TRACKA stays PARTIAL until the sealed run (B08-T04.01).

## E-B04-006 — R7a re-runs after the loader change and the alias step (BADR-0027)

Same pilot settings as E-B04-005 (smoke split, K=10, budget 4000, R7a only, 97 scored questions, test split unread), on a fresh runtime reset with `palladion_runtime.py prepare --reset` and a fresh load that names superseded versions. Four runs, each passes `validate_results.py` and `score_track_a.py`: `r7a-plain-c2`, `r7a-plain-c1` (no aliases); then `scripts/palladion_aliases.py` registered 7,990 aliases over 4,786 chunks of 1,155 approved revisions (1,491 distinct), and `r7a-aliased-c2`, `r7a-aliased-c1`. The manifests record the alias counts and the job's digest. Tests: the first full run after the changes gave 979 passed, 1 failed and 13 errors (the Qdrant start timed out after 180 s and one import failed inside a subprocess, during a 32-minute run on a loaded machine); the failing and errored files were rerun and pass (hybrid 15 passed in 48 s, the bm25 and runtime files passed), the cause of the load-time failures is not established, and there is no single clean full run after the changes; the new tests (loader 3, alias step 6, launcher 1, scorer 3) pass and fail on planted defects.

Observations only (means over the 72 questions where recall applies): recall at 10 plain C2 0.055, plain C1 0.056, aliased C2 0.083, aliased C1 0.083 (pilot R7a, earlier load: 0.055). Empty answers: plain 22 (10 Q1, 10 Q9, 2 Q7 under C2), aliased 12 (10 Q9 and 2 Q7), so the 10 code-bearing Q1 answers now return passages. Forbidden-source exposure: 0 under C2, 150 (plain) and 189 (aliased) under C1. Authority confusion 0 in all four. Wrong-vintage returns: 0 in both plain runs and 24 in both aliased runs.

Reading. Naming the superseded version at approval changed nothing measurable (recall 0.055 against 0.055). The aliases removed the empty answers on code questions and raised recall by about 0.03, a small amount on small strata with wide intervals. The 24 wrong-vintage returns appear only with aliases; a plausible cause is that a family alias (for example `POL-001`) matches chunks of every version of that policy, and Palladion's wall clock, not the question's time, decides which version is current (BR22). That is a hypothesis, not a finding: it was not tested here. Nothing here shows Palladion ranks better or worse than R0 to R3, and the R7a results remain exploratory.

Process notes. The first attempt failed at `prepare --reset` with a seed error that did not repeat, and a script I stopped left its children running, one of them a Palladion server on the benchmark's own port; I stopped those by their process ids, deleted the partial run directories and repeated the reset. The alias driver first passed relative paths to a job that runs in another directory; found by the real run, fixed with a test, and the two aliased runs were redone after the fix (the two started before it were deleted unscored).
Limits: one seed, one pass; small strata; the alias set is the coordinator's design (family id plus every identifier-shaped token in each chunk), not Palladion's; the aliased variant departs from HTTP-only setup (BADR-0027).

## E-B05-001 — Pre-phase adversary for B05 (Haiku 5.5, medium effort) and dispositions

One read-only reviewer requested with model `haiku` and effort `medium`. It read the complete protocol, the master plan, the governance documents (not PROJECT_LEARNING, RESEARCH_PROTOCOL, OWNER_LABELLING_GUIDE; ADR_LOG and PALLADION_FIXES in part), the contracts, generator, runner, Track A, results validator, evaluation modules, gold schema and configs; it read no test file. It reported 20 findings (adv-1 to adv-20: 8 HIGH, 10 MEDIUM, 2 LOW) and six claims it could not refute. The coordinator verified adv-1, adv-2, adv-3, adv-9 and adv-17 by reading the code and data (marked V); the rest are accepted on the report and re-checked when their card is built. Dispositions (finding → action):

- adv-1 V (claims, actions and outcomes have no closed vocabulary: `allowed_actions` is empty in all 100 smoke records, `preferred_action` is free text, `policy_outcome` is set for 10 of 100) → new card B05-T07.01, answer-gold sidecar (BADR-0028 item 1) instead of changing the question file.
- adv-2 V (`score_run` marks any non-list OK payload invalid and the validator rejects it, so a Track B run would score as invalid) → new card B05-T08.01 with a controlled_qa validator branch.
- adv-3 V (`GenerationError` is a `ContractError`, so a rate limit after retries is classed as an arm contract violation; a slow call can make the whole arm unusable; a timed-out worker can still dispatch) → new card B05-T09.01.
- adv-4 (no live authorization, quota does not fit) → B05-T06.01 BLOCKED until the owner authorizes; replay stored candidates; size estimate marked an estimate.
- adv-5 (oracle condition does not fit Track B; re-running the resolver is circular) → oracle moved to B07-T08.01; policy scoring never calls the resolver.
- adv-6 (contradictory accounting; bounds) → BADR-0028 item 2.
- adv-7, adv-8 (undefined gate and budget unit; answers self-declare status and citations) → item 3; the scorer recomputes citations against the delivered bundle.
- adv-9 V (the arm-visible screen is applied in `contracts.py` and `questions.py` only; the generator checks role and length) → B05-T09.01 screens every message and keeps prompt text.
- adv-10, adv-16 (judge family rule, label store, who labels) → item 6 and the rubric card.
- adv-11 (citation syntax, entailment depends on later labels, stability) → items 1 and 8; entailment reads labels and counts unlabelled pairs.
- adv-12, adv-13 (hidden dependencies, incomplete Files) → cards rewritten, run logic moved to `benchmark/track_b.py`, claim scoring split into `claims.py`, test files named.
- adv-14, adv-15 (loss events and sweeps undefined; AURC without a score) → item 7.
- adv-17 V (null token budgets send everything to the primary model) → item 10.
- adv-18 (conditions and R7a variant unspecified) → item 3.
- adv-19 (leak scan skips short strings and actions) → B05-T08.01 includes action and outcome enums, matched on token boundaries.
- adv-20 (single run is not a repetition) → B05-T06.01 states outputs are single-run and descriptive.
- Limits: one model review is not proof; the reviewer read no tests and part of the ADR log; its size estimate is unmeasured.

## E-B05-002 — B05 build, validation and entry-point evidence

All commands from `palladion-benchmark/` on Windows, CPython 3.14, uv, 2026-10-20.

- Final run: `uv run pytest`: 1173 passed in about 10 minutes. `uv run ruff check .` clean; `uv run ruff format --check benchmark tests scripts` formatted; `uv run mypy` strict, no issues in 109 files; docs checker and its self-test pass.
- Built: the answer-gold sidecar and optional structured fields on `Claim` and `CaseResponse` (B05-T07.01); fault classification, the deadline, the cancel flag, the prompt screen and the prompt record in the generator (B05-T09.01); citation, claim, policy and abstention scorers (B05-T01.01 to B05-T03.01); the label store, blinded sampling and the judge audit with injected callables (B05-T04.02); the rubric and annotation guide (B05-T04.01); `track_b.py` and `scripts/run_track_b.py` (B05-T05.01); `eval/score_answers.py`, `scripts/score_track_b.py`, the validator's Track B branch and the scorecard (B05-T08.01).
- Entry-point smoke on the real S corpus, offline stand-in generator, no provider call: `run_track_b.py --arms R0,R2,R3 --generator stub --start-qdrant` ran 261 of 261 pairs (3 arms by 87 questions; 3 withdrawn and 10 native-only questions not asked); `validate_results.py` and `score_track_b.py` pass on it. The stand-in extracts the first window it finds and says nothing about any model; its scorecard says so.
- Not run: the live Track B pilot (B05-T06.01, blocked on the owner's authorization), any judge call, the dev split (no questions or answer-gold exist for it), repetitions.
- Limits: scores are over the offline stand-in only; the answer-gold covers the closed claim kinds the templates produce; free-text prose, text-only disclosure and entailment beyond the labels are not scored deterministically (BR30, BR31).

## E-B05-003 — Mutation sweeps over the B05 modules

A defect was planted one at a time in a temporary copy and the owning tests were required to fail. First sweep, 52 mutants across the answer-gold, citations, claims, policy, abstention, Track B, scoring, generator, label store and validator: 44 killed, 6 survived and 2 anchors had moved. The survivors were real gaps (precision over all checks rather than valid ones; a directive that differs from the gold; an outcome that does not break a correct answer; a superset of versions accepted; an incorrect claim costing nothing; a directive not counted as a false answer), each now has a test, and all 8 were killed on rerun. Second sweep after the audit fixes: 15 mutants (runner flags, delivered ids, answer-gold change, tie-break, verdict parsing, duplicate judges, arm-keyed labels, useful, directive, usage, prompt record, outcome vocabulary): 14 killed and 1 moved anchor killed by hand. Final state: no survivors. Limits: mutants were chosen by the coordinator.

## E-B05-004 — Post-phase audit for B05 (Haiku 5.5, medium effort) and dispositions

One read-only auditor requested with model `haiku` and effort `medium`. It read the complete protocol, the B05 plan, BADR-0028, E-B05-001, all B05 code and most tests; it ran ruff and mypy and did not run the tests. It reported 23 findings (aud-1 to aud-23: 4 HIGH, 12 MEDIUM, 7 LOW) and nine claims it could not refute. The coordinator verified aud-1 (all 261 stand-in ledger records had empty flags) and aud-8 (printed ratios with an invented numerator) by execution; the rest by reading the code. Dispositions (finding → action):

- aud-1 (a system arm's call notes never reached the ledger; my test was vacuous) → fixed in the Runner and the test now requires the model note on every final record. aud-2 (the cancel event was dead; the prompt was written before the refusal checks) → the dead event is removed, the generator's deadline sits inside the Runner's, the prompt is written only for a call that is made. aud-3 (one runner timeout disables an arm) → by design for a hang (BR14); a slow provider now ends as a normal timeout from the provider and does not disable the arm (BADR-0028 amendment).
- aud-4 (forbidden hits cost nothing; a claim counted twice) → each forbidden behaviour maps to an event and a claim costs one minor event, with tests for both.
- aud-5 (the validator does not reject a citation outside the bundle) → the card is corrected: that is a valid run and a fabrication in the score; the validator now also rejects delivered ids that differ from the prompt. aud-6 (a refused call left a prompt; the evidence word count split on blank lines) → fixed; passages now carry an explicit delimiter and are parsed whole. aud-7 (delivered ids and status come from the answer) → delivered ids are read from the kept prompt and a mismatch is an invalid answer; the status is the declared value checked against the gold (stated in the rubric). aud-8 → accuracies print the items they are over. aud-9 → usage counts every call. aud-10 → `MODEL_RESPONSE_TOO_LARGE` is a provider fault and the misnamed test is renamed. aud-11 → the latest write among equals stands. aud-12 → replies must be exactly YES or NO and a judge listed twice is one judge. aud-13 → labels are keyed by question, arm, claim and citation.
- aud-14 (deviations from BADR-0028) → the ADR is amended to what the code does (see the amendment). aud-15 → the outcome vocabulary is checked; `as_of_basis` is carried for B07 with no scorer yet (recorded). aud-16 → tests added for a planted answer-gold in a run directory and in the published tree. aud-17 → the answer-gold digest is recorded in the run configuration and checked. aud-18 → the zero-failure confidence comes from the evaluation configuration, the order seed from the benchmark configuration; the 5-second deadline margin stays a named constant. aud-19 → the scorecard says when every question ran on one model; the Track B split list is smoke only until dev gold exists. aud-20 → record ids carry a call number. aud-21 → `useful` requires the accepted status and reason and the wrong-vintage directive reads claims too; an unclassified uncited claim is not counted as a false claim (left to the label audit). aud-22 (withdrawn reasons written into the scorecard) → accepted, they are evaluator-side files. aud-23 → one answer parser (`CaseResponse.from_payload`), imports moved to the top, `RunnerError` is caught; long functions are left as they are.
- Limits: one model audit is not proof; the auditor did not run the tests or read all test bodies; the coordinator reproduced aud-1 and aud-8 by execution.
