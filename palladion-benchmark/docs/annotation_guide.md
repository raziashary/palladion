# Annotation guide for answer labels

This guide says how the labels that no deterministic check can give are made: whether a cited clause supports a claim,
whether an abstention is adequate, and whether a free-text statement discloses a source it should not. The rules for what
counts as correct are in the [scoring rubric](scoring_rubric.md). The fixture and the people in it are fictional
(Meridian Switchworks); the earlier question-label audit is in the [labelling guide](development/OWNER_LABELLING_GUIDE.md).
The decisions behind this guide are BADR-0028 in the [ADR log](development/ADR_LOG.md).

## What gets labelled

1. **Entailment.** For a claim and one cited clause: does the clause, read alone, support the claim? Answer `supported`
   or `not supported`. Sharing words is not support. A clause that states the window for another class, tenant or
   version does not support a claim about this one.
2. **Abstention adequacy.** For an answer that declines or qualifies: does it say what is known and name the next safe
   step (ask for the missing input, ask the policy owner, retry later, use another channel)? `adequate` or `not adequate`.
3. **Disclosure in text.** For an answer that does not cite a restricted source: does its text reveal restricted content
   or confirm that restricted content exists? `discloses` or `does not`.

Only the packet's fields are visible: an item id, the stratum, the claim and the cited text. The arm, the generator model
and any judge output are hidden.

## How the sample is drawn

A seeded sample takes the same number of items from each stratum (`sample_for_labelling` in
`benchmark/eval/judge_audit.py`). The packet carries an item id built from the seed, the question, the arm and the
claim; the key that maps ids back to arms is a separate file and stays closed until every label is in. The seed, the
sample size per stratum and the date are written into the evidence log with the run.

## Who labels, and how many

At least two labellers label every item independently. Today the labellers are the owner and the coordinator working under
the owner's delegation (BADR-0026); that is two readers of one project, not two independent humans, and every report says so.
Agreement is reported as Cohen's kappa for two labellers (Krippendorff's alpha when there are more) together with the number
of items compared and the raw agreement. It is never described as human against human unless it is.

## Adjudication

Where two labellers differ, a third pass settles the item against the rubric and the published clause text, not by
preferring either labeller. The adjudicated label, who settled it and the reason are recorded. A label made after seeing
another labeller's, a judge's or the system's label is marked as such and is not counted as independent.

## Judges as a second check

A language-model judge may be asked the entailment question as a secondary check. Rules: at least two judges; each is a
different model from the one that wrote the answer; any shared provider family is named in the report (the approved pool
has only two families, so a family-distinct pair of judges is not always possible); the prompt is the exposed text in
`judge_messages`; prompts and replies are kept outside the run directory. A judge's label is stored beside the others but
never becomes the standing label when a deterministic or human label exists, and it counts toward a score only after its
agreement with the human labels has been reported with the number of items compared. Judge calls need the owner's
authorization for live use; until then the procedure is exercised with injected replies only.

## Label precedence

Deterministic check, then human, then judge. `LabelStore` keeps every label and its source. The standing label is the
highest source's. Disagreements between sources are listed, counted by the pair of sources involved, and reported.

## What to do with a hard item

Choose the best-fitting label, note the item id and the reason, and move on. A hard item is useful: it may show a rule the
rubric does not yet state. Rubric changes made after labelling starts are recorded with the date, and items already
labelled under the old rule are listed.

## Reporting

For every label type: items sampled, items labelled by each labeller, agreement (statistic and raw), adjudications, judge
agreement per judge with its denominator, and disagreements by source pair. Figures from a model reading are labelled as
such and are never presented as independent ground truth.
