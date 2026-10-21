"""Fixture and label integrity validation (B02-T06.01): a clean fixture passes, every planted defect is caught."""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from benchmark.config import load_fixtures_config
from benchmark.contracts import EvidenceStatus
from benchmark.fixtures import sha256_hex
from benchmark.fixtures.artifacts import build_corpus, plan_from_config
from benchmark.fixtures.documents import Category, Document, make_document
from benchmark.fixtures.entities import Merchant
from benchmark.fixtures.knowledge import DocKind, Interval, Lifecycle, rehash
from benchmark.fixtures.manifest import Split, build_records, snapshot_id
from benchmark.fixtures.mutations import (
    CATALOG,
    INVARIANTS,
    AskPattern,
    Expectation,
    MutationClass,
    MutationContext,
    MutationError,
    MutationInstance,
    Op,
    OpKind,
    Requirement,
    apply_corpus,
    corpus_changes,
    declared_changes,
    instantiate,
    instantiate_all,
    spec_of,
)
from benchmark.fixtures.question_gen import build_questions
from benchmark.fixtures.questions import Answerability, GoldRecord, Stratum
from benchmark.fixtures.validation import (
    MAX_LEXICAL_SOLVABILITY,
    MIN_SKELETON_DIVERSITY,
    Finding,
    ValidationReport,
    check_contradiction,
    check_forbidden_gold,
    check_gold_support,
    check_leakage,
    check_merge_identity,
    check_mutations,
    check_realism,
    check_referential,
    check_temporal,
    cross_tier_overlap,
    lexical_solvability,
    numbers_in,
    sentence_statistics,
    unplanned_conflicts,
    validate_fixture,
)
from benchmark.fixtures.world import World, build_world


def swap_doc(corpus: tuple[Document, ...], doc_id: str, **changes: Any) -> tuple[Document, ...]:
    return tuple(replace(d, **changes) if d.doc_id == doc_id else d for d in corpus)


# --------------------------------------------------------------------------- the clean fixture


def test_the_clean_s_tier_fixture_passes_every_check(
    s_world: World, s_corpus: tuple[Document, ...], s_questions: tuple[GoldRecord, ...]
) -> None:
    report = validate_fixture(s_world, s_corpus, s_questions)
    assert report.ok, report.findings[:5]
    assert set(report.metrics) == {
        "lexical_solvability",
        "sentence_length_cv",
        "skeleton_diversity",
        "naive_newest_correct",
        "naive_oldest_correct",
    }


def test_a_report_with_findings_is_not_ok() -> None:
    report = ValidationReport((Finding("leakage", "x", "y"),))
    assert not report.ok and report.checks() == {"leakage"}


# --------------------------------------------------------------------------- structure


def test_referential_defects_are_caught(s_world: World, s_corpus: tuple[Document, ...]) -> None:
    assert check_referential(s_world, s_corpus) == []
    authoritative = next(d for d in s_corpus if d.authoritative)
    missing = tuple(d for d in s_corpus if d.doc_id != authoritative.doc_id)
    assert any("no published document" in f.detail for f in check_referential(s_world, missing))
    assert any(
        "hash does not match" in f.detail
        for f in check_referential(s_world, swap_doc(s_corpus, authoritative.doc_id, text="x\n"))
    )
    ticket = next(d for d in s_corpus if d.category is Category.TICKETS_AND_CASES)
    ghost = swap_doc(
        s_corpus,
        ticket.doc_id,
        text=ticket.text + "\nTXN-NOR-99999 CASE-99999\n",
        sha256=sha256_hex(ticket.text + "\nTXN-NOR-99999 CASE-99999\n"),
    )
    details = " ".join(f.detail for f in check_referential(s_world, ghost))
    assert "unknown transaction TXN-NOR-99999" in details and "unknown case CASE-99999" in details
    clauseless = swap_doc(s_corpus, authoritative.doc_id, clauses=())
    assert any("no resolvable clauses" in f.detail for f in check_referential(s_world, clauseless))
    twin = (*s_corpus, s_corpus[0])
    assert any("duplicate document ids" in f.detail for f in check_referential(s_world, twin))


