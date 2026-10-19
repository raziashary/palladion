"""Versions, as-of bases, the typed graph and the deterministic policy evaluator (B02-T01.02)."""

from __future__ import annotations

import dataclasses
import random
from typing import Any

import pytest

from benchmark.fixtures import canonical_json
from benchmark.fixtures.entities import WorldEntities, WorldError, build_entities
from benchmark.fixtures.knowledge import (
    CONFLICT_PRECEDENCE,
    AsOfBasis,
    CaseFacts,
    CaseTimes,
    DocKind,
    DocumentFamily,
    DocumentState,
    DocumentVersion,
    Edge,
    ExceptionRule,
    Interval,
    KnowledgeBase,
    Lifecycle,
    PolicyOutcome,
    PolicyRule,
    PolicyScope,
    Relation,
    SelectionStatus,
    Verification,
    build_knowledge,
    plan_versions,
    rehash,
    resolve_policy,
    select_versions,
    specificity_precedence,
    validate_knowledge,
    validate_supersession,
    visible_to,
)

SEED = 7
ENTITIES = build_entities(SEED)
APPROVER = next(p.principal_id for p in ENTITIES.principals if p.role_id == "approver")
OTHER_APPROVER = [p.principal_id for p in ENTITIES.principals if p.role_id == "approver"][1]
RULE = PolicyRule(72, 5_000_000, ("settled",), ("amount", "txn_state"))


def at(day: str) -> str:
    return f"{day}T00:00:00Z"


def version(family: str, number: int, start: str, end: str | None, **changes: Any) -> DocumentVersion:
    base: dict[str, Any] = {
        "version_id": f"{family}@v{number}",
        "family_id": family,
        "version": number,
        "state": DocumentState.APPROVED if end is None else DocumentState.RETIRED,
        "approved_by": APPROVER,
        "valid": Interval(at(start), None if end is None else at(end)),
        "recorded": Interval(at(start), None),
        "acl_tenants": (),
        "acl_roles": (),
        "supersedes": f"{family}@v{number - 1}" if number > 1 else None,
        "claims_approval": False,
        "rule": RULE,
        "exception": None,
        "steps": (),
    }
    return DocumentVersion(**{**base, **changes})


def policy_family(family: str = "POL-900", **scope: Any) -> DocumentFamily:
    spec: dict[str, Any] = {
        "txn_type_id": "reversal",
        "merchant_class": None,
        "tenant_id": None,
        "basis": AsOfBasis.TRANSACTION_TIME,
        "precedence": 1,
    }
    return DocumentFamily(
        family, DocKind.POLICY, "t", "PRD-01", "reversal", None, PolicyScope(**{**spec, **scope}), Lifecycle.PLAIN
    )


def four_version_chain() -> tuple[DocumentVersion, ...]:
    """Four consecutive versions so that each of the four bases can land on a different one."""
    return (
        version("POL-900", 1, "2026-01-01", "2026-03-01"),
        version("POL-900", 2, "2026-03-01", "2026-05-01"),
        version("POL-900", 3, "2026-05-01", "2026-07-01"),
        version("POL-900", 4, "2026-07-01", None),
    )


TIMES = CaseTimes(at("2026-02-10"), at("2026-04-01"), at("2026-08-01"), at("2026-06-01"))


# --------------------------------------------------------------------------- intervals


def test_interval_boundaries_are_half_open() -> None:
    interval = Interval(at("2026-03-01"), at("2026-05-01"))
    assert not interval.contains("2026-02-28T23:59:59Z")
    assert interval.contains(at("2026-03-01"))  # start is inclusive
    assert interval.contains("2026-04-30T23:59:59Z")
    assert not interval.contains(at("2026-05-01"))  # end is exclusive
    assert Interval(at("2026-03-01"), None).contains(at("2099-01-01"))  # open-ended is explicit


def test_adjacent_intervals_do_not_overlap_and_shared_instants_do() -> None:
    first, second = Interval(at("2026-01-01"), at("2026-03-01")), Interval(at("2026-03-01"), None)
    assert not first.overlaps(second) and not second.overlaps(first)
    assert first.overlaps(Interval(at("2026-02-01"), at("2026-02-02")))


@pytest.mark.parametrize("start,end", [("2026-03-01", "2026-03-01"), ("2026-03-02", "2026-03-01")])
def test_empty_or_inverted_intervals_are_refused(start: str, end: str) -> None:
    with pytest.raises(WorldError, match="empty or inverted"):
        Interval(at(start), at(end))


