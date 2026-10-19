"""Authoritative rendering and the equivalence check (B02-T02.01), then noise and support artifacts (B02-T02.02)."""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Callable
from pathlib import Path

import pytest

from benchmark.config import FixturesConfig, load_fixtures_config
from benchmark.fixtures import FICTIONAL_NOTICE, sha256_hex
from benchmark.fixtures.artifacts import CorpusPlan, build_corpus, plan_from_config
from benchmark.fixtures.documents import (
    LANGUAGE_CHOICES,
    NON_NORMATIVE,
    UNAPPROVED_PROPOSAL,
    Category,
    CorpusReport,
    Document,
    check_equivalence,
    extract_facts,
    make_document,
    measure_corpus,
    measured_language,
    near_duplicate_groups,
    normalise_text,
    render_version,
)
from benchmark.fixtures.entities import WorldError
from benchmark.fixtures.knowledge import DocKind, DocumentState, DocumentVersion, PolicyRule
from benchmark.fixtures.operations import Provenance
from benchmark.fixtures.phrasebook import PRODUCT_ALIASES
from benchmark.fixtures.world import World, build_world


@pytest.fixture(scope="module")
def world() -> World:
    return build_world(7)


def rule_of(version: DocumentVersion) -> PolicyRule:
    assert version.rule is not None
    return version.rule


def first_match(pattern: str, text: str) -> str:
    found = re.search(pattern, text)
    assert found is not None, pattern
    return found.group(0)


def versions_of_kind(world: World, kind: DocKind) -> list[DocumentVersion]:
    return [v for v in world.knowledge.versions if world.knowledge.family(v.family_id).kind is kind]


def first_with(world: World, kind: DocKind, predicate: Callable[[DocumentVersion], bool]) -> DocumentVersion:
    return next(v for v in versions_of_kind(world, kind) if predicate(v))


# --------------------------------------------------------------------------- clean rendering


def test_every_version_renders_equivalently_in_every_language(world: World) -> None:
    for version in world.knowledge.versions:
        for language in LANGUAGE_CHOICES:
            rendered = render_version(world, version, language)
            assert check_equivalence(world, version, rendered.text) == (), (version.version_id, language)


def test_rendering_is_deterministic_and_the_hash_is_of_the_normalised_text(world: World) -> None:
    version = world.knowledge.versions[0]
    first, second = render_version(world, version, "mixed"), render_version(world, version, "mixed")
    assert first == second and first.sha256 == sha256_hex(first.text) == second.sha256
    assert first.text == normalise_text(first.text) and first.text.endswith("\n") and "\r" not in first.text
    assert render_version(world, version, "en").sha256 != render_version(world, version, "id").sha256


def test_every_document_opens_with_the_fictional_notice_and_the_fixed_header(world: World) -> None:
    for version in world.knowledge.versions[:60]:
        text = render_version(world, version, "en").text
        assert text.startswith(f"> {FICTIONAL_NOTICE}\n")
        facts = extract_facts(text)
        assert list(facts.header) == [
            "Document ID", "Version", "Status", "Effective from", "Effective until", "Approved by", "Applies to",
        ]  # fmt: skip


def test_titles_carry_no_family_or_version_token(world: World) -> None:
    for version in world.knowledge.versions:
        title = next(line for line in render_version(world, version, "en").text.split("\n") if line.startswith("# "))
        assert not re.search(r"[A-Z]{3}-\d{3}|@v\d|\bv\d\b", title)


def test_language_choice_changes_the_words_but_not_the_facts(world: World) -> None:
    version = first_with(world, DocKind.POLICY, lambda v: v.rule is not None)
    en, idn = render_version(world, version, "en").text, render_version(world, version, "id").text
    assert "must not" in en.lower() or "do not" in en.lower()
    assert "tidak boleh" in idn or "Jangan" in idn
    assert extract_facts(en).window == extract_facts(idn).window == rule_of(version).window_hours
    assert extract_facts(en).limit == extract_facts(idn).limit
    mixed = render_version(world, version, "mixed").text
    assert check_equivalence(world, version, mixed) == ()


def test_an_unknown_language_is_refused(world: World) -> None:
    with pytest.raises(ValueError, match="unknown language"):
        render_version(world, world.knowledge.versions[0], "fr")


