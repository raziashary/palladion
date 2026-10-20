# P10 classification, source formats and continuity

Owner GO and ADR0096–0098 authorize these changes. Engineering verification and independent end review are complete; P09/PF03 performance acceptance remains open. No semantic accuracy,
production readiness or external benchmark superiority is established here.

## Path A and the proposed alternatives

The deterministic classifier now adds explicit weighted lexical features to its hard
boundaries. Phrase/word cues cover short preferences, familiar English/Indonesian
preferences and explicit multi-step unapproved workflows. Distinct action cues plus
a sequence marker and workflow prefix are required for user-written procedural context.
Trusted backend tool summaries retain their separate procedural rule. Scores are
fixed engineering weights, not class probabilities. Ambiguous text stays episodic;
the separately enabled Path B cosine supplement only handles eligible ambiguous
preferences. Persisted promotion profiles include actual regex patterns/flags,
weights, thresholds, tools and bounds, under lexical-2/promotion-2. Manual correction
and revocation remain stronger than automatic reprocessing; no historical backfill runs.

The owner's bag-of-words idea is useful for transparent weighted features, but plain
word counts discard order and negation. Phrases and hard exclusions therefore remain
necessary. This is consistent with the [scikit-learn feature extraction guide](https://scikit-learn.org/stable/modules/feature_extraction.html).
For unit-normalized vectors, squared Euclidean distance is `2 - 2*cosine`; changing
that distance alone supplies no accuracy improvement. Cross-entropy is a supervised
training objective, not a substitute for labels or authorization. Entropy of manually
normalized weights cannot certify that a classification is correct. A trained count
classifier would require labeled examples and evaluation, as the [Naive Bayes guide](https://scikit-learn.org/stable/modules/naive_bayes.html)
illustrates. No scikit-learn dependency or trained model was added.

Thresholds trade false promotions against missed preferences. Measure both rather than
presenting a confidence number; see the [precision/recall example](https://scikit-learn.org/stable/auto_examples/model_selection/plot_precision_recall.html).
The frozen30-case synthetic development controls were written before implementing the
rules. They contain10 semantic,3 procedural and17 episodic near-miss cases. Path A
returned exactly those categories: each category has0FP/0FN and precision/recall1.0;
episodic retention17/30. These are small developer-authored controls, not independent
human labels or evidence of generalization. Unseen phrasing/languages, negation and
mixed-intent requests remain risks. Deliberate unknowns still abstain; Path B is not
required for these decisive controls.

Fixture SHA256: `1ada1c8493f6b71955abde7b345545022979d6bed06bd7d1a55a8e0a56224d39`.
Earlier measured lexical profile SHA256: `e46d59c8133b4393e77f8f62d63b4db096122e7b03e9bdf9337a42de8ec99c70`.
Later hardening adds plural privacy cues, bare-language-fragment abstention and five
separate near-miss tests. The remeasured current profile SHA256 is `e39388a6ac7171962d26d1b13d6e461550b7d0b15c09ba4bfc6c0a1293b459f5`.
All30frozen controls and5additional near-misses pass in the current safe
[consumer receipt](p10-consumer-observations.json); the earlier hash remains historical.
The metric owner is `core/evaluation.py:score_categories`; the controls include a
deliberately wrong prediction to prove FP/FN accounting can fail.

## Source representation and PDF limits

New structured/code formats are verbatim UTF8 sources through upload, independent
approval, indexing and original-span citation readback. Text is never executed or
converted into company policy. PDF uses pinned pypdf6.21.0 in an isolated owned child:
2MiB input,50pages,256KiB extracted UTF8,10seconds and512MiB memory. The parent sends
input only after Windows job assignment; POSIX applies RLIMIT_AS before parser import.
Input/output bounds, strict PDF parsing, encrypted/empty-page rejection and process
tree cleanup complement the memory/deadline boundary.

The original PDF and extracted canonical text remain separate immutable artifacts,
linked by additive SQLitev7 provenance with page intervals and parser identity.
Citation offsets refer to extracted UTF8, never PDF byte positions. Current approved
source access gates both artifacts. [pypdf's extraction documentation](https://pypdf.readthedocs.io/en/stable/user/extract-text.html)
explains why scans require OCR, reading order/layout may be lost, and decompressed
content streams can consume large memory. This importer makes no layout/OCR guarantee.
PDF output may be rejected despite human readability when it exceeds these bounds.

## Conversation and automatic memory ownership

Ordinary message serving persists runtime events before backend classification and
promotion. Uploading documents is a separate source flow. Preflight automatically
reads bounded authorized memory and builds the continuity packet; optional model
`recall_memory` is an additional read. Path B, wider sharing, corrections and graph
administration remain explicit operations.

Typed conversation context contains at most4 own-actor/session turns, with stable
request/release/trace IDs, user-query/released-response context, chronology, preceding
turn references and omission/truncation indicators. A13-request sentinel avoids an
unbounded count: omission counts are lower bounds if truncated. Packet compression
drops oldest turns first. Revoked/corrected promoted query text is suppressed; explicit
manual controls conservatively suppress raw-query replay. Only current authorized
document-backed released claim text is replayed. Old operational/policy claim text is
omitted for fresh domain reads. No drafts, tool internals or chain-of-thought enter
this history. Every turn remains NONE authority / REQUIRES_RECHECK.

`AgentRuntime._investigate` explicitly consumes these fields; adding a packet writer
alone would not have reached that prompt. Current user text remains a separate input.
`live/` is the allowlisted operational-read gateway, currently using MockAdapter
fictional snapshots, not a production database. The README describes all four reads.

## Verification record

- Baseline:398PASS/31SKIP; `runtime/p10-baseline.xml`.
- Full source suite:448PASS/31SKIP; `runtime/p10-suite.xml` (before final extra controls).
- Focused HTTP/PDF/memory consumer checks:38PASS/1SKIP; `runtime/p10-consumers.xml`.
- Additional current graph denial/PDF/memory-cap consumers:15PASS;
  `runtime/p10-final-focused.xml`.
- Strict mypy:79source/script filesPASS before the new explicit smoke script;
  the new script also passes its targeted strict check.
- Real service attempt1 failed during initial Neo4j seed publication with a client
  transaction timeout. No model call was reached. Failure retained in
  `runtime/p10-live-attempt1.json/log`; subsequent readiness returned true in1.835s.
- Attempt2 failed the smoke script's missing explicit graph setting; corrected without
  changing serving defaults. Attempt3 completed all six actual graph/PDF/Groq/reopen
  checks.9model invocations/8responses; the unreceived invocation's exact cause was
  not preserved by the initial observer and remains UNKNOWN. A null last_failure
  described the last call only. Future runs now retain per-call outcomes.
- Later overlapping source guards had62PASS/1SKIP/2deadlineFAIL under host exhaustion.
  Inspection identified Windows venv redirector/job-assignment escape risk. The worker
  now launches the base interpreter directly with isolated/no-site startup and explicit
  current package/dependency paths, and blocks on stdin until job assignment. No runtime
  deadline increase. Three actual process controls passed5.41s; current focused suite
  then86PASS/2SKIP207.24s (`runtime/p10-current-focused.xml`). It includes a small
  allocation positive control plus an explicit MemoryError under the128MiB job cap,
  and a deliberately stalled owned child that times out and is reaped.
- Host Windows reached98–99% memory use (as little as9MiB free); CoreCLR and WSL
  connection failed. A full source recollection was interrupted without claiming PASS.
  Installed proof, current native follow-up, final audit and cleanup remain pending.

The benchmark's PF07 completion appendix will change only after the actual HTTP
registration → physical graph expansion → proof-readback consumer passes. Original
handoff requests and frozen benchmark observations remain unchanged.

Current hold: the actual attempt3 consumer passed, but subsequent hardening still
needs current installed/native/type verification and the single final review. Latest
isolated build again failed1450. Even base Python startup later failed importing its
existing encodings module; native file listing confirms the file is present. Treat
host failure separately from a missing-file diagnosis. No commit or main push yet.
Owner approvals persist. PROJECT_MEMORY owns exact resumption and cleanup cautions.

## Recovered current-byte verification

After owner-reported app closure, current source458PASS32SKIP109.65s and installed
91PASS2SKIP44.62s; actual installed Qdrant PDF1PASS22.62s. Exact source/wheel/installed
comparison covers70Python/SQL files. Ruff, strict mypy80files, dependency110files with
4negative controls, structural docs126cards/21negative controls, wheel+sdist build and
installed foundation/policy CLIs PASS. Safe observations/hashes are in
[consumer receipt](p10-consumer-observations.json). The one Starlette/httpx test-client
deprecation warning is dependency guidance, not a failed test; no dependency changed
outside the approved pinned pypdf addition. Single end review/cleanup/commit pending.
Earlier host holds and failures above are historical, superseded by these current checks.

## Final parser controls and independent review

Two additional boundary controls prove50pageaccept/51pagereject and an extracted-text
limit rejection below the input-size cap. Source tests/test_extraction.py11PASS14.95s;
installed11PASS14.65s, separate overlapping runs (not additive to458/91). Only a parser
docstring changed after the broad suites; corrected text distinguishes verbatim files
from Markdown/TXT block whitespace. Rebuilt wheel+sdist, isolated reinstall and exact
70file source/wheel/installed comparison pass. Final wheel SHA256:
`a6241d204ac90ff862a2af0147cffa235b00bd758f93ceab988372273252ce01`.

The sole independent GPT6LunaMedium end reviewer directly read all1784blueprint lines,
§§1–18/I01–I15, governing P10/ADR/source/test/evidence contracts and consumers. No
confirmed material implementation defect remained. Its final evidence-freshness gap
for those added tests/docstring is resolved by these current receipts. E-P10-007 records
coverage and limits. Owned services stopped with storage preserved; Windows/WSL have
no16333/16334/17687listeners. P10 has12of13cards verified; final scoped checkpoint T06 remains open until
commit/publication. PF07handoff is complete while P09/PF03 remains open. Earlier pending/blocked text above is historical, not current status.

## Published checkpoint and final task closure

Feature checkpoint `c3c09509087c533bf93f111b5b8aec6a89b564d4` was committed with a
Conventional Commit subject/descriptive body and published to the established
`origin/main` under the owner's standing approval. Fetch verified0behind/1ahead;
the complete outgoing commit message was inspected. Push exited0 from9727f5e to
c3c0950. Only55scoped files were staged; foreign benchmark/editor dirt was excluded.
P10-T06.01 now closes against that actual published checkpoint, rather than an expected
future commit. All13P10cards complete; only P09-T02.07/PF03 remains open. This final
documentation receipt is a separate logical closeout unit. E-P10-008 records proof.

Review scope remains honest: the full blueprint and current P10 portions of all12
core development docs were reviewed; the entire historical contents of all12 were not.
No full historical-drift audit or semantic efficacy claim is inferred.
