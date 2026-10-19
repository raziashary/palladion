"""Score a run directory and the control arms that prove the scorer separates good from bad (B03-T07.01, BADR-0024).

``score_run`` reads a ledger, each arm's immutable manifest, the gold annotations and the published corpus. Every final
ledger record becomes a ``PairScore``: a scored retrieval, or a run state with no metric values. Nothing is dropped, and
a non-completed pair is never turned into a zero here; the tables decide how it enters each accounting.

The scorer refuses to run on an inconsistent run: a gold file that does not match the digest the manifests recorded,
a manifest that does not match the ledger, or a ledger with a missing, extra or duplicated final record.

Control arms live in this module and nowhere in the production registry. The perfect arm quotes the gold clauses, the
empty arm returns nothing, and the shuffled arm returns another question's gold evidence.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from benchmark.contracts import (
    ContractError,
    EvidenceCandidate,
    RetrievalRequest,
    RunStatus,
    Track,
)
from benchmark.eval.evidence_sets import score_sets
from benchmark.eval.normalize import PublishedCorpus, align_all, read_candidates
from benchmark.eval.retrieval import score_provenance, score_ranking
from benchmark.fixtures import sha256_hex
from benchmark.fixtures.manifest import manifest_digest, verify_published
from benchmark.fixtures.questions import LIVE_PREFIX, Citation, GoldRecord, SlotState, read_gold
from benchmark.registry import ArmRegistry, ArmSpec, Capability, Declaration, Support
from benchmark.run_manifest import read_verified
from benchmark.runner import LedgerRecord, RunLedger, RunnerError

# Metrics where a larger value is worse. A pair that did not complete cannot be credited with a harm, so these are
# summarised over completed pairs only (the tables count the rest) and never filled in as zero.
HARM_METRICS = frozenset({"wrong_vintage_intrusion", "forbidden_source_exposure", "authority_confusion"})
INVALID_PAYLOAD = "INVALID_PAYLOAD"


class ScoreRunError(RunnerError):
    """The run cannot be scored: its inputs disagree with each other."""


@dataclass(frozen=True)
class PairScore:
    """One ledger final record, scored or kept as a state.

    ``metrics`` holds a value for each metric that applies to this question and could be computed from the return.
    ``applicable`` names the metrics the gold says apply, so a pair that did not complete still shows what it owed.
    """

    arm: str
    question_id: str
    stratum: str
    scenario_family: str
    status: RunStatus
    code: str | None
    metrics: Mapping[str, float]
    applicable: frozenset[str]
    alignment_only: Mapping[str, float]
    forbidden_exposures: int
    authority_confusions: int
    wrong_vintages: int
    returned: int
    duration_ms: float | None


@dataclass(frozen=True)
class RunScore:
    run_id: str
    k: int
    gold_sha256: str
    pairs: tuple[PairScore, ...]
    ledger_records: tuple[LedgerRecord, ...]
    withdrawn: Mapping[str, str] = field(default_factory=dict)

    def arm_pairs(self, arm: str) -> list[PairScore]:
        return [p for p in self.pairs if p.arm == arm]

    @property
    def arms(self) -> list[str]:
        return sorted({p.arm for p in self.pairs})


# --------------------------------------------------------------------------- inputs


def gold_digest(gold_path: Path) -> str:
    return sha256_hex(gold_path.read_bytes().decode("utf-8"))


def check_manifests(
    ledger: RunLedger, manifests: Mapping[str, Path], gold_sha256: str, source_sha256: str, k: int, run_id: str | None
) -> str:
    """Each arm's manifest must verify, name this run and this gold, and be the one the ledger recorded."""
    arms = {r.arm for r in ledger.records}
    if set(manifests) != arms:
        raise ScoreRunError(f"manifests {sorted(manifests)} do not match the ledger's arms {sorted(arms)}")
    run_ids = {r.run_id for r in ledger.records}
    if len(run_ids) != 1 or (run_id is not None and run_ids != {run_id}):
        raise ScoreRunError("the ledger holds records of more than one run, or of a different run than expected")
    for arm, path in manifests.items():
        manifest = read_verified(path)
        if manifest.arm != arm or manifest.run_id not in run_ids:
            raise ScoreRunError(f"manifest {path.name} names a different arm or run")
        if manifest.gold_manifest_sha256 != gold_sha256:
            raise ScoreRunError(f"manifest {path.name} was written against a different gold file")
        recorded_k = manifest.retrieval_config.get("k")
        if recorded_k != k:
            raise ScoreRunError(f"manifest {path.name} records K={recorded_k}, but the run is scored at K={k}")
        if manifest.source_manifest_sha256 != source_sha256:
            raise ScoreRunError(f"manifest {path.name} was written against a different published corpus")
        recorded = {r.manifest_sha256 for r in ledger.records if r.arm == arm}
        if recorded != {manifest.digest()}:
            raise ScoreRunError(f"the ledger records for {arm} do not match its manifest")
    return next(iter(run_ids))