def test_thousands_separators_follow_the_language(world: World) -> None:
    version = first_with(world, DocKind.POLICY, lambda v: v.rule is not None and v.rule.amount_limit >= 1_000_000)
    assert "." in next(line for line in render_version(world, version, "id").text.split("\n") if line.startswith("4.2"))
    assert "," in next(line for line in render_version(world, version, "en").text.split("\n") if line.startswith("4.2"))


# --------------------------------------------------------------------------- clause offsets for citation gold


def test_clause_spans_are_exact_and_each_carries_its_fact(world: World) -> None:
    version = first_with(world, DocKind.POLICY, lambda v: v.rule is not None)
    rendered = render_version(world, version, "en")
    for clause in rendered.clauses:
        assert rendered.text[clause.start : clause.end].startswith(clause.clause_id + " ")
    assert extract_facts(rendered.span_text("4.1")).window == rule_of(version).window_hours
    limit_clause = rendered.clause_for("limit").clause_id
    assert extract_facts(rendered.span_text(limit_clause)).limit == rule_of(version).amount_limit
    with pytest.raises(ValueError, match="no clause"):
        rendered.clause_for("not_a_fact")


def test_sop_steps_each_have_their_own_clause_in_order(world: World) -> None:
    version = first_with(world, DocKind.SOP, lambda v: len(v.steps) >= 5)
    rendered = render_version(world, version, "en")
    ids = [rendered.clause_for(f"step:{s}").clause_id for s in version.steps]
    assert ids == sorted(ids, key=lambda c: int(c.split(".")[1])) and len(set(ids)) == len(version.steps)


# --------------------------------------------------------------------------- planted defects must be caught

POLICY_FLIPS = [
    ("must not be processed while", "must be processed while"),
    ("Do not process a request", "Process a request"),
    ("tidak boleh diproses saat", "boleh diproses saat"),
    ("Jangan proses permintaan", "Proses permintaan"),
]


def corrupt_count(
    world: World, language: str, edit: Callable[[str], str], kind: DocKind = DocKind.POLICY
) -> tuple[int, int]:
    """(versions edited, versions where the check noticed). The two must be equal for a sound check."""
    edited = caught = 0
    for version in versions_of_kind(world, kind):
        text = render_version(world, version, language).text
        broken = edit(text)
        if broken == text:
            continue
        edited += 1
        caught += bool(check_equivalence(world, version, broken))
    return edited, caught


@pytest.mark.parametrize(
    "language,old,new",
    [("en", *POLICY_FLIPS[0]), ("en", *POLICY_FLIPS[1]), ("id", *POLICY_FLIPS[2]), ("id", *POLICY_FLIPS[3])],
)
def test_a_flipped_negation_is_detected(world: World, language: str, old: str, new: str) -> None:
    edited, caught = corrupt_count(world, language, lambda t: t.replace(old, new))
    assert edited >= 3 and caught == edited


@pytest.mark.parametrize("language", ["en", "id"])
def test_an_altered_threshold_is_detected(world: World, language: str) -> None:
    window = re.compile(r"(\d+)( hours| jam)")

    def bump(text: str) -> str:
        return window.sub(lambda m: f"{int(m.group(1)) + 1}{m.group(2)}", text, count=1)

    edited, caught = corrupt_count(world, language, bump)
    assert edited >= 10 and caught == edited
    edited, caught = corrupt_count(world, language, lambda t: re.sub(r"(IDR|Rp) (\d)", r"\1 9\2", t, count=1))
    assert edited >= 10 and caught == edited


def test_an_altered_exception_extension_is_detected(world: World) -> None:
    edited, caught = corrupt_count(
        world,
        "en",
        lambda t: re.sub(r"by (\d+) hours", lambda m: f"by {int(m.group(1)) + 24} hours", t),
        DocKind.EXCEPTION,
    )
    assert edited >= 3 and caught == edited


