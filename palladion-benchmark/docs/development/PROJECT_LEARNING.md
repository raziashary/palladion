# Project learning register

Updated 2026-10-19. Mistakes, refuted claims and methods that worked, each with the evidence that shows it.
Wrong claims are struck through and corrected in place, not erased.

## Methods that worked

- **Count planned files by parsing the protocol tree, not by trusting its stated total.** The tree parses to 70 files and 56 Python files, matching
  the protocol's own claim (E-B00-001). The checker re-derives this on every run, so a changed protocol tree breaks the build until ownership is updated.
- **Generate the atomic register from structured data, then edit by hand.** Card fields stay uniform and the checker can parse them; the generator is
  scaffolding and is not kept in the repository.
- **Make the stated limits visible at the point of use.** The gate catalog repeats that gates test the benchmark, not the systems under test.

- **Plant a defect in a temporary copy and require the owning tests to fail.** Tests that passed on the first run proved nothing about their power. The sweep in E-B01-003 found real gaps:
  untracked files were never part of the tree digest, a ledger duplicate-final check was shadowed by another check, the runner's completeness check was never exercised, redirect and proxy handling had no test,
  model approval was checked only through a second path, and usage validation was invisible. Each got a test, and the survivor that remained (lock removal) is stated as a limit.
- **Read the live interface before writing an adapter-facing card.** The pre-phase adversary (E-B01-001) and the earlier correction both traced to plans written from the protocol alone.
- **Keep error text out of records by construction.** Raising a fixed-code error outside the `except` block leaves no chained exception, and a test that forces a planted key through every error path shows it.

- **Read the output of a generator against the rules it claims, not only against its tests.** The post-phase audit (E-B02-004) found 4 to 6 unplanned policy conflicts that every test had passed, because the tests only checked planted ones. Running the world's own resolver over every scope found them in minutes; the validation gate now does that on every build.
- **A mutation sweep also finds redundant code.** One survivor (E-B02-003) was a check that never decided a result; deleting it was the right fix, not another test.
- **Spend limits are also a design input.** The first model pass used 36 of 40 calls on a prompt that hid the rule clauses; the numbers it produced were worthless and could not be redone within the authorisation. A dry run with a fake transport over the real prompt, and a look at the prompt text itself, would have cost nothing.

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
- ~~Review finding labels made of the letter A and a number are safe identifiers.~~ In E-B01-001 the labels numbered 17 to 24 collided with the ablation ID namespace (A01 to A16) and the documentation checker flagged them as undefined IDs. Mechanism: the review labels reused a prefix
  the checker treats as a stable ID. Correction: findings are labelled `adv-N`. Rule going forward: pick review labels outside every defined ID pattern.
- ~~Configuration loaders belong in `contracts.py`.~~ The first plan put them there; the file grew past one responsibility, so the loaders moved to `benchmark/config.py` (BADR-0014) and the checker's recorded additions were updated in the same step.
- ~~The second model pass used the line-selecting excerpt.~~ The excerpt function was written and tested but never wired into the packet; the pass ran on a 900-character prefix. Mechanism: the replacement of the old call matched no text (the formatter had reflowed it) and nothing failed. Correction: a test now requires every packet excerpt to equal `excerpt(doc, query)`, and the card states which prompt each pass used. Rule going forward: a refactor that replaces a call needs a test that fails if the old call remains.
- ~~Question identifiers derived from a hash are pseudonymous.~~ They were recomputable from the public seed (aud-1, adv-4). Correction: a keyed secret (BADR-0023).
