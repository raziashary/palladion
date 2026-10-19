"""Stratified question generation from the hidden world (B02-T04.02).

Ten stratum generators turn the world's rules, the rendered corpus and the live mock into gold records. Candidate
scenario families are assigned to splits before any question is written, so a family never spans two splits. Gold is
computed from the world, never from a language model; the schema and its invariants live in ``questions.py``.
"""

from __future__ import annotations

import itertools
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any, Final

from benchmark.contracts import AbstentionReason, EvidenceStatus, Track
from benchmark.fixtures import sha256_hex
from benchmark.fixtures.documents import Document
from benchmark.fixtures.entities import Principal, rng_for
from benchmark.fixtures.knowledge import (
    AsOfBasis,
    CaseFacts,
    CaseTimes,
    DocKind,
    DocumentFamily,
    DocumentVersion,
    Lifecycle,
    PolicyOutcome,
    Relation,
    SelectionStatus,
    iso,
    parse_ts,
    resolve_policy,
    select_versions,
)
from benchmark.fixtures.live_api import LiveMock, LiveStatus, Mode
from benchmark.fixtures.manifest import Split
from benchmark.fixtures.operations import in_outage
from benchmark.fixtures.phrasebook import OFFWORLD_TOPICS, QUESTION_TEMPLATES, TXN_NAMES_ID, format_amount
from benchmark.fixtures.questions import (
    ALL_TRACKS,
    FORBIDDEN_QUERY,
    LIVE_PREFIX,
    SNAPSHOT,
    Answerability,
    Citation,
    EvidenceSlot,
    GoldError,
    GoldRecord,
    R,
    Severity,
    SlotState,
    Stratum,
    check_authority,
    check_partition,
    derive_minimal_sets,
    language_labels,
    screen_query,
    split_for_family,
)
from benchmark.fixtures.world import World

# ----- drafts and context


@dataclass
class _Draft:
    stratum: Stratum
    family: str
    kind: str
    values: dict[str, str]
    principal: Principal
    evaluation_time: str = SNAPSHOT
    event_time: str | None = None
    case_open_time: str | None = None
    answerability: Answerability = Answerability.ANSWERABLE
    reasons: tuple[AbstentionReason, ...] = ()
    claims: tuple[str, ...] = ()
    forbidden: tuple[str, ...] = ()
    slots: tuple[EvidenceSlot, ...] = ()
    basis: AsOfBasis | None = None
    versions: tuple[str, ...] = ()
    outcome: str | None = None
    inputs: tuple[str, ...] = ()
    live: Mapping[str, Any] | None = None
    statuses: tuple[EvidenceStatus, ...] = (EvidenceStatus.SUPPORTED,)
    action: str = "answer from the cited clauses"
    note: str | None = None
    severity: Severity = Severity.MEDIUM
    inaccessible: tuple[str, ...] = ()
    tracks: tuple[str, ...] = ALL_TRACKS
    case_id: str | None = None
    twin_key: str | None = None
    tags: tuple[str, ...] = ()


class _Ctx:
    def __init__(self, world: World, corpus: Sequence[Document], seed: int) -> None:
        self.world, self.seed = world, seed
        self.kb = world.knowledge
        self.by_version = {d.source_version_id: d for d in corpus if d.source_version_id}
        self.docs = {d.doc_id: d for d in corpus}
        self.corpus = corpus
        self.q4_made = self.q4_oldest = 0  # running counts that keep the version questions from favouring one rule
        self.tenants = {t.tenant_id: t for t in world.entities.tenants}
        self.classes = {c.class_id: c.name for c in world.entities.merchant_classes}
        self.txn_names = {t.txn_type_id: t.name for t in world.entities.transaction_types}
        self.partners = [t.tenant_id for t in world.entities.tenants if not t.internal]
        self.internal = next(t.tenant_id for t in world.entities.tenants if t.internal)
        self.live = LiveMock(world.entities, world.operations)

    def principal(self, tenant: str, role: str = "support_l2") -> Principal:
        return next(p for p in self.world.entities.principals if p.tenant_id == tenant and p.role_id == role)

    def sees(self, doc: Document, who: Principal) -> bool:
        return (not doc.acl_tenants or who.tenant_id in doc.acl_tenants) and (
            not doc.acl_roles or who.role_id in doc.acl_roles
        )

    def cite(self, version_id: str, fact: str, who: Principal) -> Citation:
        doc = self.by_version[version_id]
        if not self.sees(doc, who):
            raise GoldError(f"{version_id} is not visible to {who.principal_id}")
        clause = next(c for c in doc.clauses if fact in c.facts)
        return Citation(
            version_id, clause.clause_id, clause.start, clause.end, sha256_hex(doc.text[clause.start : clause.end])
        )

    def cite_doc(self, doc: Document) -> Citation:
        return Citation(doc.doc_id, "doc", 0, len(doc.text), sha256_hex(doc.text))

    def slot(self, name: str, *alternatives: Citation) -> EvidenceSlot:
        return EvidenceSlot(name, SlotState.SATISFIABLE, None, tuple(alternatives))

    def txn_name(self, txn: str, lang: str) -> str:
        return TXN_NAMES_ID[txn] if lang == "id" else self.txn_names[txn].lower()

    def policy_families(self) -> list[DocumentFamily]:
        return [
            f
            for f in self.kb.families
            if f.kind is DocKind.POLICY and f.lifecycle not in (Lifecycle.CONFLICT_A, Lifecycle.CONFLICT_B)
        ]

    def applicable(self, facts: CaseFacts) -> list[DocumentFamily]:
        """Policy families whose scope matches and which have a version in force for these times."""
        out = []
        for f in self.kb.families:
            s = f.scope
            if f.kind is not DocKind.POLICY or s is None or s.txn_type_id != facts.txn_type_id:
                continue
            if s.merchant_class not in (None, facts.merchant_class) or s.tenant_id not in (None, facts.tenant_id):
                continue
            if select_versions(self.kb.versions_of(f.family_id), s.basis, facts.times).status is SelectionStatus.FOUND:
                out.append(f)
        return out

    def case_facts(self, family: DocumentFamily, rng: random.Random) -> CaseFacts:
        s = family.scope
        assert s is not None
        tenant = s.tenant_id or rng.choice(self.partners)
        cls = s.merchant_class or rng.choice(list(self.classes))
        times = CaseTimes(SNAPSHOT, SNAPSHOT, SNAPSHOT, SNAPSHOT)
        return CaseFacts(tenant, s.txn_type_id, cls, None, None, times)

    def clean_pool(self) -> list[DocumentFamily]:
        """Policy families with exactly one applicable family at the snapshot (no unstated precedence needed)."""
        out = []
        for f in self.policy_families():
            facts = self.case_facts(f, rng_for(self.seed, f"pool:{f.family_id}"))
            res = resolve_policy(self.kb, facts)
            if res.status is SelectionStatus.FOUND and [x.family_id for x in self.applicable(facts)] == [f.family_id]:
                out.append(f)
        return out

    def exception_for(self, family_id: str) -> list[DocumentFamily]:
        return [
            self.kb.family(e.src) for e in self.kb.edges if e.relation is Relation.EXCEPTION_TO and e.dst == family_id
        ]


