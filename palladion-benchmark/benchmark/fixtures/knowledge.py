"""Document families and versions, policies, as-of bases, the typed graph and the policy evaluator (B02-T01.02).

Truth lives here before any prose is rendered. Construction is permissive so a mutation can plant an invalid chain;
:func:`validate_knowledge` and :func:`validate_supersession` are the checks that refuse it.
"""

from __future__ import annotations

import random
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, fields, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from functools import lru_cache
from typing import Any

from benchmark.contracts import normalise_timestamp
from benchmark.fixtures import FICTIONAL_NOTICE, digest_of, to_plain
from benchmark.fixtures.entities import Principal, Role, WorldEntities, WorldError, lookup, rng_for

SNAPSHOT_TIME = "2026-10-18T03:00:00Z"
_ANCHOR = datetime(2026, 1, 1, tzinfo=UTC)
_DAY = timedelta(days=1)


class DocKind(StrEnum):
    SOP = "sop"
    POLICY = "policy"
    EXCEPTION = "exception"


class DocumentState(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    RETIRED = "retired"
    WITHDRAWN = "withdrawn"


class AsOfBasis(StrEnum):
    TRANSACTION_TIME = "transaction_time"
    CASE_OPEN_TIME = "case_open_time"
    EVALUATION_TIME = "evaluation_time"
    APPROVED_DOMAIN_EVENT = "approved_domain_event"


class Relation(StrEnum):
    APPLIES_TO = "APPLIES_TO"
    REQUIRES = "REQUIRES"
    EXCEPTION_TO = "EXCEPTION_TO"
    SUPERSEDES = "SUPERSEDES"
    REFERENCES = "REFERENCES"


class Verification(StrEnum):
    VERIFIED = "verified"
    INFERRED = "inferred"


class Lifecycle(StrEnum):
    """How a family's version history was planted. Evaluator-side only; no arm ever sees it."""

    PLAIN = "plain"
    FUTURE = "future"
    RETROACTIVE = "retroactive"
    DRAFT_TAIL = "draft_tail"
    WITHDRAWN = "withdrawn"
    CONFLICT_A = "conflict_a"
    CONFLICT_B = "conflict_b"


@lru_cache(maxsize=65536)
def parse_ts(value: str) -> datetime:
    """Parse a timestamp that carries an explicit zone and return it in UTC."""
    return datetime.fromisoformat(normalise_timestamp("timestamp", value))


def iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class Interval:
    """A half-open interval ``[start, end)``; ``end=None`` means open-ended and is explicit, never implied."""

    start: str
    end: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "start", normalise_timestamp("Interval.start", self.start))
        if self.end is not None:
            object.__setattr__(self, "end", normalise_timestamp("Interval.end", self.end))
            if parse_ts(self.end) <= parse_ts(self.start):
                raise WorldError("interval is empty or inverted")

    def contains(self, moment: str) -> bool:
        at = parse_ts(moment)
        return parse_ts(self.start) <= at and (self.end is None or at < parse_ts(self.end))

    def overlaps(self, other: Interval) -> bool:
        starts_before_other_ends = other.end is None or parse_ts(self.start) < parse_ts(other.end)
        other_starts_before_end = self.end is None or parse_ts(other.start) < parse_ts(self.end)
        return starts_before_other_ends and other_starts_before_end


@dataclass(frozen=True)
class PolicyRule:
    window_hours: int
    amount_limit: int
    forbidden_states: tuple[str, ...]
    required_inputs: tuple[str, ...]


@dataclass(frozen=True)
class ExceptionRule:
    merchant_class: str
    extra_window_hours: int


@dataclass(frozen=True)
class PolicyScope:
    txn_type_id: str
    merchant_class: str | None
    tenant_id: str | None
    basis: AsOfBasis
    precedence: int


@dataclass(frozen=True)
class DocumentFamily:
    family_id: str
    kind: DocKind
    title: str
    product_id: str
    txn_type_id: str
    tenant_id: str | None
    scope: PolicyScope | None
    lifecycle: Lifecycle


