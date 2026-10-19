"""Stratified pilot label audit (B02-T07.02, BADR-0019).

A seeded, stratified sample of pilot questions is shown to two annotators without gold: the owner and a blinded language
model pass. Both see the question, the principal, the evaluation time, the live read (if any) and the top-ranked
documents with their access status, which is what the hidden world makes available. They label the answerability class;
the owner also judges whether the gold's cited clauses suffice. The statistics are owner against model and each against
the gold, with denominators. That is not human-human agreement and neither reader is independent of the templates;
the dataset card says so.

The packet is written by ``scripts/generate_data.py --audit-packet``. The model pass and the report run from
``palladion-benchmark/``::

    uv run python -m benchmark.fixtures.audit llm --root artifacts/fixtures/S --enable-live
    uv run python -m benchmark.fixtures.audit report --root artifacts/fixtures/S
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from benchmark.config import GeneratorSettings, load_benchmark_config
from benchmark.contracts import TransientInfrastructureError
from benchmark.fixtures import canonical_json, digest_of, sha256_hex
from benchmark.fixtures.documents import Document
from benchmark.fixtures.entities import Principal
from benchmark.fixtures.live_api import LiveMock, Mode
from benchmark.fixtures.questions import Answerability, GoldRecord, Stratum
from benchmark.fixtures.validation import Bm25, is_visible
from benchmark.fixtures.world import World
from benchmark.generator import GenerationError, GeneratorPool, assign_models

_QUERY_WORD = re.compile(r"[a-z]+")
LABELS = tuple(a.value for a in Answerability)
EVIDENCE_CHECKS = ("sufficient", "partial", "insufficient")
CONTEXT_DOCS = 4
WITHHELD_DOCS = 2
CONTEXT_CHARS = 900
TOKENS_PER_ITEM = 2500
MAX_LLM_CALLS = 40  # per pass (BADR-0019)
MAX_TOTAL_LLM_CALLS = 80  # across all passes, after the owner's amendment
PROMPT_VERSION = "excerpt-v1"
CONFIG = Path(__file__).resolve().parents[2] / "configs" / "benchmark.yaml"
DEFAULT_ENV = Path(__file__).resolve().parents[2] / ".env"
SYSTEM_PROMPT = (
    "You label support questions about a fictional payment company. Reply with one JSON object and nothing else."
)
LABEL_HELP = (
    "ANSWERABLE: the visible documents settle the question. PARTIAL: some evidence exists but a needed case input is "
    "missing. UNANSWERABLE: no document supports an answer. CONFLICT: two approved documents of equal authority "
    "disagree. BLOCKED_BY_ACL: the answer lies in a document this principal may not see. VERIFICATION_UNAVAILABLE: a "
    "required live check failed, is stale or is not permitted."
)


class AuditError(ValueError):
    """The audit inputs are inconsistent. The message names the problem, never a key or a prompt."""


@dataclass(frozen=True)
class ContextDoc:
    doc_id: str
    title: str
    registry_state: str
    visible_to_principal: bool
    excerpt: str


@dataclass(frozen=True)
class AuditItem:
    """What an annotator sees. There is no gold field."""

    item_id: str
    query: str
    principal_role: str
    principal_tenant: str
    evaluation_time: str
    live_read: Mapping[str, Any] | None
    context: tuple[ContextDoc, ...]

    def to_dict(self) -> dict[str, Any]:
        data = dict(self.__dict__)
        data["context"] = [dict(c.__dict__) for c in self.context]
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AuditItem:
        return cls(**{**data, "context": tuple(ContextDoc(**c) for c in data["context"])})


@dataclass(frozen=True)
class Packet:
    items: tuple[AuditItem, ...]
    key: Mapping[str, str]  # item id -> question id, evaluator-only


def item_id(seed: int, question_id: str) -> str:
    return "a-" + sha256_hex(f"{seed}:audit:{question_id}")[:12]


def sample_questions(records: Sequence[GoldRecord], seed: int, per_stratum: int) -> list[GoldRecord]:
    """Per stratum, one question of each answerability present (in hash order) first, then fill by hash order."""
    chosen: list[GoldRecord] = []
    for stratum in Stratum:
        pool = sorted((r for r in records if r.stratum is stratum), key=lambda r: item_id(seed, r.question_id))
        picked: list[GoldRecord] = []
        seen: set[Answerability] = set()
        for r in pool:
            if r.answerability not in seen and len(picked) < per_stratum:
                seen.add(r.answerability)
                picked.append(r)
        picked += [r for r in pool if r not in picked][: per_stratum - len(picked)]
        chosen += picked
    return chosen


def live_read(record: GoldRecord, world: World, who: Principal) -> Mapping[str, Any] | None:
    """The authorized runtime tool output an annotator would see for a live question (never the expected result)."""
    snap = record.expected_live_snapshot
    if snap is None:
        return None
    mock = LiveMock(world.entities, world.operations, {(snap["case_key"], snap["operation"]): Mode(snap["mode"])})
    got = mock.read(snap["case_key"], snap["operation"], snap["subject_id"], who, record.evaluation_time)
    return {
        "operation": got.operation,
        "status": got.status.value,
        "http_status": got.http_status,
        "read_at": got.read_at,
        "observed_at": got.observed_at,
        "max_age_seconds": got.max_age_seconds,
        "payload": dict(got.payload) if got.payload else None,
    }


def excerpt(doc: Document, query: str) -> str:
    """The lines of a document an annotator needs: its status, its rule clauses, and the lines that match the query.

    A fixed-length prefix would show only the banner and header of an authoritative document, so the lines are
    chosen instead. Lines are kept in document order and cut at ``CONTEXT_CHARS``.
    """
    words = {w for w in _QUERY_WORD.findall(query.lower()) if len(w) > 2}
    body = [line for line in doc.text.split("\n") if line and not line.startswith(("> ", "# "))]

    def priority(line: str) -> tuple[int, int]:
        always = line.startswith(("- Status:", "- Effective", "4.")) and doc.authoritative
        return (0 if always else 1, -len(words & set(_QUERY_WORD.findall(line.lower()))))

    chosen = sorted(range(len(body)), key=lambda i: (priority(body[i]), i))
    kept: list[int] = []
    used = 0
    for index in chosen:
        if used + len(body[index]) + 1 > CONTEXT_CHARS:
            continue
        kept.append(index)
        used += len(body[index]) + 1
    return "\n".join(body[i] for i in sorted(kept))


def _context(index: Bm25, docs: Mapping[str, Document], who: Principal, query: str) -> tuple[ContextDoc, ...]:
    """The best-matching visible documents plus the best-matching ones the principal may not see, in rank order."""
    ranked = [docs[i] for i in index.ranked(query, limit=len(docs))]
    seen = [d for d in ranked if is_visible(d, who.tenant_id, who.role_id)][:CONTEXT_DOCS]
    withheld = [d for d in ranked if not is_visible(d, who.tenant_id, who.role_id)][:WITHHELD_DOCS]
    keep = {d.doc_id for d in (*seen, *withheld)}
    return tuple(
        ContextDoc(d.doc_id, d.title, d.registry_state, is_visible(d, who.tenant_id, who.role_id), excerpt(d, query))
        for d in ranked
        if d.doc_id in keep
    )


def build_packet(
    records: Sequence[GoldRecord], corpus: Sequence[Document], world: World, seed: int, per_stratum: int = 3
) -> Packet:
    """The blinded packet and its evaluator-only key."""
    index = Bm25({d.doc_id: d.text for d in corpus})
    docs = {d.doc_id: d for d in corpus}
    principals = {p.principal_id: p for p in world.entities.principals}
    items: list[AuditItem] = []
    key: dict[str, str] = {}
    for r in sample_questions(records, seed, per_stratum):
        who = principals[r.principal_id]
        context = _context(index, docs, who, r.query)
        ident = item_id(seed, r.question_id)
        key[ident] = r.question_id
        items.append(
            AuditItem(ident, r.query, who.role_id, who.tenant_id, r.evaluation_time, live_read(r, world, who), context)
        )
    return Packet(tuple(sorted(items, key=lambda i: i.item_id)), key)


def prompt_for(item: AuditItem) -> list[dict[str, str]]:
    """The messages sent to the model: the item as shown to the owner, plus the label definitions."""
    docs = "\n".join(
        f"- [{'visible' if c.visible_to_principal else 'NOT visible to this principal'}; {c.registry_state}] "
        f"{c.title}: {c.excerpt}"
        for c in item.context
    )
    live = f"\nLive read: {canonical_json(item.live_read)}" if item.live_read else ""
    user = (
        f"Question: {item.query}\nPrincipal role: {item.principal_role}\nEvaluation time: {item.evaluation_time}"
        f"{live}\nTop documents:\n{docs}\n\n{LABEL_HELP}\n"
        f'Reply as {{"answerability": "<one of {", ".join(LABELS)}>"}}.'
    )
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def parse_label(text: str | None) -> str:
    """The label in a model reply, or ``INVALID``. Free text, extra shapes and unknown labels are all invalid."""
    if not text:
        return "INVALID"
    try:
        data = json.loads(text.strip())
    except ValueError:
        return "INVALID"
    label = data.get("answerability") if isinstance(data, dict) else None
    return label if isinstance(label, str) and label in LABELS else "INVALID"


# --------------------------------------------------------------------------- statistics


def cohens_kappa(a: Sequence[str], b: Sequence[str]) -> float | None:
    """Cohen's kappa for two label lists; ``None`` when chance agreement is total and the statistic is undefined."""
    if len(a) != len(b) or not a:
        raise AuditError("kappa needs two non-empty label lists of equal length")
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b, strict=True)) / n
    ca, cb = Counter(a), Counter(b)
    expected = sum(ca[label] * cb[label] for label in set(ca) | set(cb)) / (n * n)
    return None if expected == 1 else (observed - expected) / (1 - expected)


