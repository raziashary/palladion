# How well does Palladion find evidence? The benchmark report

This is a plain-language report of the Palladion benchmark: what was tested, how Palladion compares with other
ways of searching and answering, what changed while we improved it, and what is still to do. It is written for
people who were not in the room. Technical detail lives in the linked files; the numbers here come from them.

**Status: a private, exploratory comparison. It is not a sealed experiment.** Nothing here says one system is
"better" than another. Where two numbers are close, they are not distinguishable. All data is fictional (an
invented payments company called Meridian Switchworks). Last updated 2026-10-28, and it will keep growing as the
benchmark runs.

## 1. What Palladion is, and what the benchmark asks

Palladion is a system that answers support questions from company documents and **shows the exact evidence
behind every claim**, refusing to answer when the evidence is not good enough. Its first job, before any
answering, is to **find the right documents**: the version of the policy that applied at the time, the document
the person is allowed to see, the rule and its exception. The benchmark measures that job against other,
well-known ways of searching, and then measures answering.

## 2. Who is being compared (plain names)

The benchmark's files use short codes (R0, R1, ... E4). This report uses names.

| Plain name | What it does | Code in the files |
|---|---|---|
| **Keyword search** | Finds documents sharing the question's words (the classic BM25 method). Very fast. | R0 |
| **Meaning search** | Turns text into numbers that capture meaning and finds the closest documents. | R1 |
| **Keyword + meaning** | Runs both searches and merges the two lists. | R2 |
| **Keyword + meaning + re-reader** | The merged list, then a second model re-reads the top candidates and re-orders them. This is the strong, common baseline. | R3 |
| **Palladion's retriever** | Palladion's own search: keyword + meaning + re-reader, plus checks of approval, version, validity dates and who may see what. | R7a (also called "Palladion retriever without graph") |
| **Graph-based searchers** (HippoRAG 2, GraphRAG, LightRAG) | Build a web of linked facts first. Planned; not yet measured (see section 7). | R4, R5, R6 |
| **Plain LangChain** | A popular toolkit's simple "search, then answer" pipeline. | E0 |
| **LangGraph agent** | The same toolkit's agent that decides its own steps. | E1 |
| **Palladion without its critic** | The whole Palladion agent with its second-opinion step switched off. | E3 |
| **Full Palladion** | The whole Palladion agent, critic on. | E4 |

## 3. What kinds of questions

There are 100 trial questions across ten types. The types are the codes Q1 to Q10 in the files; Q7 and Q9 do not
apply to the "finding documents" test, so they have no scores in section 4.

| Type | Plain meaning |
|---|---|
| Q1 | Look up an exact code, rule number or rare term |
| Q2 | Same meaning in different words, including Indonesian and English |
| Q3 | The answer needs several documents together |
| Q4 | Which version of a policy applied at a given time |
| Q5 | A rule with exceptions and conditions |
| Q6 | Two official sources disagree |
| Q7 | The documents do not contain the answer (the right move is to say so) |
| Q8 | Who is allowed to see what, and fake "approved" stamps |
| Q9 | The answer depends on live system status |
| Q10 | A broad summary across many documents |

## 4. Test A: finding the right documents (latest results)

For each question, the system returns its ten best documents. We ask: did it find **every** document needed
(the "complete set"), and what share of the **needed** documents did it find?

Latest run: Palladion commit `49b25cb`, 72 scored questions, every system saw the same 1,200 documents, no model
was used in the search arms. Condition "C2": Palladion enforces its own per-person access lists, the other
systems use a simple shared filter. A second run with everyone given the same simple filter ("C1") is listed
under the table.

| System | Questions where **all** needed documents were found (of 72) | Share of needed documents found | How fast (typical search) |
|---|---|---|---|
| **Palladion's retriever** | **13 (18%)** | **27%** | 1.8 seconds |
| Keyword search | 12 (17%) | 29% | 0.01 seconds |
| Keyword + meaning + re-reader | 6 (8%) | 19% | 1.3 seconds |
| Keyword + meaning | 4 (6%) | 14% | 0.04 seconds |
| Meaning search | 1 (1%) | 4% | 0.03 seconds |

How to read this: **Palladion's retriever and plain keyword search are about level on finding the full set, and
both are ahead of the strong hybrid baseline, but the uncertainty ranges overlap**, so with 72 questions we
cannot say one is better. The size of the gap to the strong baseline (13 against 6 questions) is real in this run
but small in absolute terms: most systems find the complete set for fewer than one question in five. Finding the
right documents for these questions is hard for every method tested, including Palladion.

