# Testing record

One command runs the dev suite: `uv run python -m scripts.check` (ruff, 60 server tests, front-end syntax, 7 front-end
tests). It uses a deterministic fake Palladion (`tests/fake_palladion.py`), so it needs no model, Qdrant or quota. Passing it
shows the UI's own logic is right; it does not show Palladion's behavior.

## Live checks, 2026-10-28 (real Palladion, clean worktree of 5acc825 plus the uncommitted routes)

Setup: own Qdrant on its own port and data folder, own data root, collection `palladion_ui_dev`. Model: **GPT-OSS 20B only**.

| Check | Result |
|---|---|
| Informational question as `reader-a` | Real agent answered `Supported` / independently reviewed in 19 s with an exact quote of SOP 2026 §2. The citation opened the real document with "original bytes re-checked". |
| Live progress during the turn | Real timeline events appeared as they happened ("Question received", "Asking the model", "Model replied"). |
| Operational question (`Can I reverse this?`) | Real live readings were taken (transaction FAILED, settlement UNSETTLED) and the policy engine ran and returned `INCOMPLETE_INPUT` (no trusted time input). The critic call failed with provider HTTP 429, and the UI showed "Review: unavailable" and the failure plainly. **No further model calls were made after the 429.** |
| Two more operational runs for the screenshots | One answered "Partly supported" with the review passed, two live readings and the policy engine `DETERMINED`, but one model call hit HTTP 429, so the gate released its safe template (no source quote, no policy citation). The next, richer question came back "Could not verify" with `FINALIZATION_UNAVAILABLE` and the 429 named, and no further runs were made. |
| Policy creation through the UI server | Validated, registered (author resolved to the source's uploader, product defaulted, enum values filled), listed, revoked. |
| Ingestion | Draft upload invisible to a reader; approved by an admin; then found by search; listing showed it approved. |

## Power and settings, 2026-10-29 (real Palladion `68f6df6`, GPT-OSS 20B only)

| Check | Result |
|---|---|
| Runtime re-pinned from `5acc825` to `68f6df6` | Gives the agent's searches the persistent workers. Started ready with the generated settings file; the data folder opened without a migration problem. |
| Power report from the real source | Real embedding and reranker names and rerank depth (20) were read from Palladion's source; seven locked layers listed; graph shown as not available (no Neo4j). |
| Reranker off then on, real search | Off: the rerank stage took 0.9 ms and returned no warnings. On: 717 ms (the real cross-encoder). Ordinary search results came back either way. |
| Reduced options applied and reset | The restarted command lacked `--rerank` and carried `--settings`; the settings file held `continuity_enabled: false`, `critic_search_max_calls: 1`, `tool_max_calls: 4`, `search_worker_mode: "per_request"`. Reset restored every value. |
| Critic off with the agent enabled | Palladion accepted the evaluator arm (`--evaluator-arm B5 --acknowledge-not-serving`), reported ready, and no key appeared on the command line. Reset removed the arm. **No question was asked in this mode.** |
| One full-power agent turn | Finished in 9.9 s with 18 progress steps, but Groq returned HTTP 429: the review was unavailable, search was degraded, and the gate released its safe template. **A full-power answer with the critic passing was not captured**, and the speed-up from the persistent workers is not a controlled measurement (different question, different day). |

Not verified here: the experiment-mode notice on a live answer (it is covered by a server test through the fake only), the
Apply and Discard buttons by clicking (the Settings screens were rendered and captured, not driven), and any effect of a
toggle on answer quality.

## Ingestion and policy screens, 2026-10-28 (real Palladion, search-only, no model)

| Check | Result |
|---|---|
| Ingestion screen as an uploader and as an admin | Rendered from live data: the drop zone, the draft and approved steps, one-click switch to the approver, Approve and Revoke. Captured as screenshots. |
| Policy wizard "Start from an example" | Built a policy from a real approved passage and reached the review step with "Ready to register" (server validation). Captured as a screenshot. |
| How-to guides on Chat, Ingestion and Policies | Rendered from the real UI and captured as screenshots (open by default in a fresh browser; the open or closed choice is remembered per browser). Their wording was checked against the code: the policy example is the real demo policy, and the stale-reading outcome is `UNVERIFIED_INPUT`. |
| Upload, approve and policy registration clicks | Driven in a browser against the fake Palladion earlier; against the real Palladion they were exercised through the UI server's API (see above), not by clicking. |

## Not verified

* Only four real agent turns were run (two of them degraded by the provider rate limit). Answer quality, the critic's behavior and a conflict/not-established answer were not
  observed live; their rendering is covered only by the fake.
* Streaming was observed in the browser only for the first real turn and against the fake; no timing measurements.
* Browser-only behavior (drag and drop, PDF upload, "Load from a file", "Save a copy as a file", light theme, narrow screens beyond one width) was not exercised.
* The `supersede` flow was tested against Palladion's test suite and the fake, not through the live UI.
* Models other than GPT-OSS 20B were not started.
* The provider's daily quota was exhausted on 2026-10-29 before a full-power answer could be captured.

## Incident worth knowing

Killing WSL's `wslrelay.exe` to stop a Qdrant removed Windows-to-WSL port forwarding, so later Qdrants started but were
unreachable until `wsl --shutdown`. The UI now stops Qdrant inside WSL and clears a stale one of its own at start.