def test_a_dangling_edge_in_the_world_is_reported_as_a_referential_finding(
    s_world: World, s_corpus: tuple[Document, ...]
) -> None:
    edge = replace(s_world.knowledge.edges[0], dst="no_such_node")
    broken = replace(s_world, knowledge=replace(s_world.knowledge, edges=(edge, *s_world.knowledge.edges[1:])))
    assert any(f.subject == "knowledge" for f in check_referential(broken, s_corpus))


def test_contradiction_checks_catch_a_fake_conflict_and_an_accidental_one(s_world: World) -> None:
    assert check_contradiction(s_world) == []
    kb = s_world.knowledge
    a = next(f for f in kb.families if f.lifecycle is Lifecycle.CONFLICT_A)
    b = next(f for f in kb.families if f.lifecycle is Lifecycle.CONFLICT_B and f.scope == a.scope)
    last_a = [v for v in kb.versions_of(a.family_id) if v.in_force][-1]
    last_b = [v for v in kb.versions_of(b.family_id) if v.in_force][-1]
    agree = rehash(last_b, rule=last_a.rule)
    agreeing = replace(kb, versions=tuple(agree if v.version_id == last_b.version_id else v for v in kb.versions))
    assert any("do not disagree" in f.detail for f in check_contradiction(replace(s_world, knowledge=agreeing)))
    assert b.scope is not None
    elsewhere = replace(b, scope=replace(b.scope, txn_type_id="top_up", merchant_class="MC-TRAVEL", tenant_id=None))
    moved = replace(kb, families=tuple(elsewhere if f.family_id == b.family_id else f for f in kb.families))
    assert any("same scope" in f.detail for f in check_contradiction(replace(s_world, knowledge=moved)))
    normal = [
        f
        for f in kb.families
        if f.kind is DocKind.POLICY and f.lifecycle not in (Lifecycle.CONFLICT_A, Lifecycle.CONFLICT_B)
    ]
    clash = replace(normal[1], scope=normal[0].scope)
    clashing = replace(kb, families=tuple(clash if f.family_id == clash.family_id else f for f in kb.families))
    assert any(
        "accidental contradiction" in f.detail for f in check_contradiction(replace(s_world, knowledge=clashing))
    )
    lonely = replace(kb, families=tuple(f for f in kb.families if f.family_id != b.family_id))
    assert any("no partner" in f.detail for f in check_contradiction(replace(s_world, knowledge=lonely)))


def test_merge_identity_checks_catch_a_shared_id_and_a_wrong_merchant(
    s_world: World, s_corpus: tuple[Document, ...]
) -> None:
    assert check_merge_identity(s_world, s_corpus) == []
    merchants = list(s_world.entities.merchants)
    name = next(n for n in {m.display_name for m in merchants} if sum(m.display_name == n for m in merchants) > 1)
    twins = [i for i, m in enumerate(merchants) if m.display_name == name]
    merchants[twins[1]] = replace(merchants[twins[1]], merchant_id=merchants[twins[0]].merchant_id)
    shared = replace(s_world, entities=replace(s_world.entities, merchants=tuple(merchants)))
    assert any("share an identifier" in f.detail for f in check_merge_identity(shared, s_corpus))
    same_tenant = merchants[twins[0]]
    merchants[twins[1]] = Merchant("MRC-ZZZ-0001", same_tenant.tenant_id, name, same_tenant.class_id)
    colliding = replace(s_world, entities=replace(s_world.entities, merchants=tuple(merchants)))
    assert any("not in different tenants" in f.detail for f in check_merge_identity(colliding, s_corpus))
    ticket = next(d for d in s_corpus if d.category is Category.TICKETS_AND_CASES and not d.tags)
    case = next(c for c in s_world.operations.cases if c.case_id in ticket.text)
    stripped = swap_doc(s_corpus, ticket.doc_id, text=ticket.text.replace(case.merchant_id, "MRC-XXX-0000"))
    assert any("merchant's identifier" in f.detail for f in check_merge_identity(s_world, stripped))


