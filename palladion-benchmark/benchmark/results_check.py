"""Validate a Track A run directory (B04-T04.03).

A run directory is accepted only if it is complete, internally consistent and clean:

* **Schema and hashes**: every arm has a verified manifest that names this run, K, the evidence budget and the metadata
  condition; the ledger parses, matches its manifests and holds exactly one final record for each arm and question; the
  manifests' source and gold digests equal the published corpus and the annotation file on disk.
* **Budgets**: no final record returns more than K candidates or more than the budget's words, with ranks 1..n.
* **Reads**: the read log names the published corpus and one runnable split's own annotation file, never the locked test
  namespace.
* **Leakage**: no JSON key in any artifact names gold, and none of the gold text the arms must not see (required and
  forbidden claims, the abstention note, the policy outcome) appears in any artifact.
* **Secrets**: no artifact matches a credential pattern or any value supplied by the caller (a ``.env``, bearer tokens).
* **Run states**: every non-OK final record carries a code, so an arm that did not run appears with a reason.

``validate_run`` returns findings; an empty list means the directory is clean. A finding names the rule and the file or
record, never the matched text.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from benchmark.adapters.common import count_words
from benchmark.contracts import ContractError, RunStatus, gold_like_key
from benchmark.fixtures.manifest import Layout, Namespace, manifest_digest
from benchmark.fixtures.questions import GoldRecord
from benchmark.run_manifest import ManifestError, read_verified
from benchmark.runner import RunLedger, RunnerError
from benchmark.secret_scan import scan_text
from benchmark.track_a import RUNNABLE_SPLITS, TrackAError, read_annotations

MIN_GOLD_TEXT = 12
# A manifest is an evaluator-side record: it holds the gold file's digest by design (never the arm-visible view).
MANIFEST_EVALUATOR_KEYS = frozenset({"gold_manifest_sha256"})
REQUIRED_FILES = ("ledger.jsonl", "run_config.json", "read_log.json", "summary.json")


@dataclass(frozen=True)
class Finding:
    rule: str
    where: str

    def render(self) -> str:
        return f"{self.where}: {self.rule}"


def _walk_keys(value: Any) -> Iterator[str]:
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key)
            yield from _walk_keys(item)
    elif isinstance(value, list | tuple):
        for item in value:
            yield from _walk_keys(item)


def gold_texts(records: Iterable[GoldRecord]) -> list[str]:
    """Free text of the gold that an artifact must never contain."""
    texts: set[str] = set()
    for record in records:
        texts.update(record.required_claims)
        texts.update(record.forbidden_claims)
        for extra in (record.abstention_note, record.policy_outcome):
            if extra:
                texts.add(extra)
    long = [t for t in texts if len(t) >= MIN_GOLD_TEXT]
    escaped = [json.dumps(t)[1:-1] for t in long]  # how the same text reads inside a JSON file
    return sorted({*long, *escaped})


def _load_json(path: Path, findings: list[Finding]) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        findings.append(Finding("file is missing or is not valid JSON", path.name))
        return None


def validate_run(
    run_dir: Path,
    *,
    root: Path,
    secret_values: Sequence[str] = (),
) -> list[Finding]:
    """Check one run directory against the snapshot ``root`` (published namespace and the split's annotation file)."""
    findings: list[Finding] = []
    missing = [name for name in REQUIRED_FILES if not (run_dir / name).is_file()]
    findings += [Finding("required file is missing", name) for name in missing]
    config = _load_json(run_dir / "run_config.json", findings) if "run_config.json" not in missing else None
    read_log = _load_json(run_dir / "read_log.json", findings) if "read_log.json" not in missing else None
    if config is None or read_log is None or "ledger.jsonl" in missing:
        return findings
    findings += _check_reads(read_log, root)
    split = str(config.get("split"))
    if split not in RUNNABLE_SPLITS:
        return [*findings, Finding("the split is not runnable by Track A", "run_config.json")]
    try:
        records, log = read_annotations(root, split)
    except TrackAError as exc:
        return [*findings, Finding(f"the annotation file cannot be read: {exc}", "read_log.json")]
    arms = [str(a) for a in config.get("arms", [])]
    findings += _check_manifests(run_dir, config, arms, log.annotation_sha256, log.published_manifest_sha256)
    findings += _check_ledger(run_dir, config, arms, records)
    findings += _check_leakage(run_dir, records, secret_values)
    return findings


def _check_reads(read_log: Mapping[str, Any], root: Path) -> list[Finding]:
    findings: list[Finding] = []
    split = str(read_log.get("split"))
    if (
        read_log.get("test_namespace_read") is not False
        or read_log.get("annotation_namespace") == Namespace.TEST_ANNOTATIONS
    ):
        findings.append(Finding("the run read the locked test namespace", "read_log.json"))
    if split not in RUNNABLE_SPLITS or read_log.get("annotation_file") != f"questions_{split}.jsonl":
        findings.append(Finding("the run read an annotation file other than its own split's", "read_log.json"))
    published = Layout(root).path(Namespace.PUBLISHED)
    if read_log.get("published_manifest_sha256") != manifest_digest(published):
        findings.append(Finding("the published corpus changed since the run read it", "read_log.json"))
    return findings


def _check_manifests(
    run_dir: Path, config: Mapping[str, Any], arms: Sequence[str], gold_sha: str, source_sha: str
) -> list[Finding]:
    findings: list[Finding] = []
    for arm in arms:
        path = run_dir / f"manifest-{arm}.json"
        try:
            manifest = read_verified(path)
        except (ManifestError, ContractError, OSError, ValueError):
            findings.append(Finding("the manifest is missing or does not verify", path.name))
            continue
        if manifest.arm != arm or manifest.run_id != config.get("run_id"):
            findings.append(Finding("the manifest names another arm or run", path.name))
        if manifest.gold_manifest_sha256 != gold_sha or manifest.source_manifest_sha256 != source_sha:
            findings.append(Finding("the manifest was written against a different gold file or corpus", path.name))
        recorded = manifest.retrieval_config
        for key, name in (("k", "k"), ("budget_words", "budget_words"), ("metadata_condition", "metadata_condition")):
            if recorded.get(key) != config.get(name):
                findings.append(Finding(f"the manifest's {key} differs from the run configuration", path.name))
    return findings


def _check_ledger(
    run_dir: Path, config: Mapping[str, Any], arms: Sequence[str], records: Sequence[GoldRecord]
) -> list[Finding]:
    findings: list[Finding] = []
    try:
        ledger = RunLedger(run_dir / "ledger.jsonl")
        ledger.verify_complete([(arm, r.question_id) for arm in arms for r in records])
    except RunnerError as exc:
        return [Finding(f"the ledger is not a complete record of the run: {str(exc)[:120]}", "ledger.jsonl")]
    digests = {}
    for arm in arms:
        try:
            digests[arm] = read_verified(run_dir / f"manifest-{arm}.json").digest()
        except (ManifestError, ContractError, OSError, ValueError):
            continue  # already reported by the manifest check
    k, budget = int(config.get("k", 0)), int(config.get("budget_words", 0))
    for record in ledger.records:
        where = f"ledger.jsonl {record.arm}/{record.question_id}"
        if record.arm in digests and record.manifest_sha256 != digests[record.arm]:
            findings.append(Finding("the record does not match its arm's manifest", where))
        if not record.is_final:
            continue
        if record.status is not RunStatus.OK:
            if not record.code:
                findings.append(Finding("a run state without a reason code", where))
            continue
        payload = record.payload
        if not isinstance(payload, list):
            findings.append(Finding("an OK record whose payload is not a candidate list", where))
            continue
        words = sum(count_words(str(c.get("content", ""))) for c in payload)
        if len(payload) > k or words > budget:
            findings.append(
                Finding(f"the bundle exceeds K or the evidence budget ({len(payload)} items, {words} words)", where)
            )
        if [c.get("rank") for c in payload] != list(range(1, len(payload) + 1)):
            findings.append(Finding("candidate ranks are not 1..n in order", where))
    return findings


def _check_leakage(run_dir: Path, records: Sequence[GoldRecord], secret_values: Sequence[str]) -> list[Finding]:
    findings: list[Finding] = []
    texts = gold_texts(records)
    values = tuple(v for v in secret_values if v)
    for path in sorted(p for p in run_dir.rglob("*") if p.is_file()):
        raw = path.read_text(encoding="utf-8", errors="replace")
        if path.suffix in (".json", ".jsonl"):
            documents = raw.splitlines() if path.suffix == ".jsonl" else [raw]
            for document in documents:
                try:
                    keys = set(_walk_keys(json.loads(document)))
                except ValueError:
                    continue
                if path.name.startswith("manifest-"):
                    keys -= MANIFEST_EVALUATOR_KEYS
                if any(gold_like_key(key) for key in keys):
                    findings.append(Finding("a JSON key names gold", path.name))
                    break
        if any(text in raw for text in texts):
            findings.append(Finding("gold text appears in an artifact", path.name))
        findings += [
            Finding(f"secret scan: {f.rule}", f"{path.name}:{f.line}")
            for f in scan_text(raw, path.name, env_values=values)
        ]
    return findings