**Where Palladion is clearly different: avoiding the wrong kind of document.** Share of questions where the
returned ten included at least one:

| System | An **out-of-date or wrong version** of the right document | An **unapproved or non-governing** document (draft, withdrawn) | A document the person **may not see** |
|---|---|---|---|
| **Palladion's retriever** | **4.5%** | **0%** | 0% |
| Keyword search | 39% | 20% | 0% |
| Meaning search | 8% | 29% | 0% |
| Keyword + meaning | 31% | 21% | 0% |
| Keyword + meaning + re-reader | 31% | 22% | 0% |

The other systems index every document and ignore approval state and validity dates; Palladion checks them. So
this table compares **different capabilities, not equal effort**. It is also the clearest thing Palladion does
that plain search does not.

**Where Palladion is weak.** Looking up an exact code or rule number (Q1): keyword search finds the complete set
for 8 of 10 questions, Palladion for 3 of 10. This is the question type where a plain keyword engine is hard to
beat, and Palladion has an exact-identifier path that is not yet doing its job here. Conflicting sources (Q6) and
access control (Q8) are not found by any system (0 of 10 and 0 of 5 for Palladion); Q6's best score is the strong
baseline at 4 of 10. Broad summaries (Q10) are found by none (0 of 7).

By question type, questions where **all** needed documents were found (out of 10 unless noted):

| Type | Palladion | Keyword | Meaning | Keyword + meaning | + re-reader |
|---|---|---|---|---|---|
| Q1 exact codes | 3 | 8 | 1 | 2 | 2 |
| Q2 different words | 2 | 1 | 0 | 0 | 0 |
| Q3 several documents | 3 | 0 | 0 | 0 | 0 |
| Q4 which version | 2 | 0 | 0 | 0 | 0 |
| Q5 exceptions | 3 | 1 | 0 | 0 | 0 |
| Q6 conflicts | 0 | 2 | 0 | 2 | 4 |
| Q8 access (of 5) | 0 | 0 | 0 | 0 | 0 |
| Q10 summaries (of 7) | 0 | 0 | 0 | 0 | 0 |

Each cell is one to a handful of questions, so single cells are noise; the pattern (Palladion ahead on version,
exception, multi-document and paraphrase questions; behind on exact codes and conflicts) is the useful part.

**Second run, "C1": the same documents with no access or approval information given to anyone.** Here nobody
is told who may see what, so this measures raw finding power. Palladion's retriever found the complete set for
**11 of 72** questions (15%) and 25% of needed documents; keyword search 9 of 72 (12.5%) and 24%; the strong
baseline 6 (8%) and 17%; keyword + meaning 4 and 13%; meaning search 1 and 3%. The pattern is the same as above:
Palladion and keyword search level, both ahead of the other three, with overlapping ranges (Palladion minus the
strong baseline: +7 percentage points on the complete set, range -7 to +18). Because no access rules apply in
this run, **every system showed documents the person should not see in 54% to 74% of questions, Palladion
included (61%)**. That is expected for this condition and is not a finding about Palladion's access control; the
access-control result is the C2 table above (0% for all systems there, where the rules were applied). Palladion
still avoided drafts and unapproved documents (0%) and old versions (4.5%) in this run, while the others returned
old versions in 3% to 33% and unapproved material in 18% to 30% of questions.

## 5. How Palladion changed during this work

The first measurement (Palladion at an earlier commit) was poor: Palladion found the complete set for 2 questions
of 72, and was slow. We read Palladion's code for the reasons and fixed what was wrong. These are the fixes
that mattered:

* It was **throwing away or burying the right documents**: banners and bare headings became their own tiny
  pieces and crowded the results; the document that defines a term sat behind tickets that merely cited it; the
  "as of this date" rule was not always applied; a document could stop being searchable while a newer version
  was still being prepared.
* It was **slow** because every search did a full health audit of the index (about a third of the time) and the
  re-reading model used too many or too few processor threads.
* It **split small policy sections into tiny pieces**, so a question about a version found the right policy but
  the wrong part. Now neighbouring small sections share one piece of up to 600 characters.

