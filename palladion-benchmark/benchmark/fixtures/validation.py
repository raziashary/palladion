"""Fixture and label integrity validation (B02-T06.01).

Every check reads the built fixture the way a consumer would and reports findings instead of raising, so one run lists
all defects. Gold-support is verified on the rendered text with a number extractor that shares no code with the
renderer (BADR-0022), and realism is judged by the floors and ceilings fixed in that ADR before the first measurement.
Checks never edit the fixture.
"""

from __future__ import annotations

import math
import re
import statistics
from collections import Counter
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import combinations_with_replacement

from benchmark.fixtures import sha256_hex
from benchmark.fixtures.documents import Category, Document
from benchmark.fixtures.entities import WorldError, validate_entities
from benchmark.fixtures.knowledge import (
    SNAPSHOT_TIME,
    CaseFacts,
    CaseTimes,
    DocKind,
    Lifecycle,
    SelectionStatus,
    parse_ts,
    resolve_policy,
    validate_knowledge,
)
from benchmark.fixtures.manifest import find_barrier_markers
from benchmark.fixtures.operations import validate_operations
from benchmark.fixtures.questions import Answerability, GoldRecord, Stratum
from benchmark.fixtures.world import World

# Floors and ceilings fixed in BADR-0022 before the first measurement.
MAX_LEXICAL_SOLVABILITY = 0.60
MIN_SENTENCE_LENGTH_CV = 0.25
MIN_SKELETON_DIVERSITY = 0.10
MAX_NAIVE_NEWEST = 0.30
MAX_NAIVE_OLDEST = 0.60
SOLVABILITY_STRATA = (Stratum.Q2, Stratum.Q3, Stratum.Q4, Stratum.Q5)

_ID_TOKEN = re.compile(r"\b(?:[A-Z]{3}-\d{3}(?:@v\d+)?|MS-\d{4}|TXN-[A-Z]{3}-\d{5}|CASE-\d{5})\b")
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}(?:T[\d:]+Z)?")
_CLAUSE_ID = re.compile(r"(?m)^\d+(?:\.\d+)+ ")
_NUMBER = re.compile(r"\d[\d.,]*")
_WORD = re.compile(r"[a-z]+")
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")


@dataclass(frozen=True)
class Finding:
    check: str
    subject: str
    detail: str


@dataclass(frozen=True)
class ValidationReport:
    findings: tuple[Finding, ...]
    metrics: Mapping[str, float] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.findings

    def checks(self) -> set[str]:
        return {f.check for f in self.findings}


# --------------------------------------------------------------------------- structure


def _world_findings(world: World) -> list[Finding]:
    """The world's own invariant validators, reported as findings instead of raised."""
    validators: tuple[tuple[str, Callable[[], None]], ...] = (
        ("entities", lambda: validate_entities(world.entities)),
        ("knowledge", lambda: validate_knowledge(world.entities, world.knowledge)),
        ("operations", lambda: validate_operations(world.entities, world.operations)),
    )
    out: list[Finding] = []
    for label, run in validators:
        try:
            run()
        except WorldError as exc:
            out.append(Finding("referential", label, str(exc)))
    return out


def check_referential(world: World, corpus: Sequence[Document]) -> list[Finding]:
    """Every version has its document, every document its hash, and every id mentioned in a ticket exists."""
    out = _world_findings(world)
    docs = {d.doc_id: d for d in corpus}
    if len(docs) != len(corpus):
        out.append(Finding("referential", "corpus", "duplicate document ids"))
    for version in world.knowledge.versions:
        doc = docs.get(version.version_id)
        if doc is None:
            out.append(Finding("referential", version.version_id, "version has no published document"))
        elif not doc.clauses:
            out.append(Finding("referential", version.version_id, "document has no resolvable clauses"))
    versions = {v.version_id for v in world.knowledge.versions}
    transactions = {t.txn_id for t in world.operations.transactions}
    cases = {c.case_id for c in world.operations.cases}
    for doc in corpus:
        if doc.sha256 != sha256_hex(doc.text):
            out.append(Finding("referential", doc.doc_id, "hash does not match the text"))
        if doc.source_version_id is not None and doc.source_version_id not in versions:
            out.append(Finding("referential", doc.doc_id, "document names an unknown version"))
        for token in re.findall(r"TXN-[A-Z]{3}-\d{5}", doc.text):
            if token not in transactions:
                out.append(Finding("referential", doc.doc_id, f"unknown transaction {token}"))
        for token in re.findall(r"CASE-\d{5}", doc.text):
            if token not in cases:
                out.append(Finding("referential", doc.doc_id, f"unknown case {token}"))
    return out


