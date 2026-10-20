"""Track B: a retriever and the shared generator composed into one system arm (B05-T05.01, protocol 3, BADR-0028).

Every retriever gets the same generator, prompt template, answer schema, evidence budget and runtime gate, so a
difference between arms is a difference in what they retrieve. The generator sees the question, the evaluation time and
the delivered passages with their citation ids, and nothing else: no gold, no outcome label, no other arm's output.
The prompt is screened for gold markers before every call and kept in the run directory.

The runtime gate is the same for every arm and is a record, not a rewrite: a citation outside the delivered bundle is
flagged on the ledger record and counted by the scorer as a fabrication, so the generator's behaviour stays measurable.
The answer's own status and citations are never trusted; the scorer recomputes them from the delivered bundle.

Nothing here calls a provider unless a live pool is passed in; the offline transport is a labelled stand-in for tests
and smokes and produces no result about any model.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from benchmark.config import ConfigBundle, GeneratorSettings, load_all
from benchmark.contracts import (
    AbstentionReason,
    CacheCondition,
    CaseRequest,
    CaseResponse,
    Claim,
    ContractError,
    EvidenceCandidate,
    EvidenceStatus,
    RetrievalRequest,
    RetrieverAdapter,
    Track,
    UsageReport,
)
from benchmark.eval.normalize import PublishedCorpus, align_all
from benchmark.fixtures import sha256_hex
from benchmark.fixtures.answer_gold import Action, ClaimKind, answer_gold_path
from benchmark.fixtures.manifest import Layout, Namespace, Split, read_identity
from benchmark.fixtures.questions import GoldRecord
from benchmark.generator import AssignmentPlan, GeneratorPool, TransportResponse, assign_models
from benchmark.registry import default_registry
from benchmark.run_manifest import RunManifest, TreeState, collect_hardware, read_verified, sha256_of, tree_state
from benchmark.runner import (
    ArmBinding,
    PlanRegistry,
    RunLedger,
    Runner,
    RunnerCase,
    RunnerSettings,
    RunSummary,
    derived_rng,
)
from benchmark.track_a import FICTION, METHOD_VERSION, DescribedArm, TrackAError, read_annotations

TRACK_B_SPLITS = ("smoke",)  # the dev split has no answer-gold yet
CONTROLLED_QA = "controlled_qa"
OUTCOMES = ("PERMITTED", "NOT_PERMITTED", "ESCALATE", "NEEDS_INPUT")
TOKENS_PER_QUESTION = 6000  # an estimate used only to spread questions over per-model budgets; recorded in the manifest
DEADLINE_MARGIN_SECONDS = 5.0
STUB_MODEL = "offline-stub"
PASSAGE_OPEN = '<<passage ids="'
PASSAGE_CLOSE = "<<end>>"

SYSTEM_PROMPT = f"""You answer support-staff questions for Meridian Switchworks, a fictional payments company.
Use only the evidence passages in the user message. Each passage is wrapped in <<passage ids="...">> and
<<end>> and names its citation ids; cite only those ids, exactly as written. Do not use any other knowledge.
Reply with one JSON object and nothing else.

Schema:
{{"evidence_status": one of {[s.value for s in EvidenceStatus]},
 "abstention_reason": null or one of {[r.value for r in AbstentionReason]},
 "action": one of {[a.value for a in Action]},
 "policy_outcome": null or one of {list(OUTCOMES)},
 "version_ids": [document ids of the policy versions you rely on],
 "answer_text": a short plain-language answer,
 "claims": [{{"kind": one of {[k.value for k in ClaimKind]}, "params": {{string or integer values}}, "text": short text,
              "citations": [citation ids]}}]}}

