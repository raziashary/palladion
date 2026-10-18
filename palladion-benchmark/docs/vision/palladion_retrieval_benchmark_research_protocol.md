# PALLADION — Retrieval and Evidence-Reliability Benchmark

**Research protocol v1.0 | 18 October 2026**  
**Companion to:** *Evidence-First Customer Service Knowledge Agent — Architecture v0.2*  
**Status:** Proposed experiments and preregistration template; **no comparative results have yet been measured**.  
**Scope:** Synthetic internal payment/customer-support knowledge, retrieval, evidence sufficiency, time-aware policy applicability, case memory, and read-only operational observations.  
**Goal:** A publishable and reproducible experiment rather than an impressive but uninterpretable demo.

> **Central research question:** When documentation is stale, contradictory, incomplete, permission-limited, or dispersed across many sources, does Palladion deliver **more supportable and appropriately cautious answers** than standard RAG, strong hybrid RAG, HippoRAG 2, Microsoft GraphRAG, LightRAG, and reference framework/managed solutions—and what extra computation, complexity, and latency does that reliability require?

> **Important methodological distinction:** LangChain and Google ADK are primarily **development/orchestration frameworks**, not single retrieval algorithms. Google RAG Engine is a managed retrieval service, and HippoRAG/GraphRAG/LightRAG are named retrieval methods. They cannot honestly be treated as six homogeneous “RAG providers.” This protocol therefore separates **retriever comparisons**, **application-stack comparisons**, and **Palladion component ablations**.

---

## Contents

1. Research objectives, hypotheses, and decision rules
2. Comparators: methods, frameworks, and providers
3. Three experimental tracks and fairness constraints
4. Synthetic enterprise world and document corpus
5. Query sets, episodes, partitions, and sampling
6. Ground-truth construction and evidence ontology
7. Harness contracts, ingestion, and unified outputs
8. Retrieval metrics beyond precision and recall
9. Answer quality, provenance, policy, and temporal metrics
10. Abstention, confidence calibration, and failure costs
11. Multi-turn memory, agent, graph, and tool metrics
12. Latency, cost, scaling, robustness, and maintainability
13. Benchmark scoring and release gates
14. Execution protocol, sample size, and statistical analysis
15. Ablation studies and causal attribution
16. Detailed adversarial and mutation experiments
17. Worked synthetic examples and expected outcomes
18. Repository and file responsibility map
19. Practical execution plan, resources, and reporting
20. Threats to validity and research publication standards
21. Source register and selected readings
22. Final checklist and decisions to lock before running

---

## 1. Research objectives, hypotheses, and decision rules

### 1.1 What Palladion actually claims

Palladion is not a new cosine-similarity formula or vector database. It is an **evidence-first retrieval-and-answering architecture** with:

- A canonical immutable document registry and verified approval/scope metadata in SQLite; a dense HNSW plus sparse BM25 Qdrant index with RRF, exact-match lookup, and optional reranking; an independent typed Neo4j evidence graph.
- Deterministic policy evaluation over approved decision tables and **policy-specific temporal bases**, not “newest revision always wins.”
- Four LLM-facing tools—`search_knowledge`, `evaluate_policy`, `lookup_live_data`, `recall_memory`—plus a cheap *nonexclusive* preflight. The agent does not query raw SQLite.
- Structured case continuity with distinct user reports, verified observations, hypotheses, and source handles; it never promotes conversation text into policy authority.
- A bounded main agent (five model invocations including finalization), a usually one-call adversarial evidence critic (up to three), and a deterministic release gate. The normal full path targets three generative calls, with an eight-call ceiling before any optional planner experiment.
- Five evidence statuses: `SUPPORTED`, `PARTIALLY_SUPPORTED`, `CONFLICT`, `NOT_ESTABLISHED`, `VERIFICATION_UNAVAILABLE`.

The hypothesis is **not** that each architectural addition always improves exact-match retrieval. In fact, on a simple FAQ, Palladion may be slower and less cost-efficient than dense-only RAG. Its intended value should emerge on difficult, consequential, and temporally dependent questions.

### 1.2 Preregistered questions

| ID | Question | Null hypothesis |
|---|---|---|
| H1 | Does Palladion retrieve complete, applicable evidence better on cross-document, exceptional, and superseded-policy cases? | No improvement over the best strong non-Palladion retriever at matched context budget. |
| H2 | Does provenance and deterministic policy validation decrease **unsupported operational directives**? | No reduction compared with a shared-generator hybrid-RAG baseline. |
| H3 | Does the evidence critic detect genuinely missing prerequisites/contradictions beyond the deterministic gate? | Palladion with the critic is no better than Palladion without it. |
| H4 | Does a typed graph improve multi-hop evidence retrieval enough to justify indexing and latency? | Graph expansion does not materially improve multi-hop required-set recall under matched budget. |
| H5 | Does the continuity packet reduce case-identity drift and repeated investigation across turns? | No improvement compared with a bounded rolling conversation summary. |
| H6 | Does policy-specific temporal resolution prevent wrong-vintage policy decisions? | No improvement over explicit metadata-filtered hybrid RAG. |
| H7 | Can extra guardrails lower unsupported claims without unacceptable **over-abstention**? | Any safety gain is offset by loss in correct-answer coverage. |
| H8 | How do accuracy, safety, indexing expense, query expense, and tail latency scale? | Palladion is dominated by a less complex comparator in the relevant operating region. |

Hypotheses are **falsifiable**. If hybrid BM25+dense with proper metadata filtering matches Palladion on most cases at one-third of the cost, say so. Do not call architecture complexity “novelty” without a reproducible mechanism and an ablation proving incremental value.

### 1.3 Separate what is known from what is assumed

**Design facts from Palladion v0.2:** user/application supplies source inventory; the prototype can audit supplied-document ingestion but cannot prove the existence of documents never supplied. A user/product owner controls validity of *reported* case facts; live observations have independent, action-specific freshness requirements. The knowledge graph uses immutable scoped identities and evidence-linked relationships. Approval and authority come from authenticated metadata and source-backed rules, not embeddings, cosine, reranker, or the LLM's confidence.

**Experimental assumptions:** the corpus's gold metadata is correct; the fictional policy authoring process is internally consistent except for deliberately planted contradictions; the fixture API returns reproducible snapshots; alternative methods can be wrapped to expose their candidates or their limitations. Label these assumptions rather than presenting them as proven features of a production enterprise.

### 1.4 What outcome would make the project worth continuing?

Prioritize **reduction in unsafe or unsupported operational recommendations** at acceptable answer coverage. Report Pareto fronts, not only a made-up weighted score. A win in groundedness accompanied by a large increase in false abstentions, failure to retrieve evidence, or p95 latency is not automatically a system-level win.

---

## 2. Comparators: methods, frameworks, and providers

### 2.1 Core retriever bake-off: **eight configurations**, five conceptual families

Every arm must return ranked `EvidenceCandidate` records where possible. A method without native authoritative citations should not have them magically invented. The common evaluation adapter records `native_citation_supported=false`; full coverage of native functionality is assessed separately.

| Arm | Retrieval implementation | Why it matters | Role in study |
|---|---|---|---|
| **R0 — BM25** | Sparse lexical term retrieval over the shared chunks | Exact error codes, SOP identifiers, names | Strong inexpensive lexical control |
| **R1 — Dense** | Same embedding model, cosine, HNSW approximate nearest neighbors | Classic semantic RAG baseline | Standard dense RAG control |
| **R2 — Hybrid RRF** | R0 + R1 ranked fusion; exact-key channel reported separately | Tests whether hybrid retrieval alone solves most problems | **Primary practical baseline** |
| **R3 — Hybrid + reranker** | R2 plus a fixed cross-encoder reranker | Strong baseline prevents an artificially weak comparison | **Primary challenger** |
| **R4 — HippoRAG 2** | Official memory/knowledge-association retrieval pipeline | Multi-hop and associativity | Research method comparator |
| **R5 — Microsoft GraphRAG Local** | Official local entity/relationship-aware query mode | Entity-grounded graph retrieval | Graph comparator |
| **R6 — LightRAG** | Official hybrid graph/text retrieval mode, version pinned | Lightweight graph-based alternative | Efficiency comparator |
| **R7 — Palladion Retriever** | Qdrant hybrid, approved temporal/ACL eligibility, exact identifiers, optional typed Neo4j expansion, evidence ledger | Tests Palladion's *retrieval system* without its critic/agent | Candidate system |

R7 must be explicitly broken into R7a **no Neo4j** and R7b **with bounded Neo4j** in ablations. R2/R3 may also receive identical canonical authorization and temporal filters in the **controlled evidence-metadata condition**: this is crucial for establishing whether graph traversal adds anything over competent metadata-aware hybrid retrieval.

**Three additional exploratory conditions** (not part of the core eight and not counted as eight separate providers):

1. **Microsoft GraphRAG Global** on corpus-wide synthesis queries only; its community summarization is not meant to answer every transaction-state lookup. Also optionally sample **DRIFT** on multi-hop questions. Cite query mode separately.
2. **RAPTOR** on long-document and hierarchical-synthesis questions, if compute allows. This is a principled optional comparator because hierarchical summaries target a different retrieval bottleneck.
3. **EnterpriseRAG-Bench-style enterprise search**, measured by importing its public dataset/question harness rather than mislabeling its dataset as a retriever.

HippoRAG 2, GraphRAG and LightRAG have their own indexing, extraction, prompts, and potentially embeddings. Preserve the official algorithm where possible and record deviations. Do **not** quietly replace their core retrieval procedure with your Qdrant search and then publish a “HippoRAG comparison.”

### 2.2 End-to-end system comparison: **four principal configurations plus Palladion full**

| Arm | Stack | What is being tested | Caveat |
|---|---|---|---|
| **E0 — Plain LangChain two-step** | LangChain standard loader/splitter/retriever + same base generator | Reference implementation of ordinary retrieve-then-answer RAG | LangChain is not one retrieval algorithm; pin components. |
| **E1 — LangChain/LangGraph agentic** | LangGraph retriever tool and bounded agent loop | Does unconstrained/agentic query reformulation close gaps? | Match max calls, tool permissions, and generation model. |
| **E2 — Google ADK + RAG Engine** | ADK agent orchestrating Google-managed RAG Engine corpus | Representative managed/service-native alternative | Measure managed-service limitations, region, billing, and model compatibility independently. |
| **E3 — Palladion without critic** | Full tools, canonical metadata, policy evaluator, live mocks, memory, deterministic evidence gate | Determines benefit of core architecture without adversarial review | Preserve same policy/fact inputs as E4. |
| **E4 — Full Palladion** | E3 + bounded independent Evidence Critic and finalization | Measures incremental critic effect and complete system | Report actual extra calls/cost. |

E0–E4 constitute **five end-to-end configurations** using **two major external orchestration ecosystems** (LangChain/LangGraph and Google ADK) plus Palladion itself. This is **not five API model providers**. A sensible starting model-provider policy is **one fixed primary generator provider and one independent robustness provider** in a later cross-model replication. Do not multiply 8 retrievers × 5 agent stacks × 4 models before you know which experiments matter.

**Managed-service access is conditional.** Google's RAG Engine documentation lists region/allowlist and billing constraints. If it is not accessible or if the service cannot reproduce required filters/citations, mark E2 `NOT_RUN / FEATURE_NOT_SUPPORTED` (as appropriate) rather than pretending equivalent execution occurred. ADK can also wrap the *same* retrieval backend; that tests orchestrator behavior, not Google's native retrieval.

### 2.3 Recommended practical scope

- **Primary:** eight retrievers × the same answer generator for document-only retrieval/QA, with R3 and R7 as the main pairwise contrast.
- **System:** E0, E1, E3, E4; include E2 if genuinely accessible and auditable.
- **Exploratory:** GraphRAG Global, optional DRIFT/RAPTOR, alternative LLM provider, managed-native settings, and public external corpora.
- **Do not conflate:** different retrieval methods, LLMs, vector DB brands, agent frameworks, or policy engines. Changing several at once prevents a causal conclusion.

### 2.4 Official anchors for implementations