# --------------------------------------------------------------------------- scoring


def _applicable(
    record: GoldRecord, corpus: PublishedCorpus, role_id: str, kinds: Mapping[str, str], k: int
) -> frozenset[str]:
    """Metrics the gold says apply: those a return of nothing can still be scored on."""
    empty = _metrics(record, [], corpus, role_id, kinds, k)[0]
    return frozenset(empty)


def _metrics(
    record: GoldRecord,
    candidates: Sequence[EvidenceCandidate],
    corpus: PublishedCorpus,
    role_id: str,
    kinds: Mapping[str, str],
    k: int,
) -> tuple[dict[str, float], dict[str, float], int, int, int]:
    alignments = align_all(list(candidates), corpus)
    ranking = score_ranking(record, alignments, k)
    sets = score_sets(record, alignments, k)
    prov = score_provenance(record, candidates, alignments, corpus, role_id=role_id, kinds=kinds, k=k)
    raw: dict[str, float | None] = {
        "precision_at_k": ranking.precision,
        "recall_at_k": ranking.recall,
        "mrr": ranking.mrr,
        "ndcg_at_k": ranking.ndcg,
        "map_at_k": ranking.map,
        "success_at_k": ranking.success,
        "slot_coverage_at_k": sets.slot_coverage,
        "complete_set_at_k": sets.complete_set,
        "valid_source_recall": prov.valid_source_recall,
        "wrong_vintage_intrusion": prov.wrong_vintage_intrusion,
        "forbidden_source_exposure": float(prov.forbidden_exposure_count > 0),
        "authority_confusion": float(prov.authority_confusion_count > 0),
        "exception_recall": prov.exception_recall,
        "conflicting_pair_recall": prov.conflicting_pair_recall,
        "citation_locator_resolution": prov.citation_locator_resolution,
        "evidence_density": prov.evidence_density,
        "evidence_token_efficiency": prov.evidence_token_efficiency,
    }
    alignment_only = {
        name: value
        for name, value in (
            ("alignment_slot_coverage", sets.alignment_slot_coverage),
            ("alignment_complete_set", sets.alignment_complete_set),
        )
        if value is not None
    }
    metrics = {name: value for name, value in raw.items() if value is not None}
    return (
        metrics,
        alignment_only,
        prov.forbidden_exposure_count,
        prov.authority_confusion_count,
        prov.wrong_vintage_count or 0,
    )


def score_pair(
    record: GoldRecord,
    ledger_record: LedgerRecord,
    corpus: PublishedCorpus,
    role_id: str,
    kinds: Mapping[str, str],
    k: int,
) -> PairScore:
    applicable = _applicable(record, corpus, role_id, kinds, k)
    status, code = ledger_record.status, ledger_record.code
    metrics: dict[str, float] = {}
    alignment_only: dict[str, float] = {}
    exposed = confused = wrong = returned = 0
    if status is RunStatus.OK:
        try:
            if not isinstance(ledger_record.payload, list):
                raise ContractError("a retrieval payload is a list of candidates")
            candidates = read_candidates(ledger_record.payload)
        except (ContractError, KeyError, TypeError, ValueError):
            status, code = RunStatus.INVALID_RUN, INVALID_PAYLOAD
        else:
            returned = sum(1 for c in candidates if c.rank <= k)
            metrics, alignment_only, exposed, confused, wrong = _metrics(record, candidates, corpus, role_id, kinds, k)
    return PairScore(
        arm=ledger_record.arm,
        question_id=record.question_id,
        stratum=record.stratum.value,
        scenario_family=record.scenario_family,
        status=status,
        code=code,
        metrics=metrics,
        applicable=applicable,
        alignment_only=alignment_only,
        forbidden_exposures=exposed,
        authority_confusions=confused,
        wrong_vintages=wrong,
        returned=returned,
        duration_ms=ledger_record.duration_ms,
    )


