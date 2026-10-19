"""Support artifacts, noise and planted ambiguity (B02-T02.02): everything in the corpus that is not authoritative.

Tickets, incidents, runbooks, manuals, FAQs, emails and memos are generated from the same hidden world as the
authoritative documents, in English, Indonesian or mixed text. Noise is injected by exact counts derived from the
configured rates, and every injected item carries a generator tag that stays out of the published corpus. The
proportions that are *reported* come from :func:`benchmark.fixtures.documents.measure_corpus`, which does not read
the tags.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import timedelta

from benchmark.config import FixturesConfig
from benchmark.fixtures import FICTIONAL_NOTICE, sha256_hex
from benchmark.fixtures.documents import (
    NON_NORMATIVE,
    UNAPPROVED_PROPOSAL,
    Category,
    Document,
    authoritative_document,
    make_document,
    near_duplicate_groups,
)
from benchmark.fixtures.entities import WorldError, rng_for
from benchmark.fixtures.knowledge import (
    SNAPSHOT_TIME,
    AsOfBasis,
    CaseTimes,
    DocKind,
    DocumentFamily,
    Lifecycle,
    iso,
    parse_ts,
    select_versions,
)
from benchmark.fixtures.operations import Provenance, case_view
from benchmark.fixtures.phrasebook import ARTIFACT_BANKS, PRODUCT_ALIASES, format_amount
from benchmark.fixtures.world import World

SNAPSHOT = SNAPSHOT_TIME
INTERNAL_ROLES = ("engineer", "approver", "auditor")
SUPPORT_CATEGORIES = (
    Category.RUNBOOKS_AND_APIS,
    Category.MANUALS_AND_FAQS,
    Category.INCIDENT_REPORTS,
    Category.TICKETS_AND_CASES,
    Category.EMAILS_MEMOS_DRAFTS,
)
QUOTING_CATEGORIES = (
    Category.RUNBOOKS_AND_APIS,
    Category.MANUALS_AND_FAQS,
    Category.INCIDENT_REPORTS,
    Category.EMAILS_MEMOS_DRAFTS,
)
QUOTE_SHARE = 0.4


@dataclass(frozen=True)
class CorpusPlan:
    """Exact document counts per category and exact noise counts, derived once from the configured rates."""

    counts: Mapping[Category, int]
    language_percent: Mapping[str, int]
    near_duplicates: int
    stale: int
    unapproved: int
    injections: int
    truncated: int

    @property
    def total(self) -> int:
        return sum(self.counts.values())


def language_deck(total: int, percent: Mapping[str, int], rng: random.Random) -> list[str]:
    """``total`` language labels in the configured proportions (largest remainder), shuffled."""
    names = {"english": "en", "indonesian": "id", "mixed": "mixed"}
    exact = {names[k]: total * v / 100 for k, v in percent.items()}
    counts = {k: int(v) for k, v in exact.items()}
    for key in sorted(exact, key=lambda k: (counts[k] - exact[k], k))[: total - sum(counts.values())]:
        counts[key] += 1
    deck = [lang for lang, n in sorted(counts.items()) for _ in range(n)]
    rng.shuffle(deck)
    return deck


class Voice:
    """Speaks bank sentences in one document's language; mixed text switches language sentence by sentence."""

    def __init__(self, language: str, rng: random.Random) -> None:
        self.language = language
        self.rng = rng
        self._last = "en" if rng.random() < 0.5 else "id"

    def lang(self) -> str:
        if self.language != "mixed":
            return self.language
        if self.rng.random() < 0.8:  # code-switching alternates most of the time, so short documents still mix
            self._last = "id" if self._last == "en" else "en"
        return self._last

    def say(self, bank: str, /, **values: str) -> str:
        frames = ARTIFACT_BANKS[bank][self.lang()]
        return frames[self.rng.randrange(len(frames))].format(**values)


@dataclass
class _Draft:
    category: Category
    title: str
    kind: str
    body: list[str]
    acl_tenants: tuple[str, ...] = ()
    acl_roles: tuple[str, ...] = ()
    registry_state: str = NON_NORMATIVE
    tags: list[str] = field(default_factory=list)

    def text(self) -> str:
        head = [f"> {FICTIONAL_NOTICE}", "", f"# {self.title}", "", f"- Document type: {self.kind}", ""]
        return "\n".join([*head, *self.body])