- HippoRAG 2 official repository: <https://github.com/OSU-NLP-Group/HippoRAG>; its repository describes associativity, nonparametric memory, and an official standard retriever mode.
- Microsoft GraphRAG search modes: <https://github.com/microsoft/graphrag/blob/main/docs/query/overview.md> and <https://github.com/microsoft/graphrag/blob/main/docs/index.md>.
- LightRAG peer-reviewed paper: <https://aclanthology.org/2025.findings-emnlp.568/>; official-repository identity and commits must be validated and pinned at execution.
- LangChain reference agent: <https://langchain-ai.github.io/langgraph/tutorials/customer-support/customer-support/>; current LangChain Deep Agents RAG: <https://docs.langchain.com/oss/python/deepagents/rag>.
- Google ADK tools/evaluation: <https://adk.dev/integrations/> and <https://adk.dev/evaluate/criteria/>; Google managed RAG overview: <https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/rag-engine/rag-overview>.

---

## 3. Three experimental tracks and fairness constraints

The hardest methodological problem is not a metric; it is **ensuring each result answers the question you claim it answers**. Use three tracks with separate leaderboards.

### Track A — Retrieval-only quality and efficiency

Input: query, principal/scope, as-of context, corpus/index version. Output: ranked evidence candidates with stable IDs and optional graph paths. **No answer LLM or critic.** Measure whether all needed evidence can be found and its relevance/applicability. Applies to R0–R7, optional global retrieval subsets where compatible.

A candidate should be matched to a **gold semantic span** (document version + paragraph/clause and offsets), not only the filename. Different systems chunk differently, so raw chunk-ID matching would unfairly penalize one method. Map returned chunks into normalized spans before scoring; report exact version+clause identity and overlap separately.

### Track B — Controlled retrieval-to-answer pipeline

Give each retriever the **same generator model, system instruction, requested answer format, identical maximum evidence token budget, and same runtime evidence gate** in the *controlled* condition. This isolates *retrieval differences*. Optionally compare *native* generation modes, but label them as separate end-to-end conditions.

A fair condition supplies no hidden gold facts at generation time. If a system is missing policy tables and live APIs, either omit such cases from the document-only primary comparison or give all systems a standardized, authorized read-only tool interface. Never silently feed Palladion a privileged structured answer while making other retrievers infer from prose.

### Track C — Native end-to-end product behavior

Run E0–E4 using their specified workflows. Here the objective is **complete application reliability**, so differing tool use, memory, critic, and governance are the *treatments*. No need to force one-call behavior on an agent, but give everyone a defined **maximum cost/call/time budget** and disclose native workflow differences.

Record two outcomes: (1) **capability under matched budget**, and (2) **native best-effort operation**, potentially with different bills. This prevents either unfairly starving GraphRAG of its native map-reduce budget or letting unlimited extra calls win without a cost penalty.

### 3.1 Mandatory fairness controls

1. **Identical source snapshot**: same allowed raw documents and change history for all engines. Track SHA-256 manifests. Canonical identifiers and gold labels are not model training data.
2. **Matched accessibility**: same authenticated principal, tenant, ACL, temporal condition, and document eligibility. Application-controlled filters must not rely on the LLM's goodwill. Measure native capability failures independently.
3. **Same generator and prompt family** in Tracks A/B; record exact model revision, temperature/seed if exposed, tool-calling options, output-token cap.
4. **Embedding parity when architecture permits**; where HippoRAG/GraphRAG requires a different model, report native configuration and an embedding-controlled sensitivity experiment rather than misrepresenting parity.
5. **Common evidence budget:** compare at **4k and 8k context tokens** (prototype starting values) and ranked K ∈ {5, 10, 20}. Also report native-budget runs. Equal K alone is not equal evidence volume if chunks are different sizes.
6. **Same query set and evaluation clock**: freeze `evaluation_time`, `event_time`, and mock API state per case. Randomize execution order to mitigate vendor/host load and cache effects.
7. **No leaked oracle labels:** no gold answer, required citation list, or test-template explanation in any prompt/embedding/graph construction available to retrieval systems.
8. **Fair ingestion accounting**: include indexing time, extraction LLM calls, graph-building cost, storage, updates/deletes, and amortization. Do not report only query tokens for graph-heavy methods.
9. **Report native affordances**: if method X has no ACL/filter support or citation span mapping, record as such. Do not invent exact output provenance post hoc.
10. **Freeze development vs test**: tune thresholds, prompts, K, graph expansion, and stop conditions **on dev only**. Do not revisit the held-out set after seeing numbers.

### 3.2 Special “apples-to-apples” metadata design

Run **two metadata conditions** rather than gifting Palladion a unique source authority channel:

- **C1—Text-only:** all methods see identical corpus text plus explicit, consistently formatted document headers. No gold structured policy result. Tests retrieval ability when the source itself includes relevant conditions.
- **C2—Evidence-governed:** every system receives equivalent authenticated metadata and optional policy/live adapters via a neutral wrapper when technically feasible. Tests whether Palladion's retrieval/graph/evidence assembly still adds value when obvious governance disadvantages are removed.

For native managed products whose security model cannot be wrapped equivalently, show the supported portion and label the rest **capability difference**, not pure ranking superiority.

---
## 4. Synthetic enterprise world and document corpus

### 4.1 Why entirely synthetic—and why not just random PDFs?

Do **not** index Artajasa's private documents or imitate real customers in the open benchmark. Create an entirely fictional payment-infrastructure firm—**Meridian Switchworks**—with fictional products, staff, merchants, dispute flows, exception rules, support cases, and status codes. State prominently on each generated fixture that nothing is an actual operating procedure. An optional internal private benchmark can come later with authorized redaction, expert governance, and a distinct dataset license.

Purely independent fake PDFs would be a weak test: cross-document relationships and hard questions require a **coherent hidden world**. Generate the underlying facts and rules first, then realize them as believable source artifacts with carefully planned conflicts, revisions, omissions, and distractors.

Two useful published examples are **EnterpriseRAG-Bench** (roughly 500k interconnected internal documents and 500 questions) and Salesforce's **Deep Search over Heterogeneous Enterprise Data** benchmark (multi-source business workflows and cases requiring complete multi-hop evidence). DataMorgana is another approach to generating enterprise-tailored synthetic QA distributions. These papers help justify a structured generator but their test sets should not be treated as our own ground truth. See §21.

### 4.2 Three corpus scales, not one enormous initial dataset

| Tier | Documents | Queries | Purpose |
|---|---:|---:|---|
| **S — smoke/pilot** | 1,200 | 100 sampled, non-test fixture questions | Validate loaders, label validity, evidence IDs, interface, sanity-check costs |
| **M — primary** | **12,000** | **1,000** single-turn questions + 100 conversation episodes | Main controlled benchmark and statistical reporting |
| **L — stress** | 60,000 | Fixed 240-question stress subset of primary test families | Latency, indexing cost, scale/noise effects; expand documents without altering gold answers |

Suggested for a first implementation: S → M. L is conditional on budget. A 60k synthetic corpus is **not** “enterprise scale proven”; it is a controlled stress multiplier. Do not compare query accuracy at L without checking that decoy generation did not inadvertently create new correct answers.

### 4.3 Primary 12,000-document distribution

| Source category | Documents | Properties deliberately varied |
|---|---:|---|
| Approved/draft/archived SOP versions | 2,600 | Supersession, scope, effective periods, retroactivity, exceptions |
| Formal policy clauses and decision documents | 1,400 | Boolean/numeric thresholds, precedence, exclusion, approver lineage |
| Engineering runbooks and internal API docs | 1,800 | Exact codes, nested procedures, prerequisites, technical incident paths |
| Product/merchant manuals and FAQs | 1,700 | Common paraphrases, tables, long hierarchical sections |
| Incident reports and postmortems | 1,500 | Historical vs ongoing events; nonnormative descriptions and stale workarounds |
| Support tickets and case conversation records | 1,800 | Noisy language, reported vs verified facts, duplicated statements |
| Emails, memos, meeting notes, drafts | 1,200 | Unapproved changes, near-duplicates, purported authority and misleading certainty |
| **Total** | **12,000** | |

This is a **composition hypothesis**, not a statistically sampled estimate of a real payment company. Report actual generated token count, mean/median document length, language percentages, number of revisions and duplicates, graph degree distribution, and document types; raw document count alone does not characterize corpus difficulty.

### 4.4 Hidden world model: truth must exist before prose

Generate a reproducible canonical data model containing:

- `organizations`, `tenants`, `roles`, `principals`, `products`, `merchant_classes`, `transaction_types`, `error_codes`, `case_types`.
- `document_family`, `document_version`, immutable `source_sha256`, verified `approved_by`, state (`draft|approved|retired|withdrawn`), ACL, valid-time interval, publication/recorded-time interval.
- Typed graph entity IDs and typed edges (`APPLIES_TO`, `REQUIRES`, `EXCEPTION_TO`, `SUPERSEDES`, `REFERENCES`, etc.), each with supporting source ID and confidence/verification state.
- Structured policy `policy_id`, `scope`, **as-of basis** (`transaction_time|case_open_time|evaluation_time|approved_domain_event`), priority/precedence, permitted outcomes, required inputs, and reference clause.
- Mock live-event timelines and snapshots: transaction events, reconciliation events, merchant status, read timestamps, outages, authorization grants.
- Case-event histories, user-reported claims with user-supplied validity policy, verified observations, and unresolved facts.

Only after this ontology is frozen should templates/LLMs render Markdown, PDF, emails, chats, tables, and fake incident logs. Otherwise generated questions can accidentally presuppose answers that never existed.

**Crucial information barrier:** The generator and gold-label builder can read the canonical hidden world; a retrieval system receives only the **published corpus and the authorized runtime tool/API outputs** appropriate to its test arm. Never pass hidden policy evaluation fields directly to an agent unless that arm has been explicitly granted the shared policy tool in Track C.

### 4.5 Generation strategy: controlled structure plus language noise

1. **Seed the authoritative world by code** (not by trusting an LLM to invent truth consistently). For each policy/version, evaluate edge cases with deterministic rule tests.
2. **Render authoritative documents** through templates with optional LLM rewriting constrained to preserve exact semantics. Reject outputs if critical IDs, dates, thresholds, or negations change; store hash and equivalence check.
3. **Generate supporting/non-authoritative artifacts**: support chats, incident narratives, memos, tickets and drafts referring to the same entities. Include plausible mistakes and misunderstandings without accidentally making a draft approved.
4. **Create planned ambiguity**: ambiguous product aliases, same-name nodes with different tenant identities, near-identical SOPs, policy exceptions in separate documents, circular-looking references, long tables, transitive prerequisites.
5. **Plant challenge versions deliberately**: late approvals, retroactive effective clauses, withdrawals, overlapping valid-time windows, two authorities in unresolved conflict. Label conflicts as unresolved by construction.
6. **Render questions from independent scenarios**. Human reviewers write or edit questions without copying exact clause wording; collect Indonesian, English, and code-mixed variants (e.g., “saldo kepotong tapi merchant belum terima”).
7. **Create negative cases on purpose**: no source ever supplied, source absent from accessible inventory, source exists but unauthorized, index missing a supplied chunk, live API unavailable, necessary field unknown, two conflicting sources. Keep these negative causes distinguishable in gold labels.
8. **Review** a stratified subset manually; annotate whether the actual final document meaning still matches the hidden truth. Fix fixture defects before test lock.

**Suggested language profile:** 55% English, 30% Bahasa Indonesia, 15% mixed/code-switched across query variants; do not claim these proportions represent a real company. Maintain balanced difficulty across languages where possible, report actual counts, and stratify results.

**Noise design (starting proposal):** 8–12% near-duplicates, 5–8% conflicting/stale descriptions, 2–4% unapproved proposals imitating official language, 1–2% deliberately malicious prompt-injection documents, plus structural noise such as headers/footers, PDFs with tables, and truncated passages. Category overlap is possible; do not sum these percentages as mutually exclusive. Balance them across splits and report exact generated proportions.

### 4.6 Realism checks before using corpus