def test_temporal_checks_catch_an_open_ended_version_followed_by_a_later_one(s_world: World) -> None:
    assert check_temporal(s_world) == []
    kb = s_world.knowledge
    family = next(f for f in kb.families if sum(v.in_force for v in kb.versions_of(f.family_id)) >= 2)
    first = next(v for v in kb.versions_of(family.family_id) if v.in_force)
    open_ended = rehash(first, valid=Interval(first.valid.start, None))
    broken = replace(kb, versions=tuple(open_ended if v.version_id == first.version_id else v for v in kb.versions))
    assert any("followed by a later one" in f.detail for f in check_temporal(replace(s_world, knowledge=broken)))


# --------------------------------------------------------------------------- gold


def first_of(records: tuple[GoldRecord, ...], stratum: Stratum) -> GoldRecord:
    return next(r for r in records if r.stratum is stratum and r.answerability is Answerability.ANSWERABLE)


def test_gold_support_catches_a_wrong_claim_a_corrupt_span_and_an_invisible_document(
    s_world: World, s_corpus: tuple[Document, ...], s_questions: tuple[GoldRecord, ...]
) -> None:
    assert check_gold_support(s_questions, s_corpus, s_world) == []
    record = first_of(s_questions, Stratum.Q2)
    wrong = replace(record, required_claims=("the window is 7 hours",))
    assert any("claim number 7" in f.detail for f in check_gold_support([wrong], s_corpus, s_world))
    cited = record.slots[0].alternatives[0]
    bad = replace(cited, span_sha256="0" * 64)
    corrupt = replace(
        record,
        slots=(replace(record.slots[0], alternatives=(bad,)),),
        minimal_sets=((bad,),),
        citation_gold_spans=(bad,),
    )
    assert any("span hash mismatch" in f.detail for f in check_gold_support([corrupt], s_corpus, s_world))
    hidden = swap_doc(s_corpus, cited.doc_id, acl_roles=("auditor",), acl_tenants=("T-NOWHERE",))
    assert any("not visible to the principal" in f.detail for f in check_gold_support([record], hidden, s_world))
    gone = tuple(d for d in s_corpus if d.doc_id != cited.doc_id)
    assert any("does not exist" in f.detail for f in check_gold_support([record], gone, s_world))


def test_a_sum_of_two_cited_numbers_is_accepted_but_an_unrelated_number_is_not(
    s_world: World, s_corpus: tuple[Document, ...], s_questions: tuple[GoldRecord, ...]
) -> None:
    record = first_of(s_questions, Stratum.Q3)
    docs = {d.doc_id: d for d in s_corpus}
    spans = [docs[c.doc_id].text[c.start : c.end] for s in record.slots for c in s.alternatives]
    base, extra = (next(iter(numbers_in(s) - {4, 1})) for s in spans[:2])
    ok = replace(record, required_claims=(f"the total is {base + extra} hours",))
    assert check_gold_support([ok], s_corpus, s_world) == []
    bad = replace(record, required_claims=(f"the total is {base + extra + 1} hours",))
    assert check_gold_support([bad], s_corpus, s_world)


def test_forbidden_gold_catches_an_inaccessible_source_that_is_in_fact_visible(
    s_world: World, s_corpus: tuple[Document, ...], s_questions: tuple[GoldRecord, ...]
) -> None:
    assert check_forbidden_gold(s_questions, s_corpus, s_world) == []
    blocked = next(r for r in s_questions if r.answerability is Answerability.BLOCKED_BY_ACL)
    open_doc = next(d for d in s_corpus if d.category is Category.MANUALS_AND_FAQS)
    planted = replace(blocked, inaccessible_sources=(*blocked.inaccessible_sources, open_doc.doc_id))
    assert any("visible to the principal" in f.detail for f in check_forbidden_gold([planted], s_corpus, s_world))
    missing = replace(blocked, inaccessible_sources=("ART-nothing",))
    assert any("does not exist" in f.detail for f in check_forbidden_gold([missing], s_corpus, s_world))


