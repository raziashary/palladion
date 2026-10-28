# How Palladion works, in more depth

This is the longer version of the architecture section in the [README](README.md). It is for someone who has read the
README and asks: which search runs first, where does the reranker come in, what exactly is the "policy" part, and who
decides what. Everything here is checked against the code in `palladion/src/evidence_agent/`; file names are given so you
can look. Palladion is a research prototype on fictional data (see the README for its limits).

## 1. The one idea

An answer should be **attached to evidence you can check**, and the system should say "I cannot verify this" instead of
guessing. To make that true, the work is split so that the language model never has the last word:

| Part | Is it a language model? | What it decides |
|---|---|---|
| **Search** (section 3) | No (small embedding and ranking models, not a chat model) | Which passages of approved documents are worth showing |
| **Policy engine** (section 4) | No (plain code) | What an approved rule table says about a case, given verified live facts |
| **Agent** (section 5) | Yes | Which of four read-only tools to call and how to word a draft answer |
| **Critic** | Yes, in a separate conversation | Challenges the draft |
| **Gate** (section 5) | No (plain code) | Which claims may be released: only those that match the original evidence |

## 2. Getting a document in

```
upload (someone)  ->  approval (a different, authorised person)  ->  parse  ->  chunks  ->  index
```

* **Upload and approval are separate people.** A draft is invisible to search. Words such as "approved" written
  inside a document carry no authority; only the approval record does. A source can be revoked at once.
* **The original bytes are kept unchanged** and identified by their hash. Everything shown later is read back from them.
* **Chunks.** The document is cut into pieces that remember exactly which bytes they cover. Headings join the text
  under them, a banner line does not become a chunk of its own, and neighbouring short sections are packed together up
  to 600 characters so that a one-line clause is not a poor unit to retrieve. A chunk also remembers the titles above it
  (its *heading path*), and the search reads "titles + text" so that a clause such as "4.2 amounts above 10 are
  escalated" knows which policy it belongs to. The citation is still the original text.
* **Two places hold the document:**
  * **SQLite** (the *catalog*): who approved it, its validity window, which version replaces which, who may read it, its
    chunks, and a table of *exact identifiers* (section 3.3).
  * **Qdrant** (the *index*): for each chunk, two searchable representations, described next.
* **A generation** is one published batch of a document's index points. It becomes searchable only after the points read
  back from Qdrant match what the catalog expects, so a half-published document is never served.

## 3. What happens in one search

The agent's tool is `search_knowledge`. By default it asks for 8 passages in "reranked" mode. Here is the whole path;
the numbered stages are in `retrieval/hybrid.py`, and each search reports the milliseconds each stage took.

```
question
  |
  1  Which documents can apply?   (SQLite)   approved, readable by this person, valid at the case's time(s),
  |                                          not yet replaced. Result: the list of index generations allowed.
  |
  2  Ask Qdrant  -- ONE call, two searchers at the same time, only inside those generations:
  |        dense (meaning)  -> its best 40
  |        BM25  (keywords) -> its best 40
  |        merge by RRF  ->  one list
  |
  2b Exact-identifier lane (SQLite, not Qdrant): codes in the question (POL-001, MS-1817) pull in their chunks
  |
  3  Resolve   every candidate is re-checked against the original bytes, approval, access list, window, generation
  |
  4  Rerank    a cross-encoder re-reads up to 30 survivors together with the question and reorders them
  |
  5  Context   a quarter of the slots may go to neighbouring or exception-linked chunks, never displacing a ranked one
  |
  6  Release   a final check, a size budget, and a cheap health count of the index -> passages with citations
```

### 3.1 The two searchers: BM25 and dense

Both are stored on every chunk and are asked **at the same time** inside one Qdrant call. Neither goes first.

| | **BM25** (keyword) | **Dense** (meaning) |
|---|---|---|
| Idea | Count the question's words in each chunk; rare words count more; long chunks are slightly penalised | Turn question and chunk into a list of 384 numbers with a small multilingual model; nearer lists mean closer meaning |
| Good at | Exact codes, rare terms, names | The same idea in other words, Indonesian against English |
| Bad at | A synonym ("refund" for "reversal") | Telling `MS-1817` from `MS-1816`: to the model all error codes look alike |
| In the benchmark alone | Found the full set for 12 of 72 questions | 1 of 72 |

The question goes to BM25 as it is (lower-cased, English stemming and stop words) and to the dense model as a vector.

