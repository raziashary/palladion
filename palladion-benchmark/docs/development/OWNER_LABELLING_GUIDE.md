# How to label the 30 pilot questions (B02-T07.02)

This is the one document you need. It tells you what the labels are for, exactly what to do, in which order, and what
happens afterwards. Plan on one to two hours. Nothing here needs a model, a key or a network connection.

## 1. Why this matters

The benchmark scores systems against a hidden "gold" answer for each question. Before any measurement, the gold must be
checked by someone who did not write it. You are that reader. You label 30 questions blind, then check the evidence the
gold cites. Your labels are compared with the gold and with a blinded model pass, and every disagreement is settled
against the rules of the hidden world, never by trusting either reader.

Until this is done, the Track A pilot (B04-T05.01) cannot run and the gold gate (BG-GOLD) stays PARTIAL.

Everything in the data is fictional (Meridian Switchworks). There is nothing real to leak or to mis-handle.

## 2. What you need

All paths are inside `C:\palladion\palladion-benchmark\`.

| File | What it is | When you may open it |
|---|---|---|
| `artifacts/fixtures/S/generator/audit/worksheet.md` | The 30 questions, each with six documents (four the person can see, two they cannot) | Now |
| `artifacts/fixtures/S/generator/audit/owner_labels.jsonl` | Your answer sheet: 30 lines, one per question | Now (you edit it) |
| `artifacts/fixtures/S/published/corpus_manifest.jsonl` and `published/docs/` | All 1,200 documents, to look things up | Now |
| `artifacts/fixtures/S/generator/audit/key.json` | The gold: label, cited clauses and required claims | **Only after all 30 labels are written** |
| `artifacts/fixtures/S/generator/audit/llm_labels.jsonl`, `audit_report.json` | The model's labels and the earlier report | **Never before you finish**; they would bias you |

If you open `key.json`, `llm_labels.jsonl` or `audit_report.json` early, say so when you report back; the item is then
treated as unblinded. Do not change a label after you have seen the key.

## 3. Step 1: label every question (blind)

Open `worksheet.md`. Each of the 30 items shows:

- the **question**, in English, Bahasa Indonesia or a mix;
- the **principal**: a role at a tenant (for example `support_l2 at T-KESTREL`) and the **evaluation time**;
- a **live read** when the question depends on a transaction status (status `ok`, `unauthorized`, `unavailable`,
  `stale`, or a payload);
- six **documents**, each marked `visible` or `NOT visible to this principal`, with its type and state
  (`approved`, `retired`, `non_normative`, `unapproved_proposal`, `draft`, `withdrawn`).

For each item decide which one label fits. Use only what the principal is allowed to see, judged **as of the evaluation
time** (and, when the question names a case or transaction date, as of that date).

| Label | Choose it when |
|---|---|
| `ANSWERABLE` | An approved policy or exception that the principal can see, and that was in force at the right time, settles the question, and nothing needed to apply it is missing. |
| `PARTIAL` | Some applicable evidence exists, but a needed case input is missing (for example the amount, or the transaction state), so the question cannot be fully settled. |
| `UNANSWERABLE` | No visible, approved document supports an answer at all. |
| `CONFLICT` | Two approved documents of equal authority that both apply give different answers. |
| `BLOCKED_BY_ACL` | The answer exists, but only in a document marked `NOT visible to this principal`. |
| `VERIFICATION_UNAVAILABLE` | The answer needs a live check and that check failed (`unavailable`), is too old (`stale`), or was refused (`unauthorized`). |

Rules that settle most doubts:

1. **Authority.** Only `approved` documents carry authority. FAQs, memos, tickets, runbooks and API notes
   (`non_normative`) can echo a rule, and may be wrong or out of date; they never settle a question. `draft`,
   `unapproved_proposal` and `withdrawn` documents never count. `retired` documents are old versions: they count only if
   they were the version in force at the time the question asks about.
2. **Time.** If several versions of a policy exist, the one valid at the stated time applies. Read each version's
   validity dates inside the document.
3. **Visibility beats everything.** If the only settling document is marked not visible, the label is `BLOCKED_BY_ACL`,
   even though you can read it.
4. **Live checks.** If the question is about a particular transaction and its live read is not `ok`, the label is
   `VERIFICATION_UNAVAILABLE`.
5. **Search the corpus when the six documents are not enough.** The worksheet shows six documents, not all 1,200. If you
   suspect the right document is not shown, search `published/` (see step 3 for how to find a file). If you cannot find
   support, it is `UNANSWERABLE`.
6. When two labels both seem possible, choose the one that matches the **first rule above that applies** in this order:
   visibility, live check, authority, time, conflict, missing input. Write down the item number if you were unsure; I
   will ask you about it later.

Write each label into `owner_labels.jsonl` **as you go**. The file already holds 30 lines like:

```json
{"answerability":"","evidence_check":"","gold_sha256":"47019c5e…","item_id":"a-003b23a6cce2"}
```

Edit only the `answerability` value, between the quotes, and use exactly one of the six words above (capital letters,
underscores, no spaces):

```json
{"answerability":"ANSWERABLE","evidence_check":"","gold_sha256":"47019c5e…","item_id":"a-003b23a6cce2"}
```

Do not touch `item_id` or `gold_sha256`; the first matches your line to the worksheet item (the worksheet heading
`## 1. a-003b23a6cce2` carries the same id), the second proves your label was made against this exact gold. Keep one
JSON object per line and keep every line. Any plain text editor works (VS Code is fine); save the file as UTF-8.