def test_leakage_catches_gold_words_question_ids_and_stated_answers(
    s_corpus: tuple[Document, ...], s_questions: tuple[GoldRecord, ...]
) -> None:
    assert check_leakage(s_questions, s_corpus) == []
    target = s_corpus[0].doc_id
    marker = swap_doc(s_corpus, target, text=s_corpus[0].text + "\nrequired_evidence: x\n")
    assert any("gold marker" in f.detail for f in check_leakage(s_questions, marker))
    qid = swap_doc(s_corpus, target, text=s_corpus[0].text + f"\n{s_questions[0].question_id}\n")
    assert any("question id" in f.detail for f in check_leakage(s_questions, qid))
    answered = replace(
        first_of(s_questions, Stratum.Q2), query="Is it 72 hours?", required_claims=("the window is 72 hours",)
    )
    assert any("states answer numbers" in f.detail for f in check_leakage([answered], s_corpus))


# --------------------------------------------------------------------------- realism


def doc(doc_id: str, text: str, category: Category = Category.EMAILS_MEMOS_DRAFTS) -> Document:
    return make_document(doc_id, category, doc_id, text, "en")


def test_an_over_regular_corpus_fails_the_skeleton_and_length_floors(
    s_world: World, s_corpus: tuple[Document, ...], s_questions: tuple[GoldRecord, ...]
) -> None:
    uniform = tuple(
        replace(
            d, text=f"> x\n\n# t\n\n- Document type: memo\n\nPlease review item {n} today.\nThank you for item {n}.\n"
        )
        if not d.authoritative
        else d
        for n, d in enumerate(s_corpus)
    )
    findings, metrics = check_realism(s_questions, uniform, s_world)
    assert metrics["skeleton_diversity"] < MIN_SKELETON_DIVERSITY
    assert {f.check for f in findings} >= {"over_regular"}
    cv, diversity = sentence_statistics(uniform)
    assert cv < 0.25 and diversity < 0.01


def test_a_trivially_searchable_question_set_fails_the_lexical_ceiling(
    s_world: World, s_corpus: tuple[Document, ...], s_questions: tuple[GoldRecord, ...]
) -> None:
    docs = {d.doc_id: d for d in s_corpus}
    gifted = tuple(
        replace(
            r, query=" ".join(re.sub(r"[^A-Za-z ]", " ", docs[r.slots[0].alternatives[0].doc_id].text).split()[8:60])
        )
        if r.stratum in (Stratum.Q2, Stratum.Q3, Stratum.Q4, Stratum.Q5) and r.answerability is Answerability.ANSWERABLE
        else r
        for r in s_questions
    )
    assert lexical_solvability(gifted, s_corpus, s_world) > MAX_LEXICAL_SOLVABILITY
    findings, _ = check_realism(gifted, s_corpus, s_world)
    assert "trivially_searchable" in {f.check for f in findings}


def test_lexical_solvability_has_empty_and_perfect_controls(
    s_world: World, s_corpus: tuple[Document, ...], s_questions: tuple[GoldRecord, ...]
) -> None:
    empty = tuple(replace(r, query="zzzz qqqq") for r in s_questions)
    assert lexical_solvability(empty, s_corpus, s_world) == 0.0
    assert 0.0 <= lexical_solvability(s_questions, s_corpus, s_world) <= MAX_LEXICAL_SOLVABILITY


def test_choosing_the_newest_version_must_not_solve_the_version_questions(
    s_world: World, s_corpus: tuple[Document, ...], s_questions: tuple[GoldRecord, ...]
) -> None:
    shortcut = []
    for r in s_questions:
        if r.stratum is Stratum.Q4:
            in_force = [
                v.version_id
                for v in s_world.knowledge.versions_of(r.gold_applicable_version_ids[0].split("@")[0])
                if v.in_force
            ]
            r = replace(r, gold_applicable_version_ids=(in_force[-1],))
        shortcut.append(r)
    findings, metrics = check_realism(shortcut, s_corpus, s_world)
    assert metrics["naive_newest_correct"] == 1.0 and "version_shortcut" in {f.check for f in findings}


