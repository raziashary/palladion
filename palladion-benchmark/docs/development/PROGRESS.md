# Current progress

Updated 2026-10-18. Atomic task state lives in the [master plan](MASTER_DEV_PLAN.md);
command observations and review receipts live in the [evidence log](EVIDENCE_LOG.md).

## Current checkpoint

B00 (development suite) is DONE pending verification of the push (E-B00-004). The suite, the checker
and the uv bootstrap were written under the owner's 2026-10-18 request; the independent Haiku 5.5 review
returned 26 findings, dispositioned in E-B00-003. No benchmark code, fixture, retriever, provider call
or measurement exists. No benchmark gate other than BG-DOC has been run.

Owner answers recorded: benchmark lives in this repo as its own uv project (BADR-0001); generator pool is
Groq qwen/qwen3.8-27b, openai/gpt-oss-120b and openai/gpt-oss-20b (BADR-0007); template-first corpus
(BADR-0009); subagents only as needed and only Haiku 5.5 (BADR-0003); push to main allowed (BADR-0004).
Since then the owner also answered OQ01, OQ02, OQ04–OQ08 and OQ11 and accepted BADR-0006, BADR-0008 and BADR-0013.
Still open and tracked: OQ03 (read at B04), OQ09 (before B08-T07.01) and OQ10 (before B08-T03.01); see
[risks and open questions](RISKS_AND_OPEN_QUESTIONS.md).

## Phase state

| Phase | State | Evidence / next action |
|---|---|---|
| B00 | DONE | E-B00-001 to E-B00-004; push verification recorded in E-B00-004 |
| B01 | PLANNED | Awaits owner GO and the pre-phase adversary |
| B02 | PLANNED | Depends on B01 |
| B03 | PLANNED | Depends on B02 gold schema |
| B04 | PLANNED | Depends on B02, B03; needs Palladion's interface (OQ03) |
| B05 | PLANNED | Depends on B04, B01-T05 |
| B06 | PLANNED | Depends on B04; quota question OQ06 |
| B07 | PLANNED | Depends on B04, B05, B02 |
| B08 | PLANNED | Depends on B04–B07 exits |
| B09 | DEFERRED | Conditional replication and stress |

## Gate state

| Gate | State | Evidence and limits |
|---|---|---|
| BG-DOC | PASS | Checker and self-test in E-B00-001; independent review E-B00-003. Structural plus one model review only |
| BG-HARNESS | NOT_RUN | B01 |
| BG-FIXTURE | NOT_RUN | B02 |
| BG-GOLD | NOT_RUN | B02 |
| BG-METRIC | NOT_RUN | B03 |
| BG-STATS | NOT_RUN | B03 |
| BG-ADAPTER | NOT_RUN | B01, B04 |
| BG-FAIR | NOT_RUN | B04 |
| BG-TRACKA | NOT_RUN | B04 |
| BG-TRACKB | NOT_RUN | B05 |
| BG-TRACKC | NOT_RUN | B07 |
| BG-SECURITY | NOT_RUN | B02 onward |
| BG-PREREG | NOT_RUN | B08 |
| BG-ABLATION | NOT_RUN | B08 |
| BG-REPRO | NOT_RUN | B01 onward |
| BG-REPORT | NOT_RUN | B03, B08 |

## Blocked or waiting cards (the checker prints these as notices)

B01-T05.01 needs the model-selection rule implemented per BADR-0008 (answered); B01-T05.02 on an explicit enable flag (OQ01 answered); B04-T03.01 on reading Palladion's live interface (OQ03);
B04-T01.02 and B04-T02.02 on reading Palladion's pins (OQ04, OQ05 answered; reranker download needs the owner's yes); B07-T04.01 on Palladion shipping a critic switch (OQ11 answered: FEATURE_NOT_SUPPORTED until then); B08-T03.01 on OQ10 (confirmatory pairings, owner deferred; must be answered before the seal);
B08-T07.01 on OQ09 (dataset license, owner deferred; must be answered before then); B08-T01.02 on the paraphrase gate. Phase B01 does not start until the owner says GO.

## Next action

Report to the owner and wait for GO on B01. B01 starts with the pre-phase Haiku 5.5 adversary. B01-T05.02 will make the first real provider calls only on an explicit enable flag.