def test_timestamps_without_a_zone_are_refused() -> None:
    with pytest.raises(ValueError, match="explicit timezone"):
        Interval("2026-03-01T00:00:00", None)


# --------------------------------------------------------------------------- the four bases


@pytest.mark.parametrize(
    "basis,expected",
    [
        (AsOfBasis.TRANSACTION_TIME, "POL-900@v1"),
        (AsOfBasis.CASE_OPEN_TIME, "POL-900@v2"),
        (AsOfBasis.APPROVED_DOMAIN_EVENT, "POL-900@v3"),
        (AsOfBasis.EVALUATION_TIME, "POL-900@v4"),
    ],
)
def test_each_basis_selects_a_different_version_on_the_planted_case(basis: AsOfBasis, expected: str) -> None:
    selection = select_versions(four_version_chain(), basis, TIMES)
    assert selection.status is SelectionStatus.FOUND and selection.version_ids == (expected,)


def test_a_domain_event_basis_without_an_event_time_is_an_error_not_a_guess() -> None:
    times = CaseTimes(at("2026-02-10"), at("2026-04-01"), at("2026-08-01"))
    with pytest.raises(WorldError, match="domain event"):
        select_versions(four_version_chain(), AsOfBasis.APPROVED_DOMAIN_EVENT, times)


def test_the_boundary_instant_belongs_to_the_newer_version() -> None:
    times = CaseTimes(at("2026-03-01"), at("2026-03-01"), at("2026-08-01"))
    assert select_versions(four_version_chain(), AsOfBasis.TRANSACTION_TIME, times).version_ids == ("POL-900@v2",)


def test_a_time_before_the_first_version_selects_nothing() -> None:
    times = CaseTimes(at("2025-12-31"), at("2026-04-01"), at("2026-08-01"))
    assert select_versions(four_version_chain(), AsOfBasis.TRANSACTION_TIME, times).status is SelectionStatus.NONE


def test_a_future_effective_version_is_not_selected_before_it_takes_effect() -> None:
    chain = (
        version("POL-900", 1, "2026-01-01", "2026-12-01"),
        version("POL-900", 2, "2026-12-01", None, recorded=Interval(at("2026-09-01"), None)),
    )
    times = CaseTimes(at("2026-10-01"), at("2026-10-01"), at("2026-10-18"))
    assert select_versions(chain, AsOfBasis.EVALUATION_TIME, times).version_ids == (
        "POL-900@v1",
    )  # newer but not yet effective


def test_a_retroactive_clause_binds_only_evaluations_made_after_it_was_recorded() -> None:
    chain = (
        version("POL-900", 1, "2026-01-01", "2026-06-01"),
        version("POL-900", 2, "2026-06-01", None, recorded=Interval(at("2026-09-01"), None)),
    )
    before = CaseTimes(at("2026-07-01"), at("2026-07-01"), at("2026-08-01"))  # evaluated before v2 was recorded
    after = CaseTimes(at("2026-07-01"), at("2026-07-01"), at("2026-10-01"))
    assert select_versions(chain, AsOfBasis.TRANSACTION_TIME, before).version_ids == ("POL-900@v1",)
    assert select_versions(chain, AsOfBasis.TRANSACTION_TIME, after).version_ids == ("POL-900@v2",)


def test_drafts_and_withdrawn_versions_never_govern() -> None:
    chain = (
        version("POL-900", 1, "2026-01-01", None),
        version("POL-900", 2, "2026-02-01", None, state=DocumentState.DRAFT, approved_by=None, claims_approval=True),
        version("POL-900", 3, "2026-03-01", None, state=DocumentState.WITHDRAWN, approved_by=None),
    )
    times = CaseTimes(at("2026-06-01"), at("2026-06-01"), at("2026-10-01"))
    assert select_versions(chain, AsOfBasis.EVALUATION_TIME, times).version_ids == ("POL-900@v1",)


def test_overlapping_approved_versions_in_one_family_are_a_conflict() -> None:
    chain = (version("POL-900", 1, "2026-01-01", None), version("POL-900", 2, "2026-02-01", None, supersedes=None))
    times = CaseTimes(at("2026-06-01"), at("2026-06-01"), at("2026-10-01"))
    assert select_versions(chain, AsOfBasis.EVALUATION_TIME, times).status is SelectionStatus.CONFLICT


