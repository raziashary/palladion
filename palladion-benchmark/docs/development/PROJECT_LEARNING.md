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
- ~~A document locator naming only a document can credit all of its clauses.~~ The first scorer did, so a bare document id scored a full evidence set (aud-2). Correction: a document locator credits the document unit and only the clauses the candidate's text reproduces. Rule going forward: credit what the candidate shows, not what it names.
- ~~Leakage can be detected with the alignment threshold.~~ A 60 percent excerpt of a forbidden clause fell below 0.8 and counted as no leak (aud-1). Correction: a separate, lower exposure share, with near-duplicates of visible text excluded. Rule going forward: detect harm with a looser rule than credit.
- ~~`ruff format .` is safe from the project root.~~ It reformatted the protocol's code blocks and the checker. Mechanism: the formatter covers every Python file and Markdown code block it finds. Correction: format `benchmark tests scripts` only, and review `git status` after formatting.
- Method that worked: probing each audit finding by execution before fixing it, and retargeting a mutant whose anchor moved instead of counting it as killed.
- ~~A validator that passes a clean run has been shown to work.~~ The first key screen parsed each file line by line, so pretty-printed manifests were never parsed and a gold-named key in them went unseen; the tests were green because the clean run and the planted defects shared the blind spot. The real-fixture smoke exposed it. Correction: parse whole documents; one allowed key is named, not assumed. Rule going forward: a negative control must be planted in the same file format the clean artifact really has, and a clean run must be validated on a real run too.
- ~~Documents uploaded to Palladion over its API are as findable as the seeded ones.~~ Exact-identifier aliases exist only for what its own seed registers, so any query naming a code returns nothing (BR24). Found by a real call, not by reading its interface. Rule going forward: send one realistic query through every real entry point before designing the mapping to it.
- ~~A load that completed is a load that is usable.~~ After a runtime reset the revision table described a Palladion that no longer existed, and every answer was filtered out as foreign. Correction: `verify_load` fails when none of the sampled documents can be found. Rule going forward: a read-back that cannot fail is not a check.
- ~~Two halves of an OR guard can each be tested by one planted case.~~ Tampering with the text also changed its hash, so each half passed on the other's evidence. Correction: one case per half.
- ~~Approximate nearest-neighbour results are reproducible.~~ Equal scores came back in a different order after a rebuild; fixed by ordering ties by chunk id after asking for ten extra hits. Method that worked: a stand-in encoder with many equal scores exposed it in seconds.
- ~~Inline Python in a shell heredoc carries backslashes and quotes through.~~ It silently turned escape sequences into control characters or real newlines several more times; use the Write tool for any file with backslashes.
- ~~A launcher that worked in the last session starts in the next one.~~ A server record left by an earlier run named a PID that another user's process had reused, and reading that process's executable raised `PermissionError`, so every test that starts the server errored. Found only by the full suite after the pilot; fixed by treating an unreadable process as not ours, with a test that fails on the old code. Method that worked: running the whole suite after the real runs, not only the touched tests.
- Method that worked: a withdrawal list that leaves defective questions in the run (so the ledger stays complete) and out of the scores, with the list printed at the head of every scorecard and an unknown id an error.
- ~~A risk-register statement about the system under test, written from its behaviour, is a fact.~~ Two were contradicted by its source (the filter order in BR27, and supersession and validity windows in BR28, which its HTTP API does accept). Correction: read the source line before writing a limit into the register, and keep the fixes document (PALLADION_FIXES) beside the register.
- ~~A script that stops cleanly leaves nothing behind.~~ Stopping a shell script left its child runs and a Palladion server on the benchmark's port; they were found by listing processes, not by the exit status. Rule: stop children by process id, then re-list; never match on a pattern that includes the killing command.
- ~~A test that filters its own assertion set to the records that have the property is a test of the property.~~ `all(... for r in finals if r.flags)` passed while every record had empty flags; the post-phase audit found it. Rule: assert on all records, then on their content.
- ~~An evaluator helper may reuse an arm-facing guard unchanged.~~ The new prompt screen blocked the earlier label audit, whose prompt legitimately names the labels. The screen is on by default and the evaluator-side pass opts out in one named place.
- Method that worked: a first mutation sweep that left six survivors, each one a real missing test, then a focused second sweep over the audit fixes; and a validator branch that searches for gold text outside the answers, which are allowed to say what the gold says.

## B06 (graph comparators)

- ~~Passing the provider key to nobody means no comparator can read it.~~ A library imported at start-up (litellm) searched upward from its own install directory and loaded the benchmark's `.env`; found by the end audit, reproduced by printing only variable names, and invisible to a test that planted the key in the parent environment. Rule: test a secret boundary by planting the secret where the library would look, with a positive control.
- ~~A resumed run re-inserts what it lacks.~~ The upstream skips an id it already stores and records a failed duplicate, so failed documents were never retried; found only by the second live attempt. Rule: a resume path is tested with a first attempt that fails, then a second that succeeds, over one directory.
- ~~A pace under the stated per-minute limit stays under the limit.~~ The provider reserves the requested completion size, so a 700-token request counts against a 1,000-token minute limit; and every model had a separate daily limit that three attempts used up. Rule: read the provider's own rejection message before choosing a pace, and stop a run on a daily wall instead of paying a call for each rejection.
- ~~A model change is a configuration change.~~ Reasoning models spent the whole 700-token completion cap thinking and returned nothing; a larger cap was needed.
- ~~Documentation numbers copied from memory.~~ Four counts in the evidence did not reproduce against the books; the audit recounted them. Rule: derive every figure from the saved books by script when writing the entry.
- Method that worked: running the real upstream code behind a fake provider with a counting proxy before any live call (it found nine defects at zero cost); an independent read-only audit with a brief naming what to recount; and a reconstructed spend record that says it was reconstructed.