**RRF (reciprocal rank fusion)** merges the two ranked lists without trying to compare their different kinds of
scores: a chunk earns `1 / (60 + rank)` from each list that contains it, and the earnings are added. A chunk that is
ranked well by both rises; a chunk that only one list likes can still survive if that list put it near the top.

### 3.2 The reranker

BM25 and dense each look at the question and the chunk **separately**. A **cross-encoder** reads them **together**,
which is slower but more accurate about whether this passage answers this question. Palladion reranks at most the 30
best survivors, in batches of 8 on up to 4 processor threads, shortest passages first (so the model does not pad short
passages to the length of long ones). It runs *after* stage 3, so it never sees a document the person may not read,
and it only reorders; it cannot add anything. The model is English-trained, which matters because about 30 percent of the
benchmark's questions are in Indonesian.

### 3.3 The exact-identifier lane

Some questions name a thing exactly: `POL-001`, `MS-1817`. At approval Palladion records, for each chunk, the code-shaped
tokens it contains (capitals, digits and a dash or dot, such as `ISO-9001`; the full stop that ends a sentence is not
part of a code). When a question contains such a code, the lane looks it up in SQLite:

* A chunk that **defines** the code leads the results. A chunk defines it when the code is its document's own ID or when
  the code is in a **title above the chunk** (a section called "API note: MS-1817 response").
* A chunk that merely **mentions** it leads only if five or fewer chunks do. A code that appears in a table in 24
  chunks identifies none of them, so those chunks follow the semantic results instead.
* An unknown code is **never replaced by a similar one**. The search says `EXACT_IDENTIFIER_NOT_FOUND`; a question that
  is only an unknown code returns nothing.
* **The reranker does not move the lane's chunks**: chunks that lead stay first, chunks that only cite stay after the
  semantic results, and the reranker orders everything in between.
* A code with a version, `POL-001@v2`, means the **second version of POL-001**. Versions are numbered by when their
  validity starts (a revoked version keeps its number; a draft has none). Such a question is answered by that version
  alone, even if a newer one replaced it. A version that does not exist returns nothing and says
  `NAMED_VERSION_NOT_FOUND`.

### 3.4 Which documents can apply (stage 1)

This is where Palladion differs from plain search. A document is **eligible** for a question when it is approved and
indexed, the person may read it, and **at the case's time** it is inside its validity window and has not been replaced.
The "case's time" is the evaluation time plus trusted case instants (for example when the case was opened); they come
from the backend, **never from the model**. Plain BM25 or dense search over all documents has no such filter, which is
why they return out-of-date versions far more often in the benchmark.

Stage 3 then applies a fixed list of checks to every candidate before any text is released; section 8 lists them.

## 4. The policy engine, and how it differs from search

This is the part that most often confuses people, so plainly:

> **Search finds documents and shows what they say. The policy engine decides what an approved rule table says about a
> specific case. They are different tools, and the agent chooses between them.**

Search is about *text*. The policy engine is about *rules and facts*. A policy document (for example "Reversal policy")
is a normal document for search. Separately, an authorised person registers and approves a **policy specification** that turns the same
document into a machine-readable decision table, linked back to the exact clauses of the document:

| Part of a policy specification | What it is | Example (invented) |
|---|---|---|
| `family_id`, `version_id`, `valid_from` / `valid_to` | Which policy and which version, and when it applies | Reversal policy, version 4 |
| `clauses` | The exact byte ranges of approved documents it is based on | clause 4.1 of the policy document |
| `time_basis` | Which date decides the version | when the transaction occurred, when the case was opened, the evaluation time, or a named case event |
| `required_facts` | Which live facts are needed, from which of four allowed read operations, how old they may be | transaction state `settled`, from `get_transaction_status`, at most 5 minutes old |
| `rules` | Conditions written as small predicates (`all`, `any`, `not`, `eq`, `in`, `lt`, ...) with an outcome and the clause that supports them | if state is `settled` then `NOT_PERMITTED`, clause 4.3 |
| `default_outcome` | What happens when no rule matches | `ESCALATE` |

The engine (`policy/engine.py`, `policy/temporal.py`) then does, for a case:

1. **Choose the version** that applies at the time the spec's `time_basis` names, among approved, unrevoked specs for that
   case's product and transaction class. If two candidates conflict it says `POLICY_CONFLICT` rather than picking one.
2. **Read the facts itself.** The agent passes only *IDs of live observations* it obtained through `lookup_live_data`
   (a read-only call to a mock operational system); it cannot hand over a value. The engine checks each is recent
   enough and of the right type.