# --------------------------------------------------------------------------- the evaluator (hand-computed)


def facts(amount: int | None = 1_000_000, state: str | None = "captured", hours: int = 10) -> CaseFacts:
    from datetime import timedelta

    from benchmark.fixtures.knowledge import iso, parse_ts

    opened = parse_ts(at("2026-04-02")) + timedelta(hours=hours)
    times = CaseTimes(at("2026-04-02"), iso(opened), at("2026-10-18"), at("2026-04-02"))
    return CaseFacts("T-NORTHWAVE", "reversal", "MC-RETAIL", amount, state, times)


def kb_of(*families_and_versions: Any, edges: tuple[Edge, ...] = ()) -> KnowledgeBase:
    fams = tuple(x for x in families_and_versions if isinstance(x, DocumentFamily))
    vers = tuple(x for x in families_and_versions if isinstance(x, DocumentVersion))
    return KnowledgeBase(fams, vers, edges)


def single_policy_kb(rule: PolicyRule = RULE) -> KnowledgeBase:
    return kb_of(policy_family(), version("POL-900", 1, "2026-01-01", None, rule=rule))


def evaluate(case: CaseFacts, kb: KnowledgeBase | None = None) -> PolicyOutcome:
    resolution = resolve_policy(kb or single_policy_kb(), case)
    assert resolution.status is SelectionStatus.FOUND and resolution.evaluation is not None
    return resolution.evaluation.outcome


def test_evaluator_outcomes_for_hand_computed_cases() -> None:
    assert evaluate(facts()) is PolicyOutcome.PERMITTED
    assert evaluate(facts(amount=5_000_000)) is PolicyOutcome.PERMITTED  # equal to the limit is allowed
    assert evaluate(facts(amount=5_000_001)) is PolicyOutcome.ESCALATE
    assert evaluate(facts(state="settled")) is PolicyOutcome.NOT_PERMITTED
    assert evaluate(facts(hours=72)) is PolicyOutcome.PERMITTED  # exactly at the window is inside it
    assert evaluate(facts(hours=73)) is PolicyOutcome.NOT_PERMITTED


def test_a_missing_input_is_reported_before_any_other_rule() -> None:
    resolution = resolve_policy(single_policy_kb(), facts(amount=None, state="settled"))
    assert resolution.evaluation is not None
    assert resolution.evaluation.outcome is PolicyOutcome.NEEDS_INPUT
    assert resolution.evaluation.missing_inputs == ("amount",)


def test_an_exception_extends_the_window_only_for_its_merchant_class() -> None:
    exception = DocumentFamily(
        "EXC-900", DocKind.EXCEPTION, "t", "PRD-01", "reversal", None, policy_family("EXC-900").scope, Lifecycle.PLAIN
    )
    kb = kb_of(
        policy_family(),
        version("POL-900", 1, "2026-01-01", None),
        exception,
        version("EXC-900", 1, "2026-01-01", None, rule=None, exception=ExceptionRule("MC-RETAIL", 48)),
        edges=(Edge("EXC-900", Relation.EXCEPTION_TO, "POL-900", "EXC-900@v1", Verification.VERIFIED),),
    )
    assert evaluate(facts(hours=100), kb) is PolicyOutcome.PERMITTED  # 72 + 48 = 120
    assert evaluate(facts(hours=121), kb) is PolicyOutcome.NOT_PERMITTED
    other_class = dataclasses.replace(facts(hours=100), merchant_class="MC-FOOD")
    assert evaluate(other_class, kb) is PolicyOutcome.NOT_PERMITTED


def test_no_matching_policy_is_none_and_a_scope_mismatch_is_not_a_match() -> None:
    kb = kb_of(policy_family(tenant_id="T-KESTREL"), version("POL-900", 1, "2026-01-01", None))
    assert resolve_policy(kb, facts()).status is SelectionStatus.NONE  # a different tenant's policy does not apply


