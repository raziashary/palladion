# Palladion limits: what we mitigate here and what needs a fix in Palladion

Written 2026-10-19 from [RISKS_AND_OPEN_QUESTIONS](RISKS_AND_OPEN_QUESTIONS.md) (BR12, BR22, BR24, BR26, BR27, BR28 and
OQ11) and a read of Palladion's live source at the pinned commit `6444345` (`palladion/src/evidence_agent/`). Line numbers
are from that source and can drift. This document is read-only toward Palladion: the benchmark never edits `palladion/`
(BADR-0002). Part B is the hand-off to its contributor; nothing in it has been agreed with them.

Reading guide. **Part A** lists what the benchmark does or can do on its own side, with its state. **Part B** lists the
changes only the Palladion contributor can make, each with what, where, why, how, how to prove it and what the benchmark
does afterwards. **Part C** records what the owner decided. A row here is not an approval; decisions live in
[ADR_LOG](ADR_LOG.md).

## Summary

| Item | Limit (risk) | Without touching Palladion | Needs a Palladion fix |
|---|---|---|---|
| BR24 | A query naming a code returns nothing (22 of 100 smoke questions) | Yes, with a setup step (A1, owner approved as a second variant) | PF02 is the proper fix |
| BR28 | Supersession was not sent when approving versions | Yes, over HTTP (A2, done in the loader) | None |
| BR27 | Palladion cannot see our 17 principals, so our filter runs after its cut | Partly, before B08 (A3, owner chose later) | PF05 (admin route for principals) |
| BR22 | No clock, so as-of strata are unscorable for R7a | No | PF01 (small) |
| BR26 | Coverage check on every search: DEGRADED at scale and slow | No (report only) | PF03 |
| BR12 | K above 12 refused, no token budget | Harness enforces both (A5) | PF04 (optional) |
| BR34 | No HTTP route creates graph links, so R7b has an empty graph | No (R7b is FEATURE_NOT_SUPPORTED) | PF07 (needed only for R7b) |
| OQ11 | No switches for critic, gate, preflight, authority check, parser, temporal resolver | No | PF06 (needed for B07) |

---

## Part A — What we mitigate without touching Palladion

### A1. BR24 — exact-identifier aliases (approved 2026-10-19 as a second variant)

*What happens.* Palladion's search pulls identifier-shaped tokens out of the query (`storage/exact.py:9`, a capital letter,
then a dash or dot, e.g. `MS-1954`, `POL-001`, `TXN-KES-00042`). Each token is looked up in the `exact_aliases` table. If
a query holds such a token and no alias matches, `retrieval/hybrid.py:69-72` sets `EXACT_IDENTIFIER_NOT_FOUND` and
**empties the candidate list, including the semantic hits**. Only Palladion's own seed registers aliases
(`core/bootstrap.py:61-65`); a document loaded over HTTP gets none. So R7a answers nothing for every code-bearing question.

