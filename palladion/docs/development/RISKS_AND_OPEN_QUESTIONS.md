# Risks and open questions

All rows OPEN unless explicitly closed with an ADR and evidence. These are nonblocking
for P00 documentation. Do not invent business rules or silently select new dependencies.
The coordinator proposes grounded options; the user/policy owner approves escalated choices.

| ID | Unknown / risk and governing source | Owner / resolve before | Safe treatment and evidence needed |
|---|---|---|---|
| Q01 | Approval record simulation; blueprint Remaining open issues | User/design owner; P01-T01 | Propose simplest authenticated synthetic admin approval event vs simulated signatures/management metadata; select explicitly, never trust document prose. Test unauthorized/self approval. |
| Q02 | Exact Python tooling, packages, provider/embedding model and pins not chosen | User/coordinator; P01-T01 and P02-T02, paid calls only after enablement | Inspect available tools; propose minimal dependencies in blueprint stack; approve new dependencies per universal rules. Use fake LLM first, record installed versions. No default runtime model inferred from Luna development-agent instruction. |
| Q03 | Qdrant/client native parameterized RRF and sparse BM25 mode compatibility | Coordinator; P02-T02 | Verify official pinned-version APIs at implementation time and run an integration probe. Decide server/client BM25 mode; keep ingest/query model/tokenizer identical and one fusion stage. Do not silently copy SDK illustration. |
| Q04 | English/Indonesian tokenization, stemming and corpus distribution | Research owner; P02-T02 then P08-T01 | Record language mix, compare processing variants on development labels and pin manifest. No unmeasured language-quality claim. |
| Q05 | Time-basis migration, retroactive corrections and audit retention scope | Policy/user owner; P03-T01 | Default ambiguous incompatible timelines to conflict. Need explicit migration/precedence semantics and required knowledge-cutoff audit queries. Never invent a signed business rule. |
| Q06 | External inventory attestation/change feed interface and trust | User/application owner; before completeness claims or X01 | Keep supplied-source reconciliation separate; define attester/scope/time/change handling. Neither recall nor critic certifies unsupplied documents. |
| Q07 | Action-specific freshness, reported-fact validity and live operation limits | Synthetic policy/adapter owner; P03-T03/P05-T01 | Fixture values explicitly synthetic and sourced to owner; no model TTL. Decide permitted age by fact and use, preserving all timestamp meanings. |
| Q08 | Gold size, two annotators, adjudication, splits/seeds/repetitions, metrics/targets and cost/latency tradeoffs | Research/user owner; pilot before meaningful quantitative claims, freeze by P08-T01 | Establish B0/B1 observations first, then preregister numerical targets before held-out. If independent annotations unavailable, label pilot-only. Keep failure denominators. |
| Q09 | Natural-language entailment, exception sufficiency, critical challenge resolution and escalation owner | User/domain owner; before consequential supported demonstrations | Necessary-condition gate isn't a proof solver. Define supported-claim rubric and human escalation; insufficient adequacy stays qualified. Independently labeled support precision required. |
| Q10 | Graph, vector memory, planner, reranker/fusion and adaptive critic value | Research owner; owning experiment before enable/retention | Disabled/controlled feature flags; paired parent-treatment evidence, measured harms and costs. Always-on normative critic data before adaptive bypass. |
| Q11 | Exact external comparator versions, capabilities, adapter contract and resource tracks | User/research owner; X01 only | Keep baseline/ empty now. Later distinguish standard pipeline/library/provider product and capability gaps, matching corpus/access/budget where possible; no hidden privileged inputs. |
| Q12 | Real identity integration, source approval security, privacy/retention and production operations | User/security/policy owners; before any real data/connector deployment | Synthetic-only prototype; no production-ready claim. Require legitimate access, real threat review, retention and audit protections. SQLite append-only events are not automatically tamper-evident. |

## Escalation and conflict handling

### Owner decision inbox

The documentation decisions ADR-0009/ADR-0010 are accepted from the user's explicit
requests. The implementation choices below remain **proposals**, not silently made ADRs.
They do not block finishing this documentation revision. The user asked to make needed
ADRs before a push if everything is resolved, so retain this inbox and report it at closeout.

| When / owner decision | Recommendation to consider | Exact execution card |
|---|---|---|
| Before P01, Q01: how synthetic approval becomes trusted | Start with authenticated administrator approval events and separate upload/approval grants; simulate signatures only if they test a needed hypothesis. | [P01-T01.01](MASTER_DEV_PLAN.md#p01-t01-01) |
| Before package setup, Q02: approve concrete dependencies/tooling and model execution scope | Keep fake LLMs first. Propose compatible Python/tooling/client/model pins after source/API checks; hosted/local generation and spending require explicit enablement. Development-agent Luna choice does not select runtime models. | [P01-T01.02](MASTER_DEV_PLAN.md#p01-t01-02), [P01-T01.03](MASTER_DEV_PLAN.md#p01-t01-03) |
| Before temporal implementation, Q05: audit reconstruction scope and any time-basis migration | Use declared basis and knowledge_cutoff; incompatible timelines remain conflict unless owner supplies approved migration/precedence. Define retained historical queries rather than build a full temporal database. | [P03-T01.04](MASTER_DEV_PLAN.md#p03-t01-04) |
| Before live fixtures, Q07: synthetic observation freshness/validity values | Let each synthetic policy/adapter owner declare use-specific limits; preserve historical observation separately. Do not invent universal TTL or treat reported validity as freshness. | [P03-T03.01](MASTER_DEV_PLAN.md#p03-t03-01) |
| Before consequential supported demonstrations, Q09: claim adequacy and escalation owner | Approve a support/exception rubric and designated human escalation when necessary-condition checks cannot establish adequacy; preserve qualified outcomes. | [P04-T03.04](MASTER_DEV_PLAN.md#p04-t03-04) |
| Before held-out research, Q08: annotation resources, splits, repetitions, numerical acceptance and tradeoffs | Two independent annotators plus adjudication; calibrate on B0/B1 development data and freeze criteria before held-out. Label earlier evidence pilot-only if resources unavailable. | [P08-T01.01](MASTER_DEV_PLAN.md#p08-t01-01) |

Q03/Q04 primarily require implementation-time API/language compatibility evidence and
may lead to a dependency decision; Q06/Q11/Q12 concern later inventory/comparator/real
deployment scope. Q10 optional treatments need their declared owner/dependency choices
before enablement. These are not requests to decide every future detail now.

A missing future choice is not a reason to stop unrelated documentation or mock-only work.
At the owning implementation task, present the decision, evidenced options, recommendation
and required direction before dependent changes. A conflict with locked blueprint/user
constraints is surfaced explicitly; do not redefine the rule through an implementation shortcut.

Risks found later receive new stable IDs. Close a row only with owner, date, ADR/evidence,
remaining scope and revisit condition. Material newly discovered bugs follow universal
in-scope-fix versus out-of-scope-record rules.
