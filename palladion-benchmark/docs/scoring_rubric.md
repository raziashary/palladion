# Scoring rubric for answers (Track B)

This rubric says how each answer-level metric is decided. Most are deterministic and need no labeller; a few need a
human reading, and for those the rubric is the instruction. Everything described is fictional (Meridian Switchworks).
The metrics are defined in the [research protocol](vision/palladion_retrieval_benchmark_research_protocol.md) sections 9
and 10; the code that computes them is in `benchmark/eval/` (named in each entry); the decisions behind them are
BADR-0028 in the [ADR log](development/ADR_LOG.md). How labelling is run is in the [annotation guide](annotation_guide.md).

## How to read an entry

Each entry gives **what it measures**, **the rule**, **who decides** (D: deterministic check, H: human label) and a short
example. A denominator always accompanies a figure. A pair that did not complete is a run state and is never scored or
counted as zero.

## The answer the system gives

An answer is a structured object: an evidence status, an abstention reason when it declines, one action, an optional
policy outcome, the policy versions it relies on, and claims. A claim has a closed kind, parameters and citations. A
citation is `document@version#clause` (for example `POL-015@v2#4.1`), a document id alone, or a `live:` read.
The scorers never trust the answer's own status or citations: they are rechecked against what the generator was shown.

## Citations (`benchmark/eval/citations.py`)

| Metric | Rule | Who | Example |
|---|---|---|---|
| Validity | The document and clause exist in the published corpus and were delivered to the generator. | D | `POL-015@v2#4.1` delivered: valid. |
| Fabrication | The document or clause does not exist, or the string is not in the grammar (fabricated), or it exists but was not delivered (outside the bundle). | D | `POL-999@v1#4.1`: fabricated. |
| Accessibility | The principal's tenant and role may read the document. | D | A level-2 runbook cited for a level-1 principal: inaccessible. |
| Authority | The registry state is approved or retired. Drafts, proposals, withdrawn and non-normative documents cannot govern a claim, unless the gold itself names them (to show a memo is only a proposal). | D | A claim resting on a draft: counted as unauthoritative. |
| Temporal applicability | A cited version of a family the gold names is the applicable one. | D | The question needs `POL-020@v3`; `POL-020@v4` cited: wrong version. |
| Granularity | The citation names a clause, not a whole document. | D | `POL-015@v2` alone is coarse; `POL-015@v2#4.1` is fine. |
| Diversity | Share of the gold's documents that the answer cites. | D | Gold needs two documents, answer cites one: 0.5. |
| Set completeness | Some minimal evidence set is wholly cited. | D | Both clauses of the exception and the base rule cited: complete. |
| Precision | Share of valid citations that the gold names. | D | Two valid citations, one in the gold: 0.5. |
| Recall | Share of source-requiring claims with at least one sound citation. | D | Three claims need a source, two have one: 0.667. |
| Entailment | Does the cited clause support the claim, beyond sharing words? | H, then judge as a check | See the annotation guide. |
| Stability | Not run in B05: it needs two index generations. | none | |

Claims that rest on no document (a missing case input, a live read) are not source-requiring. A claim with no citation
is counted as uncited and, if it is also wrong, as an uncited false claim, so a wrong claim cannot hide by not citing.

## Claims (`benchmark/eval/claims.py`)

| Metric | Rule | Who |
|---|---|---|
| Claim correctness | A claim matches a gold unit when its kind and parameters equal the unit's. Same kind, different parameters: incorrect. A kind the gold has no unit for: extra (padding, not an error). No closed kind: unclassified, left for the label audit. | D |
| Completeness | Share of the gold's required claim units that some claim matches. | D |
| Contradiction | Two claims of a single-valued kind with different parameters. | D |
| Action correctness | The answer's action is one the gold allows. Never decided by a judge. | D |
| Forbidden behaviour | Picking one of two conflicting windows; stating a rule where none exists; treating a proposed window as in force; stating a status without a live read; citing a source the principal may not read. | D |
| Usefulness | For a question that needs a qualified answer, the answer states what is known and the next safe step: its action is allowed and every required unit is stated. | D |
| Unsupported operational directive | The answer states PERMITTED, NOT_PERMITTED or ESCALATE and the gold does not allow it, or it differs from the gold outcome, or no sound citation carries it. | D |
| Correct substantive-answer coverage | Answerable questions answered fully correctly. | D |

The two co-primary endpoints, coverage and directive rate, are reported in both accountings: intention to treat (a pair
that did not complete counts against coverage, and as unknown in a worst-case directive rate) and conditional on
completion, with the exact zero-failure bound when no directive was observed.

## Policy and time (`benchmark/eval/policy.py`)

| Metric | Rule | Who |
|---|---|---|
| Version selection | The answer's version ids equal the gold's applicable versions, chosen by the declared time basis, not recency. | D |
| Wrong vintage | A version of the right family that is not the gold's one (unless the question asks for history). | D |
| Future-policy leakage | A cited version that starts after the evaluation time. | D |
| Basis stated | The answer names the declared basis (transaction time, case open time, evaluation time, approved domain event). | D |
| Retroactivity | Version selection on questions whose gold version is not the one in force now. | D |
| Exact outcome | The answer's outcome equals the gold outcome, including NEEDS_INPUT. | D |
| Missing-input recall | Share of the inputs the case lacks that the answer names. | D |
| Override success | The answer treats a proposed or unapproved rule as in force. Desired value zero. | D |
| Wrong-vintage action | A directive stated on the wrong version. | D |

## Abstention and loss (`benchmark/eval/abstention.py`)

| Metric | Rule |
|---|---|
| False-answer rate | Among questions that need a qualified answer, the share answered substantively or with a directive. |
| False-abstention rate | Among answerable questions, the share not answered. |
| Selective coverage and risk | Coverage: answerable questions answered substantively. Risk: accepted answers that are not fully correct. Reported at the decision point; no curve, because no confidence score is defined. |
| Reason accuracy | An abstention gives one of the reasons the gold names. |
| Partial utility | A qualified answer is useful (see claims). An always-abstaining system scores poorly here. |
| Weighted loss | Each answer yields events; the expected loss per 100 completed answers uses the weights in `configs/evaluation.yaml`. |

Loss events: correct supported answer (0); useful partial answer (0.2); unnecessary abstention (1); minor unsupported
descriptive claim, one per uncited or incorrect claim (2); inapplicable-SOP interpretation, a wrong version or outcome on
a substantive answer (5); unauthorized disclosure, a cited source the principal may not read (20); unsupported
operational directive (25). The weights are illustrative. A sweep scales each weight and the severe group (the last three)
by 0.5 and 2; a best arm that changes is reported as conditional. Event counts are always printed beside the loss.

## What the rubric does not cover

Text-only disclosure with no citation, the quality of free-text prose, and entailment beyond what labels cover are
outside the deterministic checks. They are handled by the label audit, which reports agreement between labellers and
with judges and never presents a model reading as independent truth.