## 4. Step 2: only now, open the key

When all 30 `answerability` values are filled in, open `key.json`. For each item it lists the gold label, the **cited
clauses** (written `document#clause`, for example `POL-015@v2#4.1`) and the **claims** the gold requires. Do not change
any label.

## 5. Step 3: check the evidence (this is your retrieval check)

For each item that has cited clauses:

1. Find the cited document. Open `published/corpus_manifest.jsonl`, search for the document id (for example
   `POL-015@v2`), and read its `path` (a file such as `docs/1e6e1ed95a972600.md` under `published/`). Open that file.
2. Find the clause number (for example `4.1`) in the text.
3. Ask: does that clause exist, and is it enough, with the principal's visible documents, to support every claim listed
   for the item?
4. Write one word in the `evidence_check` field of that item's line in `owner_labels.jsonl`:
   - `sufficient`: the clause exists and supports all the listed claims;
   - `partial`: it exists but supports only some claims, or needs another clause that is not cited;
   - `insufficient`: it is missing, says something different, or does not support the claims.

Items whose gold cites nothing (for example `UNANSWERABLE`) can keep `evidence_check` empty. If you think the gold
**should** have cited something, or cites the wrong thing, write `insufficient` and tell me the item id.

## 6. Step 4: get the report

From `C:\palladion\palladion-benchmark` run:

```bash
uv run python -m benchmark.fixtures.audit report --root artifacts/fixtures/S
```

It prints how often you agree with the gold, with the model, and with both, Cohen's kappa for each pair, how many
evidence checks fell in each class, and every disagreement; it also writes `audit_report.json`. It refuses to run if a
label is not one of the six words, an id does not exist in the packet, or a label was made against a gold that has
changed since.

## 7. What happens next

- Send me the printed report, plus the item numbers you were unsure about and anything you opened early.
- I settle **each disagreement** against the hidden world's rules (its policy versions, dates and visibility), not by
  preferring either reader. A defective question is corrected or withdrawn **before any measurement**, and the
  before-and-after hashes go into the evidence log.
- I record the audit as complete (B02-T07.02 done, BG-GOLD closed for the pilot), and the Track A pilot can then run on
  the smoke split. B04's other work is already built and validated; this is the one open owner task.

## 8. If something goes wrong

- *The label file says my gold digest is stale.* You, or the generator, changed the fixture after your line was written.
  Do not edit the digest; tell me, and I will regenerate a blank sheet for you.
- *A word is rejected.* Use exactly: `ANSWERABLE`, `PARTIAL`, `UNANSWERABLE`, `CONFLICT`, `BLOCKED_BY_ACL`,
  `VERIFICATION_UNAVAILABLE`.
- *You cannot decide an item.* Pick the best fit, note the item number, and move on. A hard item is useful: it may show
  a question the gold got wrong.

Design and numbers behind this audit: BADR-0019 in the [ADR log](ADR_LOG.md), the "Label audit" section of the
[dataset card](../dataset_card.md), and evidence E-B02-005 in the [evidence log](EVIDENCE_LOG.md).
