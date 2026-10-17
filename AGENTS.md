# Palladion project instructions

These instructions supplement the user's universal development rules. Repository root is
`C:/palladion`; the system project is `palladion/`. Do not create a nested `evidence-agent/`
repository from the blueprint's illustrative tree.

## Start every task

1. Read the current user request and these instructions.
2. Follow [Master development plan — Task reading and execution protocol](palladion/docs/development/MASTER_DEV_PLAN.md#task-reading-and-execution-protocol).
3. Read the goal, current progress, working memory, relevant ADRs, parent work package,
   exact atomic task card and dependencies, gates,
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

## Evidence and execution rules

These rules adapt useful methods from Arcana's master plan “Rules of Development,”
“Method rules,” and “Learnings register” to Palladion. ADR-0010 records the selection.
The user's universal instructions remain governing; Arcana's product-specific rules
and architecture are not imported.

1. **Use both anchors.** The blueprint governs intent; live code, schema and observed
   behavior establish reality. Surface conflicts before changing a contract. Representative
   code, comments and old status summaries are claims to check, not substitutes for source.
2. **Execute one bounded task.** Use the master plan's checkboxed child ID and exact file
   ownership. Verify prerequisites, named producers/readers and required proof before
   editing. Update the checkbox and PROGRESS together; a parent closes only after every
   child and its own acceptance are proven. A list of files is not implementation evidence.
3. **Try to refute substantial phase premises before building.** Check that named APIs,
   sources, permissions and consumer paths really exist. For a substantial phase use a
   scoped independent Luna High review where it adds coverage. Record confirmed, refuted,
   partial and uncertain claims; verify load-bearing findings in the main session and
   correct the plan/gates before dependent code. Post-build review serves a different purpose.
4. **Prove the actual path.** Exercise the entry point and production consumer, including
   persistence reopen/readback where relevant. A helper with no caller, a test of a dead
   entry point, a matching source string or a passing import does not prove integration.
5. **Make checks capable of failing for the intended reason.** Use positive and negative
   controls. Distinguish a guard rejection from syntax/import/setup failure. Test security
   canaries are absent, not merely that a redaction marker appeared. Exclude a check's
   own fixtures/assertions from searches intended to prove production declarations.
6. **Preserve measurements and scope.** Retain exact commands, exit status, counts and
   necessary raw observations with source/artifact pointers; separate inference from
   measurement. Never filter to success lines, truncate before a possible failure, or
   replace a failed check with an unconditional success message. A bounded search proves
   only its searched scope. Recheck replacement explanations as carefully as the first.
7. **Measure the boundary that matters.** Record provider, tokenizer, index generation,
   language, authorized scope and configuration. One provider's behavior cannot establish
   another's. A missing signal is not negative evidence; a citation ID/hash is not semantic
   support; no hits or model agreement cannot certify unsupplied source completeness.
8. **Resolve review findings visibly.** Record finding, evidence, consequence, owner,
   disposition and verification. Fix authorized in-scope issues; report decisions requiring
   the user's judgment. Material unresolved findings keep the affected task/phase open.
   Out-of-scope deferrals retain a named owner and destination rather than disappearing.
9. **Keep learning and derived records live.** At each phase closeout record mistakes,
   refuted claims and methods that worked in PROJECT_LEARNING, then update affected plan,
   gates, progress, map/memory, research records and README. Derive task counts from the
   checkbox register; do not present a checkbox percentage as system readiness. Strike
   incorrect claims and append correction evidence/mechanism; do not erase failed history.
10. **Protect work during delegation.** Inspect dirty/untracked files and preserve needed
    state before concurrent writers. Use disjoint ownership; no automatic stash/reset.
    Give every agent a self-contained brief, exact resource restrictions and source
    warnings. Long investigations report findings incrementally so the coordinator can
    persist them; an agent may write only an explicitly assigned report or owned files.
11. **Preserve data through lifecycle changes.** Test fresh schema creation and populated
    upgrades, interrupted ingest and idempotent recovery separately. A successful upgrade
    does not prove new-install correctness. Back up real persistent resources before
    destructive/schema-rewriting operations; transient index cleanup cannot replace ACL.

## Phase closeout order

Build the bounded task → stack validation → actual entry-point smoke → owning integrity
gates → independent review where warranted and resolution of findings → learning and
status/evidence updates → no-stale sweep including README/navigation → process/port
cleanup → scoped staged-diff/secret review → verified commit → continue authorized work.
Skipped checks are not PASS. PARTIAL evidence does not close a later consumer obligation.
For documentation-only work, the document checker CLI is the runnable entry point;
application gates remain NOT_RUN. A checkpoint never expands the user's current mandate.

## Close every task

Run the applicable [testing gates](palladion/docs/development/TESTING_GATES.md), preserve
failure and consumer-side evidence, update progress/goal/memory/map/learning as affected,
and stop only processes started by the task. Review and deliberately stage only scoped
files. Commits require a Conventional Commit subject and descriptive body. Do not push
this `main` checkout without explicit approval.