# --------------------------------------------------------------------------- helpers and tiers


def test_numbers_are_read_without_identifiers_dates_or_separators() -> None:
    assert numbers_in(
        "Per POL-012@v3 on 2026-03-15T00:00:00Z amounts above IDR 5,000,000 or Rp 5.000.000 need 72 hours"
    ) == {
        5_000_000,
        72,
    }
    assert numbers_in("MS-4127 and TXN-NOR-00012 and CASE-00001") == set()


def test_sentence_statistics_distinguish_varied_from_repeated_text() -> None:
    repeated = [
        doc(f"a{i}", f"> n\n\n# t\n\n- Document type: memo\n\nPlease review item {i} today.\n") for i in range(30)
    ]
    varied = [
        doc(f"b{i}", f"> n\n\n# t\n\n- Document type: memo\n\n{'word ' * (3 + i)}number{i} here.\n") for i in range(30)
    ]
    assert sentence_statistics(repeated)[1] < 0.05 < sentence_statistics(varied)[1]
    assert sentence_statistics([doc("one", "> n\n")]) == (0.0, 0.0)


def test_questions_of_different_worlds_do_not_share_policy_families(
    s_world: World, s_questions: tuple[GoldRecord, ...]
) -> None:
    other = build_world(8)
    config = load_fixtures_config(Path(__file__).resolve().parents[1] / "configs" / "fixtures.yaml")
    drafts = sum(v.state.value == "draft" for v in other.knowledge.versions)
    docs = build_corpus(other, plan_from_config(config, 10, authoritative_drafts=drafts))
    records = build_questions(other, docs, snapshot_id(build_records(other, docs, 8)), 8, "S", {Split.SMOKE: 10})
    assert cross_tier_overlap(s_world, s_questions, other, records) == set()
    assert cross_tier_overlap(s_world, s_questions, s_world, s_questions) != set()


def test_an_unplanned_conflict_is_reported(s_world: World) -> None:
    kb = s_world.knowledge
    normal = [f for f in kb.families if f.kind is DocKind.POLICY and f.lifecycle is Lifecycle.PLAIN and f.scope]
    first = normal[0]
    assert first.scope is not None
    reports = []
    for other in normal[1:6]:
        tied = replace(other, scope=first.scope)  # same scope and precedence as the first, so both apply together
        families = tuple(tied if f.family_id == other.family_id else f for f in kb.families)
        reports += unplanned_conflicts(replace(s_world, knowledge=replace(kb, families=families)))
    assert reports and all("no conflict was planted" in f.detail for f in reports)
    assert unplanned_conflicts(s_world) == []


def test_clause_numbers_are_not_read_as_claim_numbers(
    s_world: World, s_corpus: tuple[Document, ...], s_questions: tuple[GoldRecord, ...]
) -> None:
    assert numbers_in("4.1 A request may be processed within 72 hours.\n5.2 See POL-001.") == {72}
    record = first_of(s_questions, Stratum.Q2)
    clause_like = replace(record, required_claims=("the window is 41 hours",))
    assert any("claim number 41" in f.detail for f in check_gold_support([clause_like], s_corpus, s_world))


# --------------------------------------------------------------------------- mutations and invariants (B07-T07.01)


@pytest.fixture(scope="module")
def mutation_ctx(
    s_world: World, s_corpus: tuple[Document, ...], s_questions: tuple[GoldRecord, ...]
) -> MutationContext:
    return MutationContext(s_world, s_corpus, s_questions, 7)


@pytest.fixture(scope="module")
def instances(mutation_ctx: MutationContext) -> tuple[MutationInstance, ...]:
    return instantiate_all(mutation_ctx)


def by_id(instances: tuple[MutationInstance, ...], instance_id: str) -> MutationInstance:
    return next(i for i in instances if i.instance_id == instance_id)