3. **Run the rules** with a small interpreter that only knows the allowed operators and never executes text from a
   document.
4. **Return a decision:** `DETERMINED` with an outcome and the list of rules that matched, or `INCOMPLETE_INPUT` (a fact
   is missing), `UNVERIFIED_INPUT`, `VERIFICATION_UNAVAILABLE`, `NO_APPLICABLE_POLICY`, `POLICY_CONFLICT`. Every
   decision is written to the audit trail and can be replayed.

No language model takes part. A model cannot invent which policy wins, cannot make up a fact, and cannot change an
outcome.

**How search and policy meet.** Only through the agent and the gate. For "what is the reversal window?" the agent calls
search and quotes the clause. For "may I reverse this settled transaction?" it needs a decision: it reads the live
status, calls `evaluate_policy`, and the answer must cite both the decision and the source clauses the decision points
to. The benchmark's retrieval test (Track A) exercises search only; the policy engine is exercised in the answering and
whole-system tests.

### 4.1 How a version is chosen, step by step

`TemporalResolver.resolve` in `policy/temporal.py`. Nothing here uses a similarity score, an upload date or a revision
number.

1. **Candidates.** Every version of the policy family for the tenant. More than 128 is `POLICY_CONFLICT`
   (`CANDIDATE_BOUND_EXCEEDED`).
2. **Scope.** Keep versions whose allowed cases include this case and whose product and transaction class match it.
3. **Approval.** Keep versions that have a `POLICY_APPROVED` event, no `POLICY_REVOKED` event and status `APPROVED`,
   and whose source clauses are still approved and match their stored hashes byte for byte.
4. **Nothing left** gives `NOT_APPLICABLE` (the family exists but nothing fits this scope) or `NO_APPLICABLE_POLICY`.
5. **One time basis.** If the survivors declare different time bases the result is `POLICY_CONFLICT`
   (`MIXED_TIME_BASIS_WITHOUT_APPROVED_MIGRATION`).
6. **The instant.** From the declared basis, never from the model or the customer:

   | Basis | Where the instant comes from | If it cannot be had |
   |---|---|---|
   | `EVALUATION_AT` | The server clock | — |
   | `CASE_OPENED_AT` | The case record | — |
   | `DOMAIN_EVENT_AT` | A named, authenticated case event | `MISSING_TIME_INPUT` |
   | `TRANSACTION_OCCURRED_AT` | A successful `get_transaction_status` read in this request, no older than the spec's limit (300 seconds by default) | `MISSING_TIME_INPUT`, or `UNVERIFIED_TIME_SOURCE` if a read was tried but is unusable; two reads that disagree give `POLICY_CONFLICT` |

   A date the customer or the agent states is not a source. The demo fixtures include exactly that trap: a customer
   message claiming a June 2025 transaction for a case whose record says August 2026 is not used to select a version.
7. **Validity.** Keep versions whose half-open interval contains the instant (`valid_from` inclusive, `valid_to`
   exclusive) and whose source documents' own windows contain it too.
8. **Precedence.** Remove a version only if an administrator recorded that a successor replaces it, with a reason, for
   the same family, time basis, product and transaction class, effective by the instant.
9. **Count.** None left is `NO_APPLICABLE_POLICY`. Exactly one is `SELECTED`. Anything else is `POLICY_CONFLICT`
   (`INCOMPARABLE_OR_CYCLIC_PRECEDENCE`).

Example from the fixtures: version A is valid from 2026-07-01 to 2026-10-01 and version B from 2026-08-01, with no
replacement recorded. On 2026-08-15 both qualify, so the answer is `POLICY_CONFLICT`. The remedy is the policy
owner's: record which one replaces the other, with a reason.

This conflict only exists between *registered policy versions*. Two ordinary documents that disagree are not detected
by it.

### 4.2 How a decision gets its status

`PolicyEngine.evaluate` in `policy/engine.py`. For each required fact the engine finds the live observations the agent
named for that operation and checks them:

* the read succeeded;
* it is no older than the fact's `max_age_seconds` (and, for BI data, its `data_as_of` is no older either);
* its value has the declared type and, for an enum, is an allowed value;
* repeated reads of the same fact agree.

The status is then set in this order:

| If | Status |
|---|---|
| Any fact failed the checks above | `UNVERIFIED_INPUT` |
| A required read did not succeed (timeout, unavailable) | `VERIFICATION_UNAVAILABLE` |
| A required fact has no reading at all | `INCOMPLETE_INPUT`, with the fact named in `missing_fields` |
| The version could not be selected | The selection's own status. A missing time maps to `INCOMPLETE_INPUT` with `time_input` missing; an unverified time to `UNVERIFIED_INPUT` |
| Otherwise | `DETERMINED`: every rule is evaluated; if the matching rules give different outcomes the status is `POLICY_CONFLICT`; if none match, the `default_outcome` applies; a rule whose outcome is `INCOMPLETE_INPUT` makes the status `INCOMPLETE_INPUT` |

The rule language is `all`, `any`, `not` and the comparisons `eq`, `in`, `lt`, `lte`, `gt`, `gte`, with literal values,
depth at most 12 and 128 nodes, and strict types (no coercion). Nothing a document says is ever executed.

### 4.3 Registering, superseding and replaying

* **Registering** (`policy/registry.py`) needs an administrator with `document:approve`. The spec's author must be a
  different person from the administrator, and must be the person who uploaded every source revision the clauses
  cite. Each clause must be an approved source whose bytes match the stored hash, and every predicate is validated
  against the declared facts. A policy string inside a document grants nothing.
* **Revoking** and **superseding** are administrator actions; a supersession needs a written reason and covers one case.
* **Replay.** Each decision is stored with its inputs. Reading it back re-checks access and the clause bytes and
  recomputes the matching rules from the stored inputs; a mismatch is a conflict error.
* **A stored decision is not permission.** When a decision is cited as evidence, the system selects the version again
  and re-checks input freshness. If a different version would be chosen now, or an input has gone stale, the citation
  is refused, and only `DETERMINED` counts as valid evidence.
* **Historical audit mode** (a knowledge cutoff and a simulated evaluation time) is administrator-only and is not
  something the agent can ask for.

### 4.4 The demo policies

Fictional fixtures in `palladion/config/policies/` and `palladion/data/demo/`:

| Version | Time basis and window | Rule |
|---|---|---|
| `demo-reversal-2025-a` | Transaction time, 2025-01-01 to 2026-07-01 | Transaction `FAILED` and settlement `UNSETTLED` gives `FOLLOW_INVESTIGATION_SOP`; default `NO_DECISION_REQUIRES_REVIEW` |
| `demo-reversal-2026-b` | Transaction time, from 2026-07-01 (replaces 2025-a) | The same rule, plus an exception: settlement `PENDING` gives `INCOMPLETE_INPUT` (cites the approved exception appendix) |
| `demo-handling-2026-a` | Evaluation time, from 2026-01-01 | No facts needed; default `FOLLOW_CURRENT_HANDLING_SOP` |
| `demo-overlap-a` / `demo-overlap-b` | Transaction time, overlapping, no replacement recorded | Used only to show `POLICY_CONFLICT` |

The JSON fixture file uses its own field names; the runtime model is `PolicySpec` in `policy/registry.py`.

## 5. Answering a question

```
authenticated request
  -> the backend builds context WITHOUT a model: current goal, own-session memory, handles to re-check
  -> the agent (a chat model) may call, within budgets:
       search_knowledge   what do approved documents say?                       (section 3)
       evaluate_policy    what does the approved rule table decide?             (section 4)
       lookup_live_data   read one named operational record (read-only, mock)
       recall_memory      what happened earlier in this case? (not a fact, not policy)
  -> the agent drafts claims, each pointing at evidence IDs
  -> the critic (a second model, separate conversation) challenges the draft; it may run its own counter-search
  -> the gate (code) re-reads every cited passage from the original bytes, checks that the claim's quote or typed
     fact really is there, and releases only claims that pass; the rest become "could not verify" or a gap
  -> released answer with citations; events saved; eligible events may become memory
```

* **Searches run in separate processes that are kept alive.** Each `search_knowledge` call runs in a child process (so it can
  be killed on a deadline, holds no credentials and cannot disturb the server). Loading the two small models takes 12 to 14
  seconds, so the server keeps up to two such worker processes running and reuses them; a worker is thrown away after a
  cancelled, late or malformed search and stopped after five idle minutes (`search_worker_mode`, `search_worker_idle_seconds`).
  The database is opened afresh for every search, so a worker never reads stale data.
* **The gate is a necessary-condition check, not a proof of meaning.** It confirms the claim matches the evidence
  and is current; it does not prove the model understood it. Model agreement is never treated as independent truth.
* **Memory** is context, never authority: private preferences of a user, notes of one session, unapproved
  experience. None of it becomes policy automatically.