@dataclass(frozen=True)
class DocumentVersion:
    version_id: str
    family_id: str
    version: int
    state: DocumentState
    approved_by: str | None
    valid: Interval
    recorded: Interval
    acl_tenants: tuple[str, ...]
    acl_roles: tuple[str, ...]
    supersedes: str | None
    claims_approval: bool
    rule: PolicyRule | None
    exception: ExceptionRule | None
    steps: tuple[str, ...]
    source_sha256: str = ""

    def __post_init__(self) -> None:
        if not self.source_sha256:
            object.__setattr__(self, "source_sha256", self.compute_hash())

    def compute_hash(self) -> str:
        """SHA-256 of the canonical structured source, i.e. every governing field except the hash itself."""
        body = {f.name: getattr(self, f.name) for f in fields(self) if f.name != "source_sha256"}
        return digest_of(body)

    @property
    def in_force(self) -> bool:
        """Approved or later retired: the only states that can ever govern a case. Drafts and withdrawn never do."""
        return self.state in (DocumentState.APPROVED, DocumentState.RETIRED) and self.approved_by is not None


@dataclass(frozen=True)
class Edge:
    src: str
    relation: Relation
    dst: str
    source_version_id: str
    verification: Verification


@dataclass(frozen=True)
class KnowledgeBase:
    families: tuple[DocumentFamily, ...]
    versions: tuple[DocumentVersion, ...]
    edges: tuple[Edge, ...]

    def family(self, family_id: str) -> DocumentFamily:
        return lookup(self.families, "family_id", family_id)

    def version(self, version_id: str) -> DocumentVersion:
        return lookup(self.versions, "version_id", version_id)

    def versions_of(self, family_id: str) -> tuple[DocumentVersion, ...]:
        return tuple(sorted((v for v in self.versions if v.family_id == family_id), key=lambda v: v.version))

    def records(self) -> Iterator[dict[str, Any]]:
        for kind in ("families", "versions", "edges"):
            for item in getattr(self, kind):
                yield {"kind": kind, "fictional": FICTIONAL_NOTICE, **to_plain(item)}

    def digest(self) -> str:
        return digest_of(list(self.records()))


@dataclass(frozen=True)
class CaseTimes:
    """The four moments a case can be anchored to (protocol section 4.4). ``domain_event`` may be absent."""

    transaction: str
    case_open: str
    evaluation: str
    domain_event: str | None = None

    def for_basis(self, basis: AsOfBasis) -> str:
        chosen = {
            AsOfBasis.TRANSACTION_TIME: self.transaction,
            AsOfBasis.CASE_OPEN_TIME: self.case_open,
            AsOfBasis.EVALUATION_TIME: self.evaluation,
            AsOfBasis.APPROVED_DOMAIN_EVENT: self.domain_event,
        }[basis]
        if chosen is None:
            raise WorldError(f"basis {basis.value} needs a domain event time and none was given")
        return chosen


class SelectionStatus(StrEnum):
    FOUND = "found"
    NONE = "none"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class Selection:
    status: SelectionStatus
    version_ids: tuple[str, ...]


def _known_end(version: DocumentVersion, siblings: Sequence[DocumentVersion], evaluation: str) -> str | None:
    """The end of a version's validity as it was known at the evaluation time.

    The end only becomes known when the version that replaces it has been recorded. Before that, the version is
    believed to be in force without limit, which is what makes a retroactive clause bind only later evaluations.
    """
    if version.valid.end is None:
        return None
    for other in siblings:
        if other.in_force and other.supersedes == version.version_id:
            return version.valid.end if parse_ts(other.recorded.start) <= parse_ts(evaluation) else None
    return version.valid.end


def select_versions(versions: Sequence[DocumentVersion], basis: AsOfBasis, times: CaseTimes) -> Selection:
    """Versions of one family in force at the basis time and already recorded at the evaluation time.

    A draft or withdrawn version never qualifies. A version recorded after the evaluation time was unknown then.
    Overlapping candidates are a conflict.
    """
    at = times.for_basis(basis)
    found = []
    for v in versions:
        if not v.in_force or parse_ts(v.recorded.start) > parse_ts(times.evaluation):
            continue
        known = Interval(v.valid.start, _known_end(v, versions, times.evaluation))
        if known.contains(at):
            found.append(v.version_id)
    if not found:
        return Selection(SelectionStatus.NONE, ())
    return Selection(SelectionStatus.FOUND if len(found) == 1 else SelectionStatus.CONFLICT, tuple(found))