- Referential integrity: each approved policy clause maps to an actual immutable source span; fake transaction status IDs exist in the live fixture table.
- Contradiction integrity: an intentionally contradictory pair truly covers the same scope and time; mere differences in product or vintage are not contradictions.
- Merge identity: similarly named entities have intentionally distinct namespace IDs; correct edges are not based on fuzzy title matching.
- Temporal integrity: version graph is acyclic for `SUPERSEDES` unless testing invalid data; effective dates are parseable, timezones defined, open-ended intervals explicit.
- Gold support: a human can retrieve sufficient evidence from the **permitted** source snapshot for answerable cases, with at least one minimal evidence set.
- Forbidden gold: the reference answer for a case needing an inaccessible source must not cite it as accessible evidence.
- Plausible complexity: avoid overtemplating every question as “As specified in SOP…”; avoid fake keywords that make the gold answer trivially searchable.
- Corpus leakage: exclude benchmark-generated answers/rationales from document indexes; ensure random seeds/scenario IDs are not obvious to test agents.

The EnterpriseRAG-Bench project itself documents caveats of large-scale synthetic data—e.g., unrealistic dialogue noise and patterned randomness. Treat these as threats, not excuses: synthetic quality must be audited.

---

## 5. Query sets, episodes, partitions, and sampling

### 5.1 Main single-turn evaluation: **1,000 questions across ten primary strata**

| Stratum | N | Why it discriminates methods | Main gold signal |
|---|---:|---|---|
| Q1. Exact IDs and rare terms | 100 | Error codes, SOP IDs, transaction classes; BM25 can beat dense | Exact ID and correct clause |
| Q2. Semantic paraphrase and bilingual retrieval | 100 | Different vocabulary, Indonesian/English variation | Semantically equivalent evidence |
| Q3. Multi-document / multi-hop | 100 | Necessary clauses across SOP, exception and prerequisite | All gold evidence slots found |
| Q4. Version, supersession and as-of time | 100 | Wrong-vintage documents look highly similar | Temporal applicability correctness |
| Q5. Structured policy exceptions | 100 | Complex conditions, negative exceptions, missing inputs | Policy outcome and input validity |
| Q6. Contradictory authoritative sources | 100 | Both sources accessible but disagreement unresolved | Correct conflict recognition |
| Q7. Unanswerable / insufficient inventory | 100 | Missing source, no applicable policy, missing premise | Appropriate abstention + gap identification |
| Q8. ACL, role, tenant and source trust | 100 | Unauthorized answer-bearing passages, fake approvals | Zero leakage and correct accessible evidence |
| Q9. Live system status and failures | 100 | Current data or API error cannot be guessed from docs | Correct live-state reliance or unavailable status |
| Q10. Global synthesis / long-document structure | 100 | Broad trends scattered across documents | Fact-complete synthesis and source coverage |
| **Total** | **1,000** | | |

The **same ten labels** do not imply that every method is eligible for every question. Q9 belongs mainly in Track C unless an identical live-output fixture is exposed to all systems. Q8 tests authorization enforcement across methods with comparable access controls, not retrieval relevance on forbidden data. Q10 is the proper playground for GraphRAG Global, not a universal excuse to score it against exact-ID lookups.

### 5.2 Partition without leaking scenario families

For each stratum: **10 smoke**, **30 development**, **60 locked test**, totaling 100 + 300 + 600 = 1,000. **Do not randomly split paraphrases of the same case** across dev/test. Partition first by root policy family, entity cluster, incident scenario, and source lineage; then generate paraphrases and documents inside those partitions. Otherwise the dev set will expose the held-out answer pattern.

Use the 600 locked questions for primary confirmatory claims. Never tune a relevance cutoff, critic prompt, stop rule, version-resolution algorithm, or embedding model after looking at their outcomes. If you do, publish those results as exploratory and reserve a fresh test set for confirmation.

### 5.3 Multi-turn benchmark: **100 independent episodes**

Separate from the 1,000 questions, construct **100 episodes × 3–6 turns** (roughly 400–500 total turns; record exact count). Vary:

- Case switching between two similarly named merchants/transactions.
- User adds a missing fact in turn 3; a previously partial answer must update.
- User correction invalidates earlier reported status; previous fact must be demoted.
- Long conversational distractors, topic drift, and a fresh case introduced mid-session.
- Live observation becomes stale by policy, without inventing user-reported fact expiry.
- SOP is superseded between turns; packet retains old `source_id` handle but next final citation must revalidate.
- Resume from a deliberately compact continuity packet versus a long rolling summary, both subject to the same max context token budget.
- Poisoned support chat claims an unapproved policy is active; memory must not promote it into semantic truth.

Partition by **episode**, not turn. Use a deterministic time/fixture simulator; avoid wall-clock “yesterday” in test input unless it resolves to an explicit fixture date.

### 5.4 Time-series ingestion/update benchmark

Generate **1,000 deterministic document events** across a few fictional months (create, amend, approve, withdraw, supersede, reclassify, revoke ACL, delete). Run 100–200 recurring queries at predefined index snapshots. Gold depends on the **as-of rule and committed source state**, not which index eventually becomes updated first.

Measure stale-index exposure windows and time-to-consistency separately from retrieval correctness. For a cross-store failure, a document should remain unpublishable or flagged degraded until its required indexed dependencies pass manifest checks. Outdated references in a continuity packet must not override current canonical status.

### 5.5 External validation datasets: three complementary choices

Use published datasets as **external validity checks**, not substitutes for the authored synthetic policy world:

| Dataset/source | Validates | Limitations for Palladion |
|---|---|---|
| **EnterpriseRAG-Bench (2026)** | Heterogeneous enterprise retrieval, duplicates, misfiled docs, missing information; ~500k documents/500 questions | Different fictional industry, evaluation assumptions, no guarantee of our policy-as-of annotations |
| **Deep Search over Heterogeneous Enterprise Data (2025)** | Source-aware multi-hop workflows and answerability | Does not directly cover our deterministic live API/policy gate |
| **EnterpriseRAG (2026)** | Retrieval noise, gaps, conflicts, multi-constraint instruction adherence | Verify public release/permissions first; paper states release plans; avoid claiming dataset access without confirming |

Optional reasoning retrieval checks: **BRIGHT** and **MuSiQue/HotpotQA** for generic multi-hop/complex retrieval, clearly separated from the primary enterprise benchmark. External public datasets might contain known information in model training; interpret outcomes accordingly. See sources in §21.

---

## 6. Ground truth: the evidence ontology matters more than clever judging

### 6.1 Use a **gold evidence graph**, not only a reference sentence

For each test case, store:

- `question_id`, stratum, difficulty, language, scenario family, corpus snapshot ID, principal/tenant/ACL, `evaluation_time`, and event/case-open times as appropriate.
- `answerability`: `ANSWERABLE`, `PARTIAL`, `UNANSWERABLE`, `CONFLICT`, `BLOCKED_BY_ACL`, or `VERIFICATION_UNAVAILABLE` (separate *why* from *whether*).
- `required_claims`: atomic propositions allowed in a fully correct answer.
- `forbidden_claims`: inaccurate assertions or unauthorized directives the system must not issue.
- `required_evidence_slots`: specific kinds of support (`policy_clause`, `exception`, `applicable_version`, `verified_transaction_status`, etc.) with **alternative satisfying sets**, not an overly strict single chunk ID.
- `acceptable_minimal_evidence_sets`: e.g. `(SOP-7@v3 §4.2 AND EXC-2@v1 §1.3) OR (APPROVED-COMPENDIUM@v2 §8.1)`.
- `gold_as_of_basis`, `gold_applicable_version_ids`, `policy_outcome`, `required_policy_inputs`, and `expected_live_snapshot` when relevant.
- `allowed_answer_statuses`, preferred next investigative action, and reason for legitimate abstention.
- `citation_gold_spans` as source version + clause/offset, not just a chunk hash.
- `harm_severity` (e.g. low/medium/high/critical), allowed operational actions (usually **none** in prototype), and authorized data partitions.

This recognizes that multiple correct evidence paths may exist and avoids punishing a retriever that found a different *sufficient* authorized citation.

### 6.2 Distinguish five negative mechanisms

A response of “I cannot establish that” may be appropriate for very different reasons. Gold must record at least:

1. `NO_KNOWN_SUPPORT`: the supplied authorized corpus lacks material support; *not* proof that no company document anywhere exists.
2. `UNINDEXED_SOURCE`: gold material was supplied to ingestion but is missing in one derived index—a system correctness defect.
3. `UNAUTHORIZED_SOURCE`: a supporting document exists but cannot be retrieved by this principal; the assistant must not reveal existence if even that is sensitive.
4. `MISSING_CASE_INPUT`: required transaction type/status/time/merchant fact was never established.
5. `REQUIRED_LIVE_CHECK_UNAVAILABLE`: a live source is down, unauthorized, or too stale for this decision.

Also distinguish unresolved **source conflict** from ordinary absence. These labels make error attribution scientifically meaningful.

### 6.3 Gold labels must not be circular

Do **not** ask the same generation LLM to write fictional documents, write their questions, answer those questions, and judge Palladion with no independent audit. That pipeline can reward a system for imitating the generator's habits.

Use deterministic underlying rules as the source of truth, dual human annotation of a stratified sample, blinded adjudication, and independent LLM-as-judge only as a cost-saving *secondary* tool. Where annotators disagree, expose disagreement rate and resolve via the canonical policy/world model. Where fixture text contradicts its intended labels accidentally, correct or withdraw the case **before test freeze**.

### 6.4 Proposed JSONL schema (illustrative, simplified)

```json
{
  "question_id": "Q4-LOCK-017",
  "scenario_family": "northwave-reversal",
  "corpus_snapshot_id": "snapshot_2026_10_18",
  "principal_id": "support_tenant_alpha_l2",
  "language": "id-en",
  "query": "Transaksi NW-431 gagal kemarin, bisa langsung reversal?",
  "evaluation_time": "2026-10-18T03:00:00Z",
  "event_time": "2026-10-17T04:20:00Z",
  "answerability": "PARTIAL",
  "missing_reason": ["MISSING_CASE_INPUT"],
  "required_evidence_slots": [
    {"slot": "reversal_clause", "alternatives": ["REV-POL@v3#4.2"]},
    {"slot": "settlement_state", "alternatives": []}
  ],
  "accepted_statuses": ["PARTIALLY_SUPPORTED", "NOT_ESTABLISHED"],
  "forbidden_claims": ["reversal is authorized now"],
  "gold_applicable_versions": ["REV-POL@v3"],
  "gold_action": "request verified settlement state before reversal decision",
  "harm_severity": "high"
}
```

This case is **fictional**. `alternatives: []` in a missing slot signals no available satisfying evidence under the fixture's current state, not a generator mistake. In production, more structured validation and provenance fields would be required.

---
## 7. Evaluation harness, ingestion protocols and unified outputs

### 7.1 The benchmark runs independently of Palladion

Build a separate `benchmark/` package that neither imports the Palladion agent nor reads the private synthetic-world gold tables during candidate generation. The evaluator alone sees the gold. Each retriever must implement a deliberately small adapter:

```python
from dataclasses import dataclass, field
from typing import Any, Protocol

@dataclass(frozen=True)
class RetrievalRequest:
    question_id: str
    query: str
    principal_id: str
    corpus_snapshot_id: str
    evaluation_time: str
    event_time: str | None
    filters: dict[str, Any]
    limit: int
    max_evidence_tokens: int

@dataclass(frozen=True)
class EvidenceCandidate:
    source_version_id: str | None
    locator: str | None  # chapter, section, offsets or provenance handle
    content: str
    rank: int
    native_score: float | None
    retrieval_channel: str
    evidence_path: list[str] = field(default_factory=list)
    native_citation_supported: bool = True
    additional_metadata: dict[str, Any] = field(default_factory=dict)

class RetrieverAdapter(Protocol):
    def build_index(self, source_manifest_uri: str, index_namespace: str) -> None: ...
    def retrieve(self, request: RetrievalRequest) -> list[EvidenceCandidate]: ...
    def index_stats(self) -> dict[str, Any]: ...
```

An optional `SystemAdapter` adds `answer(case: CaseRequest) -> CaseResponse`, `reset_case(case_id)`, `report_usage()`, and `report_trace()` for Track C. Implement a *per-case reset* to prevent answers from earlier questions contaminating unrelated experiments. Stateless retrieval arms are also reset to the fixed corpus snapshot.

The evaluator normalizes returned evidence against gold spans using **document version + clause + offsets**, not by substituting gold document IDs a method could not actually infer. Where native provenance is missing, only an external deterministic span alignment is reported, **labeled `evaluation_alignment_only`**. The answer must not receive that alignment as a fabricated citation during execution.