def check_contradiction(world: World) -> list[Finding]:
    """Planted conflicts truly share scope and time and disagree; no other two policies share a scope."""
    out: list[Finding] = []
    kb = world.knowledge
    sides = {
        lifecycle: [f for f in kb.families if f.lifecycle is lifecycle]
        for lifecycle in (Lifecycle.CONFLICT_A, Lifecycle.CONFLICT_B)
    }
    for a, b in zip(sides[Lifecycle.CONFLICT_A], sides[Lifecycle.CONFLICT_B], strict=False):
        last_a, last_b = (next(v for v in reversed(kb.versions_of(f.family_id)) if v.in_force) for f in (a, b))
        if a.scope != b.scope:
            out.append(Finding("contradiction", a.family_id, "the two authorities do not cover the same scope"))
        if not last_a.valid.overlaps(last_b.valid):
            out.append(Finding("contradiction", a.family_id, "the two authorities do not overlap in time"))
        if last_a.rule == last_b.rule:
            out.append(Finding("contradiction", a.family_id, "the two authorities do not disagree"))
    if len(sides[Lifecycle.CONFLICT_A]) != len(sides[Lifecycle.CONFLICT_B]):
        out.append(Finding("contradiction", "pairs", "a conflict family has no partner"))
    out += unplanned_conflicts(world)
    seen: dict[tuple[object, ...], str] = {}
    for f in kb.families:
        if f.kind is DocKind.POLICY and f.scope and f.lifecycle not in (Lifecycle.CONFLICT_A, Lifecycle.CONFLICT_B):
            key = (f.scope.txn_type_id, f.scope.merchant_class, f.scope.tenant_id)
            if key in seen:
                out.append(Finding("contradiction", f.family_id, f"accidental contradiction with {seen[key]}"))
            seen[key] = f.family_id
    return out


def unplanned_conflicts(world: World) -> list[Finding]:
    """Cases where overlapping policies disagree at equal precedence although no conflict was planted there."""
    planted = {
        f.family_id for f in world.knowledge.families if f.lifecycle in (Lifecycle.CONFLICT_A, Lifecycle.CONFLICT_B)
    }
    times = CaseTimes(*([SNAPSHOT_TIME] * 4))
    out: list[Finding] = []
    for tenant in (t.tenant_id for t in world.entities.tenants if not t.internal):
        for txn in world.entities.transaction_types:
            for cls in world.entities.merchant_classes:
                facts = CaseFacts(tenant, txn.txn_type_id, cls.class_id, None, None, times)
                found = resolve_policy(world.knowledge, facts)
                if found.status is SelectionStatus.CONFLICT and not any(
                    v.split("@")[0] in planted for v in found.version_ids
                ):
                    subject = f"{tenant}/{txn.txn_type_id}/{cls.class_id}"
                    out.append(
                        Finding("contradiction", subject, "overlapping policies disagree and no conflict was planted")
                    )
    return out


def check_merge_identity(world: World, corpus: Sequence[Document]) -> list[Finding]:
    """Same-named merchants stay distinct, and each ticket names the merchant id that its case belongs to."""
    out: list[Finding] = []
    by_name: dict[str, list[tuple[str, str]]] = {}
    for m in world.entities.merchants:
        by_name.setdefault(m.display_name, []).append((m.merchant_id, m.tenant_id))
    for name, holders in by_name.items():
        ids = [h[0] for h in holders]
        if len(set(ids)) != len(ids):
            out.append(Finding("merge_identity", name, "two merchants share an identifier"))
        if len({h[1] for h in holders}) != len(holders):
            out.append(Finding("merge_identity", name, "same-named merchants are not in different tenants"))
    for doc in corpus:
        if doc.category is not Category.TICKETS_AND_CASES or "truncated" in doc.tags:
            continue
        found = re.search(r"CASE-\d{5}", doc.text)
        if found is None:
            continue
        case = next((c for c in world.operations.cases if c.case_id == found.group(0)), None)
        if (
            case is not None
            and case.merchant_id not in doc.text
            and not any(t.startswith("near_duplicate") for t in doc.tags)
        ):
            out.append(Finding("merge_identity", doc.doc_id, "ticket does not carry its merchant's identifier"))
    return out