* **Optional graph.** Links between chunks can be followed to find related sources; they never authorise an answer and
  are off by default.

### 5.1 The released answer

The message endpoint returns a structured response (`MessageResponse` in `api/schemas.py`). The agent drafts claims of
five types; the gate (`agent/gate.py`) re-reads the evidence for every claim and writes the released sentence itself.

| Claim type | What the gate requires | Sentence it releases |
|---|---|---|
| `SOURCE_QUOTE` | The quote really occurs in the cited passage | "Approved source states: “…” (attribution only; no action permission)." If the passage belongs to a registered policy clause, a policy decision for that family must also be in the ledger |
| `OBSERVED_FACT` | The live record holds that exact field and value. A current claim needs a fresh record; a historical claim needs the snapshot time | "Last observed *system* *field*: *value* at *time*." or "Historical … snapshot as of *time* reported …; this does not establish current state or another system's state." |
| `RULE_REQUIREMENT` | The policy decision lists that field as required | "Applicable policy requires *field*; a requirement is not an action authorization." |
| `POLICY_RESULT` | A valid `DETERMINED` decision with an outcome and no missing fields | "Executed synthetic policy result: *outcome*; this is decision support, not authorization to perform a payment." |
| `HYPOTHESIS` | Only one fixed sentence, only on informational answers | "A reconciliation delay is possible; this is unverified." On operational guidance a hypothesis is blocked |

The disposition follows from the whole picture:

| Condition | Disposition |
|---|---|
| Any policy decision in the ledger is `POLICY_CONFLICT` | `CONFLICT` |
| Something is verified, and there is a gap, an unavailable check or a blocked claim | `PARTIALLY_SUPPORTED` |
| Nothing verified, and a check was unavailable | `VERIFICATION_UNAVAILABLE` |
| Something verified, nothing outstanding | `SUPPORTED` |
| Nothing verified | `NOT_ESTABLISHED` |

Four rules in the gate matter for a client:

* Policy-related claims need the critic's review to have run, or the answer carries `mandatory_critic_review` and is
  treated as unavailable.
* Operational guidance always adds the gap `authorized_human_review`, so it is never `SUPPORTED`. Palladion invents no
  approver and no escalation assignee; the product around it has to provide that step.
* A claim with no supporting evidence is blocked and adds `claim_support_not_established`.
* `searched_scope` says what was searched and `inventory_attested` is always `false`. "Not found in the searched
  scope" is never turned into "does not exist".

Worked sessions are in section 9.

## 6. Where things live

| Area | Folder (`palladion/src/evidence_agent/`) | Key files |
|---|---|---|
| Search | `retrieval/` | `hybrid.py` (the stages), `rerank.py`, `evidence.py` (the resolver), `coverage.py` (health count) |
| Documents, access, versions | `storage/` | `registry.py`, `catalog.py`, `applicability.py`, `exact.py`, `qdrant.py`, `sqlite.py` |
| Cutting documents | `ingest/` | `parsing.py`, `chunking.py`, `pipeline.py` |
| Policy | `policy/` | `registry.py` (specs), `temporal.py` (version choice), `engine.py` (rules) |
| Live operational reads (mock) | `live/` | `gateway.py`, `mock.py` |
| Agent, critic, gate | `agent/` | `loop.py`, `tools.py`, `critic.py`, `gate.py` |
| Memory | `memory/` | `store.py`, `packet.py`, `promotion.py` |
| HTTP | `api/` | `routes.py`, `schemas.py` |
| Access and audit | `security/`, `telemetry/` | `access.py`, `audit.py` |

## 7. Questions people ask

**Why both BM25 and dense?** Each fails where the other works (table in 3.1). Together they are a standard, strong
baseline; the benchmark shows that this baseline alone (even with a reranker) still misses exact codes, which is
what the exact-identifier lane is for.

**Why a reranker if RRF already merges?** RRF only knows each list's ranks. The reranker reads question and passage
together and can tell that a passage about a *different* error code is not the answer.

**Is the policy engine "AI"?** No. It is deterministic code over an approved table and verified facts.

**Where does time come in?** In two places: search filters documents by the case's time (3.4); the policy engine
chooses a policy version by the time its spec names (4). Neither time comes from the model.

**What can the person's question change?** The words, which codes it names, and (with `POL-001@v2`) which version
of a family is meant. It cannot change what the person may read, a time, or a rule.