def test_higher_precedence_wins_and_equal_precedence_with_different_rules_is_an_unresolved_conflict() -> None:
    strict = dataclasses.replace(RULE, window_hours=24)
    kb = kb_of(
        policy_family("POL-901", precedence=1), version("POL-901", 1, "2026-01-01", None, rule=RULE),
        policy_family("POL-902", precedence=2), version("POL-902", 1, "2026-01-01", None, rule=strict),
    )  # fmt: skip
    resolution = resolve_policy(kb, facts(hours=30))
    assert resolution.status is SelectionStatus.FOUND and resolution.version_ids == ("POL-902@v1",)
    tied = kb_of(
        policy_family("POL-901", precedence=2), version("POL-901", 1, "2026-01-01", None, rule=RULE),
        policy_family("POL-902", precedence=2), version("POL-902", 1, "2026-01-01", None, rule=strict),
    )  # fmt: skip
    conflict = resolve_policy(tied, facts(hours=30))
    assert conflict.status is SelectionStatus.CONFLICT and conflict.evaluation is None
    same = kb_of(
        policy_family("POL-901", precedence=2), version("POL-901", 1, "2026-01-01", None, rule=RULE),
        policy_family("POL-902", precedence=2), version("POL-902", 1, "2026-01-01", None, rule=RULE),
    )  # fmt: skip
    assert resolve_policy(same, facts(hours=30)).status is SelectionStatus.FOUND  # identical rules do not conflict


# --------------------------------------------------------------------------- graph and validation


def edge(src: str, dst: str, relation: Relation = Relation.SUPERSEDES) -> Edge:
    return Edge(src, relation, dst, src, Verification.VERIFIED)


def test_a_supersession_cycle_is_rejected_by_the_validator_but_not_by_construction() -> None:
    cycle = (edge("A@v1", "A@v2"), edge("A@v2", "A@v3"), edge("A@v3", "A@v1"))
    graph = KnowledgeBase((), (), cycle)  # construction stays permissive so a mutation can plant the defect
    assert len(graph.edges) == 3
    with pytest.raises(WorldError, match="cycle"):
        validate_supersession(graph.edges)
    validate_supersession(cycle[:2])  # a chain without the closing edge is fine


def test_two_successors_for_one_version_are_rejected() -> None:
    with pytest.raises(WorldError, match="more than one successor"):
        validate_supersession((edge("A@v2", "A@v1"), edge("A@v3", "A@v1")))


def valid_pair() -> KnowledgeBase:
    return kb_of(
        policy_family(),
        version("POL-900", 1, "2026-01-01", "2026-03-01"),
        version("POL-900", 2, "2026-03-01", None),
        edges=(Edge("POL-900@v2", Relation.SUPERSEDES, "POL-900@v1", "POL-900@v2", Verification.VERIFIED),),
    )


def test_a_clean_knowledge_base_passes_and_each_planted_defect_is_caught() -> None:
    clean = valid_pair()
    validate_knowledge(ENTITIES, clean)
    v1, v2 = clean.versions
    other = version("POL-901", 1, "2026-01-01", None)
    with_other = dataclasses.replace(clean, families=(*clean.families, policy_family("POL-901")))
    cases: dict[str, KnowledgeBase] = {
        "inconsistent identity": dataclasses.replace(clean, versions=(dataclasses.replace(v1, version=9), v2)),
        "source hash does not match": dataclasses.replace(clean, versions=(dataclasses.replace(v1, steps=("x",)), v2)),
        "lacks a verified approver": dataclasses.replace(clean, versions=(rehash(v1, approved_by="nobody.x.01"), v2)),
        "draft cannot hold an approver": dataclasses.replace(
            clean, versions=(rehash(v1, state=DocumentState.DRAFT), v2)
        ),
        "only a draft may claim approval": dataclasses.replace(clean, versions=(rehash(v1, claims_approval=True), v2)),
        "supersedes an unknown version": dataclasses.replace(clean, versions=(v1, rehash(v2, supersedes="Z@v1"))),
        "ACL names an unknown tenant": dataclasses.replace(clean, versions=(v1, rehash(v2, acl_tenants=("T-NOPE",)))),
        "unknown node or supporting source": dataclasses.replace(
            clean,
            edges=(
                *clean.edges,
                Edge("POL-900", Relation.APPLIES_TO, "no_such_type", "POL-900@v2", Verification.VERIFIED),
            ),
        ),
        "must link in-force versions of one family": dataclasses.replace(
            with_other, versions=(*clean.versions, other), edges=(edge("POL-901@v1", "POL-900@v1"),)
        ),
        "duplicate family or version": dataclasses.replace(clean, versions=(v1, v1)),
    }
    for message, broken in cases.items():
        with pytest.raises(WorldError, match=message):
            validate_knowledge(ENTITIES, broken)