def check_temporal(world: World) -> list[Finding]:
    """Timestamps parse with a zone, intervals are explicit, and open ends are only on the latest in-force version."""
    out: list[Finding] = []
    for family in world.knowledge.families:
        versions = world.knowledge.versions_of(family.family_id)
        in_force = [v for v in versions if v.in_force]
        for v in versions:
            try:
                parse_ts(v.valid.start)
                parse_ts(v.recorded.start)
            except ValueError as exc:
                out.append(Finding("temporal", v.version_id, str(exc)))
        for earlier in in_force[:-1]:
            if earlier.valid.end is None:
                out.append(Finding("temporal", earlier.version_id, "an open-ended version is followed by a later one"))
    return out


# --------------------------------------------------------------------------- gold


def _strip_ids(text: str) -> str:
    return _ISO_DATE.sub(" ", _ID_TOKEN.sub(" ", text))


def numbers_in(text: str) -> set[int]:
    """Integers in ``text`` with identifiers and dates removed and thousands separators ignored."""
    out: set[int] = set()
    for token in _NUMBER.findall(_CLAUSE_ID.sub(" ", _strip_ids(text))):
        digits = re.sub(r"[.,]", "", token)
        if digits:
            out.add(int(digits))
    return out


def _span_text(doc: Document, start: int, end: int) -> str:
    return doc.text[start:end] if end > start else ""


def check_gold_support(records: Sequence[GoldRecord], corpus: Sequence[Document], world: World) -> list[Finding]:
    """Cited spans exist and hash correctly, are visible to the principal, and carry every number the claims state."""
    out: list[Finding] = []
    docs = {d.doc_id: d for d in corpus}
    principals = {p.principal_id: p for p in world.entities.principals}
    for r in records:
        who = principals.get(r.principal_id)
        span_numbers: set[int] = set()
        live = False
        for slot in r.slots:
            for c in slot.alternatives:
                if c.doc_id.startswith("live:"):
                    live = True
                    continue
                doc = docs.get(c.doc_id)
                if doc is None:
                    out.append(Finding("gold_support", r.question_id, f"cited document {c.doc_id} does not exist"))
                    continue
                span = _span_text(doc, c.start, c.end) or doc.text
                if sha256_hex(doc.text[c.start : c.end] if c.end > c.start else doc.text) != c.span_sha256:
                    out.append(Finding("gold_support", r.question_id, f"span hash mismatch in {c.doc_id}"))
                if who is not None and not is_visible(doc, who.tenant_id, who.role_id):
                    out.append(Finding("gold_support", r.question_id, f"{c.doc_id} is not visible to the principal"))
                span_numbers |= numbers_in(span)
        if live or r.answerability is Answerability.UNANSWERABLE:
            continue
        for claim in r.required_claims:
            for number in numbers_in(claim):
                derived = any(a + b == number for a, b in combinations_with_replacement(sorted(span_numbers), 2))
                if number not in span_numbers and not derived:
                    out.append(
                        Finding("gold_support", r.question_id, f"claim number {number} is not in the cited text")
                    )
    return out


def is_visible(doc: Document, tenant_id: str, role_id: str) -> bool:
    return (not doc.acl_tenants or tenant_id in doc.acl_tenants) and (not doc.acl_roles or role_id in doc.acl_roles)


def check_forbidden_gold(records: Sequence[GoldRecord], corpus: Sequence[Document], world: World) -> list[Finding]:
    """Sources a question calls inaccessible really are inaccessible to its principal, and are never cited."""
    out: list[Finding] = []
    docs = {d.doc_id: d for d in corpus}
    principals = {p.principal_id: p for p in world.entities.principals}
    for r in records:
        who = principals[r.principal_id]
        cited = {c.doc_id for s in r.slots for c in s.alternatives}
        for doc_id in r.inaccessible_sources:
            doc = docs.get(doc_id)
            if doc is None:
                out.append(Finding("forbidden_gold", r.question_id, f"{doc_id} does not exist"))
            elif is_visible(doc, who.tenant_id, who.role_id):
                out.append(Finding("forbidden_gold", r.question_id, f"{doc_id} is visible to the principal"))
            if doc_id in cited:
                out.append(Finding("forbidden_gold", r.question_id, f"{doc_id} is cited as accessible evidence"))
    return out