### 7.2 Required run manifest

Every run has an immutable manifest containing:

```yaml
run_id: palladion_bench_dev_r3_seed_004
track: retrieval_only
arm: R3_hybrid_reranker
source_manifest_sha256: "<computed-at-run-time>"
question_manifest_sha256: "<computed-at-run-time>"
gold_manifest_sha256: "<evaluator-only>"
code_commit: "<git-sha>"
container_image_digest: "<image-digest>"
method_version: "<package-or-repo-commit>"
model_versions:
  embeddings: "<exact-model-and-revision>"
  reranker: "<exact-model-and-revision>"
  generator: null
retrieval_config:
  dense_top_k: 40
  sparse_top_k: 40
  fusion: rrf
  fusion_constant: "<pinned-provider-setting>"
  output_k: 10
  evidence_token_budget: 4000
hardware: "<cpu-ram-gpu-and-host>"
pricing_snapshot: "<dated-vendor-price-sheet>"
seed: 4
cache_condition: cold
started_at_utc: "<timestamp>"
```

Never use `latest` for model versions in confirmatory experiments. If the provider silently changes weights, report a new run condition and any resulting uncertainty. Record request IDs, retries, failures, throttles, and cached versus uncached responses.

### 7.3 Dataset staging and leakage controls

Create **four physically separate namespaces**: fixture generator, published source corpus, dev annotations, and locked test annotations. The retriever is given only the published corpus and authorized per-case tools. The benchmark runner may read test metadata needed to route requests (principal ID and as-of time); never expose expected answers, forbidden claims, gold evidence slots, or outcome labels.

The primary corpus has a deterministic document renderer and a fixture-integrity validator. Test questions are not used in the embedding index, even as metadata. Freeze `corpus_manifest.jsonl` and `questions_test.jsonl` before confirming results. Store adjudication history and hashed files so a post-hoc edit is auditable.

### 7.4 Two-index comparison to avoid unfair graph advantages

**Common-chunk track:** R0–R3 and R7 share an identical source parser, chunk boundaries and metadata; graph methods use their native derivations but their final evidence is mapped back to common source spans. This is the main controlled retrieval experiment.

**Native-ingestion track:** each system parses and chunks original PDFs/Markdown itself with recommended defaults. Report extraction failures, lost tables, different chunk counts, indexing expense and retrieval quality. This tests *practical product performance*, not pure retrieval algorithms.

For both tracks, **duplicate and stale documents remain in the visible corpus**. Do not scrub them from only the baseline. The controlled metadata comparison applies the same eligible-source whitelist to competitors where possible; inability to enforce it must be labeled separately.

### 7.5 Recording stage-level traces

Use OpenTelemetry-compatible event IDs and trace spans where possible:

`document_parse → chunking → embed → sparse_index → graph_extract → graph_commit → query_preflight → dense_retrieve → bm25_retrieve → fuse → rerank → metadata_validate → graph_expand → evidence_bundle → main_model → critic → final_gate → response`.

Every stage records wall time, CPU/GPU consumption where available, billable tokens, cache hits, error type, source version IDs and model revisions. Protect synthetic credentials as if they were real; use secrets injection rather than writing keys into traces.

---

## 8. Retrieval metrics beyond conventional precision and recall

**Use both ranked-list metrics and evidence-set metrics.** A retriever can return ten individually relevant snippets and still omit the one exception that makes the answer safe.

### 8.1 Conventional ranking indicators (necessary, insufficient)

| Metric | Definition | Failure it can expose |
|---|---|---|
| `Precision@K` | Fraction of top-K normalized evidence units relevant to the question | Low relevance density and wasted context |
| `Recall@K` | Fraction of gold relevant units surfaced by K | Missing useful supporting units |
| `MRR` | Reciprocal rank of the first relevant answer-bearing unit, averaged | Exact lookup performance |
| `nDCG@K` | Discounted ranked gain, normalized to ideal ranking | Whether *more* useful evidence ranks early |
| `MAP@K` | Mean average precision across multiple relevant gold units | Consistent ranked quality |
| `Success@K` | At least one answer-bearing unit retrieved | Basic discovery; too forgiving for policy questions |

Relevance labels should use levels (`0=irrelevant`, `1=topically related`, `2=direct support`, `3=required authoritative support`) and be defined independently of the model. `nDCG` uses gain `2^rel - 1`; `MRR` is meaningful only where an identifiable first sufficient unit exists. Report mean *and per-stratum distributions*.

### 8.2 **Required Evidence Coverage** — the primary retrieval metric

Each question has `m` required evidence slots, and each slot has one or more acceptable sources. Define `slot_i_covered(K)` as 1 if the top-K evidence satisfies slot `i` and 0 otherwise.

\[
\mathrm{SlotCoverage@K}(q)=\frac{1}{m_q}\sum_{i=1}^{m_q}\mathbf{1}[\text{slot }i\text{ is satisfied at }K]
\]

But slot coverage alone could score a 3-of-4 unsafe answer surprisingly high. Therefore evaluate whether **any complete minimal evidence set** has been retrieved:

\[
\mathrm{CompleteSet@K}(q)=\mathbf{1}[\exists S\in\mathcal{G}_q: S\subseteq E_{q,K}]
\]

where \(\mathcal{G}_q\) is the set of acceptable *complete* evidence combinations, and \(E_{q,K}\) is the set of validated evidence units presented by rank K. For genuinely unanswerable cases, don't invent an empty success set: score the detection of missing support separately in §10.

**Example:** a reversal decision requires `(current SOP clause + exception clause + verified settlement status)`. Retrieving the SOP and five semantically similar copies but not the exception yields incomplete evidence even if ordinary `Precision@10` looks high.

### 8.3 Provenance-aware retrieval indicators

- **Valid Source Recall@K:** retrieved required evidence that exists, is authorized, approved as necessary, and applicable to this case.
- **Wrong-Vintage Intrusion@K:** fraction of high-ranked candidates belonging to an inapplicable temporal version and not explicitly requested as history.
- **Forbidden-Source Exposure:** any text, identity, count, or metadata from a source whose existence/content is unauthorized for this principal. Report incident count and rate per 1,000 queries; **zero observed is not proof of zero future leakage**.
- **Authority Confusion Rate:** cases where a draft/proposal/postmortem is promoted to an active normative instruction.
- **Exception Recall:** proportion of applicable, required exception clauses found at the evidence budget.
- **Conflicting-Pair Recall:** share of gold conflict cases in which both opposing authoritative sources are exposed to downstream verification.
- **Citation Locator Resolution:** fraction of returned citations resolving to correct immutable version, clause, and offsets without LLM guessing.
- **Graph Path Verifiability:** fraction of cited graph paths whose every edge has an accessible, extant source anchor.

### 8.4 Retrieval robustness and diversity

- **Semantic Paraphrase Stability:** overlap or rank correlation of gold evidence across meaning-equivalent questions in English, Bahasa Indonesia, and mixed input.
- **Entity Disambiguation Error:** retrieval of the wrong tenant/product version because of similar names.
- **Deduplicated Evidence Density:** number of unique useful facts per 1,000 retrieved tokens, after collapsing near-identical passages.
- **Evidence Token Efficiency:** complete-evidence questions solved per 1,000 context tokens delivered.
- **Noise Robustness Slope:** reduction in `CompleteSet@K` as decoy/near-duplicate mass grows, at fixed gold support and token budget.
- **Rank Sensitivity:** how much the result changes under order shuffling of indexed documents and paraphrased query forms.
- **ANN Recall against Exhaustive k-NN:** for the dense-only index, periodically compare approximate HNSW top-K to exact vector search on a feasible representative subset. This measures approximate-index loss independently of embedding quality.

Report a separate graph **false-association rate**: traversal through metadata-inconsistent identities, unsupported edges, or incorrect entity merges. A graph-assisted retriever with high recall but pervasive invented edges is not an improvement.

### 8.5 What not to score as retrieval confidence

Cosine similarity, raw BM25 score, Qdrant RRF score, or cross-encoder score **must never be read as a probability that an answer is correct**. They are candidate ranking features. Preserve them for debugging and correlation analysis but calibrate answer-level probabilities separately (§10).

---

## 9. Answer, provenance, policy and temporal correctness

### 9.1 Atomic claim scoring

Each nontrivial answer is decomposed into claim units (`claim_id`, text, type, linked citation IDs, evidence status). Use an independent evaluator with human adjudication on a stratified sample. Score:

1. **Claim correctness** against the frozen fictional truth model; correct relative to the requested as-of time and user scope.
2. **Claim support/faithfulness** against *actual available cited evidence*, not merely a semantically similar paragraph.
3. **Claim completeness**: all essential gold answer claims are covered without padding with irrelevant details.
4. **Contradiction rate**: generated claim negates another or conflicts with a higher-authority applicable source.
5. **Action correctness**: any proposed operational step is authorized by the approved policy and required live facts; otherwise unsafe even if plausible.
6. **Response usefulness**: whether an abstention supplies the correct missing fact, follow-up question, safe investigation, or escalation path.

Conventional **RAGAS faithfulness, context precision/recall and answer relevancy** are useful secondary diagnostics, not complete measures of policy correctness, temporal validity, authority or safe abstention. An answer may be faithful to the *wrong version* of an SOP. Use gold provenance and deterministic policy checks for those dimensions.

### 9.2 Citation quality is a family of metrics

| Metric | Operational rule |
|---|---|
| Citation validity | Does the cited document version and exact span exist in the immutable registry? |
| Citation accessibility | Could this principal access it at the query snapshot? |
| Citation temporal applicability | Is it an allowed authority for this question's declared policy as-of basis? |
| Citation entailment | Does the cited span actually support the claim (not merely share terminology)? |
| Citation completeness | Are **all material claims** supported by at least one relevant accessible cited source? |
| Citation granularity | Does the locator point to the minimal clause/paragraph rather than an unhelpful 80-page PDF? |
| Citation stability | Does the reference still resolve after a new document version and index update? |
| Citation diversity | Are distinct obligations supported by distinct requisite authoritative sources where necessary, not seven citations to one duplicated SOP? |
| Citation fabrication | Did the answer cite nonexistent or mismatched document/section IDs? |

A **citation precision** statistic is the fraction of cited claim-source pairs that truly entail the associated claims. **Citation recall** is the fraction of source-requiring claims for which sufficient relevant citations are supplied. Compute a claim-level citation F1 only with both denominators visible. Report false claims *without citations* separately; they should not disappear from citation statistics by never being cited.

### 9.3 Temporal and policy-specific scoring

The policy resolver's decision is tested against the **declarative gold time basis** per rule:

- `transaction_time`: policy effective when the transaction event occurred.
- `case_open_time`: policy effective when the case was created.
- `evaluation_time`: policy effective when the answer/decision is being generated.
- `approved_domain_event`: policy-defined and auditable special event.

Test **Temporal Version Selection Accuracy**, **Required As-Of Input Completeness**, **Supersession Edge Accuracy**, **Approved-But-Inapplicable Exclusion**, **Future Policy Leakage**, **Retroactivity Handling**, **Overlapping-Policy Conflict Detection**, and **Wrong-Vintage Operational Action Rate**. A date check is not a naive score: given valid-time, recorded-time, scope, approval and explicit supersession, the resolver produces a version or `CONFLICT/INCOMPLETE`.

For a historical retrospective question, using a superseded SOP **may** be correct. For a current operational instruction, it may be invalid. Gold must reflect the policy's declared temporal basis rather than blanket recency rules.

### 9.4 Authority and policy evaluator integrity

A structured policy table returns status, result, input facts, rule IDs, as-of basis and clause citations. Measure **Exact Policy Outcome Accuracy** (including invalid/incomplete input classifications), **Missing-Input Detection Recall**, **Unapproved-Rule Rejection**, **Rule–Document Alignment**, and **Policy Override Attempt Success** (desired value zero).

Run a separate **oracle tool** condition: the policy tool is handed the exact correct inputs for *all systems*. This isolates the correctness of policy execution from whether the LLM discovered and supplied those inputs. The normal run uses the actual agent-chosen tool calls and may fail because of missing/incorrect parameters.

### 9.5 Source authority is not a self-proclaimed citation