class PolicyOutcome(StrEnum):
    PERMITTED = "PERMITTED"
    NOT_PERMITTED = "NOT_PERMITTED"
    ESCALATE = "ESCALATE"
    NEEDS_INPUT = "NEEDS_INPUT"


@dataclass(frozen=True)
class CaseFacts:
    tenant_id: str
    txn_type_id: str
    merchant_class: str
    amount: int | None
    txn_state: str | None
    times: CaseTimes


@dataclass(frozen=True)
class Evaluation:
    outcome: PolicyOutcome
    missing_inputs: tuple[str, ...]


def evaluate_rule(rule: PolicyRule, extra_window_hours: int, facts: CaseFacts) -> Evaluation:
    """Deterministic policy outcome: missing input first, then forbidden state, window, then amount limit."""
    known = {"amount": facts.amount, "txn_state": facts.txn_state}
    missing = tuple(name for name in rule.required_inputs if known.get(name) is None)
    if missing:
        return Evaluation(PolicyOutcome.NEEDS_INPUT, missing)
    if facts.txn_state in rule.forbidden_states:
        return Evaluation(PolicyOutcome.NOT_PERMITTED, ())
    age_hours = (parse_ts(facts.times.case_open) - parse_ts(facts.times.transaction)) / timedelta(hours=1)
    if age_hours > rule.window_hours + extra_window_hours:
        return Evaluation(PolicyOutcome.NOT_PERMITTED, ())
    if facts.amount is not None and facts.amount > rule.amount_limit:
        return Evaluation(PolicyOutcome.ESCALATE, ())
    return Evaluation(PolicyOutcome.PERMITTED, ())


@dataclass(frozen=True)
class Resolution:
    status: SelectionStatus
    version_ids: tuple[str, ...]
    exception_version_id: str | None
    evaluation: Evaluation | None


def resolve_policy(kb: KnowledgeBase, facts: CaseFacts) -> Resolution:
    """Pick the governing policy version for a case by each family's own as-of basis, then evaluate it.

    Among applicable policy families the highest precedence wins; equal precedence with different rules is a conflict
    that is left unresolved on purpose. An exception family linked by EXCEPTION_TO may extend the window.
    """
    applicable: list[tuple[DocumentFamily, Selection]] = []
    for family in kb.families:
        scope = family.scope
        if family.kind is not DocKind.POLICY or scope is None or scope.txn_type_id != facts.txn_type_id:
            continue
        if scope.merchant_class not in (None, facts.merchant_class) or scope.tenant_id not in (None, facts.tenant_id):
            continue
        selection = select_versions(kb.versions_of(family.family_id), scope.basis, facts.times)
        if selection.status is SelectionStatus.CONFLICT:
            return Resolution(SelectionStatus.CONFLICT, selection.version_ids, None, None)
        if selection.status is SelectionStatus.FOUND:
            applicable.append((family, selection))
    if not applicable:
        return Resolution(SelectionStatus.NONE, (), None, None)
    top = max(f.scope.precedence for f, _ in applicable if f.scope)
    winners = [(f, s) for f, s in applicable if f.scope and f.scope.precedence == top]
    rules = {kb.version(s.version_ids[0]).rule for _, s in winners}
    if len(rules) > 1:
        return Resolution(SelectionStatus.CONFLICT, tuple(s.version_ids[0] for _, s in winners), None, None)
    family, selection = winners[0]
    chosen = kb.version(selection.version_ids[0])
    assert chosen.rule is not None
    exception_id, extra = _applicable_exception(kb, family.family_id, facts)
    return Resolution(
        SelectionStatus.FOUND, (chosen.version_id,), exception_id, evaluate_rule(chosen.rule, extra, facts)
    )


