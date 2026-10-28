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
| Policy creation through the UI server | Validated, registered (author resolved to the source's uploader, product defaulted, enum values filled), listed, revoked. |
| Ingestion | Draft upload invisible to a reader; approved by an admin; then found by search; listing showed it approved. |

## Not verified

* Only two real agent turns were run. Answer quality, the critic's behavior and a conflict/not-established answer were not
  observed live; their rendering is covered only by the fake.
* Streaming was observed in the browser only for the first real turn and against the fake; no timing measurements.
* Browser-only behavior (drag and drop, PDF upload, light theme, narrow screens beyond one width) was not exercised.
* The `supersede` flow was tested against Palladion's test suite and the fake, not through the live UI.
* Models other than GPT-OSS 20B were not started.

## Incident worth knowing

Killing WSL's `wslrelay.exe` to stop a Qdrant removed Windows-to-WSL port forwarding, so later Qdrants started but were
unreachable until `wsl --shutdown`. The UI now stops Qdrant inside WSL and clears a stale one of its own at start.