def test_the_catalog_holds_19_mutations_and_7_invariants_and_binds_to_the_fixture(
    mutation_ctx: MutationContext, instances: tuple[MutationInstance, ...]
) -> None:
    assert [s.mutation_id for s in CATALOG] == [f"M{n:02d}" for n in range(1, 20)]
    assert [i.invariant_id for i in INVARIANTS] == [f"MT{n:02d}" for n in range(1, 8)]
    assert len(instances) == 19 + 4 + 7 and len({i.instance_id for i in instances}) == len(instances)
    assert check_mutations(mutation_ctx, instances) == []
    assert all(
        i.klass is spec_of(i.spec_id).klass for i in instances if i.spec_id.startswith("M0") or i.spec_id[1] != "T"
    )


def test_instantiation_is_deterministic(mutation_ctx: MutationContext, instances: tuple[MutationInstance, ...]) -> None:
    assert instantiate_all(mutation_ctx) == instances
    other = instantiate_all(MutationContext(mutation_ctx.world, mutation_ctx.corpus, mutation_ctx.questions, 8))
    assert other != instances


def test_each_mutation_needs_what_its_patch_touches(instances: tuple[MutationInstance, ...]) -> None:
    needs = {i.instance_id: i.requirements for i in instances}
    assert Requirement.GRAPH in needs["M07:base"] and Requirement.GRAPH in needs["M15:base"]
    assert needs["M08:base"] == {Requirement.INDEX} and needs["M11:base"] == {Requirement.LIVE}
    assert needs["M12:base"] == {Requirement.LIVE, Requirement.CLOCK}
    assert needs["M13:base"] == {Requirement.CONVERSATION} and needs["M01:base"] == {Requirement.PUBLISH}
    assert by_id(instances, "M12:base").klass is MutationClass.NEEDS_SERVER_STATE
    assert [i.instance_id for i in instances if i.ask is AskPattern.BEFORE_AFTER] == [
        "M09:base",
        "M10:base",
        "MT02:base",
    ]


def test_a_patch_changes_the_corpus_in_exactly_the_declared_way(
    mutation_ctx: MutationContext, instances: tuple[MutationInstance, ...]
) -> None:
    for instance in instances:
        ops = (*instance.precondition, *instance.patch)
        mutated = apply_corpus(mutation_ctx.corpus, ops)
        assert corpus_changes(mutation_ctx.corpus, mutated) == declared_changes(mutation_ctx.corpus, ops), (
            instance.instance_id
        )
    revoke = by_id(instances, "M09:base").patch
    other = by_id(instances, "MT07:base").patch
    changed = corpus_changes(mutation_ctx.corpus, apply_corpus(mutation_ctx.corpus, revoke))
    assert changed != declared_changes(mutation_ctx.corpus, other), "a different patch declares a different change"
    assert {kind for kind, _, _ in changed} == {"acl_roles"}


def test_a_precondition_and_its_patch_restore_the_base_corpus(
    mutation_ctx: MutationContext, instances: tuple[MutationInstance, ...]
) -> None:
    for instance_id in ("MT04:base", "MT05:base"):
        instance = by_id(instances, instance_id)
        broken = apply_corpus(mutation_ctx.corpus, instance.precondition)
        assert corpus_changes(mutation_ctx.corpus, broken) != frozenset()
        assert corpus_changes(mutation_ctx.corpus, apply_corpus(broken, instance.patch)) == frozenset()


def test_the_gold_of_a_version_mutation_matches_the_worlds_own_selector(
    mutation_ctx: MutationContext, instances: tuple[MutationInstance, ...]
) -> None:
    m01 = by_id(instances, "M01:base")
    assert m01.expectation.versions == mutation_ctx.question(m01.base_question_id).gold_applicable_version_ids
    assert by_id(instances, "M19:base").expectation.statuses == (EvidenceStatus.CONFLICT,)
    added = next(op.document for op in m01.patch if op.document)
    assert added and added.doc_id in m01.expectation.must_not_cite and added.registry_state == "approved"


