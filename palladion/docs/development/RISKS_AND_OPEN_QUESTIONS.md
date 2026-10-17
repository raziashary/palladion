# Risks, accepted answers and verification obligations

Updated 2026-10-17. The user read and accepted all recommendation directions, except
fake-first runtime: use Groq `qwen/qwen3.8-27b`. uv and package-selection authority are
explicitly approved. **No unanswered owner decision blocks this documentation task.**
Implementation is nevertheless **WAIT_FOR_GO**. Acceptance does not invent compatibility,
thresholds, fixture values, reviewer availability, completeness or production signoff.

Owner answers live once in [ADR_LOG](ADR_LOG.md); edit **My answer (editable)** there.
This register tracks remaining evidence and deferred scope, not a competing answer inbox.

| ID | Question / accepted direction | Decision and state | Remaining evidence / owning phase |
|---|---|---|---|
| Q01 | Synthetic approval authority | [ADR-0012](ADR_LOG.md#adr-0012--q01--synthetic-approval-authority) ACCEPTED: authenticated administrator events; separate upload/approval grants | P01/P02 implement registry and reject self-approval/unauthorized grants; G-SOURCE/G-SECURITY |
| Q02 | Python packages, environment and model | [ADR-0013](ADR_LOG.md#adr-0013--q02--uv-and-real-groq-runtime-generation) ACCEPTED: uv, app-local uv venv, delegated package choices, actual Groq qwen/qwen3.8-27b; fake-first overridden | Working uv installed separately; user-created ignored app .venv exists (E-DOC-004). After GO verify/reuse it, pin packages/uv.lock and probe actual model/tool/schema/quota. Embeddings remain a measured compatible selection. No provider call now. |
| Q03 | Qdrant native RRF/BM25 compatibility | [ADR-0014](ADR_LOG.md#adr-0014--q03--qdrant-hybrid-compatibility) ACCEPTED_DIRECTION; VERIFY_AT_IMPLEMENTATION | P02 compatible server/client probe, same-point dense/bm25, one RRF k=60, matched ingest/query weighting. Pin actual supported mode/version. |
| Q04 | English/Indonesian processing | [ADR-0015](ADR_LOG.md#adr-0015--q04--english-and-indonesian-retrieval) ACCEPTED_DIRECTION; VERIFY_AT_IMPLEMENTATION | P02/P08 record language mix, compare tokenizer/stemming variants on development labels, pin winner and report per-language metrics. No claimed improvement yet. |
| Q05 | Historical audits and time-basis migrations | [ADR-0016](ADR_LOG.md#adr-0016--q05--historical-audit-and-time-basis-migration) ACCEPTED_DIRECTION: minimal valid/record-time plus knowledge_cutoff, mixed-basis conflict unless explicit precedence | P03 define/review synthetic historical query fixtures and replay traces; no inferred migration or real-business retention rule. |
| Q06 | External inventory attestation/change feed | [ADR-0017](ADR_LOG.md#adr-0017--q06--external-inventory-boundary) ACCEPTED_DIRECTION; external integration DEFERRED | Distinguish INDEX_COVERAGE from INVENTORY_ATTESTED now; later owner-provided attester/scope/change contract. T12 preserves uncertainty. |
| Q07 | Reported validity and live freshness | [ADR-0018](ADR_LOG.md#adr-0018--q07--fact-validity-and-observation-freshness) ACCEPTED_DIRECTION: use-specific owner/config values, separate timestamps, no model expiry | P03/P05 record explicit synthetic fixture values/owner/rule, test stale BI and UNSPECIFIED lifetime; no numerical company policy invented. |
| Q08 | Labels, targets, splits and repetitions | [ADR-0019](ADR_LOG.md#adr-0019--q08--honest-research-acceptance) ACCEPTED_DIRECTION: two annotators/adjudication, B0/B1 development calibration, freeze before held-out | P02 pilots/P08 preregistration; actual annotator availability, case counts, repetitions and thresholds remain measured/recorded prerequisites to quantitative claims. |
| Q09 | Semantic support and escalation | [ADR-0020](ADR_LOG.md#adr-0020--q09--claim-support-and-human-escalation) ACCEPTED_DIRECTION: independent support/exception rubric, named authorized human escalation, qualify insufficient adequacy | P04 record actual rubric/reviewer assignment and gold support labels; valid citation alone is not proof. No imaginary reviewer/signoff. |
| Q10 | Optional graph/vector/planner/fusion/adaptive review | [ADR-0021](ADR_LOG.md#adr-0021--q10--optional-complexity-needs-controlled-evidence) ACCEPTED_DIRECTION: controlled flags, paired parent ablations, always-on critic labels first | Owning experiments measure incremental value/harm/cost; initially selected Groq model, no silent provider switch or default normative critic bypass. |
| Q11 | External standard RAG/LangChain/provider comparisons | [ADR-0022](ADR_LOG.md#adr-0022--q11--later-external-comparator-systems) ACCEPTED_DIRECTION; implementation DEFERRED to X01 | baseline/ isolated later; exact versions/capability tracks/shared evaluator and cost disclosures remain future evidence. No comparator built. |
| Q12 | Real identity, data privacy and production | [ADR-0023](ADR_LOG.md#adr-0023--q12--real-data-and-production-boundary) ACCEPTED_DIRECTION: synthetic-only until legitimate access/security/retention approvals | Real connectors/deployment DEFERRED; actual signoff required then, prototype test-set success cannot imply production readiness. |

## Owner decision inbox

All twelve recommendation directions are now answered in ADR-0012–ADR-0023. The
current exceptions/explicit choices are Groq runtime, exact model, uv and delegated
package selection. ADR-0011 records the editable answer format, mandatory pre-phase
adversary, single post-phase work auditor, full-vision audit and explicit GO hold.

No repeat approval is required for the accepted directions or compatible packages within
that scope after GO. Record concrete technical choices, fixture assumptions and results
when known. Material departures, new shipped-contract changes or real-data access still
follow universal escalation rules; package authority does not waive those boundaries.

## Credential and environment observation

Root `.env` exists and is ignored by the user's current root `.gitignore`; it was not
read, copied, printed or staged. That `.gitignore` is user-owned/untracked at task start
and is preserved. At that observation it listed `.env` and `venv`; the latter does not
cover `.venv`. User was advised to add `.venv/` before manually running `uv venv` inside
`C:/palladion/palladion`. Recheck ignore behavior at setup; do not relocate/copy secrets.

Current correction (E-DOC-004): the owner updated root ignore rules to `.env` and `.venv/`
and created the app environment. Interpreter existence and git check-ignore are verified;
publish those existing ignore rules unchanged. The earlier observation above is historical,
not a current missing-environment blocker. App packages/locked sync still await P01 GO.

## Updating this register

Keep stable Q IDs. When evidence arrives, cite the actual run/test and limits; accepted
recommendation is not completion. New unresolved decisions get a structured ADR with
an empty owner answer; do not silently infer approval. Maintain deferred rows until
that scope is explicitly invoked. Source evidence and current owner answers outrank
historical task wording. After this docs task, wait for explicit GO before P01.