class _Context:
    """Read-only helpers over the world shared by the generators."""

    def __init__(self, world: World, rng: random.Random) -> None:
        self.world = world
        self.rng = rng
        e = world.entities
        self.txn_names = {t.txn_type_id: t.name for t in e.transaction_types}
        self.tenant_names = {t.tenant_id: t.name for t in e.tenants}
        self.merchants = {m.merchant_id: m for m in e.merchants}
        self.internal = next(t.tenant_id for t in e.tenants if t.internal)
        self.internal_principals = [p.principal_id for p in e.principals if p.tenant_id == self.internal]
        all_snapshot = CaseTimes(SNAPSHOT, SNAPSHOT, SNAPSHOT, SNAPSHOT)
        self.current: dict[str, int] = {}
        self.older: dict[str, list[int]] = {}
        kb = world.knowledge
        for family in kb.families:
            if family.kind is not DocKind.POLICY or family.lifecycle in (Lifecycle.CONFLICT_A, Lifecycle.CONFLICT_B):
                continue
            versions = kb.versions_of(family.family_id)
            chosen = select_versions(versions, AsOfBasis.EVALUATION_TIME, all_snapshot).version_ids
            if len(chosen) != 1 or kb.version(chosen[0]).rule is None:
                continue
            now = kb.version(chosen[0]).rule
            assert now is not None
            self.current[family.family_id] = now.window_hours
            differing = sorted(
                {
                    v.rule.window_hours
                    for v in versions
                    if v.in_force and v.rule and v.rule.window_hours != now.window_hours
                }
            )
            if differing:
                self.older[family.family_id] = differing

    def alias(self, product_name: str) -> str:
        options = PRODUCT_ALIASES.get(product_name, ())
        return self.rng.choice(options) if options and self.rng.random() < 0.35 else product_name

    def quote(self, voice: Voice, stale: bool) -> tuple[str, str]:
        """A policy-window sentence and its family id; stale quotes an older, differing value."""
        pool = sorted(self.older if stale else self.current)
        family_id = self.rng.choice(pool)
        value = self.rng.choice(self.older[family_id]) if stale else self.current[family_id]
        return voice.say("policy_quote", pol=family_id, w=str(value)), family_id


