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
| Wording variants | a different-family model rewrites each question; the rewrites that keep every identifier, number and negation are scored on the same questions beside the originals and reported as a change in CompleteSet@10, with no claim |
| Labels | the generator's, delegated and unaudited by a human (the owner accepted this in writing on 2026-10-28) |

## Rules of conduct

1. The scorer prints aggregates only. The coordinator does not open a test world's annotation files or a sealed run's ledger.
2. Palladion and every other arm are frozen at the seal. A fix made after seeing a sealed result needs new worlds, and
   its results are exploratory.
3. A question found defective after the seal stays in the denominator and is listed in the report.
4. A run that fails, times out or is not completed is a result (a run state), never a zero and never dropped.

## What would change the plan

The minimum effect of 0.05 is checked against the development worlds' disagreement before the seal (B08-T02.02); if six
worlds cannot resolve it, the report says the endpoint is underpowered rather than lowering the bar.
