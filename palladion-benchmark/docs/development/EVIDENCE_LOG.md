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

Task: B00-T04.02. Recorded in the commit that follows this log; the commit hash and push result are appended to PROGRESS once the push is verified.
Intended steps: re-run the checker and self-test, scan the staged diff for secrets, stage only `palladion-benchmark/` paths, commit with a Conventional
Commit subject and body, confirm `git log origin/main..HEAD` holds only this commit, then push `main`.