@dataclass(frozen=True)
class AuditReport:
    items: int
    owner_labelled: int
    llm_labelled: int
    llm_invalid: int
    owner_vs_gold: float | None
    llm_vs_gold: float | None
    owner_vs_llm: float | None
    kappa_owner_llm: float | None
    kappa_owner_gold: float | None
    evidence_checks: Mapping[str, int]
    disagreements: tuple[Mapping[str, Any], ...]
    status: str

    def to_dict(self) -> dict[str, Any]:
        data = dict(self.__dict__)
        data["disagreements"] = [dict(d) for d in self.disagreements]
        return data


def _rate(a: Mapping[str, str], b: Mapping[str, str]) -> float | None:
    shared = sorted(set(a) & set(b))
    return sum(a[i] == b[i] for i in shared) / len(shared) if shared else None


def _kappa(a: Mapping[str, str], b: Mapping[str, str]) -> float | None:
    shared = sorted(set(a) & set(b))
    return cohens_kappa([a[i] for i in shared], [b[i] for i in shared]) if shared else None


def _status(items: int, owner: int, llm: int) -> str:
    if owner == 0:
        return "PENDING_OWNER_LABELS"
    if llm == 0:
        return "PENDING_MODEL_LABELS"
    return "COMPLETE" if owner >= items and llm >= items else "PARTIAL"