**Is Palladion just RAG with extra filters?** The filters are part of it (section 8), but the larger differences are
that rules are executed by code rather than paraphrased by a model (section 4), that live facts carry their own times
and freshness limits, and that a gate decides what may be released (section 5.1). Search is the part the benchmark
measures; the rest is not yet measured.

**Can it change anything in a customer's account?** No. It has four read tools, no write tool, and every policy outcome
is labelled decision support.

**Why does an operational answer never come back as plain `SUPPORTED`?** Because the gate always adds
`authorized_human_review` to operational guidance. A human sign-off is part of the design, not a gap to be closed.

## 8. What re-checking a candidate means

Search returns *candidates*. `EvidenceResolver.resolve` (`retrieval/evidence.py`) turns a candidate into released text,
inside one read transaction so the metadata cannot change between the checks and the byte read:

| # | Check | What it catches |
|---|---|---|
| 1 | The chunk exists and belongs to this case | A hit from another case |
| 2 | The caller holds `source:read` for the tenant and case | The wrong person or tenant |
| 3 | The revision is `APPROVED` and its index state is `READY` | Drafts, withdrawn sources, half-published documents |
| 4 | The generation is `READY` and its fingerprint equals the pinned embedding and tokenizer identity | An index built with different models |
| 5 | The chunk belongs to the generation currently served | A chunk left over from an earlier chunking of the same file |
| 6 | The separate approval record also says `APPROVED` | The revision flag and the approval record disagreeing |
| 7 | The document's access list allows the caller | A per-document restriction |
| 8 | The revision applies in time (below) | Expired or replaced versions |
| 9 | The original file is read from the content-addressed store, the chunk's byte span is re-hashed, and the file's hash must equal the chunk's recorded source hash | A missing or altered source |

Failures of checks 1 to 8 raise one uniform "permission denied", so a caller cannot learn whether a document exists.
Failures of check 9 raise a different, integrity error. Search reports what it dropped as counts (`NOT_ELIGIBLE`,
`INTEGRITY_CONFLICT`) and warnings such as `ALL_CANDIDATES_EXCLUDED`, so an all-excluded result never looks like a
search that matched nothing.

**The time check** (`storage/applicability.py`). A revision applies if, at one instant, it is inside its half-open
window and no successor has yet taken effect. The instants are the current time plus the case's trusted instants, up to
eight: when the case was opened, its named domain events and the verified transaction times of fresh live observations
already in this request. The backend derives them; the model chooses none. With the demo documents:

* The 2025 SOP is valid until 2026-07-01 and the 2026 SOP starts then. Today only the 2026 SOP passes.
* Once a live read shows a transaction on 2026-06-20, that instant joins the list and the 2025 SOP is admitted as well,
  because it was valid then.
* Search can return both, and does not decide between them. Which version *governs* is decided by the policy engine
  (section 4.1).

A question that names a version (`POL-001@v2`) is answered by that revision alone, whatever its window.

## 9. Worked examples

These are reconstructions on the demo fixtures (a fictional QR payment product, cases `case-42` and `case-43`),
written in banking terms. They were not recorded from a live run: the tool names, statuses, rule IDs, clause text and
the gate's sentence templates are real; byte offsets, IDs, the model's choice of claims and a few live values (marked)
are illustrative. Empty fields are left out.

### 9.1 An informational question

*"What does our procedure say when a customer reports a debit but the merchant hasn't confirmed receipt?"*

```
disposition: SUPPORTED   review_status: PASS
answer: The following attributed information is verified within this case scope.
verified_claims
  C1  Approved source states: “When a customer reports a debit but the merchant has not confirmed
      receipt, check both transaction and settlement status. A FAILED transaction status by itself
      does not establish that the funds remain unsettled.” (attribution only; no action permission)
citations   DOCUMENT · DEMO.DISPUTE.SOP revision 2026.2 · section 2
tool_status {search_knowledge: OK}
searched_scope: Current authorized case and supplied index searched; inventory completeness is not attested.
```

Path: only `search_knowledge` ran. The 2025 SOP (window ended 2026-07-01) and the unapproved draft memo were dropped at
stage 3. The quoted clause is not a policy clause, so no policy decision was needed.

### 9.2 "Can I reverse it?", with a settlement timeout and then a recheck (case-42)

First turn. Path:

1. `search_knowledge` returns the 2026 SOP and the exception appendix. The draft memo, which says to reverse
   immediately, is dropped as unapproved; the 2025 SOP is outside its window.