def _applicable_exception(kb: KnowledgeBase, policy_family_id: str, facts: CaseFacts) -> tuple[str | None, int]:
    for edge in kb.edges:
        if edge.relation is not Relation.EXCEPTION_TO or edge.dst != policy_family_id:
            continue
        family = kb.family(edge.src)
        if family.scope is None:
            continue
        selection = select_versions(kb.versions_of(family.family_id), family.scope.basis, facts.times)
        if selection.status is not SelectionStatus.FOUND:
            continue
        version = kb.version(selection.version_ids[0])
        if version.exception and version.exception.merchant_class == facts.merchant_class:
            return version.version_id, version.exception.extra_window_hours
    return None, 0


def visible_to(version: DocumentVersion, principal: Principal) -> bool:
    """Tenant and role access. Empty ACL tuples mean unrestricted on that axis."""
    tenant_ok = not version.acl_tenants or principal.tenant_id in version.acl_tenants
    role_ok = not version.acl_roles or principal.role_id in version.acl_roles
    return tenant_ok and role_ok


def validate_supersession(edges: Sequence[Edge]) -> None:
    """SUPERSEDES must be acyclic and each version may be superseded by exactly one successor."""
    successor: dict[str, str] = {}
    for edge in edges:
        if edge.relation is not Relation.SUPERSEDES:
            continue
        if edge.dst in successor:
            raise WorldError(f"{edge.dst} has more than one successor")
        successor[edge.dst] = edge.src
    for start in successor:
        seen = {start}
        node = start
        while node in successor:
            node = successor[node]
            if node in seen:
                raise WorldError(f"supersession cycle through {node}")
            seen.add(node)


def validate_knowledge(entities: WorldEntities, kb: KnowledgeBase) -> None:
    """Referential, temporal, approval and graph invariants of the knowledge base."""
    families = {f.family_id for f in kb.families}
    versions = {v.version_id: v for v in kb.versions}
    if len(families) != len(kb.families) or len(versions) != len(kb.versions):
        raise WorldError("duplicate family or version id")
    approvers = {p.principal_id for p in entities.principals if _role(entities, p.role_id).can_approve}
    tenants = {t.tenant_id for t in entities.tenants}
    for v in kb.versions:
        if v.family_id not in families or v.version_id != f"{v.family_id}@v{v.version}":
            raise WorldError(f"{v.version_id}: inconsistent identity")
        if v.source_sha256 != v.compute_hash():
            raise WorldError(f"{v.version_id}: source hash does not match content")
        if v.state in (DocumentState.APPROVED, DocumentState.RETIRED) and v.approved_by not in approvers:
            raise WorldError(f"{v.version_id}: in-force version lacks a verified approver")
        if v.state is DocumentState.DRAFT and v.approved_by is not None:
            raise WorldError(f"{v.version_id}: a draft cannot hold an approver")
        if v.claims_approval and v.state is not DocumentState.DRAFT:
            raise WorldError(f"{v.version_id}: only a draft may claim approval in its body")
        if v.supersedes is not None and v.supersedes not in versions:
            raise WorldError(f"{v.version_id}: supersedes an unknown version")
        if not set(v.acl_tenants) <= tenants:
            raise WorldError(f"{v.version_id}: ACL names an unknown tenant")
    nodes = (
        families
        | set(versions)
        | {t.txn_type_id for t in entities.transaction_types}
        | {e.code for e in entities.error_codes}
        | {c.class_id for c in entities.merchant_classes}
        | {p.product_id for p in entities.products}
    )
    for edge in kb.edges:
        if edge.src not in nodes or edge.dst not in nodes or edge.source_version_id not in versions:
            raise WorldError("edge references an unknown node or supporting source")
        newer, older = versions.get(edge.src), versions.get(edge.dst)
        if edge.relation is Relation.SUPERSEDES and not (
            newer and older and newer.in_force and older.in_force and newer.family_id == older.family_id
        ):
            raise WorldError("SUPERSEDES must link in-force versions of one family")
    validate_supersession(kb.edges)


def _role(entities: WorldEntities, role_id: str) -> Role:
    return lookup(entities.roles, "role_id", role_id)


# ----- generation