def summarise(
    gold: Mapping[str, str], owner: Mapping[str, str], llm: Mapping[str, str], evidence: Mapping[str, str]
) -> AuditReport:
    """Agreement figures. A pair is computed over the items both sides labelled validly, and the counts are reported."""
    valid_llm = {k: v for k, v in llm.items() if v in LABELS}
    disputes = tuple(
        {"item_id": i, "gold": gold[i], "owner": owner.get(i), "llm": llm.get(i)}
        for i in sorted(gold)
        if (i in owner and owner[i] != gold[i]) or (i in valid_llm and valid_llm[i] != gold[i])
    )
    return AuditReport(
        items=len(gold),
        owner_labelled=len(owner),
        llm_labelled=len(valid_llm),
        llm_invalid=len(llm) - len(valid_llm),
        owner_vs_gold=_rate(owner, gold),
        llm_vs_gold=_rate(valid_llm, gold),
        owner_vs_llm=_rate(owner, valid_llm),
        kappa_owner_llm=_kappa(owner, valid_llm),
        kappa_owner_gold=_kappa(owner, gold),
        evidence_checks=dict(Counter(evidence.values())),
        disagreements=disputes,
        status=_status(len(gold), len(owner), len(valid_llm)),
    )


# --------------------------------------------------------------------------- files and the model pass


