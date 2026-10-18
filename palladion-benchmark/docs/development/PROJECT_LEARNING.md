# Project learning register

Updated 2026-10-18. Mistakes, refuted claims and methods that worked, each with the evidence that shows it.
Wrong claims are struck through and corrected in place, not erased.

## Methods that worked

- **Count planned files by parsing the protocol tree, not by trusting its stated total.** The tree parses to 70 files and 56 Python files, matching
  the protocol's own claim (E-B00-001). The checker re-derives this on every run, so a changed protocol tree breaks the build until ownership is updated.
- **Generate the atomic register from structured data, then edit by hand.** Card fields stay uniform and the checker can parse them; the generator is
  scaffolding and is not kept in the repository.
- **Make the stated limits visible at the point of use.** The gate catalog repeats that gates test the benchmark, not the systems under test.

## Risks surfaced while planning (not yet mistakes)

- **A rate-limit failover pool confounds paired comparisons.** The owner's three-model Groq pool (BADR-0007) means a pair of arms could run on different models.
  Recorded as BADR-0008, OQ02 and BR04 before any code exists.
- **A shared checkout can publish another contributor's work.** Pushing `main` sends every unpushed commit. Recorded as BADR-0004 and BR02 with explicit
  path-scoped staging and an ahead-list check.
- **Palladion's interface moves.** Its phases are still open, so adapters are planned against its live source, not its plan (BR01, OQ03).

## Mistakes and corrections

- ~~E3 (Palladion without critic) can be produced by configuration, not by code edits.~~ Planned in the first draft of B07-T04.01 without reading Palladion's
  settings. Palladion's `critic_max_calls` has a minimum of 1 and its search interface has no clock or token budget (E-B00-003, F2 and F4, verified in
  `palladion/src/evidence_agent/settings.py` and `api/schemas.py`). Mechanism: the card was written from the protocol's arm list, not from the live
  interface. Correction: E3/E4 are FEATURE_NOT_SUPPORTED until Palladion documents a switch (OQ11). Rule going forward: read the live interface before a card
  claims an adapter capability.
- ~~Excluding mixed-model pairs from the primary analysis keeps comparisons clean.~~ Proposed in BADR-0008; the review showed it is informative censoring
  because rate limits follow token volume. Replaced by a model-per-question rule fixed before arms run.