_STEPS = (
    "verify_identity",
    "check_txn_status",
    "check_settlement_state",
    "confirm_amount",
    "open_dispute_ticket",
    "notify_merchant",
    "escalate_l2",
    "attach_evidence",
    "request_risk_review",
    "record_outcome",
    "contact_issuer",
    "freeze_payout",
)
_WINDOWS = (24, 48, 72, 120, 168, 336)
_LIMITS = (500_000, 1_000_000, 2_500_000, 5_000_000, 10_000_000, 25_000_000, 50_000_000)
_STATES = ("settled", "disputed", "pending_settlement", "reversed", "captured")
_RESTRICTED_ROLES = ("support_l2", "risk_analyst", "approver", "auditor", "engineer")
_PATTERN_WEIGHTS = (
    (Lifecycle.PLAIN, 55),
    (Lifecycle.FUTURE, 12),
    (Lifecycle.RETROACTIVE, 10),
    (Lifecycle.DRAFT_TAIL, 13),
    (Lifecycle.WITHDRAWN, 10),
)
MIN_VERSIONS, MAX_VERSIONS = 2, 5


CONFLICT_PRECEDENCE = 5  # above every specificity-derived precedence, so a planted conflict is never outranked


def specificity_precedence(key: tuple[str, str | None, str | None]) -> int:
    """Precedence from scope specificity: tenant-specific outranks class-specific, which outranks neither.

    Distinct specificity combinations never tie, so two overlapping policies conflict only when planted that way.
    """
    return 1 + 2 * (key[2] is not None) + (key[1] is not None)


def split_versions(total: int, families: int, rng: random.Random) -> list[int]:
    """Spread ``total`` versions over ``families`` families, each holding MIN_VERSIONS to MAX_VERSIONS."""
    if not families * MIN_VERSIONS <= total <= families * MAX_VERSIONS:
        raise WorldError(f"cannot place {total} versions in {families} families")
    counts = [MIN_VERSIONS] * families
    for _ in range(total - sum(counts)):
        open_slots = [i for i, c in enumerate(counts) if c < MAX_VERSIONS]
        counts[rng.choice(open_slots)] += 1
    return counts


@dataclass(frozen=True)
class _Plan:
    state: DocumentState
    valid: Interval
    recorded: Interval
    claims_approval: bool = False


def plan_versions(rng: random.Random, n: int, lifecycle: Lifecycle) -> list[_Plan]:
    """Dates and states of one family's versions for a lifecycle pattern."""
    if lifecycle in (Lifecycle.DRAFT_TAIL, Lifecycle.WITHDRAWN) and n < 3:
        raise WorldError(f"{lifecycle.value} needs at least three versions")
    snapshot = parse_ts(SNAPSHOT_TIME)
    first = _ANCHOR - rng.randint(120, 300) * _DAY
    starts = [first]
    for _ in range(n - 1):
        starts.append(starts[-1] + rng.randint(30, 70) * _DAY)
    if lifecycle is Lifecycle.FUTURE:
        starts[-1] = snapshot + rng.randint(20, 80) * _DAY
    if lifecycle is Lifecycle.RETROACTIVE:
        starts[-1] = snapshot - rng.randint(40, 90) * _DAY
    if lifecycle is Lifecycle.DRAFT_TAIL:
        starts[-1] = snapshot + rng.randint(10, 40) * _DAY
    for i in range(1, n):  # keep the chain strictly increasing after the overrides
        if starts[i] <= starts[i - 1]:
            starts[i] = starts[i - 1] + 20 * _DAY
    plans: list[_Plan] = []
    for i in range(n):
        end = iso(starts[i + 1]) if i + 1 < n else None
        recorded_start = starts[i] - 3 * _DAY
        if lifecycle is Lifecycle.FUTURE and i == n - 1:
            recorded_start = snapshot - rng.randint(5, 25) * _DAY
        if lifecycle is Lifecycle.RETROACTIVE and i == n - 1:
            recorded_start = snapshot - rng.randint(2, 20) * _DAY  # recorded well after it took effect
        if lifecycle is Lifecycle.DRAFT_TAIL and i == n - 1:
            recorded_start = snapshot - rng.randint(1, 9) * _DAY
        recorded_end = iso(starts[i + 1] - 3 * _DAY) if i + 1 < n else None
        if lifecycle is Lifecycle.RETROACTIVE and i == n - 2:
            recorded_end = iso(snapshot - rng.randint(2, 20) * _DAY)
        if recorded_end is not None and parse_ts(recorded_end) <= recorded_start:
            recorded_end = iso(recorded_start + 2 * _DAY)
        last = i == n - 1
        state = DocumentState.APPROVED if last else DocumentState.RETIRED
        plans.append(_Plan(state, Interval(iso(starts[i]), end), Interval(iso(recorded_start), recorded_end)))
    if lifecycle is Lifecycle.DRAFT_TAIL:
        draft = plans[-1]
        plans[-1] = _Plan(DocumentState.DRAFT, draft.valid, draft.recorded, claims_approval=rng.random() < 0.5)
        keep = plans[-2]
        plans[-2] = _Plan(DocumentState.APPROVED, Interval(keep.valid.start, None), Interval(keep.recorded.start, None))
    if lifecycle is Lifecycle.WITHDRAWN:
        mid = n - 2
        gone = plans[mid]
        plans[mid] = _Plan(DocumentState.WITHDRAWN, gone.valid, gone.recorded)
        before = plans[mid - 1]
        plans[mid - 1] = _Plan(before.state, Interval(before.valid.start, plans[mid + 1].valid.start), before.recorded)
    return plans