2. `lookup_live_data`: the transaction is `FAILED` and occurred 2026-08-15; the settlement read returns `TIMEOUT`.
3. `evaluate_policy("DEMO.REVERSAL.CHECK", [both read IDs])`: the time basis is transaction time, so
   `demo-reversal-2026-b` is selected. Settlement has no valid reading, so the status is `VERIFICATION_UNAVAILABLE` with
   `settlement_state` missing. It is not treated as "unsettled".

```
disposition: PARTIALLY_SUPPORTED
verified_claims
  C1  Last observed mock_transaction_api state: FAILED at 06:42.
  C2  Applicable policy requires settlement_state; a requirement is not an action authorization.
  C3  Approved source states: “…If settlement status is absent, stale, or unverified, request a fresh
      settlement check and do not recommend reversal.” (attribution only)
missing_requirements: settlement_state, authorized_human_review
tool_status {search_knowledge: OK, lookup_live_data: TIMEOUT, evaluate_policy: VERIFICATION_UNAVAILABLE}
verification_failures: [LIVE_UNAVAILABLE]
```

Second turn, "recheck settlement". The continuity packet carries the open slot, and the handles in it are re-validated
before use. The mock's next settlement read returns `UNSETTLED`, so rule `current-investigate` matches:

```
disposition: PARTIALLY_SUPPORTED
verified_claims
  C1  Last observed mock_transaction_api state: FAILED at 06:51.
  C2  Last observed mock_settlement_service settlement_state: UNSETTLED at 06:51.
  C3  Executed synthetic policy result: FOLLOW_INVESTIGATION_SOP; this is decision support,
      not authorization to perform a payment.
missing_requirements: authorized_human_review
```

Even a fully verified operational answer is qualified. If the rep then asks the agent to promise an immediate refund,
that claim has no evidence, is blocked, and adds `claim_support_not_established`.

### 9.3 An old transaction: two time bases (a case like case-43)

*"Customer disputes a payment from June 2025. Which procedure do we follow?"* Assumption for this example: the
settlement read returns `UNSETTLED`.

1. `lookup_live_data`: transaction `FAILED`, occurred 2025-06-20.
2. `search_knowledge` now has the instant 2025-06-20. The 2025 SOP is valid then and its successor starts only on
   2026-07-01, so it is admitted; the 2026 SOP is admitted by today's date. Both come back, and ranking does not decide.
3. `evaluate_policy` on the reversal family: as of 2025-06-20 only `demo-reversal-2025-a` has an interval containing the
   instant, so it is selected, and rule `historical-investigate` gives `FOLLOW_INVESTIGATION_SOP`.
4. `evaluate_policy` on the handling policy, which uses the evaluation time: it resolves to `demo-handling-2026-a`,
   default outcome `FOLLOW_CURRENT_HANDLING_SOP`.

The answer cites the 2025 clause for the transaction and the 2026 handling policy for today's process, both as decision
support. If the customer had insisted "it was last month", the claim would have been recorded as unverified and the
system's own record would have decided.

### 9.4 Two approved versions overlap

*"Transaction from 2026-08-15. What is the reversal rule?"* With the overlap fixtures registered, both versions' windows
contain 2026-08-15 and no replacement is recorded.

```
disposition: CONFLICT
answer: Applicable evidence conflicts; no policy winner or operational instruction can be established.
citations: POLICY_DECISION (POLICY_CONFLICT) with both candidate clauses marked UNRESOLVED_CANDIDATE
```

The system does not choose the newer or the higher-numbered version. The policy owner has to record which one replaces
the other.

### 9.5 "Not found" is not "does not exist" (case-43)

A question outside the corpus (an ATM dispute procedure, which the demo documents do not cover) gives
`NOT_ESTABLISHED` with the fixed sentence that the scoped search does not establish the conclusion. Then:
*"The BI report says TX-DEMO-143 is not found, so the customer never paid, right?"* The BI read is a dated snapshot and
the transaction service times out:

```
disposition: PARTIALLY_SUPPORTED
verified_claims
  C1  Historical mock_curated_bi snapshot as of 2026-10-16T00:00:00Z reported result: NOT_FOUND; this does not
      establish current state or another system's state.
  C2  Approved source states: “A scoped BI result of NOT_FOUND describes only that BI source and its stated
      data-as-of time. It does not establish that a transaction is absent from the transaction service when
      that service is unavailable.” (attribution only)
tool_status {lookup_live_data: TIMEOUT}   verification_failures: [LIVE_UNAVAILABLE]
```

## 10. Palladion and the comparators

