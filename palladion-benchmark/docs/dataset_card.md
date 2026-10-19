# Dataset card: Meridian Switchworks S-tier fixture

**Everything here is fictional.** Meridian Switchworks is an invented company. No document, procedure, merchant,
transaction or person in this fixture is real, and nothing in it is an actual operating procedure. Each generated
document begins with that notice.

## What it is

The S tier is the small pilot fixture of the Palladion benchmark ([protocol](vision/palladion_retrieval_benchmark_research_protocol.md)
section 4.2). It holds a published corpus of 1,200 documents and 100 pilot questions with evaluator-only gold. It exists to
check loaders, label validity, evidence identifiers and the harness interface. It is not a sample of any real company, and
no result on it supports a claim about Palladion or any comparator.

## Composition

The numbers below are written by `scripts/generate_data.py --write-card` from the fixture itself, and a test fails if the
card and the script disagree.

<!-- BEGIN GENERATED -->
| Measure | Value |
|---|---|
| Documents | 1,200 |
| Pilot questions | 100 (all smoke; none test) |
| Words (whitespace-separated), total / mean / median | 124,927 / 104.11 / 96.0 |
| Language share, tagged (en / id / mixed) | 55.0% / 30.0% / 15.0% |
| Language share, measured from text | 58.6% / 27.8% / 13.6% |
| Tagged and measured language agree | 87.7% |
| Document families / revisions | 115 / 285 |
| Near-duplicates, measured | 9.5% (114 documents) |
| Stale text, measured | 6.5% (78 documents) |
| Unapproved (draft or proposal), from registry state | 3.0% (36 documents) |
| Injection documents, measured | 1.5% (18 documents) |
| Graph degree mean / median / p95 / max | 2.139 / 2.0 / 4.0 / 12.0 |
| Identifier-free lexical solvability (ceiling 0.60) | 0.10 |
| Sentence-length variation (floor 0.25) | 0.48 |
| Skeleton diversity (floor 0.10) | 0.16 |
| Newest-version rule right on version questions (ceiling 0.30) | 0.00 |
| Oldest-version rule right on version questions (ceiling 0.60) | 0.50 |
| Corpus manifest SHA-256 | 4d14dfc45aa7c47e018220a0b6e9d6c89d9ed69b69c7feb60943024ecbd818ce |
| Questions SHA-256 | 216045d31196f3323d9a728243c1141b457138bb5178b2f33cf53125fe030cd5 |
| Snapshot id | snap-b491d64cb7a4665a |

Questions by stratum: Q1 10, Q10 10, Q2 10, Q3 10, Q4 10, Q5 10, Q6 10, Q7 10, Q8 10, Q9 10.
Questions by answerability: ANSWERABLE 67, BLOCKED_BY_ACL 5, CONFLICT 10, PARTIAL 2, UNANSWERABLE 10, VERIFICATION_UNAVAILABLE 6.
<!-- END GENERATED -->

## How it is made

A hidden world is generated first by code from a seed: tenants, roles, principals, merchants (some with the same display
name in different tenants under different identifiers), error codes, document families and dated versions, policies with
four as-of bases, typed graph edges, transaction timelines and case histories that keep user-reported facts apart from
verified ones. Documents are then rendered from that world by templates in English, Indonesian and code-mixed text. No language
model writes any text in this tier (BADR-0009); a constrained paraphrase step comes later and must pass the same
equivalence check. Gold is computed from the world's rules, with each cited span resolved from the rendered clause offsets.

Seed policy: each tier derives its own world seed from the base seed and the tier name, so tiers do not share a prefix of
generated families. The same base seed gives byte-identical manifests in any process, time zone or working directory.

```powershell
cd palladion-benchmark
uv run python scripts/generate_data.py --tier S --out artifacts/fixtures/S
```

## Information barrier

The output has four physically separate directories: `generator` (hidden world and generator tags), `published` (documents and
three manifests an arm may index), `annotations_dev` (smoke and dev gold) and `annotations_test` (locked test gold, empty
in this tier). A scan of the published tree finds no gold vocabulary, split word or question identifier. Question
identifiers are keyed-hash pseudonyms, file names are hashes, and manifest order is shuffled independently of generation
order. The generator tags (which document is a planted near-duplicate, stale, unapproved or an injection) stay in the
generator directory.

## Noise and planted ambiguity

Planted noise is reported from the documents themselves, not from the generator's tags (BADR-0021). Planted ambiguity
includes product aliases, same-named merchants in different tenants, policy exceptions kept in separate documents,
circular-looking references, long tables, transitive runbook prerequisites, late approvals, retroactive clauses, withdrawn
versions, drafts that claim board approval in their body, and two equally approved policies that disagree.

## Limits and known threats

- **Template-first text is easier than real text.** Equivalent facts reappear in a small set of phrasings. Realism checks
  (BADR-0022) only guard against an obviously searchable or over-regular fixture; they do not show that the text is realistic.
- **The author of the benchmark also builds Palladion.** The taxonomy of versions, authority and negatives may favour a
  system that models them. The text-only condition carries a consistent header and no structured result; the
  evidence-governed condition adds the same authority metadata for every arm.