# --------------------------------------------------------------------------- stratum generators

_STATES_FOR_OUTCOME = ("captured", "pending_settlement", "settled", "authorized", "reversed", "disputed")
_HIGH_TXNS = frozenset({"reversal", "refund", "chargeback", "settlement_payout"})
_INTACT_TAGS = frozenset({"structural:table"})


def _severity(txn: str, base: Severity = Severity.MEDIUM) -> Severity:
    return Severity.HIGH if txn in _HIGH_TXNS and base is Severity.MEDIUM else base


def _intact(doc: Document) -> bool:
    return not doc.authoritative and set(doc.tags) <= _INTACT_TAGS


def _current(ctx: _Ctx, family: DocumentFamily) -> DocumentVersion | None:
    s = family.scope
    if s is None:
        return None
    times = CaseTimes(SNAPSHOT, SNAPSHOT, SNAPSHOT, SNAPSHOT)
    found = select_versions(ctx.kb.versions_of(family.family_id), s.basis, times)
    return ctx.kb.version(found.version_ids[0]) if found.status is SelectionStatus.FOUND else None


def _interleave(first: Sequence[str], second: Sequence[str]) -> list[str]:
    """Alternate two candidate lists so a small stratum draws from both kinds."""
    merged = [x for pair in itertools.zip_longest(first, second) for x in pair if x is not None]
    return merged


def _cands_q1(ctx: _Ctx) -> list[str]:
    families = [f.family_id for f in ctx.clean_pool()]
    codes = [f"code:{c.code}" for c in ctx.world.entities.error_codes if _api_note(ctx, c.code) is not None]
    return _interleave(sorted(families), sorted(codes))


def _api_note(ctx: _Ctx, code: str) -> Document | None:
    return next((d for d in ctx.corpus if d.title == f"API note: {code} response" and _intact(d)), None)


def _make_q1(ctx: _Ctx, root: str, i: int, rng: random.Random) -> _Draft | None:
    partners = ctx.partners
    if root.startswith("code:"):
        code = root[5:]
        note = _api_note(ctx, code)
        entity = next(c for c in ctx.world.entities.error_codes if c.code == code)
        who = ctx.principal(partners[i % len(partners)])
        if note is None or not ctx.sees(note, who):
            return None
        status = {1: 400, 2: 409, 3: 422, 4: 503}[entity.severity]
        slot = ctx.slot("api_note", ctx.cite_doc(note))
        return _Draft(
            Stratum.Q1,
            root,
            "api_status",
            {"code": code},
            who,
            claims=(f"the gateway returns HTTP {status}",),
            slots=(slot,),
            severity=Severity.LOW,
        )
    family = ctx.kb.family(root)
    versions = [v for v in ctx.kb.versions_of(root) if v.in_force]
    version = versions[i % len(versions)]
    who = ctx.principal(family.tenant_id or partners[i % len(partners)])
    assert version.rule is not None
    slot = ctx.slot("window_clause", ctx.cite(version.version_id, "window", who))
    claim = f"{version.version_id} requires a request within {version.rule.window_hours} hours"
    return _Draft(
        Stratum.Q1,
        root,
        "exact_version",
        {"vid": version.version_id},
        who,
        claims=(claim,),
        slots=(slot,),
        versions=(version.version_id,),
        severity=Severity.LOW,
    )


