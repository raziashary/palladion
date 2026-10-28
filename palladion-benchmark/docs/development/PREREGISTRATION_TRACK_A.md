# Pre-registration of the sealed Track A run

**Decision:** BADR-0047 (owner answers of 2026-10-28). **Machine-readable form:** `configs/registration_track_a.json`
(sealed with this file; the seal is made by `scripts/seal_worlds.py create`).

This text is written before the six test worlds are used. Everything below is fixed once the seal exists; a change after
it makes the results exploratory (B08-T03.01).

## What is claimed, and what is not

The sealed run asks one question of retrieval: **does Palladion's retriever find a complete, applicable set of
documents (CompleteSet@10, condition C2) more often than the strong hybrid-plus-reranker baseline (R3)?** It makes no
claim about answers (Tracks B and C stay descriptive), about real data (the corpus is synthetic and fictional), or about
questions written by anyone other than the benchmark's generator.

## Design

| item | fixed value |
|---|---|
| Test material | six independent fictional worlds, seeds 101 to 106, 1,200 documents and 100 questions each, generated once, never read per question by the coordinator |
| Development material | worlds of seeds 11 and 12 (clean) and seed 7 (not clean: Palladion was tuned on it); tuning reads these only |
| Arms | R0, R0x, R1, R2, R3, R3f (the benchmark's own, tuned on the development worlds with the same budget each) and R7a (Palladion at the pinned commit) |
| Primary endpoint | CompleteSet@10, condition C2 (each system under its own access rule), intention to treat |
| Primary pairing | R7a minus R3, on every scored question of the six worlds |
| Secondary pairings | R7a minus R0, R0x and R3f, Holm-adjusted among the three; the primary is not adjusted |
| Interval | 95% percentile bootstrap, resampling document families within each world (families of different worlds are different clusters) |
| Claim rule | CONFIRMED only when the lower bound is above 0.05 (an absolute gain of five points); BELOW_MINIMUM when it is above 0 but not above 0.05; INCONCLUSIVE when the interval holds 0; ADVERSE when the upper bound is below 0 |
| Other conditions and measures | C1 is reported, not primary; recall, MRR, harm rates and strata are descriptive |
| Repeats | three runs of every world, each on a freshly prepared Palladion runtime; the first repeat is the registered one, the others report reproducibility |
| Wording variants | a different-family model rewrites each question; the rewrites that keep every identifier, number and negation are scored on the same questions beside the originals and reported as a change in CompleteSet@10, with no claim; their digests are sealed by a second seal before their run, and the primary result does not wait for them |
| Labels | the generator's, delegated and unaudited by a human (the owner accepted this in writing on 2026-10-28) |

## Rules of conduct

1. The scorer prints aggregates only. The coordinator does not open a test world's annotation files or a sealed run's ledger.
2. Palladion and every other arm are frozen at the seal. A fix made after seeing a sealed result needs new worlds, and
   its results are exploratory.
3. A question found defective after the seal stays in the denominator and is listed in the report.
4. A run that fails, times out or is not completed is a result (a run state), never a zero and never dropped.

## Development-world check (B08-T02.01, B08-T02.02), done before the seal

Every benchmark-built arm was tuned on the development worlds (D11 and D12, 200 questions) with the same budget; the
frozen settings are in `configs/tuned_arms.json`. Every arm kept 250-word chunks (the earlier 120 handicapped all of
them) and nothing else. On those worlds, which Palladion was never changed on, CompleteSet@10 under C2 was: R7a 0.362,
R3f 0.282, R0 0.262, R0x 0.262, R2 0.262, R3 0.235, R1 0.154. The registered pairing R7a against R3 was +0.128
[+0.066, +0.189] on the 149 questions that owe the metric, and R7a against R3f +0.081 [+0.007, +0.154].

Power of the registered claim rule with six worlds (about 260 family clusters; a Monte Carlo that draws the arms
independently within a question, so it understates the power of a paired design): 0.92 for a true gain of 0.128, 0.63
for 0.10 and 0.30 for 0.08. The minimum effect stays 0.05. A gain between 0 and about 0.10 is therefore likely to come
back INCONCLUSIVE or BELOW_MINIMUM, and the report will say the endpoint could not resolve it rather than lower the bar.