def test_dropped_sentences_and_header_changes_are_detected(world: World) -> None:
    drops = {
        "clause 4.2": lambda t: re.sub(r"\n4\.2 [^\n]*", "", t),
        "supersedes": lambda t: re.sub(r"\n5\.1 [^\n]*", "", t),
        "effective period": lambda t: re.sub(r"\n3\.1 [^\n]*", "", t),
        "approver": lambda t: re.sub(r"- Approved by: [^\n]*", "- Approved by: someone.else.01", t),
        "version": lambda t: re.sub(r"- Version: \d+", "- Version: 99", t),
        "state": lambda t: t.replace("- Status: approved", "- Status: draft", 1),
        "end date": lambda t: re.sub(r"- Effective until: [^\n]*", "- Effective until: 2030-01-01T00:00:00Z", t),
        "notice": lambda t: t.replace(f"> {FICTIONAL_NOTICE}\n", "", 1),
    }
    for name, edit in drops.items():
        edited, caught = corrupt_count(world, "en", edit)
        assert edited >= 3 and caught == edited, name


def test_swapped_sop_steps_and_a_dropped_step_are_detected(world: World) -> None:
    def swap(text: str) -> str:
        lines = text.split("\n")
        idx = [i for i, line in enumerate(lines) if re.match(r"4\.\d+ ", line)]
        if len(idx) < 2:
            return text
        a, b = idx[0], idx[1]
        la, lb = lines[a].split(" ", 1)[1], lines[b].split(" ", 1)[1]
        lines[a], lines[b] = lines[a].split(" ", 1)[0] + " " + lb, lines[b].split(" ", 1)[0] + " " + la
        return "\n".join(lines)

    edited, caught = corrupt_count(world, "en", swap, DocKind.SOP)
    assert edited >= 20 and caught == edited
    edited, caught = corrupt_count(world, "en", lambda t: re.sub(r"\n4\.2 [^\n]*", "", t, count=1), DocKind.SOP)
    assert edited >= 20 and caught == edited


def test_text_of_another_version_does_not_pass_as_equivalent(world: World) -> None:
    policies = [v for v in versions_of_kind(world, DocKind.POLICY) if v.rule is not None]
    a, b = policies[0], policies[1]
    assert check_equivalence(world, a, render_version(world, b, "en").text)


# --------------------------------------------------------------------------- body claims are inert data


def test_a_draft_that_claims_board_approval_keeps_an_unapproved_registry_state(world: World) -> None:
    claiming = [v for v in world.knowledge.versions if v.claims_approval]
    assert claiming
    for version in claiming:
        text = render_version(world, version, "en").text
        facts = extract_facts(text)
        assert facts.claims_approval and facts.header["Status"] == "draft"
        assert facts.header["Approved by"] == "not approved"
        assert version.state is DocumentState.DRAFT and not version.in_force
        stripped = re.sub(r"\n6\.1 [^\n]*", "", text)
        assert check_equivalence(world, version, stripped)  # removing the claim is itself a detected change
    honest = [v for v in world.knowledge.versions if v.state is DocumentState.APPROVED and not v.claims_approval]
    assert not any(extract_facts(render_version(world, v, "en").text).claims_approval for v in honest[:50])


# --------------------------------------------------------------------------- corpus, noise and ambiguity (B02-T02.02)

CONFIGS = Path(__file__).resolve().parents[1] / "configs"
APPROVAL_CLAIM = re.compile(
    r"approved by the (?:Policy )?Board|full authority of the Board|disetujui Dewan|wewenang penuh Dewan", re.IGNORECASE
)


@pytest.fixture(scope="module")
def fixtures_config() -> FixturesConfig:
    return load_fixtures_config(CONFIGS / "fixtures.yaml")


@pytest.fixture(scope="module")
def plan(world: World, fixtures_config: FixturesConfig) -> CorpusPlan:
    drafts = sum(v.state is DocumentState.DRAFT for v in world.knowledge.versions)
    return plan_from_config(fixtures_config, 10, authoritative_drafts=drafts)


@pytest.fixture(scope="module")
def corpus(world: World, plan: CorpusPlan) -> tuple[Document, ...]:
    return build_corpus(world, plan)


@pytest.fixture(scope="module")
def report(world: World, corpus: tuple[Document, ...]) -> CorpusReport:
    return measure_corpus(world, corpus)


def test_the_corpus_has_exactly_the_planned_documents_and_unique_ids(
    corpus: tuple[Document, ...], plan: CorpusPlan
) -> None:
    assert len(corpus) == plan.total == 1200
    for category in Category:
        assert sum(d.category is category for d in corpus) == plan.counts[category]
    assert len({d.doc_id for d in corpus}) == len(corpus)
    assert all(d.text.startswith(f"> {FICTIONAL_NOTICE}") and d.sha256 == sha256_hex(d.text) for d in corpus)