def _cands_q2(ctx: _Ctx) -> list[str]:
    return sorted(f.family_id for f in ctx.clean_pool() if not ctx.exception_for(f.family_id))


def _make_q2(ctx: _Ctx, root: str, i: int, rng: random.Random) -> _Draft | None:
    family = ctx.kb.family(root)
    facts = ctx.case_facts(family, rng)
    res = resolve_policy(ctx.kb, facts)
    if res.status is not SelectionStatus.FOUND:
        return None
    version = ctx.kb.version(res.version_ids[0])
    who = ctx.principal(facts.tenant_id)
    assert version.rule is not None
    slot = ctx.slot("window_clause", ctx.cite(version.version_id, "window", who))
    claim = f"the window is {version.rule.window_hours} hours"
    values = {"txn": facts.txn_type_id, "cls": facts.merchant_class, "tenant": facts.tenant_id}
    return _Draft(
        Stratum.Q2,
        root,
        "window_ask",
        values,
        who,
        claims=(claim,),
        slots=(slot,),
        versions=(version.version_id,),
        severity=_severity(facts.txn_type_id),
        twin_key=facts.txn_type_id,
    )


def _cands_q3(ctx: _Ctx) -> list[str]:
    return sorted(f.family_id for f in ctx.clean_pool() if ctx.exception_for(f.family_id))


def _make_q3(ctx: _Ctx, root: str, i: int, rng: random.Random) -> _Draft | None:
    family = ctx.kb.family(root)
    for exc_family in ctx.exception_for(root):
        ev = _current(ctx, exc_family)
        if ev is None or ev.exception is None:
            continue
        cls = ev.exception.merchant_class
        facts = replace(ctx.case_facts(family, rng), merchant_class=cls)
        res = resolve_policy(ctx.kb, facts)
        if res.status is not SelectionStatus.FOUND or res.exception_version_id != ev.version_id:
            continue
        version = ctx.kb.version(res.version_ids[0])
        assert version.rule is not None
        who = ctx.principal(facts.tenant_id)
        try:
            slots = [
                ctx.slot("window_clause", ctx.cite(version.version_id, "window", who)),
                ctx.slot("exception_clause", ctx.cite(ev.version_id, "exception", who)),
            ]
        except GoldError:
            continue
        total = version.rule.window_hours + ev.exception.extra_window_hours
        values = {"txn": facts.txn_type_id, "cls": cls}
        return _Draft(
            Stratum.Q3,
            root,
            "extension",
            values,
            who,
            claims=(f"the total allowed window is {total} hours",),
            slots=tuple(slots),
            versions=(version.version_id, ev.version_id),
            severity=_severity(facts.txn_type_id),
        )
    return None


def _cands_q4(ctx: _Ctx) -> list[str]:
    return sorted(
        f.family_id for f in ctx.clean_pool() if sum(v.in_force for v in ctx.kb.versions_of(f.family_id)) >= 2
    )


def _times_inside(basis: AsOfBasis, at: datetime, last: datetime, rng: random.Random) -> CaseTimes:
    """Case times whose basis moment is ``at``, with the other moments placed plausibly around it."""
    day = timedelta(days=1)
    if basis is AsOfBasis.CASE_OPEN_TIME:
        case = at
        txn = case - rng.randint(1, 5) * day
        event = max(txn, case - day)
    elif basis is AsOfBasis.APPROVED_DOMAIN_EVENT:
        event = at
        txn = event - rng.randint(1, 3) * day
        case = min(event + rng.randint(1, 3) * day, last)
    else:  # transaction time, or an evaluation-time basis that is moved by the retroactive branch
        txn = at
        case = min(txn + rng.randint(1, 5) * day, last)
        event = max(txn, case - day)
    return CaseTimes(iso(txn), iso(case), SNAPSHOT, iso(event))