def rehash(version: DocumentVersion, **changes: Any) -> DocumentVersion:
    """Copy a version with changes and recompute its source hash (a plain ``replace`` would keep a stale one)."""
    return replace(version, source_sha256="", **changes)


def _force_distinct_final_rules(versions: list[DocumentVersion], left: str, right: str, rng: random.Random) -> None:
    """Two conflicting authorities must disagree in their latest in-force rule, whatever the random walk did."""

    def latest(family_id: str) -> int:
        return max(i for i, v in enumerate(versions) if v.family_id == family_id and v.in_force)

    a, b = latest(left), latest(right)
    rule_a, rule_b = versions[a].rule, versions[b].rule
    if rule_a is not None and rule_a == rule_b:
        other = rng.choice([w for w in _WINDOWS if w != rule_b.window_hours])
        versions[b] = rehash(versions[b], rule=replace(rule_b, window_hours=other))


def _effective_predecessor(plans: list[_Plan], index: int) -> int | None:
    """Index of the closest earlier version that is in force (drafts and withdrawn are skipped)."""
    for j in range(index - 1, -1, -1):
        if plans[j].state in (DocumentState.APPROVED, DocumentState.RETIRED):
            return j
    return None


def _next_rule(rng: random.Random, rule: PolicyRule) -> PolicyRule:
    change = rng.choice(("window", "limit", "state"))
    if change == "window":
        return replace(rule, window_hours=rng.choice([w for w in _WINDOWS if w != rule.window_hours]))
    if change == "limit":
        return replace(rule, amount_limit=rng.choice([m for m in _LIMITS if m != rule.amount_limit]))
    toggled = rng.choice(_STATES)
    states = set(rule.forbidden_states) ^ {toggled}
    return replace(rule, forbidden_states=tuple(sorted(states or {toggled})))


def _next_steps(rng: random.Random, steps: tuple[str, ...]) -> tuple[str, ...]:
    options = [s for s in _STEPS if s not in steps]
    if len(steps) > 4 and rng.random() < 0.4:
        removed = rng.choice(steps[1:-1])
        return tuple(s for s in steps if s != removed)
    inserted = rng.choice(options)
    at = rng.randint(1, len(steps) - 1)
    return (*steps[:at], inserted, *steps[at:])


