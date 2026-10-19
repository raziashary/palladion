"""Template rendering of the hidden world into published documents (B02-T02.01).

Authoritative documents (SOP versions, policy clauses, exceptions) are rendered from structured versions with no model
in the loop. Critical identifiers, dates, thresholds and negations are read back out by :func:`check_equivalence`, so
a template, a typo or a later paraphrase that changes one is detected. Every document starts with the fictional notice
and a fixed header schema, which is the explicit consistent header that condition C1 relies on (protocol 3.2).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Final

from benchmark.fixtures import FICTIONAL_NOTICE, sha256_hex
from benchmark.fixtures.entities import WorldError, rng_for
from benchmark.fixtures.knowledge import (
    SNAPSHOT_TIME,
    AsOfBasis,
    CaseTimes,
    DocKind,
    DocumentVersion,
    Relation,
    parse_ts,
    select_versions,
)
from benchmark.fixtures.phrasebook import (
    ALL_WORD,
    BASIS_NAMES,
    FACT_PHRASES,
    INPUT_NAMES,
    PURPOSE,
    STEP_PHRASES,
    format_amount,
    match_fact,
    parse_amount,
)
from benchmark.fixtures.world import World

LANGUAGE_CHOICES: Final = ("en", "id", "mixed")
HEADER_FIELDS: Final = (
    "Document ID",
    "Version",
    "Status",
    "Effective from",
    "Effective until",
    "Approved by",
    "Applies to",
)
_CLAUSE_LINE = re.compile(r"^(\d+\.\d+) (.*)$")
_HEADER_LINE = re.compile(r"^- ([A-Za-z ]+): (.*)$")
_REVERSE_INPUTS = {name: key for names in INPUT_NAMES.values() for key, name in names.items()}
_REVERSE_BASIS = {name: key for names in BASIS_NAMES.values() for key, name in names.items()}
_SECTION_TITLES: Final = {DocKind.POLICY: "Requirements", DocKind.EXCEPTION: "Exception", DocKind.SOP: "Procedure"}

Values = Callable[[str], dict[str, str]]


@dataclass(frozen=True)
class Clause:
    """A numbered clause, the character span it occupies in the rendered text and the facts it carries."""

    clause_id: str
    facts: tuple[str, ...]
    start: int
    end: int


@dataclass(frozen=True)
class RenderedDocument:
    version_id: str
    language: str
    text: str
    sha256: str
    clauses: tuple[Clause, ...]

    def clause_for(self, fact: str) -> Clause:
        for clause in self.clauses:
            if fact in clause.facts:
                return clause
        raise WorldError(f"{self.version_id} has no clause carrying {fact}")

    def span_text(self, clause_id: str) -> str:
        for clause in self.clauses:
            if clause.clause_id == clause_id:
                return self.text[clause.start : clause.end]
        raise WorldError(f"{self.version_id} has no clause {clause_id}")


def normalise_text(text: str) -> str:
    """NFC, LF line ends, one trailing newline: the single text form that is hashed and indexed."""
    return unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n")).rstrip() + "\n"


class _Builder:
    """Accumulates numbered clauses for one document and speaks each sentence in a chosen language."""

    def __init__(self, world: World, version: DocumentVersion, language: str) -> None:
        if language not in LANGUAGE_CHOICES:
            raise WorldError(f"unknown language {language}")
        self.world = world
        self.version = version
        self.language = language
        self.rng = rng_for(world.seed, f"render:{version.version_id}:{language}")
        self._last = "en" if self.rng.random() < 0.5 else "id"
        self.clauses: list[tuple[str, tuple[str, ...], str]] = []

    def lang(self) -> str:
        if self.language != "mixed":
            return self.language
        if self.rng.random() < 0.8:  # alternate most of the time so even a short mixed document really mixes
            self._last = "id" if self._last == "en" else "en"
        return self._last

    def say(self, key: str, values: Values) -> str:
        lang = self.lang()
        variants = FACT_PHRASES[key][lang]
        return variants[self.rng.randrange(len(variants))].template.format(**values(lang))

    def add(self, clause_id: str, facts: tuple[str, ...], sentence: str) -> None:
        self.clauses.append((clause_id, facts, f"{clause_id} {sentence}"))


def _utc_date(moment: str) -> str:
    return parse_ts(moment).strftime("%Y-%m-%d")


def _class_name(world: World, class_id: str) -> str:
    for item in world.entities.merchant_classes:
        if item.class_id == class_id:
            return item.name
    raise WorldError(f"unknown merchant class {class_id}")


def exception_parent(world: World, family_id: str) -> str:
    for edge in world.knowledge.edges:
        if edge.relation is Relation.EXCEPTION_TO and edge.src == family_id:
            return edge.dst
    raise WorldError(f"{family_id} is not linked to a policy by EXCEPTION_TO")


def _scope_values(world: World, version: DocumentVersion) -> Values:
    family = world.knowledge.family(version.family_id)
    scope = family.scope

    def values(lang: str) -> dict[str, str]:
        cls_text = _class_name(world, scope.merchant_class) if scope and scope.merchant_class else ALL_WORD[lang]
        return {"txn": family.txn_type_id, "cls": cls_text, "tenant": family.tenant_id or ALL_WORD[lang]}

    return values


def _body(builder: _Builder) -> None:
    world, version = builder.world, builder.version
    family = world.knowledge.family(version.family_id)
    builder.add("2.1", ("scope",), builder.say("scope", _scope_values(world, version)))
    if version.valid.end:
        end = version.valid.end
        builder.add(
            "3.1",
            ("effective",),
            builder.say("effective_closed", lambda _l: {"start": version.valid.start, "end": end}),
        )
    else:
        builder.add("3.1", ("effective",), builder.say("effective_open", lambda _l: {"start": version.valid.start}))
    rule, exception = version.rule, version.exception
    if family.kind is DocKind.POLICY and rule is not None and family.scope is not None:
        basis = family.scope.basis.value
        builder.add("4.1", ("window",), builder.say("window", lambda _l: {"w": str(rule.window_hours)}))
        builder.add(
            "4.2", ("limit",), builder.say("limit", lambda lang: {"limit": format_amount(rule.amount_limit, lang)})
        )
        builder.add("4.3", ("states",), builder.say("states", lambda _l: {"states": ", ".join(rule.forbidden_states)}))
        builder.add(
            "4.4",
            ("inputs",),
            builder.say(
                "inputs", lambda lang: {"inputs": ", ".join(INPUT_NAMES[lang][n] for n in rule.required_inputs)}
            ),
        )
        builder.add("4.5", ("basis",), builder.say("basis", lambda lang: {"basis": BASIS_NAMES[lang][basis]}))
    elif family.kind is DocKind.EXCEPTION and exception is not None:
        parent = exception_parent(world, family.family_id)
        cls_name = _class_name(world, exception.merchant_class)
        extra = str(exception.extra_window_hours)
        builder.add(
            "4.1",
            ("exception",),
            builder.say("exception", lambda _l: {"cls": cls_name, "parent": parent, "extra": extra}),
        )
    elif family.kind is DocKind.SOP:
        for index, step in enumerate(version.steps, start=1):
            variants = STEP_PHRASES[step][builder.lang()]
            builder.add(f"4.{index}", (f"step:{step}",), variants[builder.rng.randrange(len(variants))])
        _sop_references(builder, family.family_id)
    if version.supersedes:
        prev = version.supersedes
        builder.add("5.1", ("supersedes",), builder.say("supersedes", lambda _l: {"prev": prev}))
    if version.claims_approval:
        date = _utc_date(version.valid.start)
        builder.add("6.1", ("spoof",), builder.say("spoof", lambda _l: {"date": date}))


def _sop_references(builder: _Builder, family_id: str) -> None:
    edges = builder.world.knowledge.edges
    policies = sorted(e.dst for e in edges if e.src == family_id and e.relation is Relation.REQUIRES)
    codes = sorted(e.dst for e in edges if e.src == family_id and e.relation is Relation.REFERENCES)
    if policies:
        builder.add("5.2", ("policy_ref",), builder.say("policy_ref", lambda _l: {"pol": policies[0]}))
    if codes:
        builder.add("5.3", ("codes_ref",), builder.say("codes_ref", lambda _l: {"codes": ", ".join(codes)}))


def render_version(world: World, version: DocumentVersion, language: str) -> RenderedDocument:
    """Render one structured version into a document with numbered clauses and character offsets."""
    builder = _Builder(world, version, language)
    family = world.knowledge.family(version.family_id)
    _body(builder)
    lines = [
        f"> {FICTIONAL_NOTICE}",
        "",
        f"# {family.title}",
        "",
        f"- Document ID: {family.family_id}",
        f"- Version: {version.version}",
        f"- Status: {version.state.value}",
        f"- Effective from: {version.valid.start}",
        f"- Effective until: {version.valid.end or 'open'}",
        f"- Approved by: {version.approved_by or 'not approved'}",
        f"- Applies to: {family.txn_type_id}",
        "",
    ]
    titles = {"1": "Purpose", "2": "Scope", "3": "Effective period", "4": _SECTION_TITLES[family.kind]}
    titles.update({"5": "References and lineage", "6": "Approval notice"})
    sections = sorted({"1", "2", "3", "4"} | {c[0].split(".")[0] for c in builder.clauses})
    placed: list[tuple[int, str, tuple[str, ...]]] = []  # (line index, clause id, facts)
    for number in sections:
        lines.append(f"## {number} {titles[number]}")
        if number == "1":
            lines.append(PURPOSE[builder.lang()][builder.rng.randrange(3)])
        for clause_id, facts, line in builder.clauses:
            if clause_id.split(".")[0] == number:
                placed.append((len(lines), clause_id, facts))
                lines.append(line)
        lines.append("")
    text = normalise_text("\n".join(lines))
    if text != "\n".join(lines).rstrip() + "\n":
        raise WorldError(f"{version.version_id}: rendering changed under normalisation")
    starts, cursor = [], 0
    for line in lines:
        starts.append(cursor)
        cursor += len(line) + 1
    clauses = tuple(Clause(cid, facts, starts[i], starts[i] + len(lines[i])) for i, cid, facts in placed)
    return RenderedDocument(version.version_id, language, text, sha256_hex(text), clauses)


# --------------------------------------------------------------------------- reading facts back out


@dataclass
class ExtractedFacts:
    """Facts read back out of rendered text by pattern, never from the world."""

    header: dict[str, str] = field(default_factory=dict)
    window: int | None = None
    limit: int | None = None
    states: tuple[str, ...] | None = None
    inputs: tuple[str, ...] | None = None
    basis: str | None = None
    exception: tuple[str, str, int] | None = None
    effective: tuple[str, str | None] | None = None
    supersedes: str | None = None
    scope: tuple[str, str, str] | None = None
    policy_ref: str | None = None
    codes: tuple[str, ...] | None = None
    steps: tuple[str, ...] = ()
    claims_approval: bool = False


_ALL_WORDS = frozenset(ALL_WORD.values())


def _star(value: str) -> str:
    return "*" if value in _ALL_WORDS else value


def extract_facts(text: str) -> ExtractedFacts:
    """Read header fields and every fact-bearing clause out of rendered text."""
    out = ExtractedFacts()
    steps: list[str] = []
    for line in text.split("\n"):
        header = _HEADER_LINE.match(line)
        if header and header.group(1) in HEADER_FIELDS:
            out.header[header.group(1)] = header.group(2)
            continue
        clause = _CLAUSE_LINE.match(line)
        if not clause:
            continue
        sentence = clause.group(2)
        step = _match_step(sentence)
        if step:
            steps.append(step)
            continue
        for key in FACT_PHRASES:
            found = match_fact(key, sentence)
            if found:
                _store(out, key, found[1])
                break
    out.steps = tuple(steps)
    return out


def _match_step(sentence: str) -> str | None:
    for key, by_language in STEP_PHRASES.items():
        if any(sentence in variants for variants in by_language.values()):
            return key
    return None


def _store(out: ExtractedFacts, key: str, got: dict[str, str]) -> None:
    if key == "window":
        out.window = int(got["w"])
    elif key == "limit":
        out.limit = parse_amount(got["limit"])
    elif key == "states":
        out.states = tuple(got["states"].split(", "))
    elif key == "inputs":
        out.inputs = tuple(_REVERSE_INPUTS.get(n, f"?{n}") for n in got["inputs"].split(", "))
    elif key == "basis":
        out.basis = _REVERSE_BASIS.get(got["basis"], f"?{got['basis']}")
    elif key == "exception":
        out.exception = (got["cls"], got["parent"], int(got["extra"]))
    elif key in ("effective_closed", "effective_open"):
        out.effective = (got["start"], got.get("end"))
    elif key == "supersedes":
        out.supersedes = got["prev"]
    elif key == "scope":
        out.scope = (got["txn"], _star(got["cls"]), _star(got["tenant"]))
    elif key == "policy_ref":
        out.policy_ref = got["pol"]
    elif key == "codes_ref":
        out.codes = tuple(got["codes"].split(", "))
    elif key == "spoof":
        out.claims_approval = True


def expected_facts(world: World, version: DocumentVersion) -> ExtractedFacts:
    """What the world says the rendered text must contain."""
    family = world.knowledge.family(version.family_id)
    scope = family.scope
    out = ExtractedFacts(
        header={
            "Document ID": family.family_id,
            "Version": str(version.version),
            "Status": version.state.value,
            "Effective from": version.valid.start,
            "Effective until": version.valid.end or "open",
            "Approved by": version.approved_by or "not approved",
            "Applies to": family.txn_type_id,
        },
        effective=(version.valid.start, version.valid.end),
        supersedes=version.supersedes,
        scope=(
            family.txn_type_id,
            _class_name(world, scope.merchant_class) if scope and scope.merchant_class else "*",
            family.tenant_id or "*",
        ),
        claims_approval=version.claims_approval,
        steps=version.steps,
    )
    if version.rule is not None and scope is not None:
        out.window, out.limit = version.rule.window_hours, version.rule.amount_limit
        out.states, out.inputs, out.basis = (
            version.rule.forbidden_states,
            version.rule.required_inputs,
            scope.basis.value,
        )
    if version.exception is not None:
        out.exception = (
            _class_name(world, version.exception.merchant_class),
            exception_parent(world, family.family_id),
            version.exception.extra_window_hours,
        )
    if family.kind is DocKind.SOP:
        edges = world.knowledge.edges
        policies = sorted(e.dst for e in edges if e.src == family.family_id and e.relation is Relation.REQUIRES)
        codes = sorted(e.dst for e in edges if e.src == family.family_id and e.relation is Relation.REFERENCES)
        out.policy_ref = policies[0] if policies else None
        out.codes = tuple(codes) if codes else None
    return out


def check_equivalence(world: World, version: DocumentVersion, text: str) -> tuple[str, ...]:
    """Compare facts read from ``text`` with the world. An empty result means every critical fact survived."""
    want, got = expected_facts(world, version), extract_facts(text)
    problems = [
        f"header {k}: expected {v!r}, found {got.header.get(k)!r}"
        for k, v in want.header.items()
        if got.header.get(k) != v
    ]
    for name in (
        "window",
        "limit",
        "states",
        "inputs",
        "basis",
        "exception",
        "effective",
        "supersedes",
        "scope",
        "policy_ref",
        "codes",
        "steps",
        "claims_approval",
    ):
        if getattr(want, name) != getattr(got, name):
            problems.append(f"{name}: expected {getattr(want, name)!r}, found {getattr(got, name)!r}")
    if not text.startswith(f"> {FICTIONAL_NOTICE}"):
        problems.append("fictional notice missing")
    return tuple(problems)


# --------------------------------------------------------------------------- corpus documents


class Category(StrEnum):
    """Source categories; the values are the keys of ``m_tier_composition`` in configs/fixtures.yaml."""

    SOP_VERSIONS = "sop_versions"
    POLICY_CLAUSES = "policy_clauses"
    RUNBOOKS_AND_APIS = "runbooks_and_apis"
    MANUALS_AND_FAQS = "manuals_and_faqs"
    INCIDENT_REPORTS = "incident_reports"
    TICKETS_AND_CASES = "tickets_and_cases"
    EMAILS_MEMOS_DRAFTS = "emails_memos_drafts"


NON_NORMATIVE = "non_normative"
UNAPPROVED_PROPOSAL = "unapproved_proposal"


@dataclass(frozen=True)
class Document:
    """One published document plus the generator-side tags that must never reach an arm."""

    doc_id: str
    category: Category
    title: str
    text: str
    sha256: str
    language: str
    registry_state: str
    source_version_id: str | None
    acl_tenants: tuple[str, ...]
    acl_roles: tuple[str, ...]
    tags: tuple[str, ...]
    clauses: tuple[Clause, ...]

    @property
    def authoritative(self) -> bool:
        return self.source_version_id is not None


def make_document(doc_id: str, category: Category, title: str, text: str, language: str, **extra: Any) -> Document:
    body = normalise_text(text)
    values: dict[str, Any] = {
        "registry_state": NON_NORMATIVE,
        "source_version_id": None,
        "acl_tenants": (),
        "acl_roles": (),
        "tags": (),
        "clauses": (),
    }
    values.update(extra)
    return Document(doc_id, category, title, body, sha256_hex(body), language, **values)


def authoritative_document(world: World, version: DocumentVersion, language: str) -> Document:
    family = world.knowledge.family(version.family_id)
    rendered = render_version(world, version, language)
    category = Category.SOP_VERSIONS if family.kind is DocKind.SOP else Category.POLICY_CLAUSES
    tags = ("claims_approval",) if version.claims_approval else ()
    return Document(
        version.version_id,
        category,
        family.title,
        rendered.text,
        rendered.sha256,
        language,
        version.state.value,
        version.version_id,
        version.acl_tenants,
        version.acl_roles,
        tags,
        rendered.clauses,
    )


# --------------------------------------------------------------------------- measuring the corpus from its output

SHINGLE_WORDS = 3
NEAR_DUPLICATE_JACCARD = 0.75
_MAX_POSTING = 60
_EN_WORDS = frozenset(
    (
        "the",
        "and",
        "is",
        "of",
        "in",
        "for",
        "with",
        "may",
        "must",
        "be",
        "by",
        "are",
        "this",
        "that",
        "it",
        "or",
        "if",
        "from",
        "was",
        "were",
        "has",
        "have",
        "when",
        "after",
        "before",
        "until",
    )
)
_ID_WORDS = frozenset(
    (
        "yang",
        "dan",
        "di",
        "ke",
        "dari",
        "untuk",
        "dengan",
        "tidak",
        "boleh",
        "adalah",
        "ini",
        "itu",
        "atau",
        "pada",
        "sudah",
        "belum",
        "kami",
        "saya",
        "anda",
        "dalam",
        "jika",
    )
)
_INJECTION = re.compile(
    r"ignore (?:all )?previous instructions|disregard your rules|abaikan semua instruksi|abaikan aturanmu|"
    r"system note to ai assistant|catatan sistem untuk asisten",
    re.IGNORECASE,
)
_QUOTE = re.compile(r"(POL-\d{3})[^.\n]{0,60}?(\d+) (?:hours|jam)")


def _body_lines(text: str) -> list[str]:
    """Lines that carry content: the fixed banner, title and header fields are excluded from text statistics."""
    return [line for line in text.split("\n") if line and not line.startswith(("> ", "# ", "- "))]


def measured_language(text: str) -> str:
    """Language of a document from stopword counts alone: en, id or mixed. Independent of the generator tag."""
    words = re.findall(r"[a-zA-Z]+", " ".join(_body_lines(text)).lower())
    en, idn = sum(w in _EN_WORDS for w in words), sum(w in _ID_WORDS for w in words)
    if en + idn == 0:
        return "mixed"
    share = idn / (en + idn)
    return "en" if share < 0.2 else "id" if share > 0.8 else "mixed"


def shingles(text: str) -> frozenset[str]:
    words = " ".join(_body_lines(text)).lower().split()
    return frozenset(" ".join(words[i : i + SHINGLE_WORDS]) for i in range(max(0, len(words) - SHINGLE_WORDS + 1)))


def near_duplicate_groups(docs: Sequence[Document]) -> list[list[str]]:
    """Groups of non-authoritative documents whose shingle sets overlap by at least the Jaccard threshold."""
    candidates = [d for d in docs if not d.authoritative]
    sets = {d.doc_id: shingles(d.text) for d in candidates}
    index: dict[str, list[str]] = {}
    for doc_id, items in sets.items():
        for shingle in items:
            index.setdefault(shingle, []).append(doc_id)
    parent = {d.doc_id: d.doc_id for d in candidates}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    seen: set[tuple[str, str]] = set()
    for holders in index.values():
        if len(holders) > _MAX_POSTING:  # boilerplate shared by many documents is not evidence of copying
            continue
        for i, a in enumerate(holders):
            for b in holders[i + 1 :]:
                if (a, b) in seen:
                    continue
                seen.add((a, b))
                inter = len(sets[a] & sets[b])
                if inter and inter / len(sets[a] | sets[b]) >= NEAR_DUPLICATE_JACCARD:
                    parent[find(a)] = find(b)
    groups: dict[str, list[str]] = {}
    for doc_id in parent:
        groups.setdefault(find(doc_id), []).append(doc_id)
    return [sorted(g) for g in groups.values() if len(g) > 1]


def current_windows(world: World) -> dict[str, int]:
    """The window in force at the snapshot for each non-conflicting policy family, from the world's own rules."""
    times = CaseTimes(*([SNAPSHOT_TIME] * 4))
    out: dict[str, int] = {}
    kb = world.knowledge
    for family in kb.families:
        if family.kind is not DocKind.POLICY:
            continue
        chosen = select_versions(kb.versions_of(family.family_id), AsOfBasis.EVALUATION_TIME, times).version_ids
        if len(chosen) == 1 and kb.version(chosen[0]).rule is not None:
            rule = kb.version(chosen[0]).rule
            assert rule is not None
            out[family.family_id] = rule.window_hours
    return out