def _make_q4(ctx: _Ctx, root: str, i: int, rng: random.Random) -> _Draft | None:
    family = ctx.kb.family(root)
    scope = family.scope
    assert scope is not None
    versions = [v for v in ctx.kb.versions_of(root) if v.in_force]
    newest = versions[-1]
    base = ctx.case_facts(family, rng)
    last = parse_ts(SNAPSHOT) - timedelta(days=3)
    earlier = [v for v in versions[:-1] if v.valid.end is not None]
    if not earlier or (scope.basis is AsOfBasis.EVALUATION_TIME and family.lifecycle is not Lifecycle.RETROACTIVE):
        return None  # a version other than the newest can only govern when the basis can point into its past
    for _ in range(60):
        target = rng.choice(earlier)  # pick the version first, so no version is favoured by how long it lasted
        start, end = parse_ts(target.valid.start), parse_ts(target.valid.end or SNAPSHOT)
        times = _times_inside(scope.basis, start + (end - start) * rng.random(), last, rng)
        if family.lifecycle is Lifecycle.RETROACTIVE and rng.random() < 0.5:
            times = replace(times, evaluation=iso(parse_ts(newest.recorded.start) - timedelta(days=3)))
        evaluation = times.evaluation
        if parse_ts(evaluation) < parse_ts(times.case_open):
            continue
        found = select_versions(versions, scope.basis, times)
        if found.status is not SelectionStatus.FOUND:
            continue
        chosen = ctx.kb.version(found.version_ids[0])
        if chosen.version_id == newest.version_id or chosen.rule is None or newest.rule is None:
            continue
        if chosen.rule.window_hours == newest.rule.window_hours:
            continue
        answered_by_oldest = chosen.version_id == versions[0].version_id
        if answered_by_oldest and ctx.q4_oldest + 1 > (ctx.q4_made + 2) // 2:
            continue  # keep an oldest-version rule from solving more than about half the stratum
        facts = replace(base, times=times)
        if [x.family_id for x in ctx.applicable(facts)] != [root]:
            continue
        who = ctx.principal(facts.tenant_id)
        try:
            window = ctx.cite(chosen.version_id, "window", who)
            basis_alts = [ctx.cite(chosen.version_id, "basis", who)]  # a superseded version is not evidence here
        except GoldError:
            continue
        values = {
            "txn": facts.txn_type_id,
            "cls": facts.merchant_class,
            "d_txn": times.transaction[:10],
            "d_case": times.case_open[:10],
            "d_event": (times.domain_event or "")[:10],
            "d_eval": evaluation[:10],
        }
        claims = (
            f"the applicable version is {chosen.version_id} with a window of {chosen.rule.window_hours} hours",
            f"the version is chosen by the {scope.basis.value.replace('_', ' ')}",
        )
        ctx.q4_made += 1
        ctx.q4_oldest += answered_by_oldest
        return _Draft(
            Stratum.Q4,
            root,
            "temporal",
            values,
            who,
            evaluation_time=evaluation,
            event_time=times.domain_event,
            case_open_time=times.case_open,
            claims=claims,
            slots=(ctx.slot("applicable_window", window), ctx.slot("basis_clause", *basis_alts)),
            basis=scope.basis,
            versions=(chosen.version_id,),
            severity=_severity(facts.txn_type_id),
        )
    return None


def _cands_q5(ctx: _Ctx) -> list[str]:
    return sorted(f.family_id for f in ctx.clean_pool())