def audit_folder(root: Path) -> Path:
    return root / "generator" / "audit"


def write_packet(root: Path, packet: Packet, records: Sequence[GoldRecord]) -> Path:
    """Write the blinded packet and the evaluator-only key under the generator namespace."""
    folder = audit_folder(root)
    folder.mkdir(parents=True, exist_ok=True)
    lines = "".join(canonical_json(i.to_dict()) + "\n" for i in packet.items)
    (folder / "packet.jsonl").write_text(lines, encoding="utf-8")
    by_id = {r.question_id: r for r in records}
    key = {
        ident: {
            "question_id": qid,
            "answerability": by_id[qid].answerability.value,
            "cited": [f"{c.doc_id}#{c.clause_id}" for s in by_id[qid].slots for c in s.alternatives],
            "claims": list(by_id[qid].required_claims),
            "gold_sha256": digest_of(by_id[qid].to_dict()),
        }
        for ident, qid in sorted(packet.key.items())
    }
    (folder / "key.json").write_text(canonical_json(key) + "\n", encoding="utf-8")
    (folder / "worksheet.md").write_text(worksheet(packet.items), encoding="utf-8")
    template = folder / "owner_labels.jsonl"
    if not template.exists():  # never overwrite the owner's work
        blank = "".join(
            canonical_json(
                {
                    "item_id": i.item_id,
                    "answerability": "",
                    "evidence_check": "",
                    "gold_sha256": key[i.item_id]["gold_sha256"],
                }
            )
            + "\n"
            for i in packet.items
        )
        template.write_text(blank, encoding="utf-8")
    return folder


def worksheet(items: Sequence[AuditItem]) -> str:
    """The packet as readable text for the owner, with the label choices stated once at the top."""
    lines = [
        "# Label audit worksheet",
        "",
        f"Labels: {', '.join(LABELS)}.",
        "",
        LABEL_HELP,
        "",
        "Fill `owner_labels.jsonl` next to this file: label every item, then open `key.json` for the evidence check.",
    ]
    for number, item in enumerate(items, start=1):
        lines += ["", f"## {number}. {item.item_id}", "", f"Question: {item.query}", ""]
        lines.append(
            f"Principal: {item.principal_role} at {item.principal_tenant}; evaluated at {item.evaluation_time}"
        )
        if item.live_read:
            lines.append(f"Live read: {canonical_json(item.live_read)}")
        for c in item.context:
            access = "visible" if c.visible_to_principal else "NOT visible to this principal"
            lines += ["", f"- {c.title} ({c.registry_state}; {access})", "", "  " + c.excerpt.replace("\n", "\n  ")]
    return "\n".join(lines) + "\n"


def load_packet(root: Path) -> list[AuditItem]:
    text = (audit_folder(root) / "packet.jsonl").read_text(encoding="utf-8")
    return [AuditItem.from_dict(json.loads(line)) for line in text.splitlines()]


