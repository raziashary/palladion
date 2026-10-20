"""Score a Track B run directory: every final ledger record becomes a scored answer or a kept run state (B05-T08.01).

The scorer trusts nothing the answer says about itself. It rebuilds each response from the ledger, derives what the
generator was shown from the delivered ids the run recorded, and scores citations, claims, policy and abstention against
the stored answer-gold. A pair that did not complete stays in the table as its run state; it is not scored and not a
zero. Intention-to-treat and conditional figures are produced side by side (BADR-0028 item 2).
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from benchmark.contracts import CaseResponse, ContractError, RunStatus
from benchmark.eval.abstention import (
    AbstentionSummary,
    PairAbstention,
    Sweep,
    expected_loss_per_100,
    loss_sweep,
    score_abstention,
    summarize_abstention,
)
from benchmark.eval.answer_case import AnswerCase
from benchmark.eval.citations import CitationScore, CitationStatus, Labels, score_citations
from benchmark.eval.claims import ClaimScore, EndpointItem, Endpoints, endpoints_from, score_claims
from benchmark.eval.evidence_sets import Unit
from benchmark.eval.normalize import DOC_UNIT, PublishedCorpus
from benchmark.eval.policy import PolicyScore, PolicySummary, score_policy, summarize_policy
from benchmark.eval.score_run import ScoreRunError, check_manifests
from benchmark.fixtures.answer_gold import (
    AnswerGold,
    AnswerGoldError,
    answer_gold_path,
    check_matches_questions,
    read_answer_gold,
)
from benchmark.fixtures.manifest import Layout, Namespace, Split, manifest_digest, read_identity, verify_published
from benchmark.fixtures.questions import Answerability, GoldRecord
from benchmark.runner import RunLedger
from benchmark.track_a import RUNNABLE_SPLITS, read_annotations
from benchmark.track_b import CONTROLLED_QA, asked_records, mixed_model_questions, read_prompt_ids

INVALID_ANSWER = "INVALID_ANSWER"
DELIVERED_MISMATCH = "DELIVERED_MISMATCH"


@dataclass(frozen=True)
class AnswerPair:
    arm: str
    question_id: str
    stratum: str
    scenario_family: str
    answerability: str
    status: RunStatus
    code: str | None
    flags: tuple[str, ...]
    mixed_model: bool
    citations: CitationScore | None
    claims: ClaimScore | None
    policy: PolicyScore | None
    abstention: PairAbstention | None

    @property
    def scored(self) -> bool:
        return self.abstention is not None


@dataclass(frozen=True)
class AnswerRunScore:
    run_id: str
    k: int
    gold_sha256: str
    answer_gold_sha256: str
    pairs: tuple[AnswerPair, ...]
    withdrawn: Mapping[str, str]
    mixed_model_questions: tuple[str, ...]
    unassigned: tuple[str, ...]
    live: bool
    generator_pool: str
    single_model: bool

    def arm_pairs(self, arm: str) -> list[AnswerPair]:
        return [p for p in self.pairs if p.arm == arm]

    @property
    def arms(self) -> list[str]:
        return sorted({p.arm for p in self.pairs})


def delivered_from_ids(ids: Sequence[str]) -> frozenset[Unit]:
    """Units the run recorded as shown to the generator: a clause id credits its clause and its document."""
    units: set[Unit] = set()
    for text in ids:
        doc, _, clause = text.partition("#")
        units.add((doc, DOC_UNIT))
        if clause:
            units.add((doc, clause))
    return frozenset(units)


def score_pair(
    record: GoldRecord,
    gold: AnswerGold,
    arm: str,
    status: RunStatus,
    code: str | None,
    payload: object,
    flags: tuple[str, ...],
    corpus: PublishedCorpus,
    role_id: str,
    mixed: bool,
    labels: Labels | None,
    shown: list[str] | None,
) -> AnswerPair:
    def pair(
        run_status: RunStatus,
        run_code: str | None,
        citations: CitationScore | None = None,
        claims: ClaimScore | None = None,
        policy: PolicyScore | None = None,
        abstention: PairAbstention | None = None,
    ) -> AnswerPair:
        return AnswerPair(
            arm, record.question_id, record.stratum.value, record.scenario_family, record.answerability.value,
            run_status, run_code, flags, mixed, citations, claims, policy, abstention,
        )  # fmt: skip

    if status is not RunStatus.OK:
        return pair(status, code)
    try:
        response = CaseResponse.from_payload(payload)
        if response.question_id != record.question_id:
            raise ContractError("the answer is for another question")
    except (ContractError, KeyError, TypeError, ValueError):
        return pair(RunStatus.INVALID_RUN, INVALID_ANSWER)
    if shown is None or list(response.used_evidence_ids) != shown:
        # What was delivered is read from the prompt the run kept, never from the answer's own claim about it.
        return pair(RunStatus.INVALID_RUN, DELIVERED_MISMATCH)
    case = AnswerCase(record, gold, status, response, delivered_from_ids(shown), role_id, code, arm)
    citations = score_citations(case, corpus, labels)
    claims = score_claims(case, citations)
    policy = score_policy(case, claims, corpus)
    return pair(status, code, citations, claims, policy, score_abstention(case, claims, citations, policy))


def score_answer_run(
    *,
    run_dir: Path,
    root: Path,
    withdrawn: Mapping[str, str] | None = None,
    labels: Labels | None = None,
) -> AnswerRunScore:
    """Score a Track B run. Raises ``ScoreRunError`` when its inputs disagree with each other."""
    withdrawn = dict(withdrawn or {})
    try:
        config = json.loads((run_dir / "run_config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ScoreRunError("run_config.json is missing or unreadable") from None
    if config.get("track") != CONTROLLED_QA:
        raise ScoreRunError("this is not a Track B run")
    split = str(config["split"])
    if split not in RUNNABLE_SPLITS:
        raise ScoreRunError("the split is not runnable by Track B")
    if sorted(config.get("withdrawn", [])) != sorted(withdrawn):
        raise ScoreRunError("the withdrawn questions of the run and of the scorer differ")
    records, read_log = read_annotations(root, split)
    layout = Layout(root)
    published = layout.path(Namespace.PUBLISHED)
    problems = verify_published(published)
    if problems:
        raise ScoreRunError(f"the published corpus does not match its manifest: {problems[:3]}")
    try:
        golds = read_answer_gold(answer_gold_path(root, Split(split)))
        check_matches_questions(golds, records)
    except (AnswerGoldError, OSError) as exc:
        raise ScoreRunError(f"the answer-gold cannot be used: {exc}") from exc
    gold_by_id = {g.question_id: g for g in golds}
    chosen = asked_records(records, withdrawn, config.get("asked"))
    unknown = sorted(set(withdrawn) - {r.question_id for r in records})
    if unknown:
        raise ScoreRunError(f"withdrawn question ids are not in the gold: {unknown[:3]}")
    arms = [str(a) for a in config["arms"]]
    k = int(config["k"])
    ledger = RunLedger(run_dir / "ledger.jsonl")
    check_manifests(
        ledger, {arm: run_dir / f"manifest-{arm}.json" for arm in arms}, read_log.annotation_sha256,
        manifest_digest(published), k, str(config["run_id"]),
    )  # fmt: skip
    ledger.verify_complete([(arm, r.question_id) for arm in arms for r in chosen])
    corpus = PublishedCorpus.load(published)
    roles = {p.principal_id: p.role_id for p in read_identity(published).principals}
    mixed = set(mixed_model_questions(run_dir / "generation_records.jsonl"))
    prompts = read_prompt_ids(run_dir / "prompts.jsonl")
    answer_gold_sha256 = _digest(answer_gold_path(root, Split(split)))
    if config.get("answer_targets_sha256") != answer_gold_sha256:
        raise ScoreRunError("the answer-gold file changed since the run")
    by_id = {r.question_id: r for r in records}
    pairs = []
    for entry in ledger.records:
        if not entry.is_final:
            continue
        record = by_id[entry.question_id]
        if record.principal_id not in roles:
            raise ScoreRunError(f"principal {record.principal_id} has no role in the identity manifest")
        pairs.append(
            score_pair(
                record,
                gold_by_id[entry.question_id],
                entry.arm,
                entry.status,
                entry.code,
                entry.payload,
                tuple(entry.flags),
                corpus,
                roles[record.principal_id],
                entry.question_id in mixed,
                labels,
                prompts.get((entry.question_id, entry.arm)),
            )
        )
    return AnswerRunScore(
        run_id=str(config["run_id"]),
        k=k,
        gold_sha256=read_log.annotation_sha256,
        answer_gold_sha256=answer_gold_sha256,
        pairs=tuple(sorted(pairs, key=lambda p: (p.arm, p.question_id))),
        withdrawn=withdrawn,
        mixed_model_questions=tuple(sorted(mixed)),
        unassigned=tuple(str(q) for q in config.get("unassigned", [])),
        live=bool(config.get("live")),
        generator_pool=str(config.get("generator_pool")),
        single_model=bool(config.get("single_model")),
    )


def _digest(path: Path) -> str:
    from benchmark.fixtures import sha256_hex

    return sha256_hex(path.read_bytes().decode("utf-8"))


# --------------------------------------------------------------------------- per-arm summaries


@dataclass(frozen=True)
class CitationTotals:
    pairs: int
    citations: int
    valid: int
    fabricated: int
    outside_bundle: int
    inaccessible: int
    unauthoritative: int
    inapplicable: int
    source_requiring_claims: int
    supported_claims: int
    uncited_claims: int
    precision: float | None
    recall: float | None
    fabrication_rate: float | None
    validity: float | None
    entailed: int
    not_entailed: int
    unlabelled: int


def _ratio(n: int, d: int) -> float | None:
    return n / d if d else None


def citation_totals(scores: Sequence[CitationScore]) -> CitationTotals:
    checks = [c for s in scores for c in s.checks]
    valid = [c for c in checks if c.status is CitationStatus.VALID]
    needing = sum(s.source_requiring_claims for s in scores)
    supported = sum(s.supported_claims for s in scores)
    fabricated = sum(1 for c in checks if c.status is CitationStatus.FABRICATED)
    outside = sum(1 for c in checks if c.status is CitationStatus.OUTSIDE_BUNDLE)
    documents = [c for c in checks if c.status is not CitationStatus.LIVE]
    return CitationTotals(
        pairs=len(scores),
        citations=len(checks),
        valid=len(valid),
        fabricated=fabricated,
        outside_bundle=outside,
        inaccessible=sum(s.inaccessible for s in scores),
        unauthoritative=sum(s.unauthoritative for s in scores),
        inapplicable=sum(s.inapplicable for s in scores),
        source_requiring_claims=needing,
        supported_claims=supported,
        uncited_claims=sum(s.uncited_claims for s in scores),
        precision=_ratio(sum(1 for c in valid if c.gold_supported), len(valid)),
        recall=_ratio(supported, needing),
        fabrication_rate=_ratio(fabricated + outside, len(documents)),
        validity=_ratio(len(valid), len(documents)),
        entailed=sum(s.entailed for s in scores),
        not_entailed=sum(s.not_entailed for s in scores),
        unlabelled=sum(s.unlabelled for s in scores),
    )


@dataclass(frozen=True)
class ArmAnswerSummary:
    arm: str
    pairs: int
    states: dict[str, int]
    endpoints: Endpoints
    citations: CitationTotals
    policy: PolicySummary
    abstention: AbstentionSummary
    loss_per_100: float | None
    mixed_model_pairs: int


def summarize_arm(
    score: AnswerRunScore, arm: str, weights: Mapping[str, float], confidence: float = 0.95
) -> ArmAnswerSummary:
    pairs = score.arm_pairs(arm)
    done = [p for p in pairs if p.scored]
    items = [EndpointItem(Answerability(p.answerability), p.status, p.claims) for p in pairs]
    abstention = summarize_abstention([p.abstention for p in pairs])
    return ArmAnswerSummary(
        arm=arm,
        pairs=len(pairs),
        states=dict(
            sorted(Counter(p.status.value if p.code != INVALID_ANSWER else "INVALID_ANSWER" for p in pairs).items())
        ),
        endpoints=endpoints_from(items, confidence),
        citations=citation_totals([p.citations for p in done if p.citations is not None]),
        policy=summarize_policy([p.policy for p in done if p.policy is not None]),
        abstention=abstention,
        loss_per_100=expected_loss_per_100(abstention.events, abstention.completed, weights),
        mixed_model_pairs=sum(1 for p in pairs if p.mixed_model),
    )


def sweep_for(score: AnswerRunScore, weights: Mapping[str, float], scales: Sequence[float]) -> Sweep:
    per_arm = {}
    for arm in score.arms:
        summary = summarize_abstention([p.abstention for p in score.arm_pairs(arm)])
        per_arm[arm] = (summary.events, summary.completed)
    return loss_sweep(per_arm, weights, scales)