- **Few scenario families.** The S tier has about 20 independent policy families, so several questions share a family.
  The effective sample size is the family count, not 100. Paraphrases of one case stay together in one split.
- **Pilot questions are all smoke.** No S-tier question is a test question, and pilot results are excluded from held-out claims.
- **Language is partly heuristic.** The tagged language is exact by construction; the measured language uses stopword
  counts and is shown beside it.
- **Global synthesis spans families.** Questions that ask for every matching policy cite clauses from several families.
- **The M tier is not yet buildable.** The vocabulary offers 240 distinct policy scopes and the M composition needs more;
  extending it is a B08 task.
- **The published manifest is the ingest list.** It names every document with its title and access list, as an indexer would see
  them; access is enforced at retrieval. A system that answers as a restricted principal must not reveal what the manifest lists
  (question stratum Q8 scores that), and an arm must not hand the manifest to its generator.
- **Pilot question identifiers are recomputable.** They are keyed by an empty secret by default, so anyone with the base seed can
  derive the stratum and split of an identifier. That is acceptable only because no pilot question is a test question; the locked
  split must be built with a private secret before the seal (B08-T03.01).
- **Some seeds are refused.** A generated world may not have enough usable policy families for ten version questions; the
  generator then stops instead of lowering a gate (base seed 8 is an example; seeds 7 and 9 to 12 build).
- **Tickets state past verified facts.** A ticket records what support verified when it was written. Live-status questions avoid
  every transaction that a ticket describes, so a document cannot answer them.
- **License:** not yet chosen (open question OQ09, due before publication).

## Label audit

**Status: the model pass on the final fixture is done; the owner's labels are pending (B02-T07.02 is open).** The design is BADR-0019. A seeded sample of 30
pilot questions (3 per stratum, covering each answerability value present in the stratum) is shown without gold to the owner
and to a blinded language-model pass. Agreement is owner against model and each against the gold; it is not human against
human, and neither reader is independent of the templates. The model sees the question, the principal, the live read
if any, and the best-matching documents (four the principal may see and two it may not, marked as such), but it cannot search
the corpus.

Results so far, with denominators (details in the evidence log). The first two model passes ran on an **earlier build** of this fixture:
the post-phase audit then changed the world (policy precedence by scope specificity) and the question generator, so
those labels no longer belong to the shipped questions and were archived, not reused.

| Pass | Calls | Agreement with gold (earlier build) |
|---|---:|---|
| Model, first prompt (documents cut at 600 characters, so rule clauses were missing) | 36 | 7 of 30 (23%) |
| Model, second prompt (documents cut at 900 characters) | 37 | 12 of 30 (40%) |
| Model, final fixture, prompt `excerpt-v1` | 36 | 17 of 30 (57%) |
| Owner | 0 | pending |

On the final fixture, the gold's cited documents were among the model's documents for only 1 of the 23 questions that have cited
evidence (the model agreed there); on the earlier build it was 2 of 23. So the low agreement mostly reflects what the model was shown, not a measured defect in the
gold, and it does not show the gold is right. The two prompts used a fixed-length document prefix; the current code selects the
informative lines instead (`excerpt-v1`) and cannot reproduce them. The owner's pass, who can search all 1,200 documents, is the real check.

### How the owner labels

The step-by-step version is in [the owner's labelling guide](development/OWNER_LABELLING_GUIDE.md); the summary follows.

All files are under `artifacts/fixtures/S/generator/audit/` (produced by `scripts/generate_data.py --audit-packet`).

1. Open `worksheet.md`. It lists the 30 items in a readable form. For each item decide which of six labels fits, using only
   the item and, if you want, the published documents (`artifacts/fixtures/S/published/`; file names are hashes, so find a document
   through its title or id in `corpus_manifest.jsonl`).
   - `ANSWERABLE`: the visible documents settle the question.
   - `PARTIAL`: some evidence exists but a needed case input (for example the amount) is missing.
   - `UNANSWERABLE`: no document supports an answer.
   - `CONFLICT`: two approved documents of equal authority disagree.
   - `BLOCKED_BY_ACL`: the answer lies in a document this principal may not see.
   - `VERIFICATION_UNAVAILABLE`: a required live check failed, is stale or is not permitted.
2. Write the label into the line for that item in `owner_labels.jsonl` (the file already holds one blank line per item;
   fill `"answerability": "..."`). Label every item before you open `key.json`.
3. Then open `key.json`. For each item it lists the cited clauses (`document#clause`) and the claims the gold requires. Check in the
   published document that the clause exists and is enough to support the claims, and fill `"evidence_check"` with `sufficient`,
   `partial` or `insufficient`. Do not change a label after seeing the key.
4. Run `uv run python -m benchmark.fixtures.audit report --root artifacts/fixtures/S` from `palladion-benchmark/`. It prints the
   agreement figures and every disagreement, and writes `audit_report.json`.
5. Each disagreement is settled against the hidden world's rules, not by either reader. A defective question is fixed or withdrawn
   before any measurement, with the before and after hashes recorded in the evidence log.