Claim kinds and their params: POLICY_WINDOW {{version, hours}}; WINDOW {{hours}}; TOTAL_WINDOW {{hours}};
APPLICABLE_VERSION {{version, hours}}; VERSION_BASIS {{basis}}; POLICY_OUTCOME {{outcome}}; INPUT_REQUIRED {{input}};
CONFLICT {{hours_a, hours_b}}; WINDOW_NOT_PROPOSAL {{hours}}; LIVE_STATE {{operation, state}}; HTTP_STATUS {{status}}.
Actions: ANSWER (the evidence settles the question), LIST_ALL (list every matching item), REPORT_CONFLICT
(approved sources disagree), NO_SUPPORT (nothing in the evidence answers), ASK_INPUT (a case input is missing),
DECLINE_ACCESS (the answer needs a source this person may not use), RETRY_LATER (a live check is unavailable).
State a policy outcome only when the evidence gives the rule and the case supplies every input. Documents that are
drafts, proposals or memos are not rules. Never state a current status that the evidence does not show.
"""


# --------------------------------------------------------------------------- the shared prompt


def candidate_ids(candidate: EvidenceCandidate, corpus: PublishedCorpus) -> list[str]:
    """The citation ids a passage can be cited by: the clauses its provenance resolves to, else its document."""
    (alignment,) = align_all([candidate], corpus)
    units = sorted(alignment.units())
    if not units:
        return []
    clauses = [f"{doc}#{clause}" for doc, clause in units if clause != "doc"]
    return clauses or [units[0][0]]


def build_messages(
    request: CaseRequest, candidates: Sequence[EvidenceCandidate], corpus: PublishedCorpus
) -> tuple[list[dict[str, str]], list[str]]:
    """The one prompt every arm gets, and the ids of everything the generator was shown."""
    shown: list[str] = []
    blocks: list[str] = []
    for candidate in candidates:
        ids = candidate_ids(candidate, corpus)
        shown.extend(ids)
        blocks.append(f'{PASSAGE_OPEN}{", ".join(ids)}">>\n{candidate.content.strip()}\n{PASSAGE_CLOSE}')
    context = [f"Question: {request.query}", f"Evaluation time: {request.evaluation_time}"]
    if request.event_time:
        context.append(f"Event time: {request.event_time}")
    evidence = "\n".join(blocks) if blocks else "(no passages were retrieved)"
    user = "\n".join(context) + "\n\nEvidence passages:\n\n" + evidence
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}], sorted(set(shown))


PROMPT_DIGEST = sha256_hex(SYSTEM_PROMPT)
_PASSAGE = re.compile(
    re.escape(PASSAGE_OPEN) + r'(?P<ids>[^"]*)">>\n(?P<body>.*?)\n' + re.escape(PASSAGE_CLOSE), re.DOTALL
)


def prompt_passages(user_message: str) -> list[tuple[list[str], str]]:
    """The passages of a Track B user message: their citation ids and their text."""
    return [
        ([i for i in found.group("ids").split(", ") if i], found.group("body"))
        for found in _PASSAGE.finditer(user_message)
    ]


def prompt_ids(user_message: str) -> list[str]:
    """Every citation id the generator was shown in one user message, sorted and without repeats."""
    return sorted({i for ids, _ in prompt_passages(user_message) for i in ids})


# --------------------------------------------------------------------------- the answer


ANSWER_RULES = (
    "NO_TEXT",
    "NOT_JSON",
    "NOT_IN_SCHEMA",
    "FIELD_NOT_STRING",
    "VOCABULARY",
    "OUTCOME_VOCABULARY",
    "VERSION_IDS",
    "CLAIMS_NOT_LIST",
    "CLAIM_NOT_OBJECT",
    "CLAIM_FIELD_TYPE",
    "FIELD_INVALID",
)


class AnswerRejected(ContractError):
    """An answer outside the schema. ``rule`` is one fixed name from ``ANSWER_RULES``; the ledger keeps it as a flag.

    The reply itself is never copied into a record: only which rule it broke.
    """

    def __init__(self, rule: str, message: str) -> None:
        if rule not in ANSWER_RULES:
            raise ValueError(f"unknown answer rule: {rule}")
        super().__init__(message)
        self.rule = rule
        self.ledger_flags = (f"ANSWER_REJECTED={rule}",)


def _text(value: object, name: str, *, allow_null: bool = False) -> str | None:
    if value is None and allow_null:
        return None
    if not isinstance(value, str):
        raise AnswerRejected("FIELD_NOT_STRING", f"the answer's {name} is not a string")
    return value


def parse_answer(text: str | None, request: CaseRequest, run_id: str, delivered: Sequence[str]) -> CaseResponse:
    """Read the generator's JSON into a ``CaseResponse``. Anything outside the schema is an invalid answer.

    The error is always an ``AnswerRejected`` naming the rule, also for a value the contracts refuse (too long).
    """
    try:
        return _read_answer(text, request, run_id, delivered)
    except AnswerRejected:
        raise
    except ContractError:
        raise AnswerRejected("FIELD_INVALID", "a field of the answer is outside its contract") from None


def _read_answer(text: str | None, request: CaseRequest, run_id: str, delivered: Sequence[str]) -> CaseResponse:
    if not text:
        raise AnswerRejected("NO_TEXT", "the generator returned no text")
    try:
        data = json.loads(text)
    except ValueError:
        raise AnswerRejected("NOT_JSON", "the answer is not valid JSON") from None
    allowed = {
        "evidence_status",
        "abstention_reason",
        "action",
        "policy_outcome",
        "version_ids",
        "answer_text",
        "claims",
    }
    if not isinstance(data, dict) or set(data) - allowed:
        raise AnswerRejected("NOT_IN_SCHEMA", "the answer is not a JSON object in the schema")
    try:
        status = EvidenceStatus(str(data.get("evidence_status")))
        reason_text = _text(data.get("abstention_reason"), "abstention_reason", allow_null=True)
        reason = AbstentionReason(reason_text) if reason_text is not None else None
        action = Action(str(data.get("action"))).value
    except ValueError:
        raise AnswerRejected(
            "VOCABULARY", "the answer names a status, reason or action outside the vocabulary"
        ) from None
    outcome = _text(data.get("policy_outcome"), "policy_outcome", allow_null=True)
    if outcome is not None and outcome not in OUTCOMES:
        raise AnswerRejected("OUTCOME_VOCABULARY", "the answer names a policy outcome outside the vocabulary")
    versions = data.get("version_ids", [])
    if not isinstance(versions, list) or not all(isinstance(v, str) for v in versions):
        raise AnswerRejected("VERSION_IDS", "version_ids must be a list of strings")
    raw_claims = data.get("claims", [])
    if not isinstance(raw_claims, list):
        raise AnswerRejected("CLAIMS_NOT_LIST", "claims must be a list")
    claims = []
    known = {k.value for k in ClaimKind}
    for number, raw in enumerate(raw_claims, start=1):
        if not isinstance(raw, dict):
            raise AnswerRejected("CLAIM_NOT_OBJECT", "a claim must be an object")
        kind = raw.get("kind")
        citations = raw.get("citations", [])
        params = raw.get("params", {})
        if not isinstance(citations, list) or not isinstance(params, dict):
            raise AnswerRejected("CLAIM_FIELD_TYPE", "a claim's citations must be a list and its params an object")
        claims.append(
            Claim(
                f"c{number}",
                str(raw.get("text") or kind or "claim"),
                tuple(str(c) for c in citations),
                kind=kind if kind in known else None,
                params=params,
            )
        )
    return CaseResponse(
        question_id=request.question_id,
        run_id=run_id,
        answer_text=str(data.get("answer_text") or ""),
        evidence_status=status,
        claims=tuple(claims),
        used_evidence_ids=tuple(delivered),
        tool_calls=(),
        critic=None,
        model_invocations=None,
        latency_ms=None,
        cost_usd=None,
        abstention_reason=reason,
        action=action,
        policy_outcome=outcome,
        version_ids=tuple(versions),
    )


def gate_flags(response: CaseResponse) -> tuple[str, ...]:
    """The runtime gate: citations outside the delivered bundle are recorded, never silently removed."""
    shown = set(response.used_evidence_ids)
    docs = {i.split("#", 1)[0] for i in shown}

    def inside(citation: str) -> bool:
        return citation in shown or ("#" not in citation and citation in docs)

    outside = sum(1 for claim in response.claims for c in claim.citations if not inside(c))
    return (f"CITATION_OUTSIDE_BUNDLE={outside}",) if outside else ()


# --------------------------------------------------------------------------- the system arm


class ControlledQaSystem:
    """A retriever plus the shared generator, behind the system-arm interface the Runner already dispatches."""

    def __init__(
        self,
        arm_id: str,
        retriever: DescribedArm,
        pool: GeneratorPool,
        corpus: PublishedCorpus,
        *,
        k: int,
        run_id: str,
        case_deadline_seconds: float,
    ) -> None:
        if not isinstance(retriever, RetrieverAdapter):
            raise TrackAError(f"{arm_id} is not a retriever")
        self.arm_id = arm_id
        self.retriever = retriever
        self.pool = pool
        self.corpus = corpus
        self.k = k
        self.run_id = run_id
        self.case_deadline_seconds = case_deadline_seconds
        self._flags: tuple[str, ...] = ()
        self._usage = UsageReport(None, None, None, None, None, None)
        self._trace: list[dict[str, Any]] = []

    def reset_case(self, question_id: str) -> None:
        self._flags = ()
        self._usage = UsageReport(None, None, None, None, None, None)
        self._trace = []

    def report_usage(self) -> UsageReport:
        return self._usage

    def report_trace(self) -> list[dict[str, Any]]:
        return list(self._trace)

    def describe(self) -> dict[str, Any]:
        return {"arm": self.arm_id, "retriever": self.retriever.describe(), "k": self.k}

    def call_flags(self) -> tuple[str, ...]:
        return self._flags

    def answer(self, case: CaseRequest) -> CaseResponse:
        # The call must be finished, or refused before it starts, before the Runner's own deadline; so a late worker
        # cannot dispatch a request or write a record after the pair was recorded as timed out.
        deadline = self.pool.now() + self.case_deadline_seconds - DEADLINE_MARGIN_SECONDS
        request = RetrievalRequest(
            question_id=case.question_id,
            query=case.query,
            principal_id=case.principal_id,
            corpus_snapshot_id=case.corpus_snapshot_id,
            evaluation_time=case.evaluation_time,
            event_time=case.event_time,
            filters=case.filters,
            limit=self.k,
            max_evidence_tokens=case.max_evidence_tokens,
        )
        candidates = self.retriever.retrieve(request)
        messages, delivered = build_messages(case, candidates, self.corpus)
        flags = list(_retriever_flags(self.retriever))
        result = self.pool.complete(case.question_id, messages, arm_id=self.arm_id, json_output=True, deadline=deadline)
        record = result.record
        flags.append(f"GENERATOR_MODEL={record.served_model or record.requested_model}")
        calls = [r for r in self.pool.records if r.question_id == case.question_id and r.arm_id == self.arm_id]
        tokens = [r.prompt_tokens for r in calls if r.prompt_tokens is not None]
        written = [r.completion_tokens for r in calls if r.completion_tokens is not None]
        # Tokens are what the provider reported; an attempt it refused reports none, so the sums cover the rest.
        self._usage = UsageReport(
            len(calls), 0, 0, sum(tokens) if tokens else None, sum(written) if written else None, None
        )
        self._trace = [
            {"step": "retrieve", "candidates": len(candidates), "delivered_ids": len(delivered)},
            {"step": "generate", "model": record.served_model or record.requested_model, "attempt": record.attempt},
        ]
        response = parse_answer(result.text, case, self.run_id, delivered)
        flags.extend(gate_flags(response))
        self._flags = tuple(flags)
        return response


def _retriever_flags(retriever: object) -> tuple[str, ...]:
    flags = getattr(retriever, "call_flags", None)
    return tuple(flags()) if callable(flags) else ()


def read_prompt_ids(prompts_path: Path) -> dict[tuple[str, str], list[str]]:
    """What the generator was shown, per (question, arm), read from the prompts the run kept (the last call wins)."""
    shown: dict[tuple[str, str], list[str]] = {}
    if not prompts_path.is_file():
        return shown
    for line in prompts_path.read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        users = [m["content"] for m in entry.get("messages", []) if m.get("role") == "user"]
        if users:
            shown[(str(entry["question_id"]), str(entry["arm_id"]))] = prompt_ids(users[-1])
    return shown


def mixed_model_questions(records_path: Path) -> list[str]:
    """Questions whose arms did not all run on one generator model, or whose own model changed between attempts.

    A pair compared across such a question differs in the generator as well as the retriever, so it is flagged
    (BADR-0008, BR13); it is never silently dropped.
    """
    if not records_path.exists():
        return []
    models: dict[str, dict[str, set[str]]] = {}
    for line in records_path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record["status"] != "OK":
            continue
        arm = str(record["arm_id"])
        served = str(record["served_model"] or record["requested_model"])
        models.setdefault(str(record["question_id"]), {}).setdefault(arm, set()).add(served)
    mixed = []
    for question, arms in models.items():
        every = {m for served in arms.values() for m in served}
        if len(every) > 1:
            mixed.append(question)
    return sorted(mixed)


# --------------------------------------------------------------------------- an offline stand-in transport


class ExtractiveStubTransport:
    """A deterministic offline stand-in for the provider: it reads the delivered passages and answers from the first
    window it finds. For tests and smokes of the plumbing only; its answers say nothing about any model."""

    _WINDOW = re.compile(r"(?:within|more than|dalam|lebih dari) (\d+) (?:hours|jam)")

    def __init__(self) -> None:
        self.calls = 0

    def post(self, payload: Mapping[str, Any]) -> TransportResponse:
        self.calls += 1
        user = str(payload["messages"][-1]["content"])
        answer: dict[str, Any] = {
            "evidence_status": "NOT_ESTABLISHED",
            "abstention_reason": "NO_KNOWN_SUPPORT",
            "action": "NO_SUPPORT",
            "policy_outcome": None,
            "version_ids": [],
            "answer_text": "nothing in the evidence answers this",
            "claims": [],
        }
        for ids, body in prompt_passages(user):
            found = self._WINDOW.search(body)
            if found and ids:
                cite = ids[0]
                answer.update(
                    evidence_status="SUPPORTED",
                    abstention_reason=None,
                    action="ANSWER",
                    answer_text=f"the window is {found.group(1)} hours",
                    claims=[
                        {"kind": "WINDOW", "params": {"hours": found.group(1)}, "text": "window", "citations": [cite]}
                    ],
                )
                break
        body_bytes = json.dumps(
            {
                "model": STUB_MODEL,
                "choices": [{"message": {"content": json.dumps(answer)}}],
                "usage": {
                    "prompt_tokens": len(user.split()),
                    "completion_tokens": 40,
                    "total_tokens": len(user.split()) + 40,
                },
            }
        ).encode()
        return TransportResponse(200, {}, body_bytes)


# --------------------------------------------------------------------------- running


@dataclass(frozen=True)
class TrackBSpec:
    run_id: str
    split: str
    k: int
    budget_words: int
    root: Path
    out: Path
    condition: str = "C2"
    live: bool = False
    tokens_per_question: int = TOKENS_PER_QUESTION
    order_seed: int | None = None
    config_dir: Path = Path(__file__).resolve().parents[1] / "configs"
    withdrawn: Mapping[str, str] | None = None
    question_ids: tuple[str, ...] | None = None  # a subset of the eligible questions, recorded in the run
    case_deadline_seconds: float | None = None  # replaces the configured case deadline for a paced live run
    pace_seconds: float = 0.0  # recorded; the pool does the pacing


@dataclass(frozen=True)
class TrackBOutcome:
    summary: RunSummary
    run_dir: Path
    questions: int
    arms: tuple[str, ...]
    unassigned: tuple[str, ...]


def eligible_records(records: Sequence[GoldRecord], withdrawn: Mapping[str, str] | None) -> list[GoldRecord]:
    """Questions Track B asks: the controlled-QA ones that were not withdrawn after the label audit."""
    skip = set(withdrawn or ())
    return [r for r in records if CONTROLLED_QA in r.track_eligibility and r.question_id not in skip]


def asked_records(
    records: Sequence[GoldRecord], withdrawn: Mapping[str, str] | None, only: Sequence[str] | None
) -> list[GoldRecord]:
    """The eligible questions, narrowed to the ids a run recorded as asked (every one must be eligible)."""
    eligible = eligible_records(records, withdrawn)
    if only is None:
        return eligible
    wanted = set(only)
    unknown = sorted(wanted - {r.question_id for r in eligible})
    if unknown:
        raise TrackAError(f"questions recorded as asked are not eligible for Track B: {unknown[:3]}")
    return [r for r in eligible if r.question_id in wanted]


def pick_subset(records: Sequence[GoldRecord], limit: int, seed: int) -> list[str]:
    """A seeded, stratum-balanced subset of ``limit`` question ids: round-robin over the strata in a seeded order."""
    if limit < 1:
        raise TrackAError("a subset takes at least one question")
    by_stratum: dict[str, list[str]] = {}
    for record in sorted(records, key=lambda r: r.question_id):
        by_stratum.setdefault(record.stratum.value, []).append(record.question_id)
    for stratum, ids in by_stratum.items():
        derived_rng(seed, f"subset:{stratum}").shuffle(ids)
    picked: list[str] = []
    rounds = max((len(ids) for ids in by_stratum.values()), default=0)
    for position in range(rounds):
        for stratum in sorted(by_stratum):
            if position < len(by_stratum[stratum]) and len(picked) < limit:
                picked.append(by_stratum[stratum][position])
    return sorted(picked)


def plan_assignment(
    records: Sequence[GoldRecord], settings: GeneratorSettings, spec: TrackBSpec, seed: int
) -> AssignmentPlan:
    return assign_models(
        [r.question_id for r in records], settings, seed=seed, tokens_per_question=spec.tokens_per_question
    )


def make_pool_paths(out: Path) -> tuple[Path, Path]:
    return out / "generation_records.jsonl", out / "prompts.jsonl"


def _manifest(
    spec: TrackBSpec,
    arm_id: str,
    describe: Mapping[str, Any],
    settings: RunnerSettings,
    digests: Mapping[str, str],
    bundle: ConfigBundle,
    generator: GeneratorSettings,
    plan: AssignmentPlan,
    system: TreeState | None,
    pool_label: str,
) -> RunManifest:
    shared = bundle.comparators.shared_models
    models: dict[str, str | None] = {f"generator:{m}": "no provider-exposed revision" for m in generator.models}
    if arm_id in ("R1", "R2", "R3"):
        models["embeddings"] = f"{shared['embeddings'].value}@{shared['embeddings'].revision}"
        qdrant = shared["qdrant_server"]
        models["qdrant_server"] = f"{qdrant.value}@sha256:{next(iter(qdrant.digests.values()))}"
    if arm_id == "R3":
        models["reranker"] = f"{shared['reranker'].value}@{shared['reranker'].revision}"
    reasons = {
        "container_image_digest": "no container is used; arms run in the benchmark environment or a pinned worktree",
        "pricing_snapshot": "no priced provider is called (free tier or offline stand-in)",
    }
    if system is None:
        reasons["system_under_test"] = "a benchmark-built arm, not the system under test"
    method: str | None = METHOD_VERSION
    if arm_id == "R7a":
        method = None
        reasons["method_version"] = "the system under test is identified by its commit in system_under_test"
    return RunManifest(
        run_id=spec.run_id,
        track=Track.CONTROLLED_QA,
        arm=arm_id,
        split=spec.split,
        source_manifest_sha256=digests["source"],
        question_manifest_sha256=digests["questions"],
        gold_manifest_sha256=digests["gold"],
        benchmark=tree_state(Path(__file__).resolve().parents[1], label="benchmark"),
        system_under_test=system,
        container_image_digest=None,
        method_version=method,
        model_versions=models,
        retrieval_config={
            **describe,
            "k": spec.k,
            "budget_words": spec.budget_words,
            "metadata_condition": spec.condition,
            "generator": {
                "pool": pool_label,
                "live": spec.live,
                "models": list(generator.models),
                "temperature": generator.temperature,
                "max_completion_tokens": generator.max_completion_tokens,
                "reasoning_effort": dict(generator.reasoning_effort),
                "tokens_per_question": spec.tokens_per_question,
                "single_model": len(set(plan.assigned.values())) <= 1,
                "failover": generator.allow_automatic_failover,
                "unassigned": len(plan.unassigned),
            },
        },
        prompt_digest=PROMPT_DIGEST,
        hardware=collect_hardware(),
        pricing_snapshot=None,
        seed=settings.order_seed,
        order_seed=settings.order_seed,
        cache_condition=CacheCondition.COLD,
        started_at_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        retry_policy=settings.retry_policy_dict(),
        generator_assignment_sha256=plan.digest(),
        confirmatory=False,
        null_reasons=reasons,
    )


def execute_track_b(
    spec: TrackBSpec,
    retrievers: Mapping[str, DescribedArm],
    pool: GeneratorPool,
    plan: AssignmentPlan,
    corpus: PublishedCorpus,
    generator: GeneratorSettings,
    *,
    pool_label: str,
    system_trees: Mapping[str, TreeState] | None = None,
) -> TrackBOutcome:
    """Run every retriever, each composed with the shared generator, on every eligible question through the Runner."""
    if spec.split not in TRACK_B_SPLITS:
        raise TrackAError("the locked test split needs the sealed run of B08; Track B runs smoke or dev")
    if spec.k < 1 or spec.budget_words < 1:
        raise TrackAError("K and the evidence budget are at least 1")
    bundle = load_all(spec.config_dir)
    records, read_log = read_annotations(spec.root, spec.split)
    chosen = asked_records(records, spec.withdrawn, spec.question_ids)
    gold_path = answer_gold_path(spec.root, Split(spec.split))
    if not gold_path.is_file():
        raise TrackAError("the answer-gold file for this split does not exist; generate it first")
    answer_gold_digest = sha256_hex(gold_path.read_bytes().decode("utf-8"))
    identity = read_identity(Layout(spec.root).path(Namespace.PUBLISHED))
    by_id = {p.principal_id: p for p in identity.principals}
    requests = []
    for record in chosen:
        principal = by_id.get(record.principal_id)
        if principal is None:
            raise TrackAError(f"principal {record.principal_id} is not in the identity manifest")
        requests.append(
            CaseRequest(
                question_id=record.question_id,
                query=record.query,
                principal_id=record.principal_id,
                corpus_snapshot_id=record.corpus_snapshot_id,
                evaluation_time=record.evaluation_time,
                event_time=record.event_time,
                filters={
                    "tenant_id": principal.tenant_id,
                    "role": principal.role_id,
                    "metadata_condition": spec.condition,
                },
                max_evidence_tokens=spec.budget_words,
                episode_id=None,
                turn_index=0,
            )
        )
    digests = {
        "source": read_log.published_manifest_sha256,
        "gold": read_log.annotation_sha256,
        "questions": sha256_of([r.to_dict() for r in requests]),
    }
    settings = RunnerSettings.from_config(bundle.benchmark, order_seed=spec.order_seed)
    if spec.case_deadline_seconds is not None:
        settings = replace(settings, case_deadline_seconds=spec.case_deadline_seconds)
    spec.out.mkdir(parents=True, exist_ok=True)
    system_trees = system_trees or {}
    bindings = []
    for arm_id, retriever in retrievers.items():
        system = ControlledQaSystem(
            arm_id, retriever, pool, corpus, k=spec.k, run_id=spec.run_id,
            case_deadline_seconds=settings.case_deadline_seconds,
        )  # fmt: skip
        path = spec.out / f"manifest-{arm_id}.json"
        if path.exists():
            recorded = read_verified(path).retrieval_config
            if (recorded.get("k"), recorded.get("budget_words"), recorded.get("metadata_condition")) != (
                spec.k, spec.budget_words, spec.condition,
            ):  # fmt: skip
                raise TrackAError(f"manifest-{arm_id}.json was written under a different K, budget or condition")
        else:
            _manifest(
                spec, arm_id, system.describe(), settings, digests, bundle, generator, plan,
                system_trees.get(arm_id), pool_label,
            ).write(path)  # fmt: skip
        bindings.append(ArmBinding(arm_id, system, path))
    runner = Runner(
        spec.run_id,
        settings,
        bindings,
        RunLedger(spec.out / "ledger.jsonl"),
        PlanRegistry(spec.out / "plans.jsonl"),
        default_registry(),
    )
    summary = runner.run([RunnerCase(r) for r in requests], split=spec.split)
    (spec.out / "read_log.json").write_text(json.dumps(read_log.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    (spec.out / "run_config.json").write_text(
        json.dumps(
            {
                "run_id": spec.run_id,
                "track": CONTROLLED_QA,
                "split": spec.split,
                "arms": sorted(retrievers),
                "k": spec.k,
                "budget_words": spec.budget_words,
                "metadata_condition": spec.condition,
                "questions": len(requests),
                "asked": None if spec.question_ids is None else sorted(spec.question_ids),
                "case_deadline_seconds": settings.case_deadline_seconds,
                "pace_seconds": spec.pace_seconds,
                "withdrawn": sorted(spec.withdrawn or ()),
                "generator_pool": pool_label,
                "live": spec.live,
                "unassigned": list(plan.unassigned),
                "single_model": len(set(plan.assigned.values())) <= 1,
                "failover": generator.allow_automatic_failover,
                "answer_targets_sha256": answer_gold_digest,
                "prompt_sha256": PROMPT_DIGEST,
                "notice": FICTION,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (spec.out / "summary.json").write_text(json.dumps(asdict(summary), indent=2, sort_keys=True), encoding="utf-8")
    return TrackBOutcome(summary, spec.out, len(requests), tuple(sorted(retrievers)), plan.unassigned)