def test_a_draft_that_claims_board_approval_is_accepted_only_while_it_stays_unapproved() -> None:
    draft = version("POL-900", 2, "2026-12-01", None, state=DocumentState.DRAFT, approved_by=None, claims_approval=True)
    kb = kb_of(policy_family(), version("POL-900", 1, "2026-01-01", None), draft)
    validate_knowledge(ENTITIES, kb)
    assert not draft.in_force
    promoted = rehash(draft, state=DocumentState.APPROVED)  # the body still claims approval, the registry now agrees
    with pytest.raises(WorldError, match="lacks a verified approver"):
        validate_knowledge(ENTITIES, kb_of(policy_family(), version("POL-900", 1, "2026-01-01", None), promoted))


def test_the_source_hash_tracks_content_and_a_plain_replace_leaves_it_stale() -> None:
    v = version("POL-900", 1, "2026-01-01", None)
    assert v.source_sha256 == v.compute_hash() and len(v.source_sha256) == 64
    assert (
        dataclasses.replace(v, steps=("x",)).source_sha256 == v.source_sha256
    )  # stale on purpose: validation catches it
    assert rehash(v, steps=("x",)).source_sha256 != v.source_sha256
    assert version("POL-900", 1, "2026-01-01", None).source_sha256 == v.source_sha256


def test_visibility_follows_tenant_and_role_lists() -> None:
    northwave = next(p for p in ENTITIES.principals if p.tenant_id == "T-NORTHWAVE" and p.role_id == "support_l1")
    kestrel = next(p for p in ENTITIES.principals if p.tenant_id == "T-KESTREL" and p.role_id == "support_l1")
    scoped = version("POL-900", 1, "2026-01-01", None, acl_tenants=("T-NORTHWAVE", "T-MERIDIAN"))
    assert visible_to(scoped, northwave) and not visible_to(scoped, kestrel)
    restricted = version("POL-900", 1, "2026-01-01", None, acl_roles=("support_l2",))
    assert not visible_to(restricted, northwave)
    assert visible_to(version("POL-900", 1, "2026-01-01", None), kestrel)


# --------------------------------------------------------------------------- the generated knowledge base


@pytest.fixture(scope="module")
def generated() -> KnowledgeBase:
    return build_knowledge(ENTITIES, SEED, sop_versions=260, policy_documents=140, conflict_pairs=4)


def test_generation_is_deterministic_and_seed_sensitive(generated: KnowledgeBase) -> None:
    again = build_knowledge(ENTITIES, SEED, sop_versions=260, policy_documents=140, conflict_pairs=4)
    assert canonical_json(again) == canonical_json(generated) and again.digest() == generated.digest()
    other_entities = build_entities(8)
    other = build_knowledge(other_entities, 8, sop_versions=260, policy_documents=140, conflict_pairs=4)
    assert other.digest() != generated.digest()


def test_generation_hits_the_requested_document_counts(generated: KnowledgeBase) -> None:
    by_kind = {k: 0 for k in DocKind}
    for v in generated.versions:
        by_kind[generated.family(v.family_id).kind] += 1
    assert by_kind[DocKind.SOP] == 260
    assert by_kind[DocKind.POLICY] + by_kind[DocKind.EXCEPTION] == 140
    validate_knowledge(ENTITIES, generated)


def test_every_planted_lifecycle_appears_and_behaves_as_labelled(generated: KnowledgeBase) -> None:
    seen = {f.lifecycle for f in generated.families}
    assert seen == set(Lifecycle)
    for family in generated.families:
        versions = generated.versions_of(family.family_id)
        if family.lifecycle is Lifecycle.DRAFT_TAIL:
            assert versions[-1].state is DocumentState.DRAFT and versions[-1].approved_by is None
        if family.lifecycle is Lifecycle.WITHDRAWN:
            assert any(v.state is DocumentState.WITHDRAWN for v in versions)
        if family.lifecycle is Lifecycle.FUTURE:
            assert parse_future(versions[-1]) and versions[-1].state is DocumentState.APPROVED
        if family.lifecycle is Lifecycle.RETROACTIVE:
            assert versions[-1].recorded.start > versions[-1].valid.start  # recorded after it took effect


def parse_future(v: DocumentVersion) -> bool:
    return v.valid.start > "2026-10-18T03:00:00Z"