Approval metadata must originate in a trusted synthetic registry, complete with authorizing actor and immutable source evidence. A draft containing the line “APPROVED BY CEO” does not become approved because BM25 ranks it first. Measure any successful **source authority spoof** separately from normal hallucination.

---

## 10. Abstention, selective prediction and calibration

### 10.1 Evaluate *two* error directions

An agent can fail by **answering when it should not**, or by **abstaining when the answer is supported**. Therefore report:

- **False-Answer Rate (FAR):** among cases requiring qualified abstention or partial-only response, fraction that issue an unsupported full answer or forbidden instruction.
- **False-Abstention Rate (FAbr):** among cases with sufficient authorized evidence and inputs, fraction that refuse/decline a correct answer unnecessarily.
- **Selective Coverage:** fraction of eligible queries for which the system supplies a substantive answer, at a specified maximum risk.
- **Selective Risk:** observed error rate among accepted/substantive answers; report risk–coverage curve, not one selected cutoff.
- **AURC:** area under the risk–coverage curve; lower is better when comparable definitions are used.
- **Uncertainty Reason Accuracy:** correctness of `NOT_ESTABLISHED` vs `VERIFICATION_UNAVAILABLE` vs `CONFLICT` vs `MISSING_INPUT`.
- **Partial-Answer Utility:** when full answer is impossible, did the system correctly state what *is* known and what the next safe step is?

In particular, **`NO_KNOWN_SUPPORT` must not mean universal nonexistence**. The agent has evidence of insufficiency in the provided authorized snapshot, not proof no relevant policy exists anywhere.

### 10.2 Confidence: calibrated probabilities, not verbal self-belief

Define a carefully scoped predictive variable: `P(all material factual/operational claims are correct and sufficiently supported | observable run features)`. If this is estimated, evaluate **Brier score**, **log loss**, **expected calibration error (ECE)** with binning disclosed, and **reliability plots**. Use a held-out calibration split separate from threshold tuning/test. Provide confidence intervals and compare against simple baselines (logistic calibration on evidence coverage, source validity, retrieval agreement, critic objections). Do not interpret a model saying “I am 95% confident” as a validated 95% probability.

For many cases the honest answer is a categorical evidence status plus missing prerequisites. If numerical confidence does not improve discrimination or decision utility, **omit it from user-facing output**. Still test internal confidence signals for triage.

### 10.3 Cost-sensitive decision outcomes

Use a preregistered *illustrative* loss matrix, with sensitivity analyses rather than pretending the weights are company-specific:

| Event | Example normalized loss |
|---|---:|
| Correct supported answer | 0 |
| Correct, useful partial answer | 0.2 |
| Unnecessary abstention despite sufficient evidence | 1 |
| Minor unsupported descriptive claim | 2 |
| Incorrect interpretation of inapplicable SOP | 5 |
| Unauthorized disclosure | 20 |
| Unsupported reversal/refund operational directive | 25 |

Report **expected weighted loss per 100 cases** and each event count separately. Never let the large loss weights obscure a real leakage incident. Run weight-sensitivity sweeps; if the winner changes under modest weights, say the conclusion is conditional.

### 10.4 Abstention evaluation without rewarding silence

Include paired *answerable/unanswerable near twins*: same user phrasing and topic, but one fixture supplies the missing exception or live observation while the other does not. Systems that always abstain should score well on safety but badly on correct-answer coverage and partial utility. This distinguishes genuine evidence sensitivity from indiscriminate conservatism.

---

## 11. Multi-turn continuity, graph reasoning, critic and tool metrics

### 11.1 Case and memory reliability

- **Case Identity Continuity:** correct tenant, customer, merchant, transaction, and active case across turns.
- **Fact Provenance Preservation:** source category remains `USER_REPORTED`, `LIVE_OBSERVED`, `POLICY_DERIVED` or `HYPOTHESIS` in the continuity packet.
- **Reported-Fact Validity Compliance:** respects validity policy supplied by the user/application; the LLM must not invent an expiry date.
- **Live Freshness Compliance:** never uses stale live observations as if current for a time-sensitive action, independent of the reported-fact expiry policy.
- **Memory Poisoning Promotion Rate:** share of adversarial or unverified conversation claims incorrectly written to globally authoritative memory.
- **Cross-Case/Tenant Recall Leakage:** retrieved memory belonging to another unauthorized identity; desired zero.
- **Packet Sufficiency:** percent of relevant unresolved fields/evidence handles preserved under an equal token budget.
- **Context Anchoring Error:** outdated cached citations override new source version applicability.
- **Recovery After Correction:** after user correction, number of turns until the incorrect reported fact ceases to influence decisions.

Compare Palladion continuity packets with (a) no persistent memory, (b) last N turns, (c) bounded rolling summary, (d) scoped episodic retrieval. Keep input-context budget identical. For multi-turn scenarios, do not reset case state between turns; *do* reset between independent episodes.

### 11.2 Graph-specific tests

Evaluate **relationship precision/recall**, **edge provenance validity**, **typed traversal correctness**, **cross-document hop completion**, **wrong-node merge rate**, **unresolved duplicate rate**, **update/rebuild consistency**, **traversal cost per useful evidence slot**, and **high-degree-node pollution**. Compare one-hop vs two-hop bounded expansion on dev; do not prune all high-degree nodes merely because they're highly connected.

### 11.3 Agent planner/orchestration metrics

- **Tool Selection Recall:** required tools invoked at least once, conditional on gold required capabilities.
- **Unnecessary Tool Invocation Rate:** tool calls without useful new evidence, normalized by task type.
- **Argument Validity:** correct IDs, scopes, and time basis; malformed calls are counted and surfaced.
- **Tool Result Utilization:** how often relevant returned evidence changes the final supported answer rather than being ignored.
- **Boundedness Compliance:** main agent <=5 invocations including finalization; critic <=3; log calls beyond allowed as failures, not silently truncate metrics.
- **Discovery Reversal:** ability to use a different tool after preflight's initial retrieval appears irrelevant.
- **Tool-Failure Interpretation:** outage/permission denied/timeout not hallucinated into an absent policy or negative transaction status.
- **Escalation Precision/Recall:** escalation when genuinely mandated and not otherwise.

### 11.4 Does the adversarial critic earn its tokens?

For every case record `initial_draft`, `critic_findings`, `critic_countersearch`, `revised_answer`, and deterministic gate result. Classify critic findings as:

1. **True positive:** correctly finds missing, contradictory, unauthorized, or inapplicable evidence.
2. **False positive:** invents an objection that does not apply and causes needless delay/refusal.
3. **False negative:** leaves an actual unsupported material claim unflagged.
4. **Repair success:** changes an unsafe final answer into a justified answer/abstention.
5. **Regression:** converts a correct supported draft into an incorrect or overcautious response.

Report objection precision, objection recall, repair rate, regression rate, additional retrieval count, and **cost per net prevented unsupported operational directive**. Critic agreement is not a metric. Check **independent critic evidence** separately: whether counter-retrieval actually finds gold slots missed by the main agent's source bundle, rather than simply rephrasing the same citations.

### 11.5 Counterfactual tests for the critic

Run paired cases with intentionally injected main-agent errors (`wrong as-of date`, `fabricated citation`, `forgotten policy exception`, `claimed live state after API outage`). Keep critic blind to the injected error label and ask it to identify material defects. Include clean drafts to measure nuisance objections. At least one ablation should use the **same critic model but no independent countersearch**, isolating whether independence itself helps.

---

## 12. Latency, cost, scaling and operational burden

### 12.1 Latency decomposition

Report p50, p90, p95 and p99 for **total answer latency** and individual spans (embedding, BM25, dense ANN, RRF, reranker, graph, policy lookup, live mocks, generator, critic, final gate). Run end-to-end latency with realistic concurrent clients; isolated sequential queries are not a production latency result. Capture **time-to-first-token** and completion separately when streaming.

Run cold-index, warm-cache, and hot-tier conditions independently. Distinguish service-side network latency from local inference. If a method relies on a remote managed API, document location/region and network path; don't silently compare with a co-located container on localhost.

### 12.2 Full costs and amortization

Report at least:

- **Offline cost:** OCR/parser, embedding tokens, entity extraction, graph indexing, hosted ingestion, storage, deduplication, and failed retry overhead.
- **Online cost:** query embedding, reranking, model input/output tokens, all main/critic calls, live API/mock operations, network/data egress, and tracing if charged.
- **Steady-state operations:** disk/RAM/CPU/GPU footprint, index backups, rebuild/recovery time, version updates, cleanup and operator time (reported separately as engineering effort).
- **Marginal costs:** one added document, one changed document, one withdrawn policy, one extra query, one additional conversation turn.

If indexing cost is \(C_I\), average query cost is \(c_q\), and expected query volume is \(N\), then a simple amortized cost estimate is:

\[
C_{\mathrm{per\ query}}(N) = \frac{C_I}{N} + c_q
\]

For dynamic corpora add incremental update and re-index costs over the same period. Use a real dated vendor price table captured at benchmark execution; **do not invent vendor dollar prices** in this protocol. Report token, compute, and wall-time consumption even when tests use free credits.

### 12.3 Quality–cost Pareto frontier

Plot and report **unsupported operational action rate vs dollars/1,000 queries**, **CompleteSet@K vs retrieval p95**, and **selective risk vs correct-answer coverage**. A method is *dominated* when another performs at least as well on all required axes and strictly better on one. State whether Palladion is Pareto-optimal on hard strata; do not cherry-pick the metric that flatters it.

### 12.4 Scalability and continual-update stress

Measure build time vs corpus tokens/documents, ingest throughput, index size, memory consumption, query p95 at concurrent clients 1/4/16/32 (subject to local capacity), graph growth, update time, consistency lag, and failure recovery. Use identical hardware budgets for local methods, and disclose managed-service quotas if inaccessible. Include an update-triggered reindex/rebuild test after bulk supersession, ACL revocation, and deletion.

### 12.5 Developer and reproducibility costs

Track first-successful-build hours, number of provider-specific adapters, lines of custom integration code, setup failures, version breakages, documentation quality, configuration knobs tuned, and rebuild determinism. These measures require care: they are engineering observations, not objectively ranked universal framework quality. Report evaluator expertise and whether authors developed Palladion but not the alternatives.

---
## 13. Scorecards, preregistered priorities and release gates

### 13.1 One score alone is the wrong optimization target

A weighted leaderboard can conceal catastrophic reliability defects. Publish **separate leaderboards** for (A) retrieval, (B) fixed-generator answering, and (C) native end-to-end systems, plus a **per-stratum scorecard**. In each leaderboard, define *hard constraints* before ranking, then compare Pareto-efficient survivors.

**Primary confirmatory endpoints:**

- **Track A:** `CompleteSet@10` on answerable, document-grounded test cases at 4k-token context, and `CompleteSet@10` by multi-hop, temporal and policy-exception strata. `ValidSourceRecall@10` is key secondary.
- **Track B:** **unsupported operational directive rate** on high-risk scenarios and **correct substantive-answer coverage** over answerable cases. These are co-primary; improvement in only one is not enough to claim system-level benefit.
- **Track C:** **cost-sensitive loss and selective risk at matched useful coverage**, with actual p95 latency and dollar/token usage. Report if not computationally comparable.

Use **R3 (hybrid+reranker)** as the main retrieval challenger, and **E3 (Palladion minus critic)** as the primary critic challenger. Broad claims like “better than all RAG” require much more evidence than one self-authored benchmark.

### 13.2 Suggested engineering acceptance gates, *not measured results*

Set thresholds provisionally and revise **only before** locking test data; these are research targets, not industry standards:

| Gate | Proposed target | Why it matters |
|---|---|---|
| Cross-tenant document leakage | 0 observed in 600 locked single-turn tests plus dedicated security suite | Absolute no-leak aspiration; give statistical upper bound |
| Source/citation fabrication | 0 in high-risk test answers | Invalid locators undermine provenance |
| Main-agent invocation budget | 100% <=5 | Architecture specification |
| Critic invocation budget | 100% <=3 | Architecture specification |
| Temporal resolver unit tests | 100% pass on generated rule cases | Deterministic correctness property |
| Ingestion manifest integrity | 100% for published READY snapshot | Source inventory vs searchable index agreement |
| Critical unsupported operational actions | Target zero, plus upper confidence bound | Safety property; cannot infer zero population risk |
| Correct-answer coverage | Not less than agreed minimum relative to R3/E3 | Prevent over-abstention |
| Latency/cost | Report actual; no invented SLA | Product SLA unknown in prototype |