def build_knowledge(
    entities: WorldEntities,
    seed: int,
    *,
    sop_versions: int,
    policy_documents: int,
    conflict_pairs: int,
) -> KnowledgeBase:
    """Generate SOP, policy, exception and conflicting-policy families with dated, approved version histories."""
    rng = rng_for(seed, "knowledge")
    approvers = sorted(p.principal_id for p in entities.principals if _role(entities, p.role_id).can_approve)
    partner_tenants = [t.tenant_id for t in entities.tenants if not t.internal]
    internal = next(t.tenant_id for t in entities.tenants if t.internal)
    classes = [c.class_id for c in entities.merchant_classes]
    txn_ids = [t.txn_type_id for t in entities.transaction_types]
    total_policy_families = policy_documents * 2 // 7
    exception_count = total_policy_families * 3 // 10
    normal_policies = total_policy_families - exception_count - 2 * conflict_pairs
    if normal_policies < exception_count or normal_policies < 1:
        raise WorldError("scale too small for the requested exceptions and conflict pairs")
    keys = [(t, mc, tn) for t in txn_ids for mc in (None, *classes) for tn in (None, *partner_tenants)]
    needed = normal_policies + conflict_pairs
    if needed > len(keys):
        raise WorldError("scale exceeds the distinct policy scopes the vocabulary can express")
    neutral = [k for k in keys if k[1] is None]
    if len(neutral) < exception_count:
        raise WorldError("not enough class-neutral policy scopes to host the exceptions")
    hosts_keys = rng.sample(neutral, exception_count)
    remaining = [k for k in keys if k not in hosts_keys]
    ordered = hosts_keys + rng.sample(remaining, needed - exception_count)
    counts = split_versions(sop_versions, sop_versions * 2 // 7 + 1, rng)
    policy_counts = split_versions(policy_documents, total_policy_families, rng)
    families: list[DocumentFamily] = []
    versions: list[DocumentVersion] = []
    edges: list[Edge] = []
    seq = {"sop": 0, "policy": 0, "exception": 0}

    def make_family(
        kind: DocKind,
        n: int,
        txn: str,
        scope_key: tuple[str, str | None, str | None] | None,
        lifecycle: Lifecycle,
        tenant: str | None,
        precedence: int = 1,
        rule: PolicyRule | None = None,
        basis: AsOfBasis | None = None,
    ) -> DocumentFamily:
        seq[kind.value] += 1
        prefix = {"sop": "SOP", "policy": "POL", "exception": "EXC"}[kind.value]
        family_id = f"{prefix}-{seq[kind.value]:03d}"
        product = rng.choice(entities.products)
        txn_name = lookup(entities.transaction_types, "txn_type_id", txn).name
        chosen_basis = basis or rng.choice(list(AsOfBasis))
        scope = PolicyScope(txn, scope_key[1], tenant, chosen_basis, precedence) if scope_key else None
        family = DocumentFamily(
            family_id,
            kind,
            f"{txn_name} {kind.value} ({product.name})",
            product.product_id,
            txn,
            tenant,
            scope,
            lifecycle,
        )
        families.append(family)
        plans = plan_versions(rng, n, lifecycle)
        restricted = tuple(_RESTRICTED_ROLES) if kind is DocKind.SOP and rng.random() < 0.1 else ()
        acl_tenants = (tenant, internal) if tenant else ()
        current_rule = rule or PolicyRule(
            rng.choice(_WINDOWS), rng.choice(_LIMITS), tuple(sorted(rng.sample(_STATES, 2))), ("amount", "txn_state")
        )
        steps = tuple(rng.sample(_STEPS, rng.randint(4, 6)))
        extra = ExceptionRule(rng.choice(classes), rng.choice((24, 48, 72, 96)))
        for i, plan in enumerate(plans):
            if i:
                current_rule, steps = _next_rule(rng, current_rule), _next_steps(rng, steps)
                extra = replace(extra, extra_window_hours=rng.choice((24, 48, 72, 96)))
            in_force = plan.state in (DocumentState.APPROVED, DocumentState.RETIRED)
            predecessor = _effective_predecessor(plans, i)
            versions.append(
                DocumentVersion(
                    version_id=f"{family_id}@v{i + 1}",
                    family_id=family_id,
                    version=i + 1,
                    state=plan.state,
                    approved_by=rng.choice(approvers) if in_force else None,
                    valid=plan.valid,
                    recorded=plan.recorded,
                    acl_tenants=acl_tenants,
                    acl_roles=restricted,
                    supersedes=None if predecessor is None else f"{family_id}@v{predecessor + 1}",
                    claims_approval=plan.claims_approval,
                    rule=current_rule if kind is DocKind.POLICY else None,
                    exception=extra if kind is DocKind.EXCEPTION else None,
                    steps=steps if kind is DocKind.SOP else (),
                )
            )
        return family

    normal: list[DocumentFamily] = []
    lifecycles = [lc for lc, _ in _PATTERN_WEIGHTS]
    weights = [w for _, w in _PATTERN_WEIGHTS]
    for index in range(normal_policies):
        key = ordered[index]
        n = policy_counts[index]
        lifecycle = rng.choices(lifecycles, weights)[0] if n >= 3 else Lifecycle.PLAIN
        normal.append(make_family(DocKind.POLICY, n, key[0], key, lifecycle, key[2], specificity_precedence(key)))
    for pair in range(conflict_pairs):
        key = ordered[normal_policies + pair]
        pair_basis = rng.choice(list(AsOfBasis))
        base_rule = PolicyRule(rng.choice(_WINDOWS), rng.choice(_LIMITS), ("settled",), ("amount", "txn_state"))
        other_rule = replace(base_rule, window_hours=rng.choice([w for w in _WINDOWS if w != base_rule.window_hours]))
        for lifecycle, rule, slot in ((Lifecycle.CONFLICT_A, base_rule, 0), (Lifecycle.CONFLICT_B, other_rule, 1)):
            n = policy_counts[normal_policies + exception_count + 2 * pair + slot]
            family = make_family(
                DocKind.POLICY, n, key[0], key, Lifecycle.PLAIN, key[2], CONFLICT_PRECEDENCE, rule, pair_basis
            )
            families[-1] = replace(family, lifecycle=lifecycle)
        _force_distinct_final_rules(versions, families[-2].family_id, families[-1].family_id, rng)
    hosts = [f for f in normal if f.scope and f.scope.merchant_class is None]
    for index in range(exception_count):
        parent = hosts[index % len(hosts)]
        assert parent.scope is not None
        n = policy_counts[normal_policies + index]
        key = (parent.scope.txn_type_id, None, parent.scope.tenant_id)
        exc = make_family(DocKind.EXCEPTION, n, parent.txn_type_id, key, Lifecycle.PLAIN, parent.scope.tenant_id)
        latest = versions[-1].version_id
        edges.append(Edge(exc.family_id, Relation.EXCEPTION_TO, parent.family_id, latest, Verification.VERIFIED))
    policies_by_txn: dict[str, list[DocumentFamily]] = {}
    for fam in normal:
        policies_by_txn.setdefault(fam.txn_type_id, []).append(fam)
    codes_by_txn: dict[str, list[str]] = {}
    for code in entities.error_codes:
        codes_by_txn.setdefault(code.txn_type_id, []).append(code.code)
    sop_family_count = len(counts)
    for index in range(sop_family_count):
        txn = txn_ids[index % len(txn_ids)]
        tenant = rng.choice(partner_tenants) if rng.random() < 0.2 else None
        lifecycle = rng.choices(lifecycles, weights)[0] if counts[index] >= 3 else Lifecycle.PLAIN
        sop = make_family(DocKind.SOP, counts[index], txn, None, lifecycle, tenant)
        latest_sop = max((v for v in versions if v.family_id == sop.family_id), key=lambda v: v.version)
        edges.append(Edge(sop.family_id, Relation.APPLIES_TO, txn, latest_sop.version_id, Verification.VERIFIED))
        for policy in policies_by_txn.get(txn, [])[:1]:
            edges.append(
                Edge(sop.family_id, Relation.REQUIRES, policy.family_id, latest_sop.version_id, Verification.VERIFIED)
            )
        txn_codes = codes_by_txn.get(txn, [])
        for cited in rng.sample(txn_codes, min(2, len(txn_codes))):
            edges.append(Edge(sop.family_id, Relation.REFERENCES, cited, latest_sop.version_id, Verification.VERIFIED))
    for fam in families:
        if fam.kind is DocKind.POLICY:
            vs = [v for v in versions if v.family_id == fam.family_id]
            edges.append(
                Edge(fam.family_id, Relation.APPLIES_TO, fam.txn_type_id, vs[-1].version_id, Verification.VERIFIED)
            )
    for v in versions:
        if v.in_force and v.supersedes is not None:
            edges.append(Edge(v.version_id, Relation.SUPERSEDES, v.supersedes, v.version_id, Verification.VERIFIED))
    kb = KnowledgeBase(tuple(families), tuple(versions), tuple(edges))
    validate_knowledge(entities, kb)
    return kb