The [benchmark](palladion-benchmark/README.md) compares Palladion with the systems a team would otherwise reach for. They
have plain names in [report.md](report.md); the codes are R (retrievers) and E (whole systems).

| Comparator | What it stands for | What it lacks that Palladion has |
|---|---|---|
| R0 keyword (BM25) | The cheapest search | Meaning matching, approval, validity, access |
| R1 dense | A plain "embed and search" RAG | Exact-code handling, and all of the above |
| R2 hybrid | Keyword plus meaning, merged | Re-reading, and all of the above |
| R3 hybrid plus re-reader | The strong, common RAG baseline | Approval, validity windows, replacement, access checks, exact-ID lane, named versions |
| R4 HippoRAG 2, R5 GraphRAG Local, R6 LightRAG | Graph-based retrieval | The same checks. Built, not yet measured |
| R7 Palladion retriever (without and with graph) | Palladion's own search | — |
| E0 plain LangChain | A simple search-then-answer pipeline | Policy engine, critic, gate |
| E1 LangGraph agent | An agent that picks its own steps | Policy engine, critic, gate |
| E2 Google ADK with RAG Engine | A managed system | Not accessible, not run |
| E3 Palladion without critic, E4 full Palladion | The whole agent | — |

There are three tracks: A (finding documents only), B (the same search results given to one shared answering model) and
C (each whole system end to end). **Track A exercises search only.** The policy engine, the critic and the gate act at
tracks B and C, which have not been re-run on the current Palladion. So the benchmark can say how good the search is,
and cannot yet say whether answers are more trustworthy. See [report.md](report.md) for the results and the hypotheses.

## 11. What an operator's screen must show

A text-only chat would drop most of what makes the answer checkable. A client should render:

| Response field | Treatment |
|---|---|
| `disposition` | A prominent badge. A partial answer must never look like a green light |
| `verified_claims` and `citations` | Each claim with clickable evidence. `GET /v1/evidence/{id}?case_id=…` re-checks access and the hash and returns the exact bytes; `/clauses/{n}` does the same for a policy clause |
| Live observations | System name and `observed_at` (and `data_as_of` for BI) visible, with a way to recheck. These facts expire |
| `missing_requirements` | A checklist of named gaps, not prose |
| `hypotheses` | Visibly separate and marked unverified |
| `tool_status`, `verification_failures` | A subtle "a system timed out" signal, so a gap is not read as "no data" |
| `searched_scope`, `inventory_attested` | A standing note that only the supplied documents were searched |
| `review_status` | Whether the critic passed, challenged or was unavailable |

Also: manage `session_id` (there are routes to start and close sessions); expect a long request, because the message
route returns only when the whole investigation finishes; keep source hashes and traces away from ordinary operators
(the trace route is admin-only); and never wire a "reverse now" button to the agent's output.

A working client that renders all of this is in [`palladion-ui/`](palladion-ui/README.md).

## 12. Known gaps between the design and the code

Checked against the source on the date of this edit:

* **`next_steps` is a fixed sentence** in `agent/gate.py` ("Obtain missing scoped evidence or request authorized human
  review."), on every response, including `SUPPORTED`. The blueprint describes concrete next steps. A client should
  derive actions from `missing_requirements`.
* **The model is chosen when the server starts** (`scripts/serve.py --model`). There is no per-request model switch.
* **No streaming route.** The message route returns once, after the gate. The timeline route (`/v1/cases/{id}/timeline`)
  shows persisted event metadata and can be polled for progress; `palladion-ui` does this, then reveals the released
  answer piece by piece. Raw model tokens are deliberately not streamed.
* **Policy registration over HTTP is new and uncommitted.** Until the `POST /v1/admin/policies` family (and the
  `GET /v1/cases/{id}/sources` listing) are committed, policies are seeded by script or the Python registry. Memory
  corrections are made through a local command-line script, not an HTTP route.
* **Policy conflict covers registered policy versions only.** Two ordinary documents that disagree are not detected by
  it; the benchmark's conflicting-source questions score 0 of 10 for Palladion.
* **The gate is a necessary-condition check.** It confirms a claim matches its evidence and is current; it does not
  prove the model understood it, and the critic's agreement is not independent truth.
* **A search started by the agent loaded its models each time** (12 to 14 seconds, as measured and recorded in
  [report.md](report.md) §5). That is a measurement of an earlier commit, not re-checked against today's source.
* **Synthetic authentication.** Bearer tokens come from a local file; there is no enterprise identity integration.