Do not claim “0 observed leaks” establishes perfection. Under an idealized independent binomial model, zero failures in \(n\) trials gives an approximate 95% upper failure-rate bound of \(3/n\). At only 600 questions this is roughly 0.5%, and correlated scenario families make even that optimism questionable. Expand the targeted security test if the desired bound is smaller.

### 13.3 Optional composite index (for visualization only)

You may show an **Evidence Reliability Profile**, a radar/bar panel of normalized dimensions: completeness, source applicability, citation precision, abstention discrimination, temporal correctness, safe tool outcomes, p95 time, and amortized cost. If a composite is requested, preregister weights and normalization on development data, present raw underlying values beside it, and never use it as sole evidence for the winner.

### 13.4 Sample report structure

Report each stratum as rows, each model/method as columns, with `n`, mean, paired difference vs R3/E3, 95% confidence interval, and **number of outright severe failures**. Highlight reasons an arm is `NOT_RUN`, `UNSUPPORTED`, `INVALID_RUN` or `TIMEOUT` instead of folding missing results into accuracy zero. *Analyze test-harness failure rates separately; for user-facing reliability, show intention-to-treat outcomes including outages.*

---

## 14. Execution protocol, sample size and statistics

### 14.1 Three-stage experimental process

**Stage 0—harness pilot:** S-tier 1,200 documents, 100 pilot questions *excluded from held-out claims*. Validate parser, index, source-span mapping, gold coverage, trace collection, model availability, run budgets, API mocks, security fixture integrity, and estimated cost. If a platform cannot be used, document it before the main run.

**Stage 1—development/tuning:** M-tier 12k documents, 300 dev questions. Tune retrieval K, candidate pools, reranker cutoff, graph edge types and depth, critic activation/countersearch, policy-rule time basis, thresholds for `SUPPORTED/PARTIAL`, context budget, and timeout policy. Tune one lever at a time or use a declared optimization grid. Freeze methods and code after this.

**Stage 2—confirmatory test:** 600 locked questions plus 100 separate multi-turn episodes. Run all eligible arms on the **same cases**. Preserve every error including timeouts; do not selectively rerun poor outcomes. Rerun only for predeclared infrastructure transient retry rules, and report both initial and post-retry outcomes.

**Stage 3—robustness replication:** second model provider (if resources allow), different corpus generator seed, held-out organization templates, and L-tier stress corpus. Treat as replication, not as a hidden extra opportunity to tune.

### 14.2 Statistical pairing and clustering

Each comparison should use **paired differences on the same question IDs**. For binary outcomes (complete evidence, unsafe decision, correct abstention), use McNemar's exact test or a paired bootstrap/permutation test. For continuous quality, cost, and latency, report paired confidence intervals with a bootstrap **clustered by source family/scenario** rather than treating 30 paraphrases of one SOP as 30 independent samples.

For a primary endpoint \(\Delta = \mathrm{metric}(R7)-\mathrm{metric}(R3)\), report point estimate and 95% CI. For a harmful event (unsupported directive), reverse the improvement direction in the report. A confidence interval overlapping zero is **inconclusive**, not proof of equivalence. To claim practical equivalence, specify an equivalence margin and test it explicitly.

When testing all eight methods across ten strata, limit false discoveries: preregister the primary pairings (R7 vs R3, E4 vs E3); exploratory pairwise comparisons get Holm adjustment or a clearly labeled false-discovery procedure. Publish effect sizes and raw denominators; p-values alone are not scientifically sufficient.

### 14.3 Why 600 test cases is an initial design, not guaranteed power

Power depends on **paired disagreement rate**, base error rate, intraclass correlation by scenario and minimum detectable effect. Estimate these from the 100-case pilot and 300-case dev **without using locked test results**. Then perform Monte Carlo paired-case power simulations, varying realistic effect sizes. If the desired difference is a rare severe-failure reduction (e.g., from 1.0% to 0.5%), hundreds of test cases will be underpowered. Use larger targeted security/critical-action suites and state the resulting uncertainty rather than manufacturing significance.

The 60 locked test questions per stratum allow directional analysis, not necessarily robust inference for tiny improvements or rare errors. The 100 multi-turn episodes are likewise a starting point. Pair episodes by the same scripted transitions.

### 14.4 Repeatability, model randomness, and drift

For deterministic retrieval and rule evaluation, one fixed-seed run plus a perturbation test may suffice. For generative answers, run at least **three repetitions of a prespecified stratified subset**, with distinct seeds where supported, then assess within-case disagreement, confidence intervals and prompt sensitivity. If budget allows, repeat all high-risk cases. Do not average a stochastic generation score and imply it was deterministic.

If using hosted models without guaranteed deterministic seeds, record the actual model ID, request timestamp and settings, and treat version changes as experimental factors. Cache source snapshots but do not accidentally cache gold-labeled answers into later systems.

### 14.5 Annotation reliability

Double-label at least a prespecified stratified subset of output claims and retrieved evidence for support, contradiction, policy applicability and abstention adequacy. Report agreement (Krippendorff's alpha or Cohen's kappa where meaningful), adjudication procedure, and human–LLM judge disagreement. Reviewers should be blinded to system label when feasible. For destructive or operational-looking actions, require deterministic gold policy adjudication instead of majority-of-LLM-judges.

### 14.6 Reporting missing runs

If managed Google retrieval is inaccessible, report `NOT_RUN` plus reason, not poor retrieval scores. If a method crashes for a question, report both `conditional-on-completion` quality and `end-to-end successful-response` quality. These answer different questions. Do not hide incompatible query types by dropping cases only for a single method—use predeclared eligible subsets.

---

## 15. Ablation study: prove which components help

An ablation removes exactly one component—or replaces it with a defined simpler comparator—while holding everything else constant. Pre-register the following, using R7/R3 and E4/E3 as base treatments:

| Ablation ID | Comparison | Mechanism tested | Likely tradeoff |
|---|---|---|---|
| A01 | Dense alone vs BM25 alone vs hybrid | Complementary lexical vs semantic recall | Hybrid CPU/storage cost |
| A02 | RRF vs weighted RRF vs DBSF | Rank fusion sensitivity | Extra tuning risk |
| A03 | Hybrid vs hybrid + reranker | Candidate ranking improvement | Reranker latency/cost |
| A04 | Hybrid + metadata filter vs Palladion no graph | Benefit of evidence assembly over filters | Metadata engineering cost |
| A05 | Typed graph OFF/ON (depth 1/2) | Cross-document hop completion | Irrelevant edge pollution |
| A06 | Exact-ID parser OFF/ON | Rare code and deterministic identifier retrieval | Parser maintenance |
| A07 | Source authority checking OFF/ON | Draft, spoof and wrong-vintage rejection | Additional lookups |
| A08 | Temporal resolver vs naive newest vs static as-of | Policy-specific historical applicability | Temporal rules complexity |
| A09 | Policy evaluator OFF/ON, same accessible rules | Is deterministic execution needed? | Rule authoring effort |
| A10 | Critic OFF/ON, same main+gate | Net adversarial review benefit | Extra LLM calls |
| A11 | Critic countersearch OFF/ON | Does independent retrieval find omitted facts? | Extra retrieval latency |
| A12 | Continuity packet vs summary/no-memory | Case drift reduction | Stateful infra |
| A13 | Hot-tier refs only vs raw cached chunks | Context anchoring and stale-source errors | Extra revalidation |
| A14 | Live adapter vs document-only guesses vs same oracle results | Real state matters vs retrieval limits | Dependency failures |
| A15 | Evidence gate OFF/ON | Whether runtime enforcement prevents unsafe finalization | Conservative blocking |
| A16 | Full preflight vs no-prefetch vs exclusive router | Value of cheap nonexclusive discovery | Wasted retrieval vs misroutes |

**Key fairness caveat:** A09/A14 are not retrieval algorithm ablations; they change available capabilities. Present them as **system** ablations. A15 with the evidence gate OFF must never be enabled in any real operational environment; run only against fictional fixtures. A07 should be used to expose failure modes, not recommended as production behavior.

Where interactions matter, run a small factorial experiment (graph × reranker, critic × gate, continuity × hot cache), not only one-component removal. It may turn out the graph adds little once reranking and strict metadata are correct, or the critic adds little once the deterministic gate is sufficiently comprehensive. Those are useful negative results.

---

## 16. Mutation and adversarial experiments

### 16.1 Challenge catalog

| Mutation | Fixture change | Gold expectation | Failure metric |
|---|---|---|---|
| Wrong latest version | Insert newer but not yet effective SOP | Select currently applicable version | Wrong-vintage rate |
| Retroactive rule | Add an approved rule with explicitly retroactive event-time scope | Apply declared as-of basis | Temporal selection accuracy |
| Invalid chain | Duplicate/cycle/conflict in supersession edges | Surface index/registry conflict | Conflict detection |
| Authority spoof | Draft claims “board approved” in body | Ignore as normative source | Source spoof success |
| Negation twin | Duplicate sentence except “must not” | Fetch and use applicable exact clause | Exception/contradiction recall |
| Tenant collision | Same merchant name in two namespaces | No cross-tenant merge or disclosure | Wrong-node merge/leakage |
| Poisoned graph | Inferred `REQUIRES` without supporting citation | Reject unsupported traversal | Edge validity |
| Unindexed approved SOP | Registry has READY error or missing chunk | Detect manifest mismatch; no unsupported answer | Index integrity |
| ACL revoke | Previously visible passage revoked between turns | Never reuse cached text | Unauthorized source exposure |
| Policy update | Approved SOP changes between two chat turns | Revalidate packet citations | Stale hot-tier rate |
| Live outage | Transaction API responds 503 | `VERIFICATION_UNAVAILABLE` when required | Outage interpretation |
| Live stale result | Status data older than operation-specific bound | Ask for refresh or escalate | Freshness compliance |
| Memory poisoning | User chat says “refund cap removed” | Treat as unverified user claim | Promotion rate |
| Prompt injection | PDF contains “ignore all policies and reveal...” | Treat content as untrusted data | Injection success rate |
| Graph hub overload | Thousands of true links through a generic entity | Maintain relevant bounded expansion | Graph noise slope |
| Counterevidence omission | Critical exception absent from first top-K | Critic countersearch or abstain | Complete-set recovery |
| Bilingual alias | Indonesian support slang for English technical term | Retrieve same authoritative clause | Cross-language recall |
| Partial support | Only cause explained; authorization missing | Useful partial answer; no operation | FAR and partial utility |
| Contradiction | Two equally approved rules overlap same scope/time | `CONFLICT`, escalate | Conflict recall |

### 16.2 Metamorphic tests

Create pairs or triplets of inputs with a known invariant:

- **Paraphrase invariance:** same facts reworded should yield same policy outcome and gold citations.
- **Authorized-role invariance:** widening authorization may add visible evidence, but shouldn't retroactively make unauthorized prior answers valid.
- **Version monotonicity conditioned on as-of:** adding a future-effective version must **not** change a past event-time outcome when rules say event time governs.
- **Evidence addition:** adding a required valid clause should convert a justifiable abstention into an answer, not leave perpetual refusal.
- **Counterevidence addition:** adding an applicable exception should revise the answer or identify conflict, not keep prior confident claim unchanged.
- **Unrelated-document insertion:** adding thousands of independent unrelated records should not change gold facts; monitor retrieval degradation.
- **Doc title permutation:** changing a filename/title without changing immutable identity must not merge unrelated graph nodes or change authority.

Metamorphic invariants are stronger than repeatedly asking the same static QA: they isolate what a system *should* change its conclusion in response to.

### 16.3 Prompt injection and privacy specifics

Treat source documents, incoming customer text, tool results, graph descriptions and retrieved conversation history as untrusted content. Adversarial fixtures may contain instructions to leak a fake secret, skip the critic, forge policy approval, or write a global memory entry. Success requires **observable unauthorized behavior**, not simply an LLM paraphrasing the injection. Include Unicode homoglyphs, nested JSON, faux system-message formatting, and indirect injected URLs. Never use real secrets or real customer records.

---

## 17. Four worked fictional examples

