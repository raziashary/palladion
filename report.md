# How well does Palladion find evidence? The benchmark report

This is a plain-language report of the Palladion benchmark: what was tested, how Palladion compares with other
ways of searching and answering, what changed while we improved it, and what is still to do. It is written for
people who were not in the room. Technical detail lives in the linked files; the numbers here come from them. How
the system itself works is in [architecture.md](architecture.md).

**Status: the document-finding comparison now has a sealed run on new questions (section 4.1); everything else is
still exploratory.** Where two numbers are close, they are not distinguishable. All data is fictional (an invented
payments company called Meridian Switchworks). Last updated 2026-10-29, and it will keep growing as the benchmark
runs.

> **Read this first.** Two kinds of result are in this report. Section 4.1 is a **sealed run on six new worlds**:
> the systems were tuned equally on separate worlds, the way of judging was written down and hashed first, and the
> questions were not looked at one by one. Section 4.2 and section 5 describe the **earlier work on the first 72
> questions**, which is "in-sample": Palladion was improved after seeing those questions' results and measured on
> them again, and the other systems were not tuned. Trust 4.1 for the size of Palladion's lead; read 4.2 as a
> history of how Palladion changed.

## 1. What Palladion is, and what the benchmark asks

Palladion is a system that answers support questions from company documents and **shows the exact evidence
behind every claim**, refusing to answer when the evidence is not good enough. Its first job, before any
answering, is to **find the right documents**: the version of the policy that applied at the time, the document
the person is allowed to see, the rule and its exception. The benchmark measures that job against other,
well-known ways of searching, and then measures answering.

### How this differs from a normal RAG system

A normal RAG system finds the passages most similar to the question and lets a language model write the answer, so
whatever the search returns is trusted. Palladion treats the model as untrusted:

* a found document is only a *candidate* until it is re-checked: approved, readable by this person, valid at the case's
  time, not replaced, and still identical to the original file;
* the *version* of a policy that applies is chosen by plain code from a date the policy names, and two valid versions
  with no recorded precedence are reported as a conflict instead of guessed;