def read_labels(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {row["item_id"]: row for row in rows}


def assignment_for(items: Sequence[AuditItem], settings: GeneratorSettings, seed: int) -> dict[str, str]:
    """Spread the items evenly over the approved models, fixed before any call (BADR-0015)."""
    per_model = -(-len(items) // len(settings.models))
    even = replace(settings, token_budgets={m: per_model * TOKENS_PER_ITEM for m in settings.models})
    plan = assign_models([_question_id(i) for i in items], even, seed=seed, tokens_per_question=TOKENS_PER_ITEM)
    if plan.unassigned:
        raise AuditError("not every audit item fits the model budgets")
    return dict(plan.assigned)


def _question_id(item: AuditItem) -> str:
    return "q-" + sha256_hex(item.item_id)[:16]


def run_llm_pass(items: Sequence[AuditItem], pool: GeneratorPool) -> dict[str, str]:
    """One call per item through the generator pool. A failed call is recorded as ``INVALID`` and never retried here."""
    labels: dict[str, str] = {}
    for item in items:
        try:
            result = pool.complete(
                _question_id(item),
                prompt_for(item),
                arm_id="audit",
                json_output=True,
            )
        except (GenerationError, TransientInfrastructureError):
            labels[item.item_id] = "INVALID"
        else:
            labels[item.item_id] = parse_label(result.text)
    return labels


def prompt_digest(item: AuditItem) -> str:
    return digest_of(prompt_for(item))


def calls_used(folder: Path) -> int:
    """Provider calls already recorded by any pass under ``folder`` (the budget is cumulative)."""
    return sum(len(path.read_text(encoding="utf-8").splitlines()) for path in sorted(folder.rglob("llm_calls.jsonl")))


def build_report(root: Path) -> AuditReport:
    folder = audit_folder(root)
    key = json.loads((folder / "key.json").read_text(encoding="utf-8"))
    gold = {ident: info["answerability"] for ident, info in key.items()}
    owner_rows = read_labels(folder / "owner_labels.jsonl")
    llm_rows = read_labels(folder / "llm_labels.jsonl")
    owner = {i: r["answerability"] for i, r in owner_rows.items() if r["answerability"]}  # blank rows are not labels
    if any(label not in LABELS for label in owner.values()):
        raise AuditError("an owner label is not one of the six answerability labels")
    llm = {i: r["answerability"] for i, r in llm_rows.items()}
    evidence = {i: r["evidence_check"] for i, r in owner_rows.items() if r.get("evidence_check") in EVIDENCE_CHECKS}
    if any(r.get("evidence_check") not in (*EVIDENCE_CHECKS, "", None) for r in owner_rows.values()):
        raise AuditError("an evidence check is not sufficient, partial or insufficient")
    if (set(owner) | set(llm)) - set(gold):
        raise AuditError("labels name an item that is not in the packet")
    stale = [i for i, r in owner_rows.items() if r["answerability"] and r.get("gold_sha256") != key[i]["gold_sha256"]]
    if stale:
        raise AuditError("an owner label was made against gold that has since changed or lacks its gold_sha256")
    return summarise(gold, owner, llm, evidence)


def _llm_command(root: Path, env_file: Path, seed: int) -> int:
    items = load_packet(root)
    folder = audit_folder(root)
    if (folder / "llm_labels.jsonl").exists():
        print("REFUSED: a model pass is already recorded; move it into its own folder first", file=sys.stderr)
        return 2
    allowed = min(MAX_LLM_CALLS, MAX_TOTAL_LLM_CALLS - calls_used(folder))
    if len(items) > allowed:
        print(f"REFUSED: {len(items)} items but BADR-0019 leaves {allowed} calls for this pass", file=sys.stderr)
        return 2
    settings = load_benchmark_config(CONFIG).generator
    try:
        pool = GeneratorPool.live(
            settings,
            env_file,
            enabled=True,
            assignment=assignment_for(items, settings, seed),
            call_budget=allowed,
            record_path=folder / "llm_calls.jsonl",
        )
    except GenerationError as exc:
        print(f"REFUSED: {exc.code}", file=sys.stderr)
        return 2
    labels = run_llm_pass(items, pool)
    digests = {item.item_id: prompt_digest(item) for item in items}
    rows = "".join(
        canonical_json(
            {"item_id": i, "answerability": label, "prompt_version": PROMPT_VERSION, "prompt_sha256": digests[i]}
        )
        + "\n"
        for i, label in sorted(labels.items())
    )
    (folder / "llm_labels.jsonl").write_text(rows, encoding="utf-8")
    print(
        f"llm: {sum(v in LABELS for v in labels.values())}/{len(labels)} valid labels; {len(pool.records)} calls made"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("command", choices=("llm", "report"))
    parser.add_argument("--root", type=Path, required=True, help="a generated fixture directory")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--enable-live", action="store_true", help="explicit permission to call the provider")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    options = parser.parse_args(argv)
    if options.command == "report":
        report = build_report(options.root)
        (audit_folder(options.root) / "audit_report.json").write_text(
            canonical_json(report.to_dict()) + "\n", encoding="utf-8"
        )
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
        return 0
    if not options.enable_live:
        print(
            "REFUSED: the model pass needs --enable-live; no credential was read and no request was sent",
            file=sys.stderr,
        )
        return 2
    return _llm_command(options.root, options.env_file, options.seed)


if __name__ == "__main__":
    sys.exit(main())
