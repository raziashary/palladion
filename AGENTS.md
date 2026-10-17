# Palladion project instructions

These instructions supplement the user's universal development rules. Repository root is
`C:/palladion`; the system project is `palladion/`. Do not create a nested `evidence-agent/`
repository from the blueprint's illustrative tree.

## Start every task

1. Read the current user request and these instructions.
2. Follow [Master development plan — Task reading and execution protocol](palladion/docs/development/MASTER_DEV_PLAN.md#task-reading-and-execution-protocol).
3. Read the goal, current progress, working memory, relevant ADRs, task row, gates,
   blueprint sections, and affected live source/tests before editing. A fresh contributor
   reads the full blueprint once; repeat affected sections on every task.
4. Verify branch, diff, and worktrees. Documents describe intended behavior; only source,
   executed checks, and measured results establish implemented behavior.

## Scope and integrity

- Current mandate: development documentation suite only. Product implementation begins
  in a subsequent task against the master plan. No UI work. `baseline/` is reserved for
  later comparator implementations; do not populate it as part of this setup.
- Preserve the [vision](palladion/docs/vision/palladion-blueprint-v2.md). Do not silently
  change locked decisions or treat representative code as complete production code.
- Keep all agent-created project planning, memory, learning, decisions, and evidence in
  `palladion/docs/development/`. There is exactly one `PROJECT_MEMORY.md`.
- Four read tools only; canonical evidence and deterministic policy/gate own authority.
  Synthetic data and mock operational systems only until explicitly authorized otherwise.
- Do not claim hypothesis success, production readiness, or baseline superiority without
  the required measurements. Test-set integrity gates are not universal guarantees.
- Log material decisions immediately in `ADR_LOG.md`; unresolved choices stay in
  `RISKS_AND_OPEN_QUESTIONS.md`. Update affected records in the same logical unit.
- Every subagent must use **GPT 6 Luna, High effort** (`gpt-6-luna`, `high`), per the user.
  If unavailable, report that limitation; do not substitute another model silently.
  Scope each dispatch, remove live-resource credentials, prohibit git/external mutations,
  and keep reviewers independent. The coordinator owns integration and status updates.
- Follow the user's approval rules for destructive actions, contract changes, new
  dependencies, remote branches, PRs, and pushes to main. A plan is not blanket approval.

## Close every task

Run the applicable [testing gates](palladion/docs/development/TESTING_GATES.md), preserve
failure and consumer-side evidence, update progress/goal/memory/map/learning as affected,
and stop only processes started by the task. Review and deliberately stage only scoped
files. Commits require a Conventional Commit subject and descriptive body. Do not push
this `main` checkout without explicit approval.