* *live facts* (a transaction's status) carry their own times and freshness limits;
* every released claim is re-checked against its evidence, and an operational answer always asks for human review;
* "I cannot verify this" is a normal, specific answer.

The longer comparison is in [architecture.md](architecture.md) (sections 8 and 10), with worked examples in section 9.

### What this benchmark can and cannot say about that

The benchmark's first test (Test A below) only asks whether a *search* finds the right documents. So it can speak to the
first bullet above, and, in section 4, to Palladion's checks of version, approval and access. It cannot yet speak to
the policy engine, the critic or the release gate: those act when the system answers (Tests B and C), which have not
been re-run on the current Palladion. A good search score does not show that answers are more trustworthy.

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

### The eight questions the benchmark is built around

The benchmark's design (its "research protocol") states eight hypotheses, H1 to H8. None has a confirmatory result.
Here is each one in plain words and what exists so far:

| | The question | What exists so far |
|---|---|---|
| H1 | Does Palladion find complete, applicable evidence better, especially for several documents, exceptions and replaced versions? | Test A, exploratory and in-sample (section 4). Not confirmed |
| H2 | Do the source checks and deterministic policy engine reduce unsupported advice to act? | Test B on an older Palladion: no difference seen between systems. To be re-run |
| H3 | Does the critic catch missing preconditions that the gate alone misses? | Palladion's own small paired pilot: neutral. Not measured by the benchmark |
| H4 | Does the graph add enough to justify its cost? | Palladion's own pilot: no extra recoveries (graph stays off). The benchmark's graph systems are not measured |
| H5 | Does the continuity packet reduce drift across turns? | Not measured |
| H6 | Does choosing the policy version by time prevent wrong-version decisions? | Test A shows version questions are still hard for search (2 of 10); the policy engine itself is not in Test A. Not measured |
| H7 | Can the extra checks cut unsupported claims without refusing too many answerable questions? | Not measured |
| H8 | How do accuracy, safety, cost and slow responses scale? | Search time is measured (section 4); cost at scale is not |

## 3. What kinds of questions

There are 100 trial questions across ten types. The types are the codes Q1 to Q10 in the files; Q7 and Q9 do not
apply to the "finding documents" test, so they have no scores in section 4.

| Type | Plain meaning |
|---|---|
| Q1 | Look up an exact code, rule number or rare term (including "according to POL-001 version 1") |
| Q2 | Same meaning in different words, including Indonesian and English |
| Q3 | The answer needs several documents together |
| Q4 | Which version of a policy applied at a given time |
| Q5 | A rule with exceptions and conditions |
| Q6 | Two official sources disagree |
| Q7 | The documents do not contain the answer (the right move is to say so) |
| Q8 | Who is allowed to see what, and fake "approved" stamps |
| Q9 | The answer depends on live system status |
| Q10 | A broad summary across many documents |

## 4. Test A: finding the right documents

For each question, the system returns its ten best documents. We ask: did it find **every** document needed
(the "complete set"), and what share of the **needed** documents did it find?

### 4.1 The sealed run on six new worlds (the result that counts)

How it was done, in order: (1) six new fictional worlds were generated with new random seeds, 1,200 documents and
100 questions each; (2) two other worlds were used to **tune every system the same amount** (a baseline run and at
most six one-change trials each, the best kept only if it clearly helped); (3) the way of judging was written down
(the main comparison, the smallest gain that would count, how to handle the many comparisons) and the new worlds,
the settings and the code were **hashed into a seal**; (4) the systems were run, three times each for the main
condition and once for the other, and scored by a program that prints only totals, so nobody tuned on the sealed
questions. Palladion is the commit `caebd53`. No answering model is used in the search arms (they use small pre-trained search models only). Condition "C2": Palladion
enforces its own per-person access lists, the other systems use a simple shared filter. 600 questions were asked and
446 test document-finding.

| System | Questions where **all** needed documents were found | Share of needed documents found |
|---|---|---|
| **Palladion's retriever** | **39.9%** | **49.5%** |
| Strong baseline plus Palladion's approval-and-date rule | 26.9% | 33.2% |
| Keyword + meaning | 24.7% | 29.4% |
| Strong common baseline (keyword + meaning + re-reader) | 22.6% | 28.4% |
| Keyword + exact-code rule | 22.4% | 29.9% |
| Keyword search | 22.2% | 29.7% |
| Meaning search | 13.2% | 19.2% |

**The check written down beforehand: Palladion minus the strong baseline is +17 percentage points, range +12 to
+23; the bar was +5, so it passed.** Against the three other comparisons: keyword search +18 (range +13 to +22),
keyword with the exact-code rule +18 (+13 to +22), and the strong baseline with Palladion's own approval-and-date
rule +13 (+7 to +19). The range covers 95% of what chance would give when questions about the same document family
are counted as one cluster.

What explains the lead? Part of it is a rule any system could apply: only look at documents that are approved and
valid at the time of the question, and treat a named version (like POL-001@v1) as asking for exactly that version.
Adding that rule to the strong baseline lifts it from 22.6% to 26.9%. The rest of the lead, 13 points, is the rest
of Palladion's design (how it cuts documents into pieces, how it finds an exact code, and how it orders results).

By question type, questions where all needed documents were found (60 each unless stated):

| Type | Palladion | Strong baseline | Baseline + rule | Keyword | Keyword + code rule |
|---|---|---|---|---|---|
| Q1 exact codes | **100%** | 38% | 40% | 67% | 68% |
| Q2 different words | **45%** | 32% | 35% | 15% | 15% |
| Q3 several documents | **37%** | 3% | 3% | 2% | 2% |
| Q4 which version | 20% | 27% | **45%** | 13% | 13% |
| Q5 exceptions | **43%** | 20% | 15% | 42% | 42% |
| Q6 conflicts | 52% | 48% | **62%** | 27% | 27% |
| Q8 access (26 questions) | 0% | 0% | 0% | 0% | 0% |
| Q10 summaries | 0% | 0% | 0% | 0% | 0% |

Palladion's gain is concentrated in exact codes and several-document questions. It is **behind** on "which
version" and on conflicts, and no system finds the access and summary questions at all.

**Wrong kinds of document** (condition C2, share of questions whose ten results included at least one):
an out-of-date version of the right document: Palladion 0.3%, strong baseline plus rule 0.5%, the others 8% to 10%;
a document of unclear authority (a draft, a withdrawn one): Palladion 0%, baseline plus rule 0%, the others 10% to
15%; a document the person may not see: 0% for every system.

**Other condition, "C1": nobody is told who may see what.** Palladion 35.9% of questions complete, strong baseline
plus rule 25.6%, strong baseline 22.4%, keyword 20.9%, keyword + meaning 20.9%, meaning 11.4%. Because no access
rules apply here, every system shows some documents the person should not see; that is the condition, not a finding
about access control.

**Repeats.** Rebuilding Palladion from scratch and asking again gave the same ten documents in the same order for
92% (second run) and 95% (third run) of the questions; the other systems gave exactly the same lists every time.
The registered result is the first run and was not picked among the three.

**What this does not show.** It does not show that Palladion's *answers* are better (that is tests B and C). It
does not show that real people's questions behave like these: one generator wrote the documents, the questions and
the labels, and no human has checked the labels. It does not show that Palladion works on other document sets.
A test with questions reworded by a different model, and a test on public documents, are still to do.

### 4.2 The earlier run on the first 72 questions (in-sample, untuned baselines)

This is the run reported before the sealed one. It is kept for the history of how Palladion changed, not as the
size of its lead (see the box at the top).

Palladion commit `5acc825`, 72 scored questions, every system saw the same 1,200 documents.

| System | Questions where **all** needed documents were found (of 72) | Share of needed documents found | How fast (typical search) |
|---|---|---|---|
| **Palladion's retriever** | **22 (31%)** | **40%** | 1.0 second |
| Keyword search | 12 (17%) | 29% | 0.01 seconds |
| Keyword + meaning + re-reader | 6 (8%) | 19% | 0.7 seconds |
| Keyword + meaning | 4 (6%) | 14% | 0.04 seconds |
| Meaning search | 1 (1%) | 4% | 0.03 seconds |

How to read this: **in this run Palladion's retriever is clearly ahead of the strong baseline** (22 against 6
questions; the difference on the complete set is +22 percentage points, range +6 to +35, and it is unlikely to be
chance), and ahead of plain keyword search on the full set (22 against 12). But, again, this is in-sample (see the
box at the top), it is one run, and most systems still find the complete set for fewer than a third of the
questions.