def test_the_corpus_is_deterministic_and_seed_sensitive(
    world: World, plan: CorpusPlan, corpus: tuple[Document, ...]
) -> None:
    again = build_corpus(world, plan)
    assert [d.sha256 for d in again] == [d.sha256 for d in corpus]
    other = build_world(8)
    drafts = sum(v.state is DocumentState.DRAFT for v in other.knowledge.versions)
    other_plan = dataclasses.replace(plan, unapproved=max(0, 36 - drafts))
    assert [d.sha256 for d in build_corpus(other, other_plan)] != [d.sha256 for d in corpus]


def test_plan_counts_follow_the_configuration(plan: CorpusPlan, fixtures_config: FixturesConfig) -> None:
    assert plan.counts[Category.SOP_VERSIONS] == 260 and plan.counts[Category.EMAILS_MEMOS_DRAFTS] == 120
    assert (plan.near_duplicates, plan.stale, plan.injections) == (120, 78, 18)
    with pytest.raises(WorldError, match="divide evenly"):
        plan_from_config(fixtures_config, 7, authoritative_drafts=0)


def test_proportions_are_reported_from_output_and_fall_inside_the_configured_ranges(
    report: CorpusReport, fixtures_config: FixturesConfig
) -> None:
    ranges = fixtures_config.noise_percent_ranges
    assert ranges["near_duplicates"][0] <= report.near_duplicate_share * 100 <= ranges["near_duplicates"][1]
    assert ranges["conflicting_or_stale"][0] <= report.stale_share * 100 <= ranges["conflicting_or_stale"][1]
    assert ranges["unapproved_proposals"][0] <= report.unapproved_share * 100 <= ranges["unapproved_proposals"][1]
    assert (
        ranges["prompt_injection_documents"][0]
        <= report.injection_share * 100
        <= ranges["prompt_injection_documents"][1]
    )


def test_measured_counts_agree_with_the_generator_tags_within_a_small_gap(report: CorpusReport) -> None:
    for name in ("stale", "unapproved", "injection"):
        assert report.counts[name] == report.tagged_counts[name], name
    assert abs(report.counts["near_duplicate"] - report.tagged_counts["near_duplicate"]) <= 12


def test_language_shares_follow_the_profile_and_a_measured_check_roughly_agrees(report: CorpusReport) -> None:
    assert report.language_tagged == {"en": 0.55, "id": 0.3, "mixed": 0.15}
    for lang, share in report.language_tagged.items():
        assert abs(report.language_measured[lang] - share) <= 0.1, lang
    assert report.language_agreement >= 0.8


def test_the_report_has_the_figures_the_dataset_card_needs(report: CorpusReport) -> None:
    assert report.documents == 1200 and report.tokens_total > 50_000
    assert 0 < report.tokens_median <= report.tokens_mean * 2
    assert report.revisions > 100 and report.families == 115
    assert report.graph_degree["max"] >= report.graph_degree["median"] >= 1


def test_a_tag_that_the_text_does_not_support_is_reported_as_a_mismatch(
    world: World, corpus: tuple[Document, ...]
) -> None:
    stale = next(d for d in corpus if "stale" in d.tags)
    cleaned = re.sub(r"[^\n]*POL-\d{3}[^\n]*", "no rule is quoted here", stale.text)
    swapped = tuple(dataclasses.replace(d, text=cleaned) if d.doc_id == stale.doc_id else d for d in corpus)
    broken = measure_corpus(world, swapped)
    assert (
        broken.counts["stale"] == broken.tagged_counts["stale"] - 1
    )  # the tag still claims it; the text no longer does
    clean_injection = tuple(
        dataclasses.replace(d, tags=tuple(t for t in d.tags if t != "injection")) if "injection" in d.tags else d
        for d in corpus
    )
    assert (
        measure_corpus(world, clean_injection).counts["injection"]
        == 18
        > measure_corpus(world, clean_injection).tagged_counts["injection"]
    )