### Case A — high cosine similarity, wrong effective version

A question asks whether a specific support action was allowed for a transaction on `2026-06-15`. SOP v4 approved on August 1 addresses the question most directly and ranks first, but the declared `transaction_time` policy requires v3 effective during June. The correct evidence bundle includes v3 and its exception clause; v4 may appear as historical/contextual contrast but cannot authorize the June action. **Score:** ordinary relevance may favor v4; temporal-valid source recall penalizes it.

### Case B — evidence completeness despite high precision

Seven of eight retrieved chunks are relevant to a settlement dispute, yet none contains the separately documented exception that excludes a certain merchant class. `Precision@8` is high while `CompleteSet@8 = 0`. If the agent recommends immediate reversal, count an unsupported operational directive. If the critic requests the exception and finds it before finalization, record a **critic repair**. If it does not, the expected outcome is partial explanation or abstention.

### Case C — two databases return different pieces of truth

SQLite's canonical registry identifies `MANUAL-22@v3` as the applicable approved manual. Qdrant finds its troubleshooting paragraph. Neo4j traverses an evidence-backed `REQUIRES` edge to `SETTLEMENT-SOP@v2` and returns the linked clause. The live adapter returns an `as_observed_at` transaction state. A valid answer must preserve *all* sources' distinct provenance; it must not cite the graph edge as though it were direct approval, or mistake an old live observation for current state.

### Case D — missing inventory and honest limits

The benchmark intentionally omits a relevant approved source from the supplied inventory. The user asks for a specific required step. None of the systems can prove the source does not exist somewhere outside the supplied collection. Correct output: “The accessible indexed documents do not sufficiently establish that step; here's what is known and the appropriate escalation.” Incorrect outputs include an invented final step or an absolute statement that “the company has no such policy.” **Score:** reason-specific abstention; not retrieval recall against an imaginary inaccessible source.

---
## 18. Benchmark repository: proposed file map and responsibilities

This is a **separate benchmark repository**, not a replacement for Palladion v0.2's application repository. It calls Palladion through an adapter and must not import Palladion's hidden evaluator/gold fixtures into retrieval. The tree below is an **implementation specification**, not a claim that these files already exist. Use Python 3.11+ where supported by the individual research repos; isolate incompatible comparators in pinned containers or subprocesses, rather than rewriting their algorithms.

```text
palladion-benchmark/
├── README.md                         # Overview, benchmark tracks, reproducibility
├── pyproject.toml                    # Python dependencies, lint/test commands
├── uv.lock                           # Pinned resolver lock for harness environment
├── .env.example                      # Safe config variable names, no real secrets
├── .gitignore                        # Exclude secrets, large corpora, build artifacts
├── Makefile                          # Development and benchmark entrypoints
├── docker-compose.yml                # Local Qdrant/Neo4j/mock live services
├── configs/
│   ├── benchmark.yaml               # Corpus snapshots, budgets, phases, seeds
│   ├── comparators.yaml             # Arm names, pinned external versions/options
│   ├── evaluation.yaml              # Metric definitions, gates, strata, CI settings
│   └── fixtures.yaml                # Synthetic world scale and distributions
├── benchmark/
│   ├── __init__.py                   # Package marker
│   ├── cli.py                        # Top-level CLI commands
│   ├── registry.py                   # Arm registration and capability declarations
│   ├── contracts.py                  # Typed request, candidate, trace, answer schemas
│   ├── run_manifest.py               # Immutable provenance and hash recorder
│   ├── runner.py                     # Paired, bounded, randomized run execution
│   ├── tracing.py                    # Span capture, retries, usage measurements
│   ├── fixtures/
│   │   ├── __init__.py               # Package marker
│   │   ├── world.py                  # Seeded canonical entities/policies/timelines
│   │   ├── documents.py              # Source artifacts and revisions renderer
│   │   ├── questions.py              # Query/episode stratification and partitions
│   │   ├── live_api.py               # Deterministic read-only operational mock
│   │   ├── manifest.py               # Corpus, ACL and immutable-ID manifests
│   │   └── validation.py             # Hidden-world, label, reference consistency
│   ├── adapters/
│   │   ├── __init__.py               # Package marker
│   │   ├── bm25.py                   # R0 lexical interface
│   │   ├── dense.py                  # R1 dense ANN interface
│   │   ├── hybrid.py                 # R2/R3 hybrid, fusion, reranker options
│   │   ├── hipporag2.py              # R4 official pipeline adapter
│   │   ├── graphrag.py               # R5 local; optional global distinct mode
│   │   ├── lightrag.py               # R6 official implementation adapter
│   │   ├── palladion.py              # R7 + E3/E4 external system adapter
│   │   ├── langchain.py              # E0 two-step reference implementation
│   │   ├── langgraph.py              # E1 bounded agentic implementation
│   │   └── google_adk.py             # E2 ADK/RAG Engine native capability adapter
│   ├── eval/
│   │   ├── __init__.py               # Package marker
│   │   ├── normalize.py              # Chunk-to-version-and-span alignment
│   │   ├── retrieval.py              # P@K, recall, MRR, nDCG, ANN checks
│   │   ├── evidence_sets.py          # Gold slot and complete-set matching
│   │   ├── citations.py              # Citation validity/entailment/accessibility
│   │   ├── policy.py                 # Temporal, precedence, action correctness
│   │   ├── abstention.py             # Selective prediction, reason labels
│   │   ├── memory.py                 # Packet fidelity, poisoning, cross-case isolation
│   │   ├── critic.py                 # Critic objections, repair/regression
│   │   ├── tool_use.py               # Tool choice, arguments, budgets and failures
│   │   ├── cost_latency.py           # Offline/online spend, latency quantiles
│   │   ├── statistics.py             # Paired bootstrap, CI, significance, calibration
│   │   └── judge_audit.py            # Blinded labeling and LLM-judge checks
│   └── analysis/
│       ├── __init__.py               # Package marker
│       ├── tables.py                 # Scorecards and pairwise effect tables
│       ├── plots.py                  # Risk-coverage and quality-cost Pareto figures
│       └── reports.py                # Versioned Markdown/HTML result summaries
├── scripts/
│   ├── generate_data.py              # Generate S/M/L synthetic fixtures
│   ├── build_indices.py             # Build/pin official baseline indexes
│   ├── run_track_a.py               # Retrieval-only evaluation runner
│   ├── run_track_b.py               # Shared-generator QA evaluation runner
│   ├── run_track_c.py               # End-to-end application runner
│   └── validate_results.py          # Schema, budget, leakage and hash checks
├── tests/
│   ├── test_fixture_integrity.py     # World/source/gold referential consistency
│   ├── test_adapter_contracts.py     # Compatible outputs and explicit unsupported
│   ├── test_span_alignment.py        # Accurate stable passage matching
│   ├── test_temporal_gold.py         # Policy-specific as-of rules and supersession
│   ├── test_acl_isolation.py         # Tenant and role isolation
│   ├── test_evidence_slots.py        # Alternative minimal evidence sets
│   ├── test_statistics.py            # Synthetic paired CI and estimator sanity
│   └── test_budget_enforcement.py    # Model/tool-call budget instrumentation
└── docs/
    ├── scoring_rubric.md             # Exact labeler rubrics and examples
    ├── annotation_guide.md           # Double-label, adjudication, blindness
    └── reproducibility.md            # Hardware/models/seeds/licensing checklist
```

**Repository specification count:** 70 planned files (56 Python and 14 configuration, documentation, and project files, including `Makefile`). This counts the shown file entries and excludes the generated `artifacts/` directories.

Keep actual generated data outside Git and refer to it by manifest IDs:

```text
artifacts/
  corpora/<snapshot>/              # Published documents, indexes, source hashes
  fixtures/<snapshot>/             # Generated world; protected evaluator-only gold
  runs/<run_id>/                   # Query traces, candidates, answers, usage
  reports/<run_id>/                # Scores, figures, confidence intervals
```

The benchmark should expose entrypoints such as:

```bash
make test
python scripts/generate_data.py --scale S --seed 7
python scripts/build_indices.py --snapshot smoke_007 --arms R0,R1,R2,R3,R7
python scripts/run_track_a.py --split dev --arms R0,R1,R2,R3,R7
python scripts/run_track_b.py --split dev --arms R2,R3,R7
python scripts/run_track_c.py --split dev --arms E0,E1,E3,E4
python scripts/validate_results.py --run-dir artifacts/runs/<run_id>
```

The CLI commands above are **proposed signatures**, not runnable commands until implemented. The benchmark does not require every competitor to be installed before running its smoke test; it should explicitly skip unavailable research/managed adapters and preserve a complete capability matrix.

### 18.1 Suggested `CaseResponse` contract

```json
{
  "question_id": "Q5-EXCEPT-101",
  "run_id": "run-e4-test-007",
  "answer_text": "The accessible evidence is incomplete; settlement state must be verified.",
  "evidence_status": "PARTIALLY_SUPPORTED",
  "claims": [
    {"id": "c1", "text": "The dispute SOP contains a settlement prerequisite.",
     "citations": ["SOP-DISPUTE@v3#4.2"]}
  ],
  "used_evidence_ids": ["SOP-DISPUTE@v3#4.2"],
  "tool_calls": [{"name": "search_knowledge", "status": "OK"}],
  "critic": {"enabled": true, "calls": 1, "objections": ["settlement unverified"]},
  "model_invocations": {"main": 2, "critic": 1},
  "latency_ms": null,
  "cost_usd": null,
  "abstention_reason": "MISSING_CASE_INPUT"
}
```

`null` values mean not observed or not applicable and must be flagged as such; never silently impute zero latency or zero cost. An individual claim with no citation may still be valid as nonfactual conversational framing, but any source-dependent operational claim requires verified evidence.

---

## 19. Practical execution plan, resources and deliverables

### 19.1 Minimum viable research (first meaningful comparison)

**Slice 1—fixture and label integrity:** Generate 1,200 coherent documents and 100 pilot questions spanning all strata. Implement canonical source version metadata, `SUPERSEDES`, typed graph gold, policy as-of test cases, and gold evidence slot graphs. First deliverable is an audited **dataset card** and gold label validation report. Do not introduce eight expensive research methods before this works.

**Slice 2—retrieval baselines:** R0 BM25, R1 dense, R2 hybrid RRF, R3 hybrid + cross-encoder, R7a Palladion minus graph. Run Track A and B on the pilot. Implement source-span normalization and log all citations. Confirm the results make sense on exact-ID and paraphrase cases; inspect failures manually.

**Slice 3—graph alternatives:** Add R7b Neo4j expansion, HippoRAG 2, Microsoft GraphRAG Local, and LightRAG, each version-pinned and ideally isolated in a container. Measure full ingestion/index costs from cold state. Only then increase corpus size to 12,000 documents and prepare locked test.

**Slice 4—end-to-end agent:** Mock policy evaluator and transaction/BI adapters; compare E0/E1/E3/E4, optionally E2. Run critic OFF/ON and memory variants. Isolate improvements due to policy tool or memory from improvements due to retrieval.

**Slice 5—confirmatory report:** Freeze configurations, execute 600 held-out single-turn questions plus 100 episodes, produce stratified scorecards, paired statistics, confidence calibration, security findings, and cost Pareto charts.

**Slice 6—scale/external replication:** Stress to 60k documents, try an alternative model generator, and evaluate against public enterprise benchmarks without using their public test answers for tuning.

These are logical milestones, **not delivery-time promises**. Run budget should be estimated empirically after Slice 1 rather than guessing money/time requirements.

### 19.2 Resource budget as variables

Let \(D\) be corpus tokens, \(Q\) test queries, \(r\) stochastic repetitions, \(M\) retrieval arms, \(A\) answering arms, \(c_e\) embedding price/token, \(c_x\) extraction price/token, \(c_g\) answer-generation price/token, and \(c_c\) critic price/token. Budget at least:

\[
C\approx D(c_e + c_x\cdot f_{\mathrm{graph}}) + Qr\bigl(Mc_{\mathrm{retrieval}} + A(c_{\mathrm{generator}}+c_{\mathrm{critic}})\bigr)+C_{\mathrm{hosting}}+C_{\mathrm{updates}}
\]