def stale_documents(world: World, docs: Sequence[Document]) -> list[str]:
    """Non-authoritative documents that quote a policy window different from the one in force at the snapshot."""
    current = current_windows(world)
    stale = []
    for doc in docs:
        if doc.authoritative or doc.registry_state == UNAPPROVED_PROPOSAL:
            continue
        for family_id, value in _QUOTE.findall(doc.text):
            if family_id in current and int(value) != current[family_id]:
                stale.append(doc.doc_id)
                break
    return stale


def graph_degrees(world: World) -> dict[str, float]:
    degree: dict[str, int] = {}
    for edge in world.knowledge.edges:
        degree[edge.src] = degree.get(edge.src, 0) + 1
        degree[edge.dst] = degree.get(edge.dst, 0) + 1
    values = sorted(degree.values())
    return {
        "nodes": len(values),
        "mean": round(sum(values) / len(values), 3),
        "median": float(values[len(values) // 2]),
        "p95": float(values[int(0.95 * (len(values) - 1))]),
        "max": float(values[-1]),
    }


@dataclass(frozen=True)
class CorpusReport:
    """Proportions computed from the documents themselves, with the generator tags shown beside them."""

    documents: int
    by_category: Mapping[str, int]
    tokens_total: int
    tokens_mean: float
    tokens_median: float
    language_measured: Mapping[str, float]
    language_tagged: Mapping[str, float]
    language_agreement: float
    revisions: int
    families: int
    near_duplicate_share: float
    stale_share: float
    unapproved_share: float
    injection_share: float
    counts: Mapping[str, int]
    tagged_counts: Mapping[str, int]
    graph_degree: Mapping[str, float]


def measure_corpus(world: World, docs: Sequence[Document]) -> CorpusReport:
    total = len(docs)
    tokens = sorted(len(d.text.split()) for d in docs)
    measured = [measured_language(d.text) for d in docs]
    shares = {lang: round(measured.count(lang) / total, 4) for lang in ("en", "id", "mixed")}
    tagged_share = {lang: round(sum(d.language == lang for d in docs) / total, 4) for lang in ("en", "id", "mixed")}
    groups = near_duplicate_groups(docs)
    redundant = sum(len(g) - 1 for g in groups)
    stale = stale_documents(world, docs)
    unapproved = sum(d.registry_state in (UNAPPROVED_PROPOSAL, "draft") for d in docs)
    injection = sum(bool(_INJECTION.search(d.text)) for d in docs)
    kb = world.knowledge
    counts = {
        "near_duplicate": redundant,
        "stale": len(stale),
        "unapproved": unapproved,
        "injection": injection,
    }
    tagged = {
        "near_duplicate": sum(any(t.startswith("near_duplicate_of") for t in d.tags) for d in docs),
        "stale": sum("stale" in d.tags for d in docs),
        "unapproved": sum(d.registry_state in (UNAPPROVED_PROPOSAL, "draft") for d in docs),
        "injection": sum("injection" in d.tags for d in docs),
    }
    return CorpusReport(
        documents=total,
        by_category={c.value: sum(d.category is c for d in docs) for c in Category},
        tokens_total=sum(tokens),
        tokens_mean=round(sum(tokens) / total, 2),
        tokens_median=float(tokens[total // 2]),
        language_measured=shares,
        language_tagged=tagged_share,
        language_agreement=round(sum(m == d.language for m, d in zip(measured, docs, strict=True)) / total, 4),
        revisions=len(kb.versions) - len(kb.families),
        families=len(kb.families),
        near_duplicate_share=round(redundant / total, 4),
        stale_share=round(len(stale) / total, 4),
        unapproved_share=round(unapproved / total, 4),
        injection_share=round(injection / total, 4),
        counts=counts,
        tagged_counts=tagged,
        graph_degree=graph_degrees(world),
    )