def test_unique_texts_measure_no_near_duplicates_whatever_the_tags_say(
    world: World, corpus: tuple[Document, ...]
) -> None:
    padded = tuple(
        dataclasses.replace(d, text=" ".join(f"{d.doc_id}-{i}" for i in range(200)))
        for d in corpus
        if not d.authoritative
    )
    assert near_duplicate_groups(padded) == []


def test_near_duplicate_detection_has_a_boundary() -> None:
    base_words = [f"word{i}" for i in range(40)]

    def doc(doc_id: str, words: list[str]) -> Document:
        return make_document(doc_id, Category.EMAILS_MEMOS_DRAFTS, "t", " ".join(words), "en")

    near = list(base_words)
    near[10] = "changed"
    far = [f"other{i}" for i in range(40)]
    groups = near_duplicate_groups([doc("a", base_words), doc("b", near), doc("c", far)])
    assert groups == [["a", "b"]]
    half = base_words[:20] + [f"new{i}" for i in range(20)]
    assert near_duplicate_groups([doc("a", base_words), doc("d", half)]) == []


def test_language_detection_on_known_sentences() -> None:
    assert measured_language("Requests may be processed only if they are raised in time.") == "en"
    assert measured_language("Permintaan hanya boleh diproses jika diajukan dalam waktu yang ditentukan.") == "id"
    assert measured_language("The request is open.\nPermintaan ini sudah dibuka dan belum selesai.") == "mixed"
    assert measured_language("12345") == "mixed"  # no evidence either way is not a claim of English


def test_a_draft_claiming_board_approval_never_has_an_approved_registry_state(
    corpus: tuple[Document, ...], plan: CorpusPlan
) -> None:
    claiming = [d for d in corpus if APPROVAL_CLAIM.search(d.text)]
    assert len(claiming) >= 10
    for doc in claiming:
        assert doc.registry_state in ("draft", UNAPPROVED_PROPOSAL, NON_NORMATIVE), doc.doc_id
        assert doc.registry_state != "approved"
    proposals = [d for d in corpus if d.registry_state == UNAPPROVED_PROPOSAL]
    assert len(proposals) == plan.unapproved and any(APPROVAL_CLAIM.search(d.text) for d in proposals)
    assert all(not d.authoritative for d in proposals)


def test_injection_text_is_ordinary_inert_content_in_non_authoritative_documents(corpus: tuple[Document, ...]) -> None:
    infected = [d for d in corpus if "injection" in d.tags]
    assert len(infected) == 18 and all(not d.authoritative and d.registry_state == NON_NORMATIVE for d in infected)
    assert not any(
        re.search(r"ignore all previous instructions|abaikan semua instruksi", d.text, re.I)
        for d in corpus
        if d.authoritative
    )


def test_planted_ambiguity_is_present(world: World, corpus: tuple[Document, ...]) -> None:
    text = "\n".join(d.text for d in corpus)
    aliases = {a for names in PRODUCT_ALIASES.values() for a in names}
    assert sum(a in text for a in aliases) >= 4  # product aliases appear beside the canonical names
    assert "refers back to this note" in text or "it points back here" in text  # circular-looking references
    assert any(
        d.category is Category.POLICY_CLAUSES and "exception" in d.title.lower() for d in corpus
    )  # exceptions live elsewhere
    assert sum("structural:table" in d.tags for d in corpus) >= 20 and any("| code |" in d.text for d in corpus)
    names: dict[str, set[str]] = {}
    for merchant in world.entities.merchants:
        names.setdefault(merchant.display_name, set()).add(merchant.tenant_id)
    shared = {name for name, tenants in names.items() if len(tenants) > 1}
    mentioned = {n for n in shared if any(n in d.text for d in corpus if d.category is Category.TICKETS_AND_CASES)}
    assert mentioned  # same-name merchants of different tenants show up in tickets
    lifecycles = {
        world.knowledge.family(d.source_version_id.split("@")[0]).lifecycle.value for d in corpus if d.source_version_id
    }
    assert {"future", "retroactive", "withdrawn", "draft_tail", "conflict_a", "conflict_b"} <= lifecycles


