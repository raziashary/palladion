# Palladion documentation

The [blueprint v0.2](vision/palladion-blueprint-v2.md) is the master vision. Its 18 sections
describe intended architecture, representative interfaces, experiments, and eight build
slices. Its proposed 74-file tree is not the current repository.

All development working documents live in **[development/](development/MASTER_DEV_PLAN.md)**.
Begin with the master plan's reading protocol and the current progress record.

| Document | Owns |
|---|---|
| [MASTER_DEV_PLAN.md](development/MASTER_DEV_PLAN.md) | Per-task rules, work packages, atomic file-specific checkbox cards, dependencies, proof, phase exits |
| [GOAL.md](development/GOAL.md) | Checkable current setup goal and longer-term system outcomes |
| [ADR_LOG.md](development/ADR_LOG.md) | Questions, reasons, recommendations, impact and editable owner answers; accepted versus verified state |
| [TESTING_GATES.md](development/TESTING_GATES.md) | Integrity gates, hard cases, validation and smoke procedures |
| [RESEARCH_PROTOCOL.md](development/RESEARCH_PROTOCOL.md) | Hypotheses, metrics, ablations, honest later comparisons |
| [REQUIREMENTS_TRACEABILITY.md](development/REQUIREMENTS_TRACEABILITY.md) | Blueprint-to-task-to-proof coverage |
| [PROJECT_MAP.md](development/PROJECT_MAP.md) | Actual repository and explicitly planned architecture/flows |
| [PROJECT_MEMORY.md](development/PROJECT_MEMORY.md) | Compact recovery/navigation facts |
| [PROJECT_LEARNING.md](development/PROJECT_LEARNING.md) | Evidence-backed lessons, experiments, corrections |
| [PROGRESS.md](development/PROGRESS.md) | Current task/gate status, checkpoint and next action |
| [RISKS_AND_OPEN_QUESTIONS.md](development/RISKS_AND_OPEN_QUESTIONS.md) | All accepted Q01–Q12 directions, remaining verification and deferred scope |
| [EVIDENCE_LOG.md](development/EVIDENCE_LOG.md) | Verification records and evidence format |
| [check_docs.py](development/check_docs.py) | Dependency-free structural documentation check |

Authority, update rules, and conflict handling are defined once in the master plan.
Do not create competing plans, memories, or unlinked status files elsewhere.

Current scope is P01 end-to-end under explicit GO. Foundation code/locked packaging,
contracts/access/storage and synthetic fixtures are verified complete, with 75 tests,
installed-wheel smoke and single independent audit/resolution at E-P01-001. P02 and provider calls are outside this phase.
Both phase reviewers read the full blueprint under the master review contract.