def _table(rows: Sequence[Sequence[str]], header: Sequence[str]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    return out + ["| " + " | ".join(row) + " |" for row in rows]


def _runbook(ctx: _Context, index: int, voice: Voice) -> _Draft:
    codes = ctx.world.entities.error_codes
    code = codes[index % len(codes)]
    variant = (index // len(codes)) % 3
    txn = ctx.txn_names[code.txn_type_id]
    product = ctx.rng.choice(ctx.world.entities.products).name
    symptom = voice.say("symptom", txn=txn, code=code.code, fault=code.name)
    if variant == 1:  # API note: public, with a response table
        status = {1: 400, 2: 409, 3: 422, 4: 503}[code.severity]
        shown = ctx.rng.sample(list(codes), 12)
        rows = [
            (c.code, str(({1: 400, 2: 409, 3: 422, 4: 503})[c.severity]), c.name)
            for c in sorted(shown, key=lambda c: c.code)
        ]
        body = [
            voice.say("api_note", status=str(status), code=code.code, n=str(10 * code.severity)),
            symptom,
            "",
            *_table(rows, ("code", "http status", "meaning")),
        ]
        return _Draft(
            Category.RUNBOOKS_AND_APIS,
            f"API note: {code.code} response",
            "api reference",
            body,
            tags=["structural:table"],
        )
    prerequisite = codes[(index + 7) % len(codes)].code
    steps = [voice.say("diagnosis", product=ctx.alias(product)) for _ in range(2 + variant)]
    body = [
        "## Symptoms",
        symptom,
        "",
        "## Prerequisite",
        voice.say("prerequisite", rb=f"RB-{prerequisite}"),
        "",
        "## Diagnosis",
        *[f"{n}. {s}" for n, s in enumerate(dict.fromkeys(steps), start=1)],
        "",
        "## Mitigation",
        voice.say("mitigation"),
        voice.say("escalation"),
    ]
    if variant == 2:
        body += ["", voice.say("see_also", ref=f"the runbook for {codes[(index + 3) % len(codes)].code}")]
    title = f"Runbook: {code.code} {code.name}" if variant == 0 else f"Troubleshooting {code.code}"
    kind = "runbook" if variant == 0 else "troubleshooting guide"
    return _Draft(Category.RUNBOOKS_AND_APIS, title, kind, body, (ctx.internal,), INTERNAL_ROLES)


def _manual(ctx: _Context, index: int, voice: Voice) -> _Draft:
    e = ctx.world.entities
    product = e.products[index % len(e.products)]
    txn_id = e.transaction_types[(index // len(e.products) + index) % len(e.transaction_types)].txn_type_id
    if index % 2:  # FAQ
        question = voice.say("faq_q", txn=ctx.txn_names[txn_id].lower())
        body = [f"Q: {question}", "A: "]
        voice_answer = voice.say("faq_a", product=ctx.alias(product.name))
        body.append(voice_answer)
        return _Draft(Category.MANUALS_AND_FAQS, f"FAQ: {ctx.alias(product.name)} requests", "faq", body)
    states = ("initiated", "authorized", "captured", "pending_settlement", "settled", "reversed", "disputed", "failed")
    rows = [(s, ctx.rng.choice(("yes", "no")), str(ctx.rng.randint(1, 48))) for s in states]
    body = [
        f"## Chapter {index // 2 + 1}",
        *[voice.say("manual", product=ctx.alias(product.name)) for _ in range(3)],
        "",
    ]
    body += _table(rows, ("state", "visible to merchant", "refresh hours"))
    return _Draft(
        Category.MANUALS_AND_FAQS,
        f"{product.name} user guide, chapter {index // 2 + 1}",
        "manual",
        body,
        tags=["structural:table"],
    )


def _incident(ctx: _Context, index: int, voice: Voice) -> _Draft:
    ops, e = ctx.world.operations, ctx.world.entities
    if index < len(ops.outages):
        outage = ops.outages[index]
        operation, start, end = outage.operation, outage.period.start, outage.period.end or SNAPSHOT
    else:
        operation = ctx.rng.choice(
            ("transaction_status", "settlement_state", "merchant_status", "reconciliation_status")
        )
        begin = parse_ts("2026-02-01T00:00:00Z") + timedelta(minutes=ctx.rng.randrange(60 * 24 * 200))
        start, end = iso(begin), iso(begin + timedelta(hours=ctx.rng.randint(1, 20)))
    fault = ctx.rng.choice(e.error_codes).name
    merchant = ctx.rng.choice(e.merchants)
    mention = merchant.display_name if ctx.rng.random() < 0.5 else f"{merchant.display_name} ({merchant.merchant_id})"
    body = [
        f"## Incident IR-2026-{index + 1:03d}",
        voice.say("incident_summary", operation=operation, start=start, end=end),
        f"Requests affected: {ctx.rng.randint(12, 4000)}.",
        f"Affected merchant: {mention}.",
        voice.say("incident_cause", fault=fault),
        voice.say("incident_status"),
    ]
    return _Draft(
        Category.INCIDENT_REPORTS,
        f"Incident report: {operation} outage",
        "incident report",
        body,
        (ctx.internal,),
        INTERNAL_ROLES,
    )


def _ticket(ctx: _Context, index: int, voice: Voice) -> _Draft:
    case = ctx.world.operations.cases[index]
    merchant = ctx.merchants[case.merchant_id]
    view = case_view(case, SNAPSHOT)
    body = [
        f"Ticket {case.case_id} | tenant {ctx.tenant_names[case.tenant_id]} | merchant {merchant.display_name} "
        f"({merchant.merchant_id}) | opened {case.opened_at}",
    ]
    for event in sorted(case.events, key=lambda ev: ev.seq):
        when = event.time
        if event.provenance is Provenance.USER_REPORTED and event.fact_key == "txn_state":
            key = "ticket_correction" if event.corrects_seq else "ticket_report"
            body.append(voice.say(key, txn_id=case.txn_id, state=event.value or ""))
        elif event.provenance is Provenance.USER_REPORTED:
            body.append(voice.say("ticket_amount", amount=format_amount(int(event.value or 0), voice.lang())))
        elif event.provenance is Provenance.VERIFIED:
            body.append(voice.say("ticket_verified", time=when, state=event.value or ""))
        elif event.fact_key in view.unresolved:
            body.append(voice.say("ticket_unresolved", key=event.fact_key.replace("_", " ")))
    body.append(voice.say("chatter"))
    return _Draft(
        Category.TICKETS_AND_CASES,
        f"Support ticket {case.case_id}",
        "support ticket",
        body,
        (case.tenant_id, ctx.internal),
    )


def _email(ctx: _Context, index: int, voice: Voice, role: str) -> _Draft:
    kb = ctx.world.knowledge
    sender = ctx.rng.choice(ctx.internal_principals)
    internal_tenants = (ctx.internal,)
    head = [f"From: {sender}", f"To: {ctx.rng.choice(ctx.internal_principals)}", ""]
    if role == "proposal":
        family_id = ctx.rng.choice(sorted(ctx.current))
        old = ctx.current[family_id]
        new = ctx.rng.choice([w for w in (24, 48, 72, 120, 168, 336) if w != old])
        date = parse_ts(SNAPSHOT) + timedelta(days=ctx.rng.randint(5, 60))
        body = [*head, voice.say("proposal", pol=family_id, old=str(old), new=str(new), date=date.strftime("%Y-%m-%d"))]
        tags = ["unapproved_proposal", f"proposal:{family_id}:{new}"]
        if ctx.rng.random() < 0.3:
            body.append(voice.say("official_cloak"))
            tags.append("claims_approval")
        return _Draft(
            Category.EMAILS_MEMOS_DRAFTS,
            f"Memo: proposed change to {family_id}",
            "memo",
            body,
            internal_tenants,
            INTERNAL_ROLES,
            registry_state=UNAPPROVED_PROPOSAL,
            tags=tags,
        )
    if role == "announcement":
        # Any family with a later version qualifies, so an announcement says nothing about how the history was planted.
        announced = [f for f in kb.families if len(kb.versions_of(f.family_id)) >= 2]
        family: DocumentFamily = ctx.rng.choice(announced)
        latest = kb.versions_of(family.family_id)[-1]
        body = [
            *head,
            voice.say("announcement", version=latest.version_id, family=family.family_id, date=latest.valid.start[:10]),
        ]
        return _Draft(
            Category.EMAILS_MEMOS_DRAFTS,
            f"Notice about {family.family_id}",
            "email",
            body,
            internal_tenants,
            INTERNAL_ROLES,
        )
    body = [*head, voice.say("chatter")]
    body.append(voice.say("see_also", ref=ctx.rng.choice(sorted(ctx.current))))
    return _Draft(
        Category.EMAILS_MEMOS_DRAFTS,
        f"Meeting notes {index + 1}",
        "meeting notes",
        body,
        internal_tenants,
        INTERNAL_ROLES,
    )


# --------------------------------------------------------------------------- the corpus pipeline


def plan_from_config(
    fixtures: FixturesConfig, divisor: int, *, authoritative_drafts: int, truncation_share: float = 0.03
) -> CorpusPlan:
    """Exact counts for one tier: composition divided by ``divisor`` and noise at the midpoint of each range."""
    counts: dict[Category, int] = {}
    for name, value in fixtures.m_tier_composition.items():
        if value % divisor:
            raise WorldError(f"{name} does not divide evenly by {divisor}")
        counts[Category(name)] = value // divisor
    total = sum(counts.values())

    def middle(name: str) -> int:
        low, high = fixtures.noise_percent_ranges[name]
        return round(total * (low + high) / 200)

    return CorpusPlan(
        counts=counts,
        language_percent=fixtures.language_profile_percent,
        near_duplicates=middle("near_duplicates"),
        stale=middle("conflicting_or_stale"),
        unapproved=max(0, middle("unapproved_proposals") - authoritative_drafts),
        injections=middle("prompt_injection_documents"),
        truncated=round(total * truncation_share),
    )


_SPECIAL_TAGS = frozenset({"stale", "unapproved_proposal", "injection", "claims_approval", "truncated"})


def _is_plain(doc: Document) -> bool:
    return not doc.authoritative and not any(t in _SPECIAL_TAGS or t.startswith("near_duplicate") for t in doc.tags)


def _generate(ctx: _Context, plan: CorpusPlan, deck: list[str], first: int) -> list[Document]:
    """One document per planned support slot, with the stale-quote slots chosen up front."""
    rng = ctx.rng
    email_count = plan.counts[Category.EMAILS_MEMOS_DRAFTS]
    announcements = min(10, email_count // 12)
    if plan.unapproved + announcements > email_count:
        raise WorldError("not enough email slots for the planned proposals")
    roles = ["proposal"] * plan.unapproved + ["announcement"] * announcements
    roles += ["notes"] * (email_count - len(roles))
    rng.shuffle(roles)
    slots = [
        (c, i)
        for c in QUOTING_CATEGORIES
        for i in range(plan.counts[c])
        if c is not Category.EMAILS_MEMOS_DRAFTS or roles[i] == "notes"
    ]
    quoting = rng.sample(slots, min(len(slots), max(plan.stale, round(QUOTE_SHARE * len(slots)))))
    if plan.stale > len(quoting) or (plan.stale and not ctx.older):
        raise WorldError("cannot place the planned stale quotes")
    stale_slots = set(rng.sample(sorted(quoting, key=lambda s: (s[0].value, s[1])), plan.stale))
    quoting_slots = set(quoting)
    docs: list[Document] = []
    cursor = first
    for category in SUPPORT_CATEGORIES:
        for i in range(plan.counts[category]):
            language = deck[cursor]
            cursor += 1
            voice = Voice(language, rng_for(ctx.world.seed, f"voice:{category.value}:{i}"))
            if category is Category.RUNBOOKS_AND_APIS:
                draft = _runbook(ctx, i, voice)
            elif category is Category.MANUALS_AND_FAQS:
                draft = _manual(ctx, i, voice)
            elif category is Category.INCIDENT_REPORTS:
                draft = _incident(ctx, i, voice)
            elif category is Category.TICKETS_AND_CASES:
                if i >= len(ctx.world.operations.cases):
                    raise WorldError("fewer case histories than planned tickets")
                draft = _ticket(ctx, i, voice)
            else:
                draft = _email(ctx, i, voice, roles[i])
            if (category, i) in quoting_slots:
                stale = (category, i) in stale_slots
                sentence, _family = ctx.quote(voice, stale)
                if draft.kind == "faq":
                    draft.body[1] = "A: " + sentence
                else:
                    draft.body.append(sentence)
                if stale:
                    draft.tags.append("stale")
            elif draft.kind == "faq":
                draft.body[1] = "A: " + draft.body.pop()
            doc_id = "ART-" + sha256_hex(f"{ctx.world.seed}:{category.value}:{i}")[:10]
            docs.append(
                make_document(
                    doc_id,
                    category,
                    draft.title,
                    draft.text(),
                    language,
                    registry_state=draft.registry_state,
                    acl_tenants=draft.acl_tenants,
                    acl_roles=draft.acl_roles,
                    tags=tuple(draft.tags),
                )
            )
    return docs


def _retext(doc: Document, text: str, tags: tuple[str, ...]) -> Document:
    body = make_document(doc.doc_id, doc.category, doc.title, text, doc.language)
    return replace(doc, text=body.text, sha256=body.sha256, tags=tags)


def _inject(docs: list[Document], plan: CorpusPlan, rng: random.Random) -> None:
    plain = [i for i, d in enumerate(docs) if _is_plain(d)]
    if plan.injections > len(plain):
        raise WorldError("not enough plain documents to carry the planned injections")
    for index in rng.sample(plain, plan.injections):
        doc = docs[index]
        voice = Voice(doc.language, rng)
        docs[index] = _retext(doc, doc.text + "\n" + voice.say("injection") + "\n", (*doc.tags, "injection"))


_COPY_PREFIXES = ("FW: ", "Re: ", "Fwd: ", "")
_COPY_SUFFIXES = ("", " Thanks.", " Regards.", " (see above)")


def _near_duplicate(docs: list[Document], plan: CorpusPlan, rng: random.Random) -> set[int]:
    """Overwrite plain documents with lightly edited copies of other plain documents of the same category."""
    plain = [i for i, d in enumerate(docs) if _is_plain(d)]
    if plan.near_duplicates > len(plain) // 2:
        raise WorldError("not enough plain documents to plant the near-duplicates")
    targets = set(rng.sample(plain, plan.near_duplicates))
    touched = set(targets)
    for target in sorted(targets):
        category = docs[target].category
        sources = [i for i in plain if i not in targets and docs[i].category is category]
        if not sources:
            raise WorldError(f"no source documents for near-duplicates in {category.value}")
        source_index = rng.choice(sources)
        touched.add(source_index)
        source = docs[source_index]
        prefix, suffix = rng.choice(_COPY_PREFIXES), rng.choice(_COPY_SUFFIXES)  # no single tell marks a copy
        title = f"{prefix}{source.title}"
        text = source.text.replace(f"# {source.title}", f"# {title}", 1).rstrip("\n") + f"{suffix}\n"
        copy = replace(docs[target], title=title, acl_tenants=source.acl_tenants, acl_roles=source.acl_roles)
        docs[target] = _retext(copy, text, (*source.tags, f"near_duplicate_of:{source.doc_id}"))
    return touched


def _split_header(text: str) -> tuple[str, str]:
    """The banner, title and header fields (through the document-type line) and the body that follows."""
    marker = text.index("- Document type:")
    cut = text.index("\n", marker) + 1
    return text[:cut], text[cut:]


def _truncate(docs: list[Document], plan: CorpusPlan, rng: random.Random, protected: set[int]) -> set[int]:
    """Cut the body of plain documents mid-passage. The header stays whole so the document still identifies itself."""
    pool = [
        i
        for i, d in enumerate(docs)
        if _is_plain(d) and i not in protected and len(_split_header(d.text)[1].split()) > 30
    ]
    if plan.truncated > len(pool):
        raise WorldError("not enough documents to truncate")
    chosen = rng.sample(pool, plan.truncated)
    for index in chosen:
        doc = docs[index]
        head, body = _split_header(doc.text)
        words = body.split(" ")
        keep = max(10, int(len(words) * rng.uniform(0.6, 0.8)))
        docs[index] = _retext(doc, head + " ".join(words[:keep]) + " [...]\n", (*doc.tags, "truncated"))
    return set(chosen)


def _footers(docs: list[Document], rng: random.Random, protected: set[int]) -> None:
    for index, doc in enumerate(docs):
        if doc.authoritative or index in protected or rng.random() > 0.25:
            continue
        voice = Voice(doc.language, rng)
        footer = voice.say("footer", n=str(rng.randint(1, 3)), m="3")
        docs[index] = _retext(
            doc, doc.text.rstrip("\n") + "\n\n---\n" + footer + "\n", (*doc.tags, "structural:footer")
        )


def build_corpus(world: World, plan: CorpusPlan) -> tuple[Document, ...]:
    """The whole published corpus for one tier: authoritative documents first, then support artifacts and noise."""
    kb = world.knowledge
    authoritative = [v for v in kb.versions]
    sop = sum(1 for v in authoritative if kb.family(v.family_id).kind is DocKind.SOP)
    if sop != plan.counts[Category.SOP_VERSIONS] or len(authoritative) - sop != plan.counts[Category.POLICY_CLAUSES]:
        raise WorldError("the world's version counts do not match the corpus plan")
    deck = language_deck(plan.total, plan.language_percent, rng_for(world.seed, "corpus:language"))
    docs = [authoritative_document(world, v, deck[i]) for i, v in enumerate(authoritative)]
    ctx = _Context(world, rng_for(world.seed, "corpus:context"))
    docs += _generate(ctx, plan, deck, len(docs))
    _inject(docs, plan, rng_for(world.seed, "corpus:injection"))
    natural = sum(len(g) - 1 for g in near_duplicate_groups(docs))  # templates repeat on their own; count that first
    planted = replace(plan, near_duplicates=max(0, plan.near_duplicates - natural))
    protected = _near_duplicate(docs, planted, rng_for(world.seed, "corpus:duplicates"))
    cut = _truncate(docs, plan, rng_for(world.seed, "corpus:truncation"), protected)
    _footers(docs, rng_for(world.seed, "corpus:footers"), protected | cut)
    ids = [d.doc_id for d in docs]
    if len(set(ids)) != len(ids) or len(docs) != plan.total:
        raise WorldError("corpus ids must be unique and the document count must match the plan")
    return tuple(docs)