def score_run(
    *,
    ledger_path: Path,
    manifests: Mapping[str, Path],
    gold_path: Path,
    published_dir: Path,
    roles: Mapping[str, str],
    kinds: Mapping[str, str],
    k: int,
    run_id: str | None = None,
    withdrawn: Mapping[str, str] | None = None,
) -> RunScore:
    """Score every final record of a Track A run. Raises ``ScoreRunError`` (or a gold error) on any inconsistency.

    ``withdrawn`` maps question ids found defective by the label audit to the reason. Those questions still ran (the
    ledger must be complete for them) but leave the scored pairs; they are kept on the result so a report can state
    the denominator and what was left out. An id that is not in the gold is an error, never silently ignored.
    """
    if k < 1:
        raise ScoreRunError("K must be at least 1")
    gold_sha256 = gold_digest(gold_path)
    gold = {r.question_id: r for r in read_gold(gold_path)}
    withdrawn = dict(withdrawn or {})
    unknown = sorted(set(withdrawn) - set(gold))
    if unknown:
        raise ScoreRunError(f"withdrawn question ids are not in the gold: {unknown[:3]}")
    ledger = RunLedger(ledger_path)
    problems = verify_published(published_dir)
    if problems:
        raise ScoreRunError(f"the published corpus does not match its manifest: {problems[:3]}")
    resolved_run = check_manifests(ledger, manifests, gold_sha256, manifest_digest(published_dir), k, run_id)
    arms = sorted(manifests)
    ledger.verify_complete([(arm, q) for arm in arms for q in gold])
    corpus = PublishedCorpus.load(published_dir)
    pairs: list[PairScore] = []
    for ledger_record in ledger.records:
        if not ledger_record.is_final:
            continue
        if ledger_record.question_id in withdrawn:
            continue
        record = gold[ledger_record.question_id]
        if record.principal_id not in roles:
            raise ScoreRunError(f"principal {record.principal_id} has no role in the identity manifest")
        pairs.append(score_pair(record, ledger_record, corpus, roles[record.principal_id], kinds, k))
    return RunScore(
        resolved_run,
        k,
        gold_sha256,
        tuple(sorted(pairs, key=lambda p: (p.arm, p.question_id))),
        ledger.records,
        withdrawn,
    )


# --------------------------------------------------------------------------- control arms


CONTROL_PERFECT = "CTRL-perfect"
CONTROL_EMPTY = "CTRL-empty"
CONTROL_SHUFFLED = "CTRL-shuffled"
CONTROL_IDS = (CONTROL_PERFECT, CONTROL_EMPTY, CONTROL_SHUFFLED)


def control_registry() -> ArmRegistry:
    """A registry holding only the controls. It is never merged into ``default_registry``."""
    registry = ArmRegistry()
    declared = {c: Declaration(Support.UNSUPPORTED, "control arm with no behaviour to verify") for c in Capability}
    for arm_id, name in (
        (CONTROL_PERFECT, "Control: quotes the gold clauses"),
        (CONTROL_EMPTY, "Control: returns nothing"),
        (CONTROL_SHUFFLED, "Control: returns another question's gold evidence"),
    ):
        registry.register(ArmSpec(arm_id, name, (Track.RETRIEVAL_ONLY,), declared))
    return registry