def test_no_draft_or_withdrawn_version_is_ever_in_force_or_selected(generated: KnowledgeBase) -> None:
    claiming = [v for v in generated.versions if v.claims_approval]
    assert claiming and all(v.state is DocumentState.DRAFT and not v.in_force for v in claiming)
    times = CaseTimes("2026-06-01T00:00:00Z", "2026-06-01T00:00:00Z", "2026-10-18T03:00:00Z", "2026-06-01T00:00:00Z")
    for family in generated.families:
        for basis in AsOfBasis:
            chosen = select_versions(generated.versions_of(family.family_id), basis, times).version_ids
            assert all(generated.version(v).in_force for v in chosen)


def test_conflict_pairs_overlap_in_scope_and_time_and_really_disagree(generated: KnowledgeBase) -> None:
    left = [f for f in generated.families if f.lifecycle is Lifecycle.CONFLICT_A]
    right = [f for f in generated.families if f.lifecycle is Lifecycle.CONFLICT_B]
    assert len(left) == len(right) == 4
    for a, b in zip(left, right, strict=True):
        assert a.scope == b.scope  # identical scope, precedence and basis
        last_a, last_b = generated.versions_of(a.family_id)[-1], generated.versions_of(b.family_id)[-1]
        assert last_a.valid.overlaps(last_b.valid) and last_a.rule != last_b.rule


def test_a_conflict_pair_resolves_to_conflict_for_a_case_in_scope(generated: KnowledgeBase) -> None:
    family = next(f for f in generated.families if f.lifecycle is Lifecycle.CONFLICT_A)
    assert family.scope is not None
    times = CaseTimes(*(["2026-09-01T00:00:00Z"] * 4))
    tenant = family.scope.tenant_id or "T-NORTHWAVE"
    merchant_class = family.scope.merchant_class or "MC-RETAIL"
    case = CaseFacts(tenant, family.scope.txn_type_id, merchant_class, 1_000_000, "captured", times)
    assert resolve_policy(generated, case).status is SelectionStatus.CONFLICT


def test_the_newest_version_is_often_not_the_applicable_one(generated: KnowledgeBase) -> None:
    """Version order must not give the answer away: some families have a newer version that does not govern."""
    times = CaseTimes(*(["2026-10-18T03:00:00Z"] * 4))
    not_newest = 0
    for family in generated.families:
        versions = generated.versions_of(family.family_id)
        chosen = select_versions(versions, AsOfBasis.EVALUATION_TIME, times).version_ids
        if chosen and chosen[0] != versions[-1].version_id:
            not_newest += 1
    assert not_newest >= 10


def test_every_edge_has_a_supporting_source_in_the_same_snapshot(generated: KnowledgeBase) -> None:
    versions = {v.version_id for v in generated.versions}
    assert generated.edges and all(e.source_version_id in versions for e in generated.edges)
    assert {e.relation for e in generated.edges} == set(Relation)
    assert all(e.verification is Verification.VERIFIED for e in generated.edges)


def test_scale_that_cannot_fit_is_refused() -> None:
    with pytest.raises(WorldError, match="cannot place"):
        build_knowledge(ENTITIES, SEED, sop_versions=1, policy_documents=140, conflict_pairs=4)
    with pytest.raises(WorldError, match="scale too small"):
        build_knowledge(ENTITIES, SEED, sop_versions=260, policy_documents=14, conflict_pairs=4)


def test_world_entities_type_is_unchanged_by_knowledge_generation() -> None:
    assert isinstance(ENTITIES, WorldEntities)
    before = ENTITIES.digest()
    build_knowledge(ENTITIES, SEED, sop_versions=260, policy_documents=140, conflict_pairs=4)
    assert ENTITIES.digest() == before


def test_precedence_follows_scope_specificity_so_overlapping_policies_never_tie() -> None:
    assert specificity_precedence(("reversal", None, None)) == 1
    assert specificity_precedence(("reversal", "MC-FOOD", None)) == 2
    assert specificity_precedence(("reversal", None, "T-NORTHWAVE")) == 3
    assert specificity_precedence(("reversal", "MC-FOOD", "T-NORTHWAVE")) == 4
    assert specificity_precedence(("reversal", "MC-FOOD", "T-NORTHWAVE")) < CONFLICT_PRECEDENCE


def test_a_version_history_that_needs_three_versions_refuses_two() -> None:
    for lifecycle in (Lifecycle.DRAFT_TAIL, Lifecycle.WITHDRAWN):
        with pytest.raises(WorldError, match="at least three versions"):
            plan_versions(random.Random(1), 2, lifecycle)