**Second run, "C1": nobody is told who may see what or what is approved** (raw finding power):

| System | All needed documents found (of 72) | Share of needed documents found |
|---|---|---|
| **Palladion's retriever** | **21 (29%)** | **38%** |
| Keyword search | 9 (12%) | 24% |
| Keyword + meaning + re-reader | 7 (10%) | 19% |
| Keyword + meaning | 4 (6%) | 13% |
| Meaning search | 1 (1%) | 3% |

Same picture; Palladion minus the strong baseline is +19 percentage points on the complete set (range +3 to +32).
Because no access rules apply in this run, **every system showed documents the person should not see in 54% to 74%
of questions, Palladion included (66%)**. That is expected for this condition and is not a finding about
Palladion's access control; the access-control result is the C2 table (0% for all systems, where the rules were
applied).

**Where Palladion is clearly different: avoiding the wrong kind of document** (condition C2). Share of questions
where the returned ten included at least one:

| System | An **out-of-date or wrong version** of the right document | An **unapproved or non-governing** document (draft, withdrawn) | A document the person **may not see** |
|---|---|---|---|
| **Palladion's retriever** | **4.5%** | **0%** | 0% |
| Keyword search | 39% | 20% | 0% |
| Meaning search | 8% | 29% | 0% |
| Keyword + meaning | 31% | 21% | 0% |
| Keyword + meaning + re-reader | 33% | 26% | 0% |

The other systems index every document and ignore approval state and validity dates; Palladion checks them. So
this table compares **different capabilities, not equal effort**. It is also the clearest thing Palladion does
that plain search does not.

By question type, questions where **all** needed documents were found (out of 10 unless noted), condition C2:

| Type | Palladion | Keyword | Meaning | Keyword + meaning | + re-reader |
|---|---|---|---|---|---|
| Q1 exact codes | 10 | 8 | 1 | 2 | 2 |
| Q2 different words | 4 | 1 | 0 | 0 | 0 |
| Q3 several documents | 3 | 0 | 0 | 0 | 0 |
| Q4 which version | 2 | 0 | 0 | 0 | 0 |
| Q5 exceptions | 3 | 1 | 0 | 0 | 0 |
| Q6 conflicts | 0 | 2 | 0 | 2 | 4 |
| Q8 access (of 5) | 0 | 0 | 0 | 0 | 0 |
| Q10 summaries (of 7) | 0 | 0 | 0 | 0 | 0 |

Each cell is one to a handful of questions, so single cells are noise; the pattern is the useful part. Five of the
ten exact-code questions ask "According to POL-001@v1" about a *replaced* version; Palladion could not answer those
until it learned that syntax (section 5), so that column is the clearest example of an in-sample fix.

**Where Palladion is still weak:** two official sources that disagree (Q6: 0 of 10, the strong baseline gets 4),
who may see what (Q8: 0 of 5, no system finds these), and broad summaries (Q10: 0 of 7, no system does). Version
questions (Q4) improved from 0 to 2 of 10 and are still low.

## 5. How Palladion changed during this work

The first measurement (Palladion at an earlier commit) was poor: Palladion found the complete set for 2 questions
of 72, and was slow. We read Palladion's code for the reasons, probed what it actually returned stage by stage, and
fixed what was wrong. The fixes that mattered:

* It was **throwing away or burying the right documents**: banners and bare headings became their own tiny pieces
  and crowded the results; the document that defines a term sat behind tickets that merely cited it; the "as of
  this date" rule was not always applied; a document could stop being searchable while a newer version was still
  being prepared.
* It was **slow** because every search did a full health audit of the index (about a third of the time) and the
  re-reading model was set up badly.
* It **split small policy sections into tiny pieces**, so a question about a version found the right policy but the
  wrong part. Now neighbouring small sections share one piece of up to 600 characters.
* **Exact codes were weak.** A code that titles a section (such as "API note: MS-1817 response") was treated like
  one of the 24 documents that merely list it; the re-reader moved exact-code matches behind the rest; and the full
  stop at the end of a sentence was glued to the code, so "fails with code MS-1817." could not be found as MS-1817.
  Each is fixed.
* **A question can now name a version**, `POL-001@v2`, and is then answered by that version even if a newer one
  replaced it. The version must be written by the *user*, not by the model, and the numbering counts only versions
  the reader may see, so it cannot reveal a hidden one.
* The re-reader now reads 20 passages instead of 30: it found as much and was about a quarter faster.

| Palladion at | Found the full set | Share of needed documents found | Version questions (Q4) | Typical search time |
|---|---|---|---|---|
| First measurement | 2 of 72 | 4% | 0 of 10 | 1.9 s |
| After correctness fixes and faster audit | 9 of 72 | 22% | 0 of 10 | 1.6 s |
| After packing small sections (1,200 characters) | 13 of 72 | 27% | 5 of 10 | 2.2 s |
| With 600-character packing | 13 of 72 | 27% | 2 of 10 | 1.8 s |
| **Now (exact codes, named versions, 20 re-read passages)** | **22 of 72** | **40%** | **2 of 10** | **1.0 s** |

Honest reading: the largest gains came from correctness fixes; packing small sections raised quality again but made
the re-reader slower; the latest changes raised quality and, because the re-reader reads fewer passages and a
mistake of ours was fixed (a bookkeeping query that went from 25 thousandths of a second to almost a second), made
the search faster again. We chose 600 characters over 1,200, and 20 passages over 30, after seeing the numbers, so
those choices are exploratory. The machine is shared with other programs and the same code has measured 1.5 and
2.3 seconds in two runs, so differences smaller than about 1.5 times between single runs cannot be told apart.
Two independent reviewers (an AI model reading the code and the design document) found real defects in our changes,
including that the model could widen what is searched and that a version number revealed a hidden version; both are
fixed and tested. Details: `palladion/docs/development/EVIDENCE_LOG.md`, entries E-P11-001 to E-P11-003.