*Mitigation.* A benchmark-owned setup step, run once after the load, registers the aliases an operator's indexing job
would register: for every chunk of an approved revision, its document id and family id, and every identifier-shaped
token found in the chunk text (the same pattern Palladion's own query side uses). It calls Palladion's own
`Catalog.add_alias` (`storage/catalog.py:362`) inside the isolated worktree's environment as a subprocess, and writes only
to the benchmark's runtime root. Searches stay HTTP-only.

*Rules kept.* It reads published text only, never gold. Today's R7a stays as the "no aliases" variant; the new variant is
reported as **R7a-aliased** beside it. This is a deviation from "HTTP only" for setup only; it is logged as a decision
(BADR-0027). It does not repair PF02: a real deployment would still need Palladion to do this itself.

*State.* Built and run (E-B04-006): 7,990 aliases over 4,786 chunks; the 10 code-bearing Q1 answers that were empty now return passages and recall moves from 0.055 to 0.083 (exploratory). New observation: 24 wrong-vintage returns appear with aliases, probably because a family alias matches every version of a policy (a hypothesis, not tested).

### A2. BR28 — supersession and validity windows (done in the loader)

*Correction to the earlier risk text.* BR28 said retired, withdrawn and supersession cannot be expressed. Reading the
source shows they can, over HTTP: `POST /sources` takes `valid_from`, `valid_to` and `allowed_principal_ids`
(`api/schemas.py:11-21`), and `POST /sources/{id}/approve` takes `supersedes_revision_id` (`api/routes.py:103-125`,
`storage/registry.py:416-470`; the predecessor must be approved, in the same case and family). The adapter already sent
the validity window and approved retired and non-normative documents, but did not send supersession.

*Mitigation.* The loader now approves a version with `supersedes_revision_id` set to its predecessor's Palladion
revision when the manifest names a predecessor that is still approved at that moment, and defers revocations of
withdrawn documents until every approval is done. A predecessor that cannot be superseded is recorded, not hidden.
Drafts and unapproved proposals stay unapproved on purpose: Palladion refuses to retrieve unapproved text, which is its
correct behaviour, so R0 to R3 seeing them and R7a not seeing them is a declared difference, not a defect.

*State.* Built and run (E-B04-006). Naming superseded versions changed no measured number (recall 0.055 before and after); the pilot's R7a numbers are kept as history.

### A3. BR27 — access filter after the cut (owner chose: later, before B08)

*What happens.* The adapter maps all 17 benchmark principals to one Palladion reader, so Palladion cannot filter by
principal; the harness filter runs after Palladion's 12-result cut. Reading `retrieval/hybrid.py:61-100`: Palladion
discovers 40 candidates, drops the ones the calling principal may not read, then cuts to the limit. So with one identity
per benchmark principal the access filter would run before the 12 cut (inside the first 40), which is what we want.

*Mitigation.* A setup step like A1 that creates the 17 identities and memberships (`registry.bootstrap_principal`,
`bootstrap_membership`) and uploads each document with `allowed_principal_ids`. Larger than A1 and it changes the
corpus load. Owner chose to do it before the sealed run (B08), not now; it is listed in the plan card for B08-T01.01 work
to schedule. PF05 would make it a normal operation instead of a setup trick.

### A4. BR22 — no clock

No benchmark-side fix: Palladion's HTTP search has no `as_of` (see PF01). Mitigations that stay: R7a is reported
separately on as-of strata, and its validity follows the wall clock (2026-10-19 for the pilot against the fixture time
2026-10-18). Faking the process clock is not recommended: the fixture needs a different time per question.

### A5. BR12 — K above 12 and no token budget

Already enforced harness-side: K above 12 is refused for R7a, the pilot uses K=10, and the evidence budget is applied
after retrieval by whitespace words. The only loss is that R7a cannot be compared at K above 12.

### A6. Accepted or not Palladion's

BR23 (the reranker is English-only) and BR25 (BM25 statistics include hidden documents) are properties of the pinned
models and of BM25, not of Palladion's interface. BR26 is report-only until PF03.

---

## Part B — Fixes only the Palladion contributor can make

Each fix is the smallest change that removes the limit. Priority: **P1** blocks a meaningful sealed comparison,
**P2** improves fairness or cost, **P3** optional.

### PF01 — Expose `as_of` on `POST /search` (P1, small)

- **What.** Add an optional `as_of` timestamp to the search request and pass it through.
- **Where.** `api/schemas.py:24-29` (`Search`), `api/routes.py:150-160` (`search`). The core already accepts it:
  `HybridSearch.search(..., as_of=...)` at `retrieval/hybrid.py:53` and resolves with it at lines 81, 107, 115 and 132.
- **Why.** BR22. Four of the benchmark's strata ask for the version in force at a past time; without a parameter the HTTP
  interface can only answer "now", so R7a cannot be scored on them and the result changes from day to day.
- **How.** `as_of: datetime | None = None` in `Search`; `as_of=body.as_of` in the route; reject a naive timestamp.
- **Proof.** A test that uploads two versions of one family with different `valid_from`, searches with `as_of` between them
  and gets the older one, and without `as_of` gets the newer.
- **Benchmark follow-up.** The adapter sends the question's evaluation time; BR22 is closed; R7a joins the as-of strata
  comparison.

### PF02 — Register exact aliases for sources loaded over HTTP (P1)

- **What.** Make the exact-identifier lane work for documents that did not come from the seed.
- **Where.** `ingest/pipeline.py` (`IngestPipeline.index`, called from `api/routes.py:103-135`) after chunking, doing what
  `core/bootstrap.py:61-65` does for seeded sources: `catalog.add_alias(admin, family_id | revision id | each
  identifier-shaped token in the chunk, revision, chunk)`. Alternative: a `POST /sources/{id}/aliases` route with the
  `document:approve` grant.
- **Why.** BR24. Without it every query naming a code, policy id or transaction id returns nothing for any source ingested
  through the API, which is the normal path. A second, related design choice at `retrieval/hybrid.py:69-72` throws away
  the semantic hits when an identifier is not found; consider keeping them and keeping the warning.
- **How.** Automatic registration on approval is the least surprising; the token pattern is already in `storage/exact.py:9`.
- **Proof.** Load a document through the API that contains `MS-1954`; search "what status does MS-1954 return" and get
  that chunk; search an unknown code and get the warning (and, if the design choice is changed, semantic results).
- **Benchmark follow-up.** The A1 setup step becomes unnecessary; R7a and R7a-aliased merge.

### PF03 — Make the coverage check cheap and honest at scale (P2)

- **What.** The check runs on every search and over a hard cap of 100 sources.
- **Where.** `retrieval/coverage.py:79-96` (`LIMIT 101`, `COVERAGE_SCOPE_TRUNCATED`), called per search at
  `retrieval/hybrid.py:133`.
- **Why.** BR26. With 1,164 approved sources every search is marked DEGRADED and pays for a scan that cannot cover the
  corpus (median about 1.1 s, maximum 10.6 s on the S tier), so latency is not comparable and a real client would treat
  every answer as degraded.
- **How.** Compute coverage from per-case counters kept at ingest, or cache it per index generation; report truncation
  only when it matters; or accept `coverage=false` on the request.
- **Proof.** Latency on 1,000 sources within a small multiple of latency on 10; no DEGRADED warning when the index is
  healthy.
- **Benchmark follow-up.** R7a latency becomes comparable; the adapter's note on `COVERAGE_SCOPE_TRUNCATED` is removed.

### PF04 — Allow more than 12 results and an optional token budget (P3)

- **What.** `limit` is capped at 12 and there is no evidence budget.
- **Where.** `api/schemas.py:28`, `retrieval/hybrid.py:55`, `agent/tools.py:32`.
- **Why.** BR12. K above 12 cannot be tested for R7a, and the equal-budget control is applied after the fact.
- **How.** Raise the cap (the candidate pool is 40 at `retrieval/hybrid.py:64`, so up to 40 is natural) and add
  `max_evidence_tokens`.
- **Proof.** A request with `limit=20` returns 20 passages; with a small budget it returns fewer and says why.
- **Benchmark follow-up.** R7a runs at the same K and budget as the others without harness truncation.

### PF05 — An administrative route to create principals, memberships and grants (P2)

- **What.** Principals, cases and memberships come only from the seed bundle.
- **Where.** `core/bootstrap.py:29-36` (`bootstrap_principal`, `bootstrap_case`, `bootstrap_membership`); the routes list
  in `api/routes.py` has none for them.
- **Why.** BR27 and fairness. The benchmark has 17 principals (role by tenant). A deployment that cannot create them over
  its own interface forces every benchmark principal onto one reader.
- **How.** Admin-only `POST /principals` and `POST /cases/{id}/members`, with the existing grant checks. Source-level ACL
  already exists (`allowed_principal_ids` on upload).
- **Proof.** Two principals with different grants get different answers to one query, with the denied passage excluded
  before the limit.
- **Benchmark follow-up.** A3 becomes a normal HTTP step.

### PF06 — Documented switches for the pieces the ablations remove (P1 for B07, none for Track A)

- **What.** Settings cannot turn off the critic (minimum one call), the gate, preflight, the authority check, the parser
  or the temporal resolver; the independent critic is a later phase of Palladion's own plan (OQ11).
- **Where.** `agent/critic.py`, `agent/gate.py`, `agent/loop.py`, `settings.py`. Re-read at B07; this item is from OQ11 and
  has not been re-verified against the current source.
- **Why.** The challengers E3 and E4 and most ablations A01 to A16 are FEATURE_NOT_SUPPORTED without them. They stay
  marked, never relabelled.
- **How.** One documented setting per component, default on, with a recorded value in every response trace.
- **Proof.** A run with the switch off shows the component absent from the trace.
- **Benchmark follow-up.** The affected ablations move from FEATURE_NOT_SUPPORTED to runnable at B07-T04.01.

### PF07 — A route to register typed links from published text (P2, needed only for R7b)

- **What.** At the pinned commit the only link relation the store accepts is `EXCEPTION_TO` (a SQL check on the links
  table) and links are created only by in-process helpers used by Palladion's own demo seed. No HTTP route creates a link,
  so a corpus loaded over HTTP has an empty graph and R7b has nothing to expand.
- **Where.** `storage/sqlite.py` (the relation check), `storage/catalog.py` (the link writer), `ingest/graph_extract.py`
  (the extraction that projects relations), `api/routes.py` and `api/schemas.py` (no route). Line numbers are from
  `E-B06-001` and can drift; the working tree of the contributor is moving.
- **Why.** The graph arm and ablation A05 cannot be measured over the benchmark corpus. Meanwhile R7b is recorded as
  FEATURE_NOT_SUPPORTED with this reason, never as zero.
- **How.** An administrative route, behind the same admin authorization as PF05, that registers a bounded set of typed
  links between chunks or sources the caller already administers, each with its evidence span and its source version;
  idempotent; no link without provenance; link types from a closed list.
- **Proof.** Upload, approve, register a link, search with expansion and read back the link in the citation trace; a link
  to a source the caller may not read is refused; a link without evidence is refused.
- **Constraint from the benchmark.** The benchmark supplies links derived from published text only. It must not supply a
  world relation or a supersession edge (BR37), or R7b's relation precision would match the gold by construction.
- **Benchmark follow-up.** A later card runs R7b at a pin that differs from R7a only by the graph code (the pin is chosen
  then; today's working tree also changes retrieval, so it would be a confound).

---

## Part C — Decisions and open items

| Item | Decision | Date and source |
|---|---|---|
| A1 alias setup | Approved as a second variant (R7a stays "no aliases", add R7a-aliased); logged as BADR-0027 | 2026-10-19, owner |
| A2 supersession in the loader | Coordinator decision inside B04 scope; BR28 text corrected; recorded in BADR-0027 | 2026-10-19 |
| A3 per-principal identities | Later, before B08; no work now | 2026-10-19, owner |
| Part B | Handed to the Palladion contributor as a request; no benchmark work depends on a reply except PF06 at B07 | open |

Open for the owner: whether to send Part B to the Palladion contributor now or after the sealed run, and whether PF01
(a few lines) should be asked for first because it alone unlocks the as-of strata.


## Palladion contributor response — 2026-10-20

Owner approved Palladion-side Part B changes (ADR0087–0089/0092/0095) and this status
appendix. Original requests and benchmark observations above are retained as history.
Benchmark adapter implementation and sealed-run decisions remain with its contributor.

| Item | Palladion status | Current contract / retained limit |
|---|---|---|
| PF01 | DONE — verified HTTP consumer | Optional aware `as_of` on `/search`; same cutoff on `/evidence/{chunk_id}`. Current ACL/approval/revocation still apply; not trusted operational event time. |
| PF02 | DONE — verified upload/approval/search/citation | Approval-owned bounded family/revision/code aliases. Unknown structured IDs still return no substitute plus warning, per locked vision. Search exact candidates capped100 with visible truncation and ACL before cut. |
| PF03 | OPEN — mechanisms implemented, performance acceptance unresolved | Up to10000authorized sources, explicit count truncation beyond that, bounded physical batches and canonical/physical aggregate100000chunks. Opt-in `reuse_physical_audit` on `/search` and `/index-health` reuses complete healthy physical audits for≤5seconds from original start; current canonical checks still run. Default fresh. Visible mode/time/cache status; out-of-band physical corruption may remain undetected inside that window. Large-case benefit and small-case overhead/expiry misses retained; owner instructed leave open if worse. No `coverage=false` bypass. |
| PF04 | DONE — verified HTTP/tokenizer/span consumer | HTTP default12/max40, optional `token_budget` counts the pinned retrieval tokenizer's whole-passage prefix with disclosed identity/count/separator. Four-tool limit remains12. This is not whitespace/provider billing equivalence; benchmark must choose its equal-budget convention explicitly. |
| PF05 | DONE — verified provisioning/current ACL consumer | Scoped admins use `POST /v1/admin/principals`, `/v1/admin/cases`, `/v1/admin/cases/{case_id}/memberships`. Submitted principal ID is a tenant-local subject key: store/use returned opaque canonical ID for membership, ACL and operator token mappings. No bearer/admin/tenant minting or restoration of revoked access. |
| PF06 | DONE within owner-approved safe capability scope | `python scripts/evaluate.py --capabilities` reports11supported isolated arms and explicit unsupported bypasses. Critic exists; B4/B5 omit critic in isolated studies, retaining final gate. Serving gate/preflight/source/parser/time bypasses remain FEATURE_NOT_SUPPORTED; do not relabel those benchmark ablations runnable. |

Palladion source/evidence authority: `palladion/docs/development/evidence/P09_AUDIT_AND_HANDOFF.md`,
`EVIDENCE_LOG.md` E-P09-001 onward, MASTER_DEV_PLAN P09 and ADR0087–0095. These fixes do
not retroactively change frozen benchmark scores or validate a sealed comparison.