def test_the_injection_variants_are_inert_text_with_a_made_up_canary(instances: tuple[MutationInstance, ...]) -> None:
    variants = [i for i in instances if i.spec_id == "M14"]
    assert [i.variant for i in variants] == ["plain", "homoglyph", "nested_json", "faux_system", "indirect_url"]
    texts = {i.variant: next(op.document.text for op in i.patch if op.document) for i in variants}
    assert all(i.expectation.must_not_expose[0].startswith("ZK-") for i in variants)
    assert texts["plain"].isascii() and not texts["homoglyph"].isascii()
    assert '"instruction"' in texts["nested_json"] and "<|system|>" in texts["faux_system"]
    assert ".invalid" in texts["indirect_url"] and "http://" not in "".join(texts.values())


def test_a_mutation_that_cannot_be_built_is_refused_with_its_reason(mutation_ctx: MutationContext) -> None:
    with pytest.raises(MutationError, match="no variant"):
        instantiate(mutation_ctx, "M01", "other")
    with pytest.raises(MutationError, match="no mutation"):
        spec_of("M99")
    empty = MutationContext(mutation_ctx.world, mutation_ctx.corpus, (), 7)
    with pytest.raises(MutationError, match="has no question"):
        instantiate(empty, "M01")


def test_corpus_operations_refuse_what_they_cannot_do(mutation_ctx: MutationContext) -> None:
    corpus = mutation_ctx.corpus
    plain = next(d for d in corpus if not d.authoritative)
    restricted = next(d for d in corpus if d.acl_roles)
    authoritative = next(d for d in corpus if d.authoritative)
    cases = [
        (Op(OpKind.EDIT_TEXT, plain.doc_id, "x", old=" "), "exactly once"),
        (Op(OpKind.EDIT_TEXT, authoritative.doc_id, "x", old=authoritative.text.split()[0]), "replaced by a version"),
        (Op(OpKind.REVOKE_ROLE, restricted.doc_id, "no_such_role"), "does not hold"),
        (Op(OpKind.GRANT_ROLE, plain.doc_id, "engineer"), "nothing to widen"),
        (Op(OpKind.SET_TITLE, "ART-missing", "x"), "no document"),
        (Op(OpKind.ADD_DOCUMENT, document=plain), "already exists"),
    ]
    for op, reason in cases:
        with pytest.raises(MutationError, match=reason):
            apply_corpus(corpus, [op])
    with pytest.raises(MutationError, match="exact text"):
        Op(OpKind.EDIT_TEXT, "x", "y")
    with pytest.raises(MutationError, match="not a live mode"):
        Op(OpKind.SET_LIVE, "TXN-1", "sideways")


def test_each_planted_defect_in_the_mutations_is_caught(
    mutation_ctx: MutationContext, instances: tuple[MutationInstance, ...]
) -> None:
    m01 = by_id(instances, "M01:base")
    doc = next(op.document for op in m01.patch if op.document)
    assert doc
    claim = next((c for q in mutation_ctx.questions for c in q.required_claims if len(c) > 8), None)
    assert claim
    leaking_q = next(q for q in mutation_ctx.questions if claim in q.required_claims)
    planted = {
        "names a mutation": replace(
            m01,
            patch=(Op(OpKind.ADD_DOCUMENT, document=replace(doc, text=doc.text + "\nthis is wrong_latest_version")),),
        ),
        "repeats a gold claim": replace(
            m01,
            base_question_id=leaking_q.question_id,
            patch=(Op(OpKind.ADD_DOCUMENT, document=replace(doc, text=claim)),),
        ),
        "does not apply": replace(m01, patch=(Op(OpKind.REVOKE_ROLE, doc.doc_id, "x"),)),
        "constrains nothing": replace(m01, expectation=Expectation("nothing")),
        "not in the fixture": replace(m01, base_question_id="q-ffffffffffffffff"),
    }
    for reason, bad in planted.items():
        found = check_mutations(mutation_ctx, [bad])
        assert any(reason in f.detail for f in found), (reason, found[:3])
    assert any("no instance" in f.detail for f in check_mutations(mutation_ctx, instances[:-1]))