**Two speed ideas that were measured and not adopted.** A multilingual re-reader (BGE reranker v2 m3) roughly doubled
the number of complete sets on the benchmark's hybrid arm (6 to 12 of 72) but took 19 seconds a question on this
computer instead of 1.2, so it only makes sense on faster hardware. And a search started by the agent currently
starts a fresh process that needs 12 to 14 seconds to load its models before it can search at all; keeping one
process running would remove most of that, but it is a design decision that has not been made.

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
* **A sealed run for answering (tests B and C)**: not possible on the free model quota (it would take millions of
  tokens); those tests stay descriptive. The sealed run in section 4.1 covers document-finding only.
* **Test B at the current Palladion**: run on 2026-10-29, 196 of 200 question-and-system pairs are done (189 gave a
  valid answer and 7 gave an answer outside the required form); 4 pairs wait for the model quota and the
  result is not scored yet.
* **Test C for the full Palladion (E4)**: the first attempt is void, because a test run of mine stopped a shared
  service under it; it is re-run when the quota allows, and the other Palladion variant (E3) is not run yet.
* **Questions reworded by a different model, and public documents**: not done yet. The first needs a little model
  quota and has its own seal; the second needs permission to download named public datasets.
* **Labels checked by a person**: not done; the owner accepted the generator's labels in writing.
* **Keeping the search process running** (section 5) and **conflicts / access / summary questions**, where
  Palladion still scores 0.

## 8. Progress

| Piece | State |
|---|---|
| Harness, fictional dataset, scoring rules and statistics | Built and tested |
| Test A (finding documents), all search systems and Palladion | **Sealed run on six new worlds done (section 4.1)**; the earlier 72-question run is history (4.2) |
| Palladion improvements (correctness, speed, packing, exact codes, named versions) | Done, measured, reviewed; 645 automated tests pass |
| Test B (answering) | Run at the current Palladion: 196 of 200 pairs done, 4 wait for quota; not scored yet |
| Test C (whole systems) | Partly run; the first attempt at the full Palladion is void and will be re-run |
| Graph systems | Built; not measured |
| Final publication package (licence, dataset card, reproducibility) | Not done |
| Plain-language documentation (README, [architecture.md](architecture.md), this report) | Written; worked examples are reconstructions, not recorded runs |

## 9. Limits, so nobody over-reads this

* **In-sample, for the earlier run only.** The first 72 questions (section 4.2) were seen before Palladion was
  changed. The sealed run (section 4.1) was not.
* **One author.** One generator wrote the documents, the questions and the answer labels, and no human checked
  them; the sealed run cannot show that real questions behave the same way.
* One small, invented document set; results may not carry to real company data.
* Single runs, one machine shared with other programs; timings move by up to 1.5 times between runs.
* The 72 questions give wide uncertainty for most comparisons.
* Palladion was changed by the same people who wrote the benchmark; no tuning to specific question wording was
  done, but the fixes were driven by what the benchmark showed.
* Every system is measured the same way, but Palladion also does checks the others do not, so some comparisons
  compare capabilities, not just search quality.
* One load of Palladion's documents failed once with a server error ("HTTP 503") during the first C1 run at this
  commit; it was recorded, its cause is not established (the server log was not kept), and the run was repeated with
  the same code and succeeded. The failed run is kept as `p11g-a-c1` and is not part of any number above.

## 10. Where the raw material is

* The sealed result: `palladion-benchmark/docs/development/EVIDENCE_LOG.md` entry E-B08-013, the registered design in
  `palladion-benchmark/docs/development/PREREGISTRATION_TRACK_A.md`, and the aggregate cards
  `palladion-benchmark/artifacts/comparison/sealed-track-a-c2.md` and `-c1.md` (regenerable)
* The earlier run's tables: `palladion-benchmark/artifacts/runs/p11g-report-c2/report.md` (C2) and
  `p11h-report-c1/report.md` (C1)
* Full records of every run, decisions and evidence: `palladion-benchmark/docs/development/`
* Palladion's change records: `palladion/docs/development/ADR_LOG.md` and `EVIDENCE_LOG.md`
* How the system works: [architecture.md](architecture.md)
* The benchmark's design: `palladion-benchmark/docs/vision/palladion_retrieval_benchmark_research_protocol.md`