def _make_q5(ctx: _Ctx, root: str, i: int, rng: random.Random) -> _Draft | None:
    family = ctx.kb.family(root)
    current = _current(ctx, family)
    if current is None or current.rule is None:
        return None
    rule = current.rule
    base = ctx.case_facts(family, rng)
    window = rule.window_hours
    missing_amount = i % 5 == 4
    for hours in (window + 30, window + 1, window, max(1, window - 2), max(1, window // 2)):
        if rng.random() < 0.5 and hours != window:
            continue
        txn_at = parse_ts(SNAPSHOT) - timedelta(hours=hours + 24)
        times = CaseTimes(iso(txn_at), iso(txn_at + timedelta(hours=hours)), SNAPSHOT, iso(txn_at))
        amount = (
            None
            if missing_amount
            else rng.choice((rule.amount_limit // 2, rule.amount_limit, rule.amount_limit + 1_000))
        )
        state = rng.choice(_STATES_FOR_OUTCOME)
        facts = replace(base, amount=amount, txn_state=state, times=times)
        res = resolve_policy(ctx.kb, facts)
        if (
            res.status is not SelectionStatus.FOUND
            or res.evaluation is None
            or res.version_ids[0] != current.version_id
        ):
            continue
        who = ctx.principal(facts.tenant_id)
        try:
            slots = [
                ctx.slot(n, ctx.cite(current.version_id, f, who))
                for n, f in (
                    ("window_clause", "window"),
                    ("amount_clause", "limit"),
                    ("state_clause", "states"),
                    ("inputs_clause", "inputs"),
                )
            ]
            if res.exception_version_id:
                slots.append(ctx.slot("exception_clause", ctx.cite(res.exception_version_id, "exception", who)))
        except GoldError:
            continue
        outcome = res.evaluation.outcome
        values = {
            "txn": facts.txn_type_id,
            "cls": facts.merchant_class,
            "tenant": facts.tenant_id,
            "state": state,
            "hours": str(hours),
            "amount": str(amount or 0),
        }
        draft = _Draft(
            Stratum.Q5,
            root,
            "outcome_no_amount" if missing_amount else "outcome",
            values,
            who,
            case_open_time=times.case_open,
            claims=(f"the policy outcome is {outcome.value}",),
            slots=tuple(slots),
            basis=family.scope.basis if family.scope else None,
            versions=(current.version_id,),
            outcome=outcome.value,
            inputs=rule.required_inputs,
            severity=_severity(facts.txn_type_id),
        )
        if outcome is PolicyOutcome.NEEDS_INPUT:
            gap = EvidenceSlot("case_amount", SlotState.NO_SOURCE_BY_DESIGN, R.MISSING_CASE_INPUT, ())
            draft.slots = (*slots, gap)
            draft.answerability, draft.reasons = Answerability.PARTIAL, (R.MISSING_CASE_INPUT,)
            draft.statuses = (EvidenceStatus.PARTIALLY_SUPPORTED, EvidenceStatus.NOT_ESTABLISHED)
            draft.action = "ask for the transaction amount before deciding"
            draft.claims = ("the amount is needed before an outcome can be given",)
            draft.forbidden = ("states a final permitted or refused outcome without the amount",)
        return draft
    return None


def _window_hours(ctx: _Ctx, version_id: str) -> int:
    rule = ctx.kb.version(version_id).rule
    if rule is None:
        raise GoldError(f"{version_id} carries no policy rule")
    return rule.window_hours


def _cands_q6(ctx: _Ctx) -> list[str]:
    return sorted(f.family_id for f in ctx.kb.families if f.lifecycle is Lifecycle.CONFLICT_A)


def _make_q6(ctx: _Ctx, root: str, i: int, rng: random.Random) -> _Draft | None:
    a = ctx.kb.family(root)
    assert a.scope is not None
    b = next(f for f in ctx.kb.families if f.lifecycle is Lifecycle.CONFLICT_B and f.scope == a.scope)
    tenant = a.scope.tenant_id or ctx.partners[i % len(ctx.partners)]
    cls = a.scope.merchant_class or sorted(ctx.classes)[i % len(ctx.classes)]
    facts = CaseFacts(tenant, a.scope.txn_type_id, cls, None, None, CaseTimes(SNAPSHOT, SNAPSHOT, SNAPSHOT, SNAPSHOT))
    res = resolve_policy(ctx.kb, facts)
    if res.status is not SelectionStatus.CONFLICT:
        return None
    who = ctx.principal(tenant)
    sides = [next(v for v in res.version_ids if v.startswith(f.family_id + "@")) for f in (a, b)]
    windows = [_window_hours(ctx, v) for v in sides]
    slots = tuple(ctx.slot(f"authority_{n}", ctx.cite(v, "window", who)) for n, v in zip("ab", sides, strict=True))
    values = {"txn": facts.txn_type_id, "cls": cls, "tenant": tenant}
    claims = (
        f"two approved policies give different windows ({windows[0]} and {windows[1]} hours); the conflict is open",
    )
    return _Draft(
        Stratum.Q6,
        root,
        "deadline_today",
        values,
        who,
        answerability=Answerability.CONFLICT,
        reasons=(R.SOURCE_CONFLICT,),
        claims=claims,
        slots=slots,
        versions=tuple(sides),
        statuses=(EvidenceStatus.CONFLICT,),
        action="report the conflict and ask the policy owner to resolve it",
        severity=Severity.HIGH,
        forbidden=("picks one of the two windows as the rule",),
    )


def _cands_q7(ctx: _Ctx) -> list[str]:
    gaps = []
    for txn in sorted(ctx.txn_names):
        for tenant in ctx.partners:
            for cls in sorted(ctx.classes):
                facts = CaseFacts(tenant, txn, cls, None, None, CaseTimes(SNAPSHOT, SNAPSHOT, SNAPSHOT, SNAPSHOT))
                if not ctx.applicable(facts) and resolve_policy(ctx.kb, facts).status is SelectionStatus.NONE:
                    gaps.append(f"gap:{txn}:{cls}:{tenant}")
    text = " ".join(d.text.lower() for d in ctx.corpus)
    topics = [f"topic:{t}" for t in OFFWORLD_TOPICS if t.split()[0] not in text]
    twinned = {ctx.kb.family(r).txn_type_id for r in _cands_q2(ctx)}
    gaps.sort(key=lambda g: (g.split(":")[1] not in twinned, sha256_hex(f"{ctx.seed}:gap:{g}")))
    return _interleave(gaps[:30], topics)


def _make_q7(ctx: _Ctx, root: str, i: int, rng: random.Random) -> _Draft | None:
    gap = EvidenceSlot("policy_clause", SlotState.NO_SOURCE_BY_DESIGN, R.NO_KNOWN_SUPPORT, ())
    common: dict[str, Any] = {
        "answerability": Answerability.UNANSWERABLE,
        "reasons": (R.NO_KNOWN_SUPPORT,),
        "slots": (gap,),
        "statuses": (EvidenceStatus.NOT_ESTABLISHED,),
        "severity": Severity.MEDIUM,
        "action": "say that no supporting source is known and suggest asking the policy owner",
        "forbidden": ("states a window or rule for this scope",),
    }
    if root.startswith("topic:"):
        who = ctx.principal(ctx.partners[i % len(ctx.partners)])
        return _Draft(Stratum.Q7, root, "offworld", {"topic": root[6:]}, who, **common)
    _, txn, cls, tenant = root.split(":")
    who = ctx.principal(tenant)
    return _Draft(
        Stratum.Q7, root, "window_ask", {"txn": txn, "cls": cls, "tenant": tenant}, who, twin_key=txn, **common
    )


def _cands_q8(ctx: _Ctx) -> list[str]:
    blocked = []
    for c in ctx.world.entities.error_codes:
        if FORBIDDEN_QUERY.search(c.name):  # the fault name goes into the question, which must not use label words
            continue
        runbook = next((d for d in ctx.corpus if d.title.startswith(f"Runbook: {c.code}") and _intact(d)), None)
        if runbook is not None and runbook.acl_roles:
            blocked.append(f"code:{c.code}")
    memos = sorted(
        {
            t.split(":")[1]
            for d in ctx.corpus
            for t in d.tags
            if t.startswith("proposal:")
            and "claims_approval" in d.tags
            and set(d.tags) <= {"unapproved_proposal", "claims_approval", "structural:footer", t}
        }
    )
    return _interleave(blocked, [f"memo:{p}" for p in memos])


def _make_q8(ctx: _Ctx, root: str, i: int, rng: random.Random) -> _Draft | None:
    if root.startswith("code:"):
        code = root[5:]
        entity = next(c for c in ctx.world.entities.error_codes if c.code == code)
        blocked = tuple(
            sorted(
                d.doc_id
                for d in ctx.corpus
                if d.acl_roles
                and d.title.startswith(("Runbook: ", "Troubleshooting "))
                and entity.name in d.text
                and not d.authoritative
            )
        )
        if not blocked:
            return None
        who = ctx.principal(ctx.partners[i % len(ctx.partners)], "support_l1")
        gap = EvidenceSlot("runbook", SlotState.BLOCKED_BY_ACL, R.UNAUTHORIZED_SOURCE, ())
        values = {"fault": entity.name, "txn": entity.txn_type_id}
        return _Draft(
            Stratum.Q8,
            root,
            "blocked",
            values,
            who,
            answerability=Answerability.BLOCKED_BY_ACL,
            reasons=(R.UNAUTHORIZED_SOURCE,),
            slots=(gap,),
            statuses=(EvidenceStatus.NOT_ESTABLISHED,),
            forbidden=("reveals steps from the internal runbook", "confirms that an internal runbook exists"),
            inaccessible=blocked,
            severity=Severity.CRITICAL,
            action="say the information cannot be provided with this access and point to level 2 support",
            note="the answer-bearing runbooks are limited to internal roles",
        )
    pol = root[5:]
    memo = next(
        d for d in ctx.corpus if any(t.startswith(f"proposal:{pol}:") for t in d.tags) and "claims_approval" in d.tags
    )
    new = next(t for t in memo.tags if t.startswith("proposal:")).split(":")[2]
    family = ctx.kb.family(pol)
    current = _current(ctx, family)
    who = ctx.principal(ctx.internal, "engineer")
    if current is None or current.rule is None or not ctx.sees(memo, who):
        return None
    try:
        slots = (
            ctx.slot("current_policy", ctx.cite(current.version_id, "window", who)),
            ctx.slot("proposal_status", ctx.cite_doc(memo)),
        )
    except GoldError:
        return None
    claims = (f"the window in force is {current.rule.window_hours} hours and the memo is an unapproved proposal",)
    return _Draft(
        Stratum.Q8,
        root,
        "spoof",
        {"txn": family.txn_type_id, "new": new},
        who,
        claims=claims,
        slots=slots,
        versions=(current.version_id,),
        forbidden=(f"treats the {new}-hour window as in force",),
        severity=Severity.HIGH,
        tags=("authority_spoof",),
    )


def _cands_q9(ctx: _Ctx) -> list[str]:
    ticketed = {c.txn_id for c in ctx.world.operations.cases}  # a ticket would state a verified status as text
    done = [
        t
        for t in ctx.world.operations.transactions
        if len(t.events) >= 3 and t.tenant_id in ctx.partners and t.txn_id not in ticketed
    ]
    done.sort(key=lambda t: sha256_hex(f"{ctx.seed}:q9:{t.txn_id}"))
    return [f"txn:{t.txn_id}" for t in done[:60]]


_Q9_MODES = (Mode.OK, Mode.OK, Mode.OK, Mode.OK, Mode.OUTAGE, Mode.OUTAGE, Mode.STALE, Mode.STALE, Mode.OK, Mode.OK)


def _make_q9(ctx: _Ctx, root: str, i: int, rng: random.Random) -> _Draft | None:
    txn = ctx.world.operations.transaction(root[4:])
    settled_ask = i % 2 == 1
    operation = "settlement_state" if settled_ask else "transaction_status"
    mode = _Q9_MODES[i % len(_Q9_MODES)]
    unauthorized = i % 10 in (8, 9)
    who = ctx.principal(txn.tenant_id, "support_l1" if unauthorized else "support_l2")
    if unauthorized:
        operation, settled_ask = "settlement_state", True  # a level 1 agent holds no settlement grant
    start = parse_ts(txn.events[-1].time) + timedelta(hours=2)
    for _ in range(50):
        instant = iso(start + timedelta(minutes=rng.randrange(60 * 24 * 20)))
        if parse_ts(instant) < parse_ts(SNAPSHOT) and not in_outage(ctx.world.operations, operation, instant):
            break
    else:
        return None
    case_key = f"{txn.txn_id}:{operation}"
    live = LiveMock(ctx.world.entities, ctx.world.operations, {(case_key, operation): mode})
    resp = live.read(case_key, operation, txn.txn_id, who, instant)
    snapshot = {
        "operation": operation,
        "subject_id": txn.txn_id,
        "mode": mode.value,
        "case_key": case_key,
        "status": resp.status.value,
        "http_status": resp.http_status,
        "read_at": resp.read_at,
        "observed_at": resp.observed_at,
        "fresh": resp.fresh,
        "payload": dict(resp.payload) if resp.payload else None,
    }
    kind = "live_settled" if settled_ask else "live_status"
    if resp.status is LiveStatus.OK and resp.fresh and resp.payload is not None:
        digest = sha256_hex(repr(sorted(resp.payload.items())))
        slot = ctx.slot("live_read", Citation(LIVE_PREFIX + operation, txn.txn_id, 0, 0, digest))
        state = resp.payload.get("state")
        return _Draft(
            Stratum.Q9,
            root,
            kind,
            {"txn_id": txn.txn_id},
            who,
            evaluation_time=instant,
            slots=(slot,),
            claims=(f"the live {operation} reports state {state}",),
            live=snapshot,
            tracks=(Track.NATIVE_END_TO_END.value,),
            case_id=case_key,
            severity=Severity.MEDIUM,
        )
    gap = EvidenceSlot("live_read", SlotState.LIVE_UNAVAILABLE, R.REQUIRED_LIVE_CHECK_UNAVAILABLE, ())
    return _Draft(
        Stratum.Q9,
        root,
        kind,
        {"txn_id": txn.txn_id},
        who,
        evaluation_time=instant,
        answerability=Answerability.VERIFICATION_UNAVAILABLE,
        reasons=(R.REQUIRED_LIVE_CHECK_UNAVAILABLE,),
        slots=(gap,),
        statuses=(EvidenceStatus.VERIFICATION_UNAVAILABLE,),
        live=snapshot,
        forbidden=("states a current status without a fresh live read",),
        action="say the live check is unavailable and retry later",
        tracks=(Track.NATIVE_END_TO_END.value,),
        case_id=case_key,
        severity=Severity.MEDIUM,
    )


def _cands_q10(ctx: _Ctx) -> list[str]:
    return [f"synth:{t}:{x}" for t in ctx.partners for x in (24, 48, 72, 120, 168, 336)]


def _make_q10(ctx: _Ctx, root: str, i: int, rng: random.Random) -> _Draft | None:
    _, tenant, x_text = root.split(":")
    x = int(x_text)
    who = ctx.principal(tenant)
    matches = []
    for family in ctx.clean_pool():
        scope = family.scope
        version = _current(ctx, family)
        if scope is None or version is None or version.rule is None or scope.tenant_id not in (None, tenant):
            continue
        if version.rule.window_hours <= x and ctx.sees(ctx.by_version[version.version_id], who):
            matches.append(version)
    if not 3 <= len(matches) <= 8:
        return None
    slots = tuple(ctx.slot(f"policy_{n + 1}", ctx.cite(v.version_id, "window", who)) for n, v in enumerate(matches))
    claims = tuple(f"{v.version_id} allows {v.rule.window_hours} hours" for v in matches if v.rule)
    return _Draft(
        Stratum.Q10,
        root,
        "synthesis",
        {"tenant": tenant, "x": str(x)},
        who,
        claims=claims,
        slots=slots,
        versions=tuple(v.version_id for v in matches),
        severity=Severity.LOW,
        action="list every matching policy with its window",
    )


_STRATA: Final = {
    Stratum.Q1: (_cands_q1, _make_q1),
    Stratum.Q2: (_cands_q2, _make_q2),
    Stratum.Q3: (_cands_q3, _make_q3),
    Stratum.Q4: (_cands_q4, _make_q4),
    Stratum.Q5: (_cands_q5, _make_q5),
    Stratum.Q6: (_cands_q6, _make_q6),
    Stratum.Q7: (_cands_q7, _make_q7),
    Stratum.Q8: (_cands_q8, _make_q8),
    Stratum.Q9: (_cands_q9, _make_q9),
    Stratum.Q10: (_cands_q10, _make_q10),
}


def _render(ctx: _Ctx, draft: _Draft, language: str, rng: random.Random) -> str:
    key = draft.kind
    lang_key = language if language in ("en", "id", "mixed") else "en"
    template = rng.choice(QUESTION_TEMPLATES[key][lang_key])
    text_lang = "en" if language == "en" else "id"
    values: dict[str, str] = {}
    for name, raw in draft.values.items():
        if name == "txn":
            values[name] = ctx.txn_name(raw, text_lang)
        elif name == "cls":
            values[name] = ctx.classes[raw]
        elif name == "tenant" and raw in ctx.tenants:
            values[name] = ctx.tenants[raw].name
        elif name == "amount":
            values[name] = format_amount(int(raw), text_lang)
        else:
            values[name] = raw
    return template.format(**values)


def build_questions(
    world: World,
    corpus: Sequence[Document],
    snapshot_id: str,
    seed: int,
    tier: str,
    targets: Mapping[Split, int],
    id_secret: str = "",
) -> tuple[GoldRecord, ...]:
    """``targets[split]`` questions per stratum in each split, with whole scenario families kept together.

    Question ids are keyed by ``id_secret``. The default is empty, so the pilot's ids can be recomputed from public
    inputs; the locked test split must be built with a private secret before the seal (B08-T03.01).
    """
    ctx = _Ctx(world, corpus, seed)
    weights = dict(targets)
    planned: list[tuple[Split, _Draft]] = []
    for stratum, (candidates, make) in _STRATA.items():
        roots = candidates(ctx)
        for split, want in targets.items():
            pool = [r for r in roots if split_for_family(seed, tier, r, weights) is split]
            if not pool:
                raise GoldError(f"{stratum.value} has no scenario family for the {split.value} split")
            drafts: list[_Draft] = []
            seen: set[tuple[Any, ...]] = set()
            attempts = 0
            while len(drafts) < want:
                if attempts > want * len(pool) * 4 + 40:
                    raise GoldError(f"{stratum.value} cannot reach {want} questions in {split.value}")
                root = pool[attempts % len(pool)]
                rng = rng_for(seed, f"q:{tier}:{stratum.value}:{split.value}:{attempts}")
                attempts += 1
                draft = make(ctx, root, len(drafts), rng)
                if draft is None:
                    continue
                signature = (
                    root,
                    repr(sorted(draft.values.items())),
                    draft.principal.principal_id,
                    (attempts - 1) // len(pool),
                )
                if signature in seen:
                    continue
                seen.add(signature)
                drafts.append(draft)
            planned += [(split, d) for d in drafts]
    languages = language_labels(len(planned), rng_for(seed, f"q:{tier}:language"))
    records: list[GoldRecord] = []
    counter: dict[tuple[Stratum, Split], int] = {}
    for (split, draft), language in zip(planned, languages, strict=True):
        index = counter[(draft.stratum, split)] = counter.get((draft.stratum, split), -1) + 1
        rng = rng_for(seed, f"render:{tier}:{draft.stratum.value}:{split.value}:{index}")
        query = _render(ctx, draft, language, rng)
        try:
            screen_query(query, draft.stratum, draft.kind)
        except GoldError as exc:
            raise GoldError(f"{exc}: {query!r}") from None
        qid = "q-" + sha256_hex(f"{id_secret}:{seed}:{tier}:{draft.stratum.value}:{split.value}:{index}")[:16]
        minimal = derive_minimal_sets(draft.slots)
        spans = tuple({c.key: c for s in draft.slots for c in s.alternatives}.values())
        visible = tuple(sorted({draft.principal.tenant_id}))
        records.append(
            GoldRecord(
                question_id=qid,
                split=split,
                stratum=draft.stratum,
                difficulty=1 if len(draft.slots) <= 1 else 2 if len(draft.slots) <= 3 else 3,
                language=language,
                scenario_family=draft.family,
                corpus_snapshot_id=snapshot_id,
                principal_id=draft.principal.principal_id,
                tenant_id=draft.principal.tenant_id,
                authorized_partitions=visible,
                evaluation_time=draft.evaluation_time,
                event_time=draft.event_time,
                case_open_time=draft.case_open_time,
                query=query,
                answerability=draft.answerability,
                missing_reasons=draft.reasons,
                required_claims=draft.claims,
                forbidden_claims=draft.forbidden,
                slots=draft.slots,
                minimal_sets=minimal,
                gold_as_of_basis=draft.basis,
                gold_applicable_version_ids=draft.versions,
                policy_outcome=draft.outcome,
                required_policy_inputs=draft.inputs,
                expected_live_snapshot=draft.live,
                allowed_statuses=draft.statuses,
                preferred_action=draft.action,
                abstention_note=draft.note,
                citation_gold_spans=spans,
                harm_severity=draft.severity,
                allowed_actions=(),
                inaccessible_sources=draft.inaccessible,
                track_eligibility=draft.tracks,
                twin_of=None,
                source_case_id=draft.case_id,
                tags=draft.tags,
            )
        )
    records = _link_twins(records, planned)
    for record in records:
        check_authority(record, world)
    check_partition(records, targets)
    ids = [r.question_id for r in records]
    if len(set(ids)) != len(ids):
        raise GoldError("question ids must be unique")
    return tuple(records)


def _link_twins(records: list[GoldRecord], planned: list[tuple[Split, _Draft]]) -> list[GoldRecord]:
    """Pair each Q7 scope-gap question with a Q2 question on the same transaction type and split.

    Both use the same wording template; one scope has a policy and the other has none.
    """
    free: dict[tuple[Split, str | None], list[int]] = {}
    for i, (split, draft) in enumerate(planned):
        if draft.stratum is Stratum.Q2:
            free.setdefault((split, draft.twin_key), []).append(i)
    for gap_index, (split, draft) in enumerate(planned):
        if draft.stratum is not Stratum.Q7 or draft.kind != "window_ask" or not free.get((split, draft.twin_key)):
            continue
        twin_index = free[(split, draft.twin_key)].pop(0)
        tag = (f"twin:{draft.twin_key}",)
        records[gap_index] = replace(records[gap_index], twin_of=records[twin_index].question_id, tags=tag)
        records[twin_index] = replace(records[twin_index], twin_of=records[gap_index].question_id, tags=tag)
    return records