def gold_candidates(record: GoldRecord, corpus: PublishedCorpus) -> list[EvidenceCandidate]:
    """One candidate per required document slot, quoting the first alternative and naming its document and clause."""
    picks: list[Citation] = [
        s.alternatives[0]
        for s in record.slots
        if s.state is SlotState.SATISFIABLE and not s.alternatives[0].doc_id.startswith(LIVE_PREFIX)
    ]
    out: list[EvidenceCandidate] = []
    for rank, citation in enumerate(picks, start=1):
        doc = corpus.docs[citation.doc_id]
        if citation.clause_id == "doc":
            content, locator = doc.text, "doc"
        else:
            start, end = doc.clauses[citation.clause_id]
            content, locator = doc.text[start:end], f"clause:{citation.clause_id}"
        out.append(
            EvidenceCandidate(
                source_version_id=None,
                locator=locator,
                content=content,
                rank=rank,
                native_score=None,
                retrieval_channel="control",
                evidence_path=(),
                native_citation_supported=False,
                additional_metadata={},
                source_document_id=citation.doc_id,
            )
        )
    return out


class ControlArm:
    """A retriever that answers from a table built from gold. It exists to test the scorer, nothing else."""

    def __init__(self, returns: Mapping[str, Sequence[EvidenceCandidate]]) -> None:
        self._returns = {q: list(c) for q, c in returns.items()}

    def build_index(self, source_manifest_uri: str, index_namespace: str) -> None:
        return None

    def retrieve(self, request: RetrievalRequest) -> list[EvidenceCandidate]:
        return list(self._returns.get(request.question_id, ()))[: request.limit]

    def index_stats(self) -> dict[str, Any]:
        return {}


def control_arms(records: Sequence[GoldRecord], corpus: PublishedCorpus) -> dict[str, ControlArm]:
    """The three controls. The shuffled arm answers each question with the next question's gold evidence."""
    ordered = sorted(records, key=lambda r: r.question_id)
    if len(ordered) < 2:
        raise ScoreRunError("the shuffled control needs at least two questions")
    perfect = {r.question_id: gold_candidates(r, corpus) for r in ordered}
    shifted = {r.question_id: perfect[ordered[(i + 1) % len(ordered)].question_id] for i, r in enumerate(ordered)}
    return {
        CONTROL_PERFECT: ControlArm(perfect),
        CONTROL_EMPTY: ControlArm({}),
        CONTROL_SHUFFLED: ControlArm(shifted),
    }


def retrieval_request(record: GoldRecord, *, limit: int, max_evidence_tokens: int) -> RetrievalRequest:
    """The arm-visible view of a gold record: the question, the principal and the clock, nothing else."""
    return RetrievalRequest(
        question_id=record.question_id,
        query=record.query,
        principal_id=record.principal_id,
        corpus_snapshot_id=record.corpus_snapshot_id,
        evaluation_time=record.evaluation_time,
        event_time=record.event_time,
        filters={},
        limit=limit,
        max_evidence_tokens=max_evidence_tokens,
    )


@dataclass(frozen=True)
class Separation:
    """Whether the controls tell apart on one stratum, over the questions the metric applies to."""

    stratum: str
    questions: int
    perfect_vs_empty: bool
    perfect_vs_shuffled: bool


def _mean_metric(score: RunScore, arm: str, owed: set[str], metric: str) -> float | None:
    values = [p.metrics[metric] for p in score.arm_pairs(arm) if p.question_id in owed and metric in p.metrics]
    return sum(values) / len(values) if values else None


def control_separation(score: RunScore, metric: str = "complete_set_at_k") -> list[Separation]:
    """Per stratum: do the perfect, empty and shuffled controls differ? Where no question owes the metric evidence the
    answer is no with zero questions, and a report must say so instead of ranking arms there."""
    out: list[Separation] = []
    for stratum in sorted({p.stratum for p in score.pairs}):
        owed = {p.question_id for p in score.pairs if p.stratum == stratum and metric in p.applicable}
        perfect, empty, shuffled = (
            _mean_metric(score, arm, owed, metric) for arm in (CONTROL_PERFECT, CONTROL_EMPTY, CONTROL_SHUFFLED)
        )
        out.append(
            Separation(
                stratum,
                len(owed),
                perfect is not None and empty is not None and perfect != empty,
                perfect is not None and shuffled is not None and perfect != shuffled,
            )
        )
    return out