def check_leakage(records: Sequence[GoldRecord], corpus: Sequence[Document]) -> list[Finding]:
    """No gold vocabulary or question id in the corpus, and no required answer number stated in a question."""
    out: list[Finding] = []
    ids = {r.question_id for r in records}
    for doc in corpus:
        for marker in find_barrier_markers(f"{doc.title}\n{doc.text}"):
            out.append(Finding("leakage", doc.doc_id, f"{marker} in the published text"))
        out += [Finding("leakage", doc.doc_id, f"question id {q}") for q in ids if q in doc.text]
    for r in records:
        stated = numbers_in(r.query)
        answers = {n for claim in r.required_claims for n in numbers_in(claim)}
        shared = (stated & answers) - {1}
        if shared and r.stratum is not Stratum.Q10:
            out.append(Finding("leakage", r.question_id, f"the question states answer numbers {sorted(shared)}"))
    return out


# --------------------------------------------------------------------------- realism


def _tokens(text: str) -> list[str]:
    return [t for t in _WORD.findall(text.lower()) if len(t) > 1]


class Bm25:
    def __init__(self, docs: Mapping[str, str], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.terms = {doc_id: Counter(_tokens(text)) for doc_id, text in docs.items()}
        self.lengths = {doc_id: sum(c.values()) for doc_id, c in self.terms.items()}
        self.average = sum(self.lengths.values()) / max(1, len(docs))
        self.frequency: Counter[str] = Counter(t for c in self.terms.values() for t in c)

    def ranked(self, query: str, allowed: Collection[str] | None = None, limit: int = 1) -> list[str]:
        """Document ids by descending BM25 score for ``query``, ties by id; zero-score documents are left out."""
        n = len(self.terms)
        scored: list[tuple[float, str]] = []
        for doc_id in sorted(self.terms if allowed is None else allowed):
            counts, length = self.terms[doc_id], self.lengths[doc_id]
            score = 0.0
            for term in set(_tokens(query)):
                tf = counts.get(term, 0)
                if not tf:
                    continue
                df = self.frequency[term]
                idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
                score += idf * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * length / self.average))
            if score > 0:
                scored.append((-score, doc_id))
        return [doc_id for _, doc_id in sorted(scored)[:limit]]

    def top(self, query: str, allowed: Collection[str]) -> str | None:
        found = self.ranked(query, allowed, 1)
        return found[0] if found else None


def lexical_solvability(records: Sequence[GoldRecord], corpus: Sequence[Document], world: World) -> float:
    """Share of policy questions whose gold document ranks first for an identifier-free BM25 query."""
    index = Bm25({d.doc_id: d.text for d in corpus})
    principals = {p.principal_id: p for p in world.entities.principals}
    hits = total = 0
    for r in records:
        if r.stratum not in SOLVABILITY_STRATA or r.answerability not in (
            Answerability.ANSWERABLE,
            Answerability.PARTIAL,
        ):
            continue
        who = principals[r.principal_id]
        allowed = {d.doc_id for d in corpus if is_visible(d, who.tenant_id, who.role_id)}
        query = " ".join(t for t in r.query.split() if not any(ch.isdigit() for ch in t))
        gold = {c.doc_id for s in r.slots for c in s.alternatives}
        total += 1
        hits += index.top(query, allowed) in gold
    return hits / total if total else 0.0


def _skeleton(sentence: str) -> str:
    return re.sub(r"\d+", "0", _ID_TOKEN.sub("ID", sentence.lower())).strip()