## B07 (system arms, memory, critic and mutations)

- ~~A client timeout that works for one call works for a message.~~ A Palladion message is several paced model calls, so a 60 s client gave up on seven of eight turns while the server went on spending 77,000 tokens for nobody. Rule: the client's timeout is the server's own deadline plus a margin, and a timed-out call is checked against the book for work that continued.
- ~~A dry run with a scripted provider estimates live cost.~~ It was low by a factor of 3.1 on prompt tokens: it issues one short search, the real model issued two to ten tool calls in a turn. Rule: report a scripted estimate as a lower bound and size a live pilot from one real answered turn, not from the plan.
- ~~A case per episode isolates private memory.~~ Palladion's sources belong to the case they were uploaded under, so a new case sees an empty corpus (found by one probe before any design). Rule: probe the real interface with the smallest possible request before building on a decision about it.
- ~~Two servers on one store are two arms.~~ A mutation made for one is seen by the other, and an identical re-upload is refused; the dry run found it, the plan did not. Rule: arms that share state run one at a time, and a mutation is undone (and the residue named) after its case.
- ~~A metric module that works on test data reads the real trace.~~ The adapter's trace held only the model calls; the critic and tool-use scorers needed the whole evaluator block. Rule: one test per metric module that feeds it the output of the real producer.
- ~~A generator that picks documents by depth covers the chain.~~ It filled the quota on root versions and never emitted a supersede event; found because the test was written from the spec (every kind of event) and failed on the first run. Rule: assert that every kind the spec lists appears.
- ~~A freshly published document is retrievable and citable.~~ Palladion returned it, but the arm's view did not know it, so every passage of it was dropped as foreign. Found only by a real retrieval after a real publish.
- ~~A clause that looks defensive is needed.~~ A mutation sweep showed the leakage check's `own_text` clause was redundant with the token set built from the same utterances; removed rather than tested around.
- Method that worked: a pre-phase adversary whose 29 findings became cards; one real probe per Palladion assumption; a scripted provider that exercises every arm end to end at zero cost; mutation sweeps with every survivor read, not suppressed; a Palladion change made only with its own ADR first and its own tests.
- Tooling: the Edit tool turns `\u043e` into the character it names, and a shell heredoc turns `\n` in a Python string into a real newline; build such strings with `chr()` or write the file with the Write tool.
- ~~A run that recounts its own totals has checked its book.~~ It compared two in-memory numbers; the audit recounted the saved rows and found one reserved call with no row. Rule: a check of a book reads the book.
- ~~A test that reads back what the code wrote proves the state.~~ `PalladionTarget.verified` compared the arm's own record with itself. Rule: an independent read (a retrieval) is the proof, and the weaker check is named as such.
- ~~An invariant in a decision record is an invariant in the code.~~ `dd70c0e`: memory recall still read the wall clock although ADR-0101 said memory validity was moved; the test covered `read` and `write`, not `recall`. Rule: one test per reader of the thing that was moved, and a mutant that puts the old read back.

## B08 (descriptive comparison under the free tier)

- ~~A daily provider refusal is a failure of the pair.~~ It was written as a final INVALID_RUN, so everything left when the quota ran out would have become a permanent arm failure (pre-phase adversary, adv-2). Rule: a limit that stops a run is a pause with its own state (`QUOTA_BLOCKED`), resumed in the same directory, never an arm's result and never a zero; a cap the owner sets is stopped the same way.
- ~~A request schema states what a server accepts.~~ Palladion's `Search` schema allows 40 results and PF04 says "max 40", but lexical and hybrid search answered HTTP 400 above 12 on the full corpus (a two-document test corpus never showed it, because fewer results exist than the limit). Found by the first real run, which marked R7a NOT_RUN for all 100 questions. Rule: probe a limit at the corpus size that matters, and keep a failed first attempt as a result.
- ~~A quota ledger that adds up directories adds up the spend.~~ A directory named once by glob and once by the caller counted twice (a relative against an absolute path), so the books showed 300,000 tokens and every model looked spent; found only by a resume that did nothing. Rule: resolve paths before comparing them, and give every aggregation a test where the same thing is named two ways.
- ~~A command that prints nothing succeeded.~~ `python -m benchmark.analysis.reports` ran, wrote nothing and printed nothing because the module had no `__main__` guard. Rule: every command line has a test that runs it as a command.
- ~~Putting the comparison's numbers in the shipped default configuration is harmless.~~ Setting per-model budgets in `configs/benchmark.yaml` broke 16 tests and would have changed every later pilot. Rule: the default is a contract; an experiment's numbers go in the frozen file its run records.
- ~~An offline stand-in is a model.~~ Its rows named the real model asked for, so the quota books charged the day's quota for a dry run; the ledger now keys by the model that served the call, and the stand-in serves under its own name.
- ~~Starting the next background job while the last one runs is faster.~~ Two chains that each reset the same Palladion runtime root deleted each other's files and produced three different errors. Rule: one writer per runtime root; kill the stale chain before starting a new one, and run a multi-step chain from one script.
- ~~A harm table with one column is one measure.~~ The harm bounds counted pairs while the conditional column averaged a fraction; both were correct and read as a contradiction. Rule: say in the header which one a column is.
- Method that worked: a pre-phase adversary whose confirmed findings became cards before any spend (E-B08-001); a free dry run of every live path with the offline stand-in over the frozen list; a trial report over real runs read end to end before the tests were written; mutants that put each defect back and must fail the new tests; the quota CLI before every live day; the owner's decisions asked once with measured numbers (cap, Track C size, license).