| Palladion at | Found the full set | Share of needed documents found | Version questions (Q4) | Typical search time (as the benchmark sees it) |
|---|---|---|---|---|
| First measurement | 2 of 72 | 4% | 0 of 10 | 1.9 s |
| After correctness fixes and faster audit | 9 of 72 | 22% | 0 of 10 | 1.6 s |
| After packing small sections (1,200 characters) | 13 of 72 | 27% | 5 of 10 | 2.2 s |
| **Now (600 characters, faster re-reader, count fix)** | **13 of 72** | **27%** | **2 of 10** | **1.8 s** |

Honest reading: the largest gains came from correctness fixes; packing small sections raised quality again but
makes the re-reader slower (it reads longer pieces). We chose 600 characters over 1,200 because the shorter
choice kept most of the gain without lowering any question type, but we chose it after seeing the 1,200 result,
so that comparison is exploratory. We also found and fixed a slowdown we had introduced ourselves (a
bookkeeping query that went from 25 thousandths of a second to almost a second). The machine is shared with other
programs, and the same code measured 2.3 s and 1.5 s in two separate timing runs of the search itself, so differences smaller than about 1.5 times
between single runs cannot be told apart. Details: `palladion/docs/development/EVIDENCE_LOG.md`, entry E-P11-002.

## 6. Test B: answering the questions, and Test C: whole systems

**Test B (every system's search results are given to the same answering model).** Run earlier, at an older
Palladion version, on 40 questions. The headline: **almost no system answered a question completely correctly.**
Of the 31 questions with a checkable answer, the best systems had 2 right; Palladion's retriever had 0, the
others 1 or 2. The share of answers that stated an action the evidence did not support was about 28% to 40% for
every system, with no real difference between them. The answers are limited by what the answering model does with
the evidence, not only by what was retrieved. These results are **older than the current Palladion** and have to
be re-run (needs a day's model quota); until then they should not be used to judge the current retriever.

**Test C (the whole systems with an agent).** Run only partly because of daily model limits: the plain
LangChain pipeline answered 15 of 16 turns, the LangGraph agent was mostly blocked by the daily limit, and
Palladion's agent answered 3 of 8 turns in an earlier trial. None of this supports a comparison yet.

## 7. What has not been done

* **Graph systems** (HippoRAG 2, GraphRAG, LightRAG): built and tested offline, but one partial live trial only.
  No measured result. They are on hold until quota allows.
* **Google's managed system**: no access, not run.
* **Palladion with graph links**: not supported by the benchmark yet.
* **The sealed, confirmatory run**: never run. This benchmark is exploratory, uses one small document set
  (1,200 documents, 100 questions of which 97 are scored), and the answer labels were produced by the benchmark's
  author, not an independent reader.
* **Test B and Test C at the current Palladion**, when the model quota allows (the daily limit renews about
  2026-10-28 12:35 UTC).

## 8. Progress

| Piece | State |
|---|---|
| Harness, fictional dataset, scoring rules and statistics | Built and tested |
| Test A (finding documents), all search systems and Palladion | Run, current Palladion measured (section 4) |
| Palladion improvements (correctness, speed, packing) | Done, measured, 605 automated tests pass |
| Test B (answering) | Run once on an older Palladion; re-run pending |
| Test C (whole systems) | Partly run; needs model quota |
| Graph systems | Built; not measured |
| Final publication package (licence, dataset card, reproducibility) | Not done |

## 9. Limits, so nobody over-reads this

* One small, invented document set; results may not carry to real company data.
* Single runs, one machine shared with other programs; timings move by up to 1.5 times between runs.
* The 72 questions give wide uncertainty; the ranges for Palladion, keyword search and the strong baseline overlap.
* Palladion was changed by the same people who wrote the benchmark; the improvements were driven by what the
  benchmark showed, so the "now" numbers are not an independent test. No tuning to specific question wording was done.
* Every system is measured the same way, but Palladion also does checks the others do not, so some comparisons
  compare capabilities, not just search quality.

## 10. Where the raw material is

* Latest numbers and tables: `palladion-benchmark/artifacts/runs/p11e-report-c2/report.md`
* Full records of every run, decisions and evidence: `palladion-benchmark/docs/development/`
* Palladion's change records: `palladion/docs/development/ADR_LOG.md` and `EVIDENCE_LOG.md`
* The benchmark's design: `palladion-benchmark/docs/vision/palladion_retrieval_benchmark_research_protocol.md`
