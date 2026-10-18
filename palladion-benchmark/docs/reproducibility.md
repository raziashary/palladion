# Reproducibility checklist

Started in B01-T03.02 and finished in B08-T07.01. This checklist records what a reader needs to reconstruct a run
from its manifest (protocol §7.2, §14.4, §19.3, §22). An unchecked box means the evidence does not exist yet, not
that the item was waived.

## Run identity and integrity

- [x] A run manifest schema exists with source, question and evaluator-only gold digests (`benchmark/run_manifest.py`).
- [x] A manifest is created exclusively and never overwritten; its digest is recorded outside the file as well.
- [x] Benchmark and system-under-test trees are captured separately: commit, content digest and every dirty path.
- [x] Every ledger record carries the manifest digest and the runner refuses a manifest that changed after the ledger recorded it (`benchmark/runner.py`).
- [ ] The system under test is pinned to a commit in a separate worktree or an image digest (B04, BADR-0016).
- [ ] Container image digests are resolved and recorded (needs a container runtime; Docker cannot run on the author's machine, so services run as pinned standalone binaries, BADR-0017).

## Models, prompts and parameters

- [x] Every generation call records the requested and served model, temperature, completion cap, reasoning effort,
      response format, request time and token counts (`benchmark/generator.py`). Groq exposes no model revision; the record states it.
- [ ] Embedding and reranker models are pinned to exact revisions and match Palladion's pins (OQ04, OQ05; B04).
- [ ] Prompts and templates are archived with their digest (B05).
- [ ] The per-question generator assignment is fixed before any arm runs and its digest is in the manifest (BADR-0015). `assign_models` and its digest exist; wiring into a run is B05.
- [ ] Seeds are recorded: data seed, order seed, and repetition seeds where supported. Data and order seeds are manifest fields; repetition seeds arrive with B05.

## Data and labels

- [ ] Synthetic world, corpus and question manifests are generated from a seed and reproduce identical digests (B02).
- [ ] The four namespaces (generator, published corpus, dev annotations, locked test annotations) are physically separate.
- [ ] The locked test set is sealed by SHA-256 before the confirmatory run (B08-T03.01).
- [ ] Annotation procedure, agreement statistics and adjudication history are archived (B02-T07.02, B05-T04).

## Environment and cost

- [x] Hardware description is captured without hostname or user identity (`collect_hardware`).
- [ ] Pricing snapshot is a dated vendor sheet, or the run states it used a free tier and reports tokens and wall time.
- [ ] Indexing, extraction, storage and update costs are recorded for every arm (B04, B06).
- [ ] Rate-limit events, retries, throttles and cached versus uncached responses are retained.

## Licensing and disclosure

- [ ] Dataset and generator licenses are chosen (OQ09, before B08-T07.01).
- [ ] The report states that fixtures are fictional and not actual operating procedures.
- [ ] Fairness deviations, unsupported native capabilities and failed or missing runs are listed beside the scores.
