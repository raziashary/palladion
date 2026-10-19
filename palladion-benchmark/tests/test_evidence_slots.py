"""Gold evidence schema, generated questions and their consumers (B02-T04.01)."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from benchmark.contracts import AbstentionReason, EvidenceStatus, screen_arm_visible
from benchmark.fixtures import question_gen, sha256_hex
from benchmark.fixtures.documents import Document, extract_facts
from benchmark.fixtures.knowledge import DocumentState, DocumentVersion
from benchmark.fixtures.live_api import LiveMock, LiveStatus, Mode
from benchmark.fixtures.manifest import Split, build_records, snapshot_id
from benchmark.fixtures.phrasebook import QUESTION_TEMPLATES
from benchmark.fixtures.question_gen import build_questions
from benchmark.fixtures.questions import (
    ANSWERABILITY_RULES,
    Answerability,
    Citation,
    EvidenceSlot,
    GoldError,
    GoldRecord,
    Severity,
    SlotState,
    Stratum,
    arm_request,
    check_authority,
    derive_minimal_sets,
    screen_query,
)
from benchmark.fixtures.world import World

CONFIGS = Path(__file__).resolve().parents[1] / "configs"
SEED = 7
R = AbstentionReason
CITE_A = Citation("POL-001@v1", "4.1", 10, 60, "a" * 64)
CITE_B = Citation("POL-001@v2", "4.1", 10, 60, "b" * 64)


@pytest.fixture
def world(s_world: World) -> World:
    return s_world


@pytest.fixture
def corpus(s_corpus: tuple[Document, ...]) -> tuple[Document, ...]:
    return s_corpus


@pytest.fixture
def records(s_questions: tuple[GoldRecord, ...]) -> tuple[GoldRecord, ...]:
    return s_questions


def gap(
    name: str = "policy_clause",
    state: SlotState = SlotState.NO_SOURCE_BY_DESIGN,
    why: AbstentionReason = R.NO_KNOWN_SUPPORT,
) -> EvidenceSlot:
    return EvidenceSlot(name, state, why, ())


def found(name: str, *alternatives: Citation) -> EvidenceSlot:
    return EvidenceSlot(name, SlotState.SATISFIABLE, None, alternatives)


def record(**changes: Any) -> GoldRecord:
    """A valid answerable record; tests override the fields they want to break."""
    slots = changes.get("slots", (found("window_clause", CITE_A),))
    spans = tuple({c.key: c for s in slots for c in s.alternatives}.values())
    base: dict[str, Any] = {
        "question_id": "q-00000001",
        "split": Split.SMOKE,
        "stratum": Stratum.Q2,
        "difficulty": 1,
        "language": "en",
        "scenario_family": "POL-001",
        "corpus_snapshot_id": "snap-0123456789abcdef",
        "principal_id": "northwave.support_l2.01",
        "tenant_id": "T-NORTHWAVE",
        "authorized_partitions": ("T-NORTHWAVE",),
        "evaluation_time": "2026-10-18T03:00:00Z",
        "event_time": None,
        "case_open_time": None,
        "query": "How long?",
        "answerability": Answerability.ANSWERABLE,
        "missing_reasons": (),
        "required_claims": ("the window is 72 hours",),
        "forbidden_claims": (),
        "slots": slots,
        "minimal_sets": derive_minimal_sets(slots),
        "gold_as_of_basis": None,
        "gold_applicable_version_ids": (),
        "policy_outcome": None,
        "required_policy_inputs": (),
        "expected_live_snapshot": None,
        "allowed_statuses": (EvidenceStatus.SUPPORTED,),
        "preferred_action": "answer",
        "abstention_note": None,
        "citation_gold_spans": spans,
        "harm_severity": Severity.LOW,
        "allowed_actions": (),
        "inaccessible_sources": (),
        "track_eligibility": ("retrieval_only",),
        "twin_of": None,
    }
    base.update(changes)
    if "slots" in changes:
        base["citation_gold_spans"] = changes.get(
            "citation_gold_spans", tuple({c.key: c for s in changes["slots"] for c in s.alternatives}.values())
        )
        base["minimal_sets"] = changes.get("minimal_sets", derive_minimal_sets(changes["slots"]))
    return GoldRecord(**base)


# --------------------------------------------------------------------------- the schema


def test_a_valid_answerable_record_is_accepted() -> None:
    assert record().answerability is Answerability.ANSWERABLE


def test_empty_alternatives_with_a_stated_mechanism_mean_unavailable_not_error() -> None:
    unanswerable = record(
        answerability=Answerability.UNANSWERABLE,
        missing_reasons=(R.NO_KNOWN_SUPPORT,),
        slots=(gap(),),
        allowed_statuses=(EvidenceStatus.NOT_ESTABLISHED,),
        required_claims=(),
    )
    assert unanswerable.slots[0].alternatives == () and unanswerable.minimal_sets == ()


def test_a_slot_must_agree_with_its_own_state() -> None:
    with pytest.raises(GoldError, match="satisfiable slot needs alternatives"):
        EvidenceSlot("s", SlotState.SATISFIABLE, None, ())
    with pytest.raises(GoldError, match="satisfiable slot needs alternatives"):
        EvidenceSlot("s", SlotState.SATISFIABLE, R.NO_KNOWN_SUPPORT, (CITE_A,))
    with pytest.raises(GoldError, match="unavailable slot needs a matching mechanism"):
        EvidenceSlot("s", SlotState.NO_SOURCE_BY_DESIGN, None, ())
    with pytest.raises(GoldError, match="unavailable slot needs a matching mechanism"):
        EvidenceSlot("s", SlotState.BLOCKED_BY_ACL, R.NO_KNOWN_SUPPORT, ())
    with pytest.raises(GoldError, match="unavailable slot needs a matching mechanism"):
        EvidenceSlot("s", SlotState.LIVE_UNAVAILABLE, R.REQUIRED_LIVE_CHECK_UNAVAILABLE, (CITE_A,))


def test_an_answerable_record_cannot_carry_an_unavailable_slot_or_no_slot() -> None:
    with pytest.raises(GoldError, match="slot mechanisms differ"):
        record(slots=(found("a", CITE_A), gap("b")))
    with pytest.raises(GoldError, match="every slot satisfiable"):
        record(slots=())
    with pytest.raises(GoldError, match="negative mechanism does not fit"):
        record(missing_reasons=(R.NO_KNOWN_SUPPORT,))


@pytest.mark.parametrize("answerability", list(Answerability))
def test_every_answerability_rejects_a_mechanism_it_does_not_allow(answerability: Answerability) -> None:
    allowed, _ = ANSWERABILITY_RULES[answerability]
    outside = next(r for r in R if r not in allowed)
    with pytest.raises(GoldError):
        record(answerability=answerability, missing_reasons=(outside,))


def test_each_answerability_accepts_its_own_shape() -> None:
    partial = record(
        answerability=Answerability.PARTIAL,
        missing_reasons=(R.MISSING_CASE_INPUT,),
        slots=(found("clause", CITE_A), gap("amount", why=R.MISSING_CASE_INPUT)),
        allowed_statuses=(EvidenceStatus.PARTIALLY_SUPPORTED,),
    )
    conflict = record(
        answerability=Answerability.CONFLICT,
        missing_reasons=(R.SOURCE_CONFLICT,),
        slots=(found("a", CITE_A), found("b", CITE_B)),
        allowed_statuses=(EvidenceStatus.CONFLICT,),
    )
    blocked = record(
        answerability=Answerability.BLOCKED_BY_ACL,
        missing_reasons=(R.UNAUTHORIZED_SOURCE,),
        slots=(gap("runbook", SlotState.BLOCKED_BY_ACL, R.UNAUTHORIZED_SOURCE),),
        inaccessible_sources=("ART-1",),
        allowed_statuses=(EvidenceStatus.NOT_ESTABLISHED,),
        required_claims=(),
    )
    live = record(
        answerability=Answerability.VERIFICATION_UNAVAILABLE,
        missing_reasons=(R.REQUIRED_LIVE_CHECK_UNAVAILABLE,),
        slots=(gap("live", SlotState.LIVE_UNAVAILABLE, R.REQUIRED_LIVE_CHECK_UNAVAILABLE),),
        allowed_statuses=(EvidenceStatus.VERIFICATION_UNAVAILABLE,),
        required_claims=(),
    )
    assert (partial.answerability, conflict.answerability, blocked.answerability, live.answerability) == (
        Answerability.PARTIAL,
        Answerability.CONFLICT,
        Answerability.BLOCKED_BY_ACL,
        Answerability.VERIFICATION_UNAVAILABLE,
    )


def test_a_conflict_is_a_distinct_label_from_absence() -> None:
    with pytest.raises(GoldError, match="negative mechanism does not fit"):
        record(
            answerability=Answerability.CONFLICT,
            missing_reasons=(R.NO_KNOWN_SUPPORT,),
            slots=(found("a", CITE_A), found("b", CITE_B)),
            allowed_statuses=(EvidenceStatus.CONFLICT,),
        )
    with pytest.raises(GoldError, match="two satisfiable sides"):
        record(
            answerability=Answerability.CONFLICT,
            missing_reasons=(R.SOURCE_CONFLICT,),
            slots=(found("a", CITE_A),),
            allowed_statuses=(EvidenceStatus.CONFLICT,),
        )


def test_a_partial_record_needs_both_kinds_of_slot() -> None:
    with pytest.raises(GoldError, match="satisfiable and missing slots"):
        record(
            answerability=Answerability.PARTIAL,
            missing_reasons=(R.MISSING_CASE_INPUT,),
            slots=(gap("amount", why=R.MISSING_CASE_INPUT),),
            allowed_statuses=(EvidenceStatus.PARTIALLY_SUPPORTED,),
        )


def test_a_blocked_record_must_name_what_is_inaccessible_and_never_cite_it() -> None:
    blocked: dict[str, Any] = {
        "answerability": Answerability.BLOCKED_BY_ACL,
        "missing_reasons": (R.UNAUTHORIZED_SOURCE,),
        "allowed_statuses": (EvidenceStatus.NOT_ESTABLISHED,),
        "required_claims": (),
    }
    slots = (gap("runbook", SlotState.BLOCKED_BY_ACL, R.UNAUTHORIZED_SOURCE),)
    with pytest.raises(GoldError, match="name the inaccessible sources"):
        record(slots=slots, **blocked)
    cited = (gap("runbook", SlotState.BLOCKED_BY_ACL, R.UNAUTHORIZED_SOURCE), found("other", CITE_A))
    with pytest.raises(GoldError, match="forbidden gold"):
        record(slots=cited, inaccessible_sources=("POL-001@v1",), **blocked)


def test_statuses_must_fit_the_answerability() -> None:
    with pytest.raises(GoldError, match="accepted statuses"):
        record(allowed_statuses=(EvidenceStatus.CONFLICT,))
    with pytest.raises(GoldError, match="accepted statuses"):
        record(allowed_statuses=())


def test_minimal_sets_and_citation_spans_must_match_the_slots() -> None:
    slots = (found("a", CITE_A, CITE_B), found("b", Citation("EXC-001@v1", "4.1", 0, 5, "c" * 64)))
    good = record(slots=slots)
    assert len(good.minimal_sets) == 2 and all(len(s) == 2 for s in good.minimal_sets)  # (A or B) and C
    with pytest.raises(GoldError, match="minimal evidence sets"):
        record(slots=slots, minimal_sets=good.minimal_sets[:1])
    with pytest.raises(GoldError, match="citation spans"):
        record(slots=slots, citation_gold_spans=(CITE_A,))


def test_metadata_rules() -> None:
    with pytest.raises(GoldError, match="difficulty"):
        record(difficulty=4)
    with pytest.raises(GoldError, match="required claims"):
        record(required_claims=())
    with pytest.raises(GoldError, match="unknown track"):
        record(track_eligibility=("everything",))
    with pytest.raises(GoldError, match="own twin"):
        record(twin_of="q-00000001")


def test_a_draft_cannot_satisfy_a_slot(world: World) -> None:
    draft = next(v for v in world.knowledge.versions if v.state is DocumentState.DRAFT)
    approved = next(v for v in world.knowledge.versions if v.in_force)

    def cite(version: DocumentVersion) -> Citation:
        return Citation(version.version_id, "4.1", 0, 10, "d" * 64)

    check_authority(record(slots=(found("w", cite(approved)),)), world)
    with pytest.raises(GoldError, match="not in force"):
        check_authority(record(slots=(found("w", cite(draft)),)), world)
    with pytest.raises(GoldError, match="cannot be an applicable version"):
        check_authority(record(gold_applicable_version_ids=(draft.version_id,)), world)
    with pytest.raises(GoldError, match="cannot be an applicable version"):
        check_authority(record(gold_applicable_version_ids=("NOPE-001@v1",)), world)


# --------------------------------------------------------------------------- query screening


@pytest.mark.parametrize(
    "text,stratum,kind,message",
    [
        ("Is this unanswerable?", Stratum.Q7, "offworld", "answer-class vocabulary"),
        ("Two sources conflict here", Stratum.Q6, "x", "answer-class vocabulary"),
        ("What is the gold answer", Stratum.Q2, "x", "gold-like"),
        ("Check POL-012 please", Stratum.Q2, "window_ask", "document or version id"),
        ("Check POL-012@v2", Stratum.Q4, "temporal", "document or version id"),
        ("Why MS-4127 now?", Stratum.Q8, "blocked", "error code"),
        ("Status of TXN-NOR-00012?", Stratum.Q2, "x", "transaction id"),
    ],
)
def test_query_screening_refuses_each_planted_leak(text: str, stratum: Stratum, kind: str, message: str) -> None:
    with pytest.raises(GoldError, match=message):
        screen_query(text, stratum, kind)


def test_identifiers_are_allowed_only_in_their_own_strata() -> None:
    screen_query("According to POL-012@v2, how long?", Stratum.Q1, "exact_version")
    screen_query("HTTP status for error MS-4127?", Stratum.Q1, "api_status")
    screen_query("Status of TXN-NOR-00012?", Stratum.Q9, "live_status")


# --------------------------------------------------------------------------- generated questions


def test_the_pilot_has_ten_questions_in_each_stratum_all_in_smoke(records: tuple[GoldRecord, ...]) -> None:
    assert len(records) == 100 and {r.split for r in records} == {Split.SMOKE}
    assert Counter(r.stratum for r in records) == {s: 10 for s in Stratum}
    assert len({r.question_id for r in records}) == 100


def test_the_pilot_covers_every_answerability_and_the_language_profile(records: tuple[GoldRecord, ...]) -> None:
    assert {r.answerability for r in records} == set(Answerability)
    assert Counter(r.language for r in records) == {"en": 55, "id": 30, "mixed": 15}
    assert {m for r in records for m in r.missing_reasons} == {
        R.NO_KNOWN_SUPPORT,
        R.UNAUTHORIZED_SOURCE,
        R.MISSING_CASE_INPUT,
        R.REQUIRED_LIVE_CHECK_UNAVAILABLE,
        R.SOURCE_CONFLICT,
    }


def test_every_protocol_field_is_present_and_the_record_serialises(records: tuple[GoldRecord, ...]) -> None:
    required = {
        "question_id",
        "stratum",
        "difficulty",
        "language",
        "scenario_family",
        "corpus_snapshot_id",
        "principal_id",
        "tenant_id",
        "authorized_partitions",
        "evaluation_time",
        "event_time",
        "case_open_time",
        "answerability",
        "missing_reasons",
        "required_claims",
        "forbidden_claims",
        "slots",
        "minimal_sets",
        "gold_as_of_basis",
        "gold_applicable_version_ids",
        "policy_outcome",
        "required_policy_inputs",
        "expected_live_snapshot",
        "allowed_statuses",
        "preferred_action",
        "citation_gold_spans",
        "harm_severity",
        "allowed_actions",
        "track_eligibility",
    }
    for r in records:
        plain = json.loads(json.dumps(r.to_dict()))
        assert required <= set(plain)


def test_every_citation_resolves_to_the_exact_span_in_the_published_text(
    records: tuple[GoldRecord, ...], corpus: tuple[Document, ...]
) -> None:
    docs = {d.doc_id: d for d in corpus}
    checked = 0
    for r in records:
        for slot in r.slots:
            for c in slot.alternatives:
                if c.doc_id.startswith("live:"):
                    continue
                span = docs[c.doc_id].text[c.start : c.end]
                assert sha256_hex(span) == c.span_sha256 and span
                checked += 1
    assert checked > 150


def test_cited_policy_clauses_state_what_the_claims_say(
    records: tuple[GoldRecord, ...], corpus: tuple[Document, ...]
) -> None:
    """Read the window back out of the cited text with the extractor, not from the world."""
    docs = {d.doc_id: d for d in corpus}
    exact = [r for r in records if r.stratum is Stratum.Q1 and r.slots[0].slot == "window_clause"]
    assert exact
    for r in exact:
        c = r.slots[0].alternatives[0]
        window = extract_facts(docs[c.doc_id].text[c.start : c.end]).window
        assert window is not None and f"within {window} hours" in r.required_claims[0]


def test_blocked_questions_name_runbooks_the_principal_cannot_see(
    records: tuple[GoldRecord, ...], corpus: tuple[Document, ...], world: World
) -> None:
    docs = {d.doc_id: d for d in corpus}
    blocked = [r for r in records if r.answerability is Answerability.BLOCKED_BY_ACL]
    assert len(blocked) == 5
    for r in blocked:
        who = next(p for p in world.entities.principals if p.principal_id == r.principal_id)
        assert r.inaccessible_sources
        for doc_id in r.inaccessible_sources:
            doc = docs[doc_id]
            assert doc.acl_roles and who.role_id not in doc.acl_roles
        assert any("exists" in f for f in r.forbidden_claims)  # existence must not be confirmed


def test_conflict_questions_cite_two_different_authorities_with_different_windows(
    records: tuple[GoldRecord, ...],
) -> None:
    for r in (r for r in records if r.answerability is Answerability.CONFLICT):
        a, b = (s.alternatives[0] for s in r.slots)
        assert a.doc_id.split("@")[0] != b.doc_id.split("@")[0] and a.span_sha256 != b.span_sha256
        assert r.missing_reasons == (R.SOURCE_CONFLICT,) and r.gold_as_of_basis is None


def test_temporal_questions_choose_an_older_version_whose_window_differs(
    records: tuple[GoldRecord, ...], world: World
) -> None:
    for r in (r for r in records if r.stratum is Stratum.Q4):
        chosen = world.knowledge.version(r.gold_applicable_version_ids[0])
        in_force = [v for v in world.knowledge.versions_of(chosen.family_id) if v.in_force]
        assert chosen.version_id != in_force[-1].version_id  # "newest" is the wrong answer
        assert chosen.rule and in_force[-1].rule and chosen.rule.window_hours != in_force[-1].rule.window_hours
        assert r.gold_as_of_basis is not None and r.event_time is not None and r.case_open_time is not None


def test_policy_outcome_questions_carry_outcome_and_required_inputs(records: tuple[GoldRecord, ...]) -> None:
    q5 = [r for r in records if r.stratum is Stratum.Q5]
    assert all(r.policy_outcome and r.required_policy_inputs == ("amount", "txn_state") for r in q5)
    partial = [r for r in q5 if r.answerability is Answerability.PARTIAL]
    assert partial and all(r.policy_outcome == "NEEDS_INPUT" for r in partial)
    assert {r.policy_outcome for r in q5} >= {"NEEDS_INPUT"}


def test_live_questions_match_the_mock_replayed_from_their_stored_snapshot(
    records: tuple[GoldRecord, ...], world: World
) -> None:
    live_records = [r for r in records if r.stratum is Stratum.Q9]
    assert Counter(r.expected_live_snapshot["mode"] for r in live_records if r.expected_live_snapshot) == {
        "ok": 6,
        "outage": 2,
        "stale": 2,
    }
    for r in live_records:
        snap = r.expected_live_snapshot
        assert snap is not None and r.track_eligibility == ("native_end_to_end",)
        mock = LiveMock(world.entities, world.operations, {(snap["case_key"], snap["operation"]): Mode(snap["mode"])})
        who = next(p for p in world.entities.principals if p.principal_id == r.principal_id)
        got = mock.read(snap["case_key"], snap["operation"], snap["subject_id"], who, r.evaluation_time)
        assert (got.status.value, got.http_status, got.fresh) == (snap["status"], snap["http_status"], snap["fresh"])
        answerable = got.status is LiveStatus.OK and got.fresh
        assert (r.answerability is Answerability.ANSWERABLE) == answerable


def test_unauthorized_live_reads_are_labelled_as_a_live_check_that_cannot_be_made(
    records: tuple[GoldRecord, ...],
) -> None:
    unauthorized = [
        r for r in records if r.expected_live_snapshot and r.expected_live_snapshot["status"] == "unauthorized"
    ]
    assert unauthorized and all(r.answerability is Answerability.VERIFICATION_UNAVAILABLE for r in unauthorized)


def test_unanswerable_twins_pair_with_answerable_questions_of_the_same_split(records: tuple[GoldRecord, ...]) -> None:
    by_id = {r.question_id: r for r in records}
    twinned = [r for r in records if r.twin_of]
    assert len(twinned) >= 4
    for r in twinned:
        other = by_id[r.twin_of or ""]
        assert other.twin_of == r.question_id and other.split == r.split
        assert {r.answerability, other.answerability} == {Answerability.ANSWERABLE, Answerability.UNANSWERABLE}


def test_off_world_topics_really_are_absent_from_the_corpus(
    records: tuple[GoldRecord, ...], corpus: tuple[Document, ...]
) -> None:
    text = " ".join(d.text.lower() for d in corpus)
    topics = [r.scenario_family[6:] for r in records if r.scenario_family.startswith("topic:")]
    assert topics and all(t.split()[0] not in text for t in topics)


def test_spoofed_approval_questions_name_the_unapproved_memo_as_a_source(records: tuple[GoldRecord, ...]) -> None:
    spoof = [r for r in records if "authority_spoof" in r.tags]
    assert spoof
    for r in spoof:
        assert {s.slot for s in r.slots} == {"current_policy", "proposal_status"}
        assert any("in force" in f for f in r.forbidden_claims)


def test_track_eligibility_keeps_live_questions_out_of_retrieval_only_runs(records: tuple[GoldRecord, ...]) -> None:
    assert all("retrieval_only" not in r.track_eligibility for r in records if r.stratum is Stratum.Q9)
    assert all("retrieval_only" in r.track_eligibility for r in records if r.stratum is not Stratum.Q9)


# --------------------------------------------------------------------------- the barrier


def test_the_arm_visible_request_carries_no_gold_and_derives_filters_from_the_principal(
    records: tuple[GoldRecord, ...], world: World
) -> None:
    for r in records:
        request = arm_request(r, world)
        plain = request.to_dict()
        screen_arm_visible("request", plain)
        who = next(p for p in world.entities.principals if p.principal_id == r.principal_id)
        assert plain["filters"] == {"tenant_id": who.tenant_id, "role": who.role_id}
        text = json.dumps(plain)
        assert r.split.value not in text and r.stratum.value not in text
        if r.stratum is not Stratum.Q1:  # only the exact-id stratum names its policy in the question
            assert r.scenario_family not in text


def test_generation_is_deterministic_and_seed_sensitive(
    records: tuple[GoldRecord, ...], world: World, corpus: tuple[Document, ...]
) -> None:
    sid = snapshot_id(build_records(world, corpus, SEED))
    again = build_questions(world, corpus, sid, SEED, "S", {Split.SMOKE: 10})
    assert [r.to_dict() for r in again] == [r.to_dict() for r in records]
    other_tier = build_questions(world, corpus, sid, SEED, "T", {Split.SMOKE: 10})
    assert {r.question_id for r in other_tier}.isdisjoint({r.question_id for r in records})


def test_a_record_that_breaks_a_rule_after_construction_is_caught_by_replacing_it(
    records: tuple[GoldRecord, ...],
) -> None:
    with pytest.raises(GoldError):
        replace(records[0], allowed_statuses=(EvidenceStatus.CONFLICT,))


def test_question_ids_depend_on_the_secret_and_cannot_be_recomputed_without_it(
    records: tuple[GoldRecord, ...], world: World, corpus: tuple[Document, ...]
) -> None:
    sid = snapshot_id(build_records(world, corpus, SEED))
    keyed = build_questions(world, corpus, sid, SEED, "S", {Split.SMOKE: 10}, id_secret="private")
    assert keyed == build_questions(world, corpus, sid, SEED, "S", {Split.SMOKE: 10}, id_secret="private")
    assert {r.question_id for r in keyed}.isdisjoint({r.question_id for r in records})
    assert [r.query for r in keyed] == [r.query for r in records]  # only the identifiers change


def test_a_leaking_template_is_refused_when_questions_are_built(
    world: World, corpus: tuple[Document, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    leaking = {
        **QUESTION_TEMPLATES,
        "window_ask": {lang: ("This is an unanswerable {txn} case",) for lang in ("en", "id", "mixed")},
    }
    monkeypatch.setattr(question_gen, "QUESTION_TEMPLATES", leaking)
    sid = snapshot_id(build_records(world, corpus, SEED))
    with pytest.raises(GoldError, match="answer-class vocabulary"):
        build_questions(world, corpus, sid, SEED, "S", {Split.SMOKE: 10})


def test_live_questions_never_concern_a_transaction_that_a_ticket_describes(
    records: tuple[GoldRecord, ...], world: World
) -> None:
    ticketed = {c.txn_id for c in world.operations.cases}
    live = [r for r in records if r.stratum is Stratum.Q9]
    assert live and not any(
        r.expected_live_snapshot and r.expected_live_snapshot["subject_id"] in ticketed for r in live
    )


def test_twins_share_a_transaction_type_and_a_wording_template(records: tuple[GoldRecord, ...]) -> None:
    by_id = {r.question_id: r for r in records}
    twinned = [r for r in records if r.twin_of]
    assert len(twinned) >= 4
    for r in twinned:
        other = by_id[r.twin_of or ""]
        assert r.tags == other.tags and r.tags[0].startswith("twin:")
        assert {r.stratum, other.stratum} == {Stratum.Q2, Stratum.Q7}


def test_the_basis_clause_of_a_version_question_comes_from_the_applicable_version_only(
    records: tuple[GoldRecord, ...],
) -> None:
    for r in (r for r in records if r.stratum is Stratum.Q4):
        basis = next(s for s in r.slots if s.slot == "basis_clause")
        assert [c.doc_id for c in basis.alternatives] == list(r.gold_applicable_version_ids)