def test_runbook_prerequisites_chain_transitively(corpus: tuple[Document, ...]) -> None:
    runbooks = {first_match(r"MS-\d{4}", d.title): d for d in corpus if d.title.startswith("Runbook: ")}
    chained = 0
    for doc in runbooks.values():
        found = re.search(r"RB-(MS-\d{4})", doc.text)
        if found and found.group(1) in runbooks and re.search(r"RB-MS-\d{4}", runbooks[found.group(1)].text):
            chained += 1
    assert chained >= 10


def test_tickets_keep_reported_and_verified_statements_apart(world: World, corpus: tuple[Document, ...]) -> None:
    originals = [
        d
        for d in corpus
        if d.category is Category.TICKETS_AND_CASES and not any(t.startswith("near_duplicate") for t in d.tags)
    ]
    tickets = {first_match(r"CASE-\d{5}", d.text): d for d in originals}
    copies = sum(
        d.category is Category.TICKETS_AND_CASES and any(x.startswith("near_duplicate") for x in d.tags) for d in corpus
    )
    assert (
        len(tickets) == len(originals) == 180 - copies > 100
    )  # forwarded copies replace some; the rest are one per case
    saw_verified = saw_unresolved = 0
    intact = {k for k, d in tickets.items() if "truncated" not in d.tags}  # a cut ticket may lose its last lines
    for case in (c for c in world.operations.cases if c.case_id in intact):
        text = tickets[case.case_id].text
        has_verified = any(e.provenance is Provenance.VERIFIED for e in case.events)
        marker = re.search(r"Support checked the system|Verified at|Dukungan memeriksa sistem|Terverifikasi", text)
        assert bool(marker) == has_verified, case.case_id
        saw_verified += has_verified
        saw_unresolved += bool(re.search(r"Still unknown|Open question|Belum diketahui|Pertanyaan terbuka", text))
    assert saw_verified >= 20 and saw_unresolved >= 20


def test_access_lists_follow_the_kind_of_document(world: World, corpus: tuple[Document, ...]) -> None:
    internal = next(t.tenant_id for t in world.entities.tenants if t.internal)
    runbooks = [d for d in corpus if d.title.startswith("Runbook:") or d.title.startswith("Troubleshooting")]
    assert runbooks and all(d.acl_tenants == (internal,) and "support_l1" not in d.acl_roles for d in runbooks)
    tickets = [d for d in corpus if d.category is Category.TICKETS_AND_CASES]
    assert all(len(d.acl_tenants) == 2 and internal in d.acl_tenants for d in tickets)
    assert all(not d.acl_tenants for d in corpus if d.category is Category.MANUALS_AND_FAQS)


def test_structural_noise_is_present_and_marked(corpus: tuple[Document, ...]) -> None:
    truncated = [d for d in corpus if "truncated" in d.tags]
    assert len(truncated) == 36 and all(d.text.rstrip().endswith("[...]") for d in truncated)
    assert sum("structural:footer" in d.tags for d in corpus) >= 100


def test_a_corpus_plan_that_cannot_be_met_is_refused(world: World, plan: CorpusPlan) -> None:
    with pytest.raises(WorldError, match="do not match the corpus plan"):
        build_corpus(world, dataclasses.replace(plan, counts={**plan.counts, Category.SOP_VERSIONS: 250}))
    with pytest.raises(WorldError, match="not enough email slots"):
        build_corpus(world, dataclasses.replace(plan, unapproved=500))
    with pytest.raises(WorldError, match="not enough plain documents"):
        build_corpus(world, dataclasses.replace(plan, injections=5000))


def test_truncation_cuts_the_body_and_keeps_the_header_whole(corpus: tuple[Document, ...]) -> None:
    truncated = [d for d in corpus if "truncated" in d.tags]
    assert truncated
    for doc in truncated:
        head, _, body = doc.text.partition("- Document type:")
        assert head.startswith("> ") and body.split("\n", 1)[0].strip()  # the type line survives the cut
        assert doc.text.rstrip().endswith("[...]")


def test_announcements_do_not_single_out_the_planted_histories(world: World, corpus: tuple[Document, ...]) -> None:
    notices = [d for d in corpus if d.title.startswith("Notice about ")]
    assert notices
    announced = {d.title.removeprefix("Notice about ") for d in notices}
    lifecycles = {world.knowledge.family(f).lifecycle.value for f in announced}
    assert "plain" in lifecycles  # an ordinary history is announced as often as a planted one