def sentence_statistics(corpus: Sequence[Document]) -> tuple[float, float]:
    """(coefficient of variation of sentence length, distinct skeletons over sentences) for support documents."""
    sentences = [
        s.strip()
        for d in corpus
        if not d.authoritative
        for s in _SENTENCE.split(
            "\n".join(line for line in d.text.split("\n") if not line.startswith(("> ", "- ", "|")))
        )
        if len(s.split()) >= 3
    ]
    if len(sentences) < 2:
        return 0.0, 0.0
    lengths = [len(s.split()) for s in sentences]
    cv = statistics.pstdev(lengths) / statistics.mean(lengths)
    return cv, len({_skeleton(s) for s in sentences}) / len(sentences)


def version_order_baselines(records: Sequence[GoldRecord], world: World) -> tuple[float, float]:
    """(share of Q4 answers a newest-version rule gets right, share an oldest-version rule gets right)."""
    q4 = [r for r in records if r.stratum is Stratum.Q4]
    if not q4:
        return 0.0, 0.0
    newest = oldest = 0
    for r in q4:
        chosen = r.gold_applicable_version_ids[0]
        in_force = [v.version_id for v in world.knowledge.versions_of(chosen.split("@")[0]) if v.in_force]
        newest += chosen == in_force[-1]
        oldest += chosen == in_force[0]
    return newest / len(q4), oldest / len(q4)


def check_realism(
    records: Sequence[GoldRecord], corpus: Sequence[Document], world: World
) -> tuple[list[Finding], dict[str, float]]:
    solvable = lexical_solvability(records, corpus, world)
    cv, diversity = sentence_statistics(corpus)
    newest, oldest = version_order_baselines(records, world)
    metrics = {
        "lexical_solvability": round(solvable, 4),
        "sentence_length_cv": round(cv, 4),
        "skeleton_diversity": round(diversity, 4),
        "naive_newest_correct": round(newest, 4),
        "naive_oldest_correct": round(oldest, 4),
    }
    limits: list[tuple[str, bool, str]] = [
        ("trivially_searchable", solvable <= MAX_LEXICAL_SOLVABILITY, f"identifier-free BM25 solves {solvable:.2f}"),
        ("over_regular", cv >= MIN_SENTENCE_LENGTH_CV, f"sentence-length variation {cv:.2f}"),
        ("over_regular", diversity >= MIN_SKELETON_DIVERSITY, f"skeleton diversity {diversity:.2f}"),
        ("version_shortcut", newest <= MAX_NAIVE_NEWEST, f"newest-version rule is right {newest:.2f}"),
        ("version_shortcut", oldest <= MAX_NAIVE_OLDEST, f"oldest-version rule is right {oldest:.2f}"),
    ]
    return [Finding(name, "corpus", detail) for name, ok, detail in limits if not ok], metrics


# --------------------------------------------------------------------------- tiers


def family_fingerprint(world: World, family_id: str) -> str:
    """A family's identity by content, so two worlds that reuse a name are still told apart."""
    return sha256_hex("|".join(v.source_sha256 for v in world.knowledge.versions_of(family_id)))


def cross_tier_overlap(
    world_a: World, records_a: Sequence[GoldRecord], world_b: World, records_b: Sequence[GoldRecord]
) -> set[str]:
    """Content fingerprints of policy families used by questions in both tiers. Empty means disjoint."""

    def used(world: World, records: Sequence[GoldRecord]) -> set[str]:
        names = {v.split("@")[0] for r in records for v in r.gold_applicable_version_ids} | {
            r.scenario_family for r in records if r.scenario_family in {f.family_id for f in world.knowledge.families}
        }
        return {family_fingerprint(world, n) for n in names}

    return used(world_a, records_a) & used(world_b, records_b)


# --------------------------------------------------------------------------- entry point


def validate_fixture(world: World, corpus: Sequence[Document], records: Sequence[GoldRecord]) -> ValidationReport:
    """Run every check on a built fixture and return all findings with the realism metrics."""
    findings: list[Finding] = []
    runs: tuple[Callable[[], list[Finding]], ...] = (
        lambda: check_referential(world, corpus),
        lambda: check_contradiction(world),
        lambda: check_merge_identity(world, corpus),
        lambda: check_temporal(world),
        lambda: check_gold_support(records, corpus, world),
        lambda: check_forbidden_gold(records, corpus, world),
        lambda: check_leakage(records, corpus),
    )
    for run in runs:
        findings += run()
    realism, metrics = check_realism(records, corpus, world)
    return ValidationReport(tuple(findings + realism), metrics)
