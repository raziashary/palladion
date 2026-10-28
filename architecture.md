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

* **The gate is a necessary-condition check, not a proof of meaning.** It confirms the claim matches the evidence
  and is current; it does not prove the model understood it. Model agreement is never treated as independent truth.
* **Memory** is context, never authority: private preferences of a user, notes of one session, unapproved
  experience. None of it becomes policy automatically.
* **Optional graph.** Links between chunks can be followed to find related sources; they never authorise an answer and
  are off by default.

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
| HTTP | `api/` | `routes.py` |

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
