# Palladion benchmark project instructions

These instructions supplement the user's universal development rules and apply to work under
`palladion-benchmark/`. They are separate from the repository-root `AGENTS.md`, which governs the
Palladion system contributor and is not edited from here. Repository root is `C:/palladion`.

## Start every task

1. Read the current request and these instructions.
2. Follow the [master plan's task reading and execution protocol](docs/development/MASTER_DEV_PLAN.md#task-reading-and-execution-protocol).
3. Read the [goal](docs/development/GOAL.md), [progress](docs/development/PROGRESS.md), [working memory](docs/development/PROJECT_MEMORY.md),
   the relevant ADRs, the parent work package and exact atomic card, the gates, and the protocol sections
   the card names. A fresh contributor reads the whole [research protocol](docs/vision/palladion_retrieval_benchmark_research_protocol.md) once.
4. Verify branch, diff and worktrees. Documents state intent; only source, executed checks and measurements show behavior.

## Scope and integrity

- This project builds the benchmark. It never edits, stages or commits anything under `palladion/` or the repository-root
  files. Learn Palladion's interface by reading its live source and docs; reach it only through an adapter over its
  HTTP interface, never by importing its code (BADR-0002).
- The research protocol is the vision. Do not silently change its locked methods. Its numbers are provisional until the
  B08-T03.01 seal; after the seal, changes flag later results exploratory.
- Keep planning, memory, learning, decisions and evidence in `docs/development/`. Exactly one `PROJECT_MEMORY.md`.
- Log material decisions immediately in `ADR_LOG.md` using Question, Why, Options, Recommendation, What affects what,
  My answer (editable), Verification, Status and Authority. Unresolved choices go to `RISKS_AND_OPEN_QUESTIONS.md`.
  Read the owner's answer before each affected task; an empty or proposed answer grants nothing.
- Data is fictional and synthetic only. No real company, customer, transaction or credential data. Mark generated
  artifacts as fictional.
- Do not claim hypothesis success, superiority, production readiness or "best RAG" without the required sealed
  measurement. Zero observed failures are reported with an upper bound.
- Missing, unsupported, invalid or timed-out runs are results, never zeros and never dropped.
- Generator pool is Groq `qwen/qwen3.8-27b` with `openai/gpt-oss-120b` and `openai/gpt-oss-20b` as explicit,
  recorded alternatives when rate limited (BADR-0007, BADR-0008). Never a hidden fallback. Secrets stay in a
  gitignored `.env`, are loaded only by an explicitly enabled command, and are never printed, committed, copied from
  Palladion's `.env`, or given to a subagent. Credential presence is not permission to spend.
- Libraries may be added (BADR-0005) with the dependency recorded on the card. Use `uv`; comparators live in
  separate pinned environments.
- Subagents: only as needed, only Haiku 5.5 (BADR-0003). Default roles are one read-only adversary before a phase and one
  read-only auditor after its gates. Each reads the complete protocol, gets no credentials, makes no git or external changes,
  and gets a self-contained brief with exact paths and an output contract. The coordinator verifies every load-bearing
  finding and owns integration, task state and status. If Haiku 5.5 is unavailable, say so and ask; do not substitute silently.

## Evidence and execution rules

1. **Two anchors.** The protocol governs intent; live code, fixtures and measured behavior establish reality.
2. **One bounded task.** Use the master plan's child ID and file ownership. Update the checkbox and PROGRESS together.
   A parent closes only after all children and its own acceptance are proven.
3. **Prove the actual path.** Exercise the real entry point and consumer, including readback. A helper with no caller,
   a matching string or a passing import is not integration.
4. **Checks that can fail.** Give every guard a positive and a negative control; distinguish a guard rejection from a setup error.
   Every metric gets perfect, empty and shuffled controls and a hand-computed case.
5. **Preserve measurements.** Keep exact commands, exit status, counts and raw observations with pointers. Never filter to
   success lines. A bounded search proves only its scope. Separate inference from measurement.
6. **Measure the boundary that matters.** Record provider, model revision, tokenizer, index generation, language, scope and
   configuration. One model or method cannot establish another's behavior; similarity scores are not probabilities.
7. **Information barrier.** Gold labels are evaluator-only. Nothing arm-visible, including prompts, embeddings, graph builds
   and file names, may contain expected answers, required citations or outcome labels (BI01, BI03).
8. **Resolve review findings visibly:** finding, evidence, consequence, owner, disposition, verification. Material unresolved
   findings keep the phase open. Deferrals keep a named owner and destination.
9. **Keep derived records live.** At closeout update learning, plan, gates, progress, map, memory and READMEs. Strike wrong
   claims and append the correcting evidence; do not erase failed history.
10. **Shared checkout hygiene.** Another contributor edits `palladion/` in the same working tree. Inspect status first, stage
    explicit `palladion-benchmark/` paths only, run `git diff --cached --name-only` before every commit, and commit with a path
    list so unrelated staged files cannot ride along.

## Phase closeout order

Build the bounded task → stack validation (`uv run pytest`, `ruff`, `mypy`) → entry-point smoke → owning gates → end-of-phase
auditor and resolution → learning, status and evidence updates → no-stale sweep including READMEs → process and port cleanup →
scoped staged-diff and secret review → verified commit → continue only authorized work. Skipped checks are not PASS. For
documentation-only work the checker is the entry point: `python palladion-benchmark/docs/development/check_docs.py` and `--self-test`.

## Version control

Commit one logical unit at a time with a Conventional Commit subject and a descriptive body (reason, meaningful changes,
validation and limits). Pushing to `main` is permitted by the owner (BADR-0004) after verifying `git log origin/main..HEAD`
holds only benchmark commits. Never force-push, rewrite published history, tag, delete branches, or change git config. If a
push is rejected, fetch, report the divergence and ask. Do not commit secrets, `.env`, generated corpora or large artifacts.

## Close every task

Run the applicable [testing gates](docs/development/TESTING_GATES.md), preserve failure and consumer-side evidence, update
progress, goal, memory, map and learning as affected, and stop only processes the task started.