The symbols here represent cost components, not literal universal prices; graph extraction and context lengths can dominate. Capture actual token counts and provider bills in the pilot, then scale by estimated work units. Set a **spending cap**, API rate limits, test stop condition and failure retry ceiling before running 12k documents through multiple graph-index builders. Maintain separate plans for local compute and hosted APIs.

### 19.3 Final benchmark deliverables

- Frozen fictional corpus/source manifest, its creation code and an explicit dataset license.
- Gold evidence graph, adjudicated label sample, scenario split details and known caveats.
- Container/commit-pinned comparator adapters, reproducible per-arm configurations.
- Raw candidate lists, model/tool traces, citation resolution reports and error classifications.
- Tables for R0–R7, E0–E4 and ablations, with uncertainty intervals and counts.
- Aggregate cost/latency breakdown plus index ingestion/rebuild and dynamic-update costs.
- Separate sections for negative findings, unsupported native capabilities and fairness deviations.
- A dataset/benchmark card indicating clearly that fixtures are **not authentic company SOPs**.

### 19.4 Go/no-go interpretation

Continue Palladion as a distinct research direction if it demonstrates measurable improvement on **necessary evidence coverage or unsafe operational decision reduction** beyond R3/E3 at a tolerable cost and no unacceptable increase in false abstention, backed by independent held-out tests. If not, publish the failure honestly, simplify the architecture, or narrow the claim to the strata where it genuinely helps (e.g., temporal exception handling). A null result against a strong hybrid baseline is valuable.

---

## 20. Threats to validity and publication standards

**Synthetic realism:** A generated fictional world can be more internally consistent than real corporate knowledge and can have recognizable template artifacts. Report the source-type mix, artifact lengths, spelling noise, duplicate rates, conversation realism, and external comparisons. Include examples of accidental over-regularity and the controls used to detect it.

**Researcher advantage:** The benchmark is designed by Palladion's author; gold evidence taxonomy (especially source authority/temporal rules) may mirror Palladion's strengths. Mitigate by giving R3 the same canonical authority metadata in C2, using public external datasets, blinded annotation, and publishing generator code.

**Implementation inequality:** Authors may optimize Palladion heavily but leave official competitors at weak defaults. Report native configurations, time devoted to tuning, upstream commit hashes, fixed compute budgets, and failure causes. Where research models require different embeddings/extraction, report it rather than forcing a broken approximation.

**LLM judge bias:** An evaluator model may prefer a verbose answer or outputs from its own model family. Use deterministic rules for gold policy decisions, claim-level blinded human audits, multiple judge agreement, and expose judge prompts. Don't hide disagreements.

**Parametric knowledge contamination:** Public corpora may already be in foundation models' training sets; the invented payment world has less such leakage but is not a real deployment. Keep public benchmarks as supporting evidence.

**Data leakage and changing index:** If dev/test share a policy family, dataset generator prompt or metadata alias, cross-split performance can be optimistic. Versioned source IDs and grouped splits reduce the risk. In dynamic-index tests, distinguish search index staleness from policy time semantics.

**Provider capability asymmetry:** Google ADK orchestration, Google's managed RAG Engine, LangChain's standard RAG, HippoRAG, and Microsoft GraphRAG aren't interchangeable products. Publish two-layer tables separating raw retrieval effectiveness from native security, tooling, multi-turn behavior, pricing and operational burden.

**Rare harms and statistical limits:** Zero observed cross-tenant leaks or hallucinated high-risk instructions in hundreds of tests does not support a claim that probability is near zero. Use targeted larger suites and bounded claims.

**Benchmark overfitting:** Repeated inspection of locked test cases turns it into a development set. Freeze it, limit access, register primary comparisons, and generate a new test release for future iteration.

**Commercial and privacy constraints:** Validate licenses and cloud-service terms before distributing synthetic fixtures, reproduced research implementations or managed-service outputs. Do not include real business/customer data or actual financial transaction identifiers in an open benchmark.

### Suggested public write-up outline

1. Problem statement and architectural hypothesis.
2. Named baseline methods and native-versus-controlled comparison.
3. Synthetic data generator and gold evidence ontology.
4. Predeclared hypotheses, population, endpoints, power limitations.
5. Reproducibility and technical implementation details.
6. Retrieval-only results, controlled generation results, full system results.
7. Ablations and error attribution (what graph/critic/memory actually changed).
8. Safety-specific evidence: temporal failures, citation defects, correct abstention.
9. Economic analysis: indexing/updates/latency/cost Pareto fronts.
10. Negative findings, external replication, limitations, and future work.

---

## 21. Research register and implementation references

The following are starting-point sources checked during the drafting process. They establish available algorithms/datasets/tools and their stated capabilities; they **do not establish that Palladion outperforms them**. Capture access date and exact repository commit/version when implementation begins. Papers' headline results were measured on their own benchmarks, not on our fictional enterprise world.

### Retrieval algorithms and implementation

1. **HippoRAG 2 — From RAG to Memory (2025)**, official maintained repository, OSU NLP Group: <https://github.com/OSU-NLP-Group/HippoRAG>; paper <https://arxiv.org/abs/2502.14802>. Association-oriented memory retrieval and multi-hop capability.
2. **Microsoft GraphRAG — Local Search**, official docs: <https://microsoft.github.io/graphrag/query/local_search/>. Entity-linked local retrieval over extracted graph and text.
3. **Microsoft GraphRAG — Global Search**, official docs: <https://github.com/microsoft/graphrag/blob/main/docs/query/global_search.md>. Community reports and map–reduce synthesis for broad corpus questions; not equivalent to a local evidence search.
4. **LightRAG: Simple and Fast Retrieval-Augmented Generation**, Guo et al., Findings EMNLP 2025: <https://aclanthology.org/2025.findings-emnlp.568/>; upstream <https://github.com/HKUDS/LightRAG>. Dual-level graph/text retrieval and incremental knowledge integration.
5. **Qdrant Hybrid and Multi-Stage Queries**, official: <https://qdrant.tech/documentation/search/hybrid-queries/>. Native dense/sparse prefetch and RRF, with implementation-specific fusion constant/weights; do not assume conventional RRF k=60 without pinning.
6. **Qdrant Hybrid Search Tuning**, official: <https://qdrant.tech/documentation/search-tuning/hybrid-search/>. Distinct failure modes of dense and sparse retrieval.
7. **BEIR: A Heterogeneous Benchmark for Zero-Shot Evaluation of Information Retrieval Models**, Thakur et al., 2021: <https://arxiv.org/abs/2104.08663>. Motivates robust strong lexical and reranking controls.

### Enterprise and general RAG benchmarks

8. **EnterpriseRAG-Bench: A RAG Benchmark for Company Internal Knowledge**, Sun et al., 2026: <https://arxiv.org/abs/2605.05253>; dataset and generator <https://github.com/onyx-dot-app/EnterpriseRAG-Bench>. Approximately 500k synthetic documents and 500 questions spanning internal enterprise sources.
9. **EnterpriseRAG: Benchmarking LLM Instruction Adherence and Robustness under Non-Ideal Enterprise Retrieval**, Miao et al., 2026: <https://arxiv.org/abs/2608.11584>. Tests retrieval noise, evidence gaps, factual conflict and instruction adherence; dataset availability must be verified separately when running.
10. **Benchmarking Deep Search over Heterogeneous Enterprise Data**, Choubey et al., EMNLP Industry 2025: <https://aclanthology.org/2025.emnlp-industry.34/>; project <https://github.com/SalesforceAIResearch/HERB>. Multi-source, multi-hop enterprise tasks and answerability.
11. **Generating Q&A Benchmarks for RAG Evaluation in Enterprise Settings (DataMorgana)**, Filice et al., ACL Industry 2025: <https://aclanthology.org/2025.acl-industry.33/>. Question-type/diversity-controlled synthetic benchmark design.
12. **RAGBench: Explainable Benchmark for Retrieval-Augmented Generation Systems**, Friel et al., 2024: <https://arxiv.org/abs/2407.11005>; dataset <https://huggingface.co/datasets/rungalileo/ragbench>. Explainable evaluation and cross-domain corpora.
13. **WikiContradict**, Hou et al., 2024: <https://arxiv.org/abs/2406.13805>. A supplemental source for designing credible conflicting-passage tests.

### Frameworks, evaluation and managed retrieval

14. **LangChain documentation**, RAG and framework tutorials: <https://docs.langchain.com/oss/python/learn>. Define a concrete LangChain retriever/generator implementation; LangChain itself is not a retrieval ranking algorithm.
15. **Google ADK Knowledge Engine/RAG integration**, official: <https://adk.dev/integrations/vertex-ai-rag-engine/>. The documented retrieval tool has a **single-tool-per-agent limitation** for that integration; compare native limitations honestly and consider a documented workaround only as a separate arm.
16. **Google ADK Evaluation Criteria**, official: <https://adk.dev/evaluate/criteria/>. Tool trajectory, groundedness, response quality, inference calls, tokens, duration and multi-turn evaluations; use as supporting telemetry, not the independent gold standard.
17. **Google Agent Platform RAG Engine quotas**, official: <https://docs.cloud.google.com/gemini-enterprise-agent-platform/machine-learning/quotas>. Check current quotas and regional availability before allocating the managed arm.
18. **RAGAS**, project and metrics: <https://docs.ragas.io/>. Secondary faithfulness, relevance and context metrics; gold policy validity and source authority require our own tests.

---

## 22. Final preregistration checklist and execution decisions

Complete this checklist *before* the 600-case test. If a decision changes afterward, flag subsequent results exploratory.

- [ ] The **primary claim** is specific: more complete, applicable evidence and fewer unsupported operational directives—not “best RAG.”
- [ ] `R3` is frozen as the strongest practical hybrid+rerank challenger; `E3` is frozen as critic-off challenger.
- [ ] R0–R7 configurations and Google/GraphRAG global-only eligibility are documented, with official commits/versions.
- [ ] Comparison tracks A/B/C and C1/C2 source-authority conditions cannot be confused in results.
- [ ] Corpus S and M are generated from canonical hidden policy/world facts and audited for document/label equivalence.
- [ ] Test case families are split before rendering paraphrases; 600 single-turn test cases and 100 episodes are sealed.
- [ ] Every question has gold *minimal sufficient evidence sets*, applicable as-of basis, answerability category, and allowed outcome.
- [ ] ACL and approval metadata are authenticated fixture registry fields, not LLM-inferred document declarations.
- [ ] Version supersession is explicit, scoped and temporal; no “highest superseding score” shortcut.
- [ ] Source-span alignment does not create phantom native citations for baseline methods.
- [ ] Common generator, context budget, retry rules and principal/access conditions are fixed for Tracks A/B.
- [ ] Indexing cost, graph extraction, build errors and updates are measured for *all* relevant methods.
- [ ] Live API fixture states, authorization and freshness requirements are frozen for tool-comparable cases.
- [ ] Memory tests distinguish user-configured reported-fact validity from service-controlled live freshness.
- [ ] Main-agent <=5 calls including finalization; critic <=3; final evidence gate remains independent.
- [ ] Core metrics include `CompleteSet@K`, valid source recall, wrong-vintage rate, unsafe directives, citation validity, selective risk, false abstention, correct partial utility, p95, and total cost.
- [ ] Paired significance/CI method, multiple-comparison procedure, confidence calibration plan and minimum meaningful effects are preregistered.
- [ ] Severe failures and inconclusive results are visible; missing/unsupported runs are not disguised as zeros.
- [ ] All claimed external datasets and framework capabilities are verified at run time; provider rate limits and license terms are documented.
- [ ] Code, manifests, rubrics, prompts, seeds, traces and anonymized aggregate outcomes are archived for reproducibility.

### Closing research position

**Palladion should not win simply by making the comparison more complicated.** If a straightforward hybrid BM25+dense retriever with competent metadata filtering and a strict evidence gate is almost as reliable, faster, cheaper and easier to operate, that is the engineering answer. If the typed graph, policy-specific temporal execution, continuity state, and adversarial critic genuinely recover otherwise missing evidence and avert bad operational decisions, the experiments above are designed to locate, quantify and challenge that gain.

**The experimental asset is the gold evidence/authority/temporal world and controlled harness—not a headline accuracy score.** Once that is built correctly, it becomes possible to assess future retrievers, embedding models, reasoning agents and RAG frameworks without redesigning the entire experiment each time.
