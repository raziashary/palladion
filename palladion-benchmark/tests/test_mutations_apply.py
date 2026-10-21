"""Mutation application (B07-T07.02): applied, not supported, not run and failed are different recorded results."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from test_palladion_runtime import mini_view, request, runtime

from benchmark.adapters.common import Condition, PublishedView
from benchmark.adapters.palladion import TABLE_FILE, PalladionArm
from benchmark.contracts import EvidenceStatus
from benchmark.fixtures.documents import Document
from benchmark.fixtures.manifest import build_records
from benchmark.fixtures.mutations import (
    MutationContext,
    MutationError,
    MutationInstance,
    Op,
    OpKind,
    instantiate,
    instantiate_all,
)
from benchmark.fixtures.world import World
from benchmark.mutations_apply import (
    Application,
    Outcome,
    PalladionTarget,
    RebuildTarget,
    apply_instance,
    expected_held,
    violations,
)


@pytest.fixture(scope="module")
def ctx(s_world: World, s_corpus: tuple[Document, ...], s_questions: Any) -> MutationContext:
    return MutationContext(s_world, s_corpus, s_questions, 7)


@pytest.fixture(scope="module")
def instances(ctx: MutationContext) -> dict[str, MutationInstance]:
    return {i.instance_id: i for i in instantiate_all(ctx)}


class Builds:
    """A rebuild callback that records every corpus it was asked to build from."""

    def __init__(self) -> None:
        self.corpora: list[tuple[Document, ...]] = []

    def __call__(self, corpus: tuple[Document, ...]) -> None:
        self.corpora.append(corpus)


def rebuild_target(ctx: MutationContext) -> tuple[RebuildTarget, Builds]:
    builds = Builds()
    return RebuildTarget("R2", ctx.corpus, builds), builds


# --------------------------------------------------------------------------- an arm that rebuilds its index


def test_a_corpus_mutation_is_applied_by_a_rebuild_and_the_arm_holds_what_the_patch_declares(
    ctx: MutationContext, instances: dict[str, MutationInstance]
) -> None:
    target, builds = rebuild_target(ctx)
    instance = instances["M01:base"]
    result = apply_instance(target, instance, ctx.corpus)
    added = next(op.document for op in instance.patch if op.document)
    assert added
    assert result.verified and result.applied == (OpKind.ADD_DOCUMENT,) and result.carried == ()
    assert len(builds.corpora) == 1 and builds.corpora[0][-1] == added and len(builds.corpora[0]) == len(ctx.corpus) + 1
    assert target.held()[added.doc_id] is True


def test_a_rebuild_target_restores_the_base_corpus_by_building_it_again(
    ctx: MutationContext, instances: dict[str, MutationInstance]
) -> None:
    target, builds = rebuild_target(ctx)
    apply_instance(target, instances["M01:base"], ctx.corpus)
    assert target.restore() == () and target.corpus == ctx.corpus
    assert len(builds.corpora) == 2 and builds.corpora[-1] == ctx.corpus


def test_a_precondition_is_applied_before_the_patch_and_both_leave_the_base_state(
    ctx: MutationContext, instances: dict[str, MutationInstance]
) -> None:
    target, _ = rebuild_target(ctx)
    instance = instances["MT04:base"]
    result = apply_instance(target, instance, ctx.corpus)
    assert result.verified and result.applied == (OpKind.SET_REGISTRY_STATE, OpKind.SET_REGISTRY_STATE)
    assert target.corpus == ctx.corpus, "withdrawn and then restored"
    assert expected_held(ctx.corpus, (*instance.precondition, *instance.patch)) == {
        instance.expectation.must_cite[0]: True
    }


def test_operations_that_live_in_the_request_are_carried_not_applied(
    ctx: MutationContext, instances: dict[str, MutationInstance]
) -> None:
    target, builds = rebuild_target(ctx)
    result = apply_instance(target, instances["M06:base"], ctx.corpus)
    assert result.verified and [op.kind for op in result.carried] == [OpKind.SET_QUERY]
    assert result.applied == (OpKind.ADD_DOCUMENT,) and len(builds.corpora) == 1
    only_request = apply_instance(target, instances["M17:base"], ctx.corpus)
    assert [op.kind for op in only_request.carried] == [OpKind.SET_QUERY] and only_request.applied == ()


@pytest.mark.parametrize(
    ("instance_id", "expected"),
    [
        ("M07:base", "no graph"),
        ("M08:base", "no entry can be dropped"),
        ("M11:base", "no live-state tool"),
        ("M13:base", "no conversation"),
        ("M15:base", "no graph"),
    ],
)
def test_a_mutation_the_arm_cannot_take_is_recorded_with_the_reason_and_nothing_is_applied(
    ctx: MutationContext, instances: dict[str, MutationInstance], instance_id: str, expected: str
) -> None:
    target, builds = rebuild_target(ctx)
    result = apply_instance(target, instances[instance_id], ctx.corpus)
    assert result.outcome is Outcome.FEATURE_NOT_SUPPORTED and not result.verified
    assert any(expected in reason for reason in result.reasons)
    assert builds.corpora == [] and target.corpus == ctx.corpus, "a refused mutation leaves the system untouched"


def test_an_instance_the_caller_could_not_try_is_not_run_and_never_a_pass(
    ctx: MutationContext, instances: dict[str, MutationInstance]
) -> None:
    target, builds = rebuild_target(ctx)
    result = apply_instance(target, instances["M01:base"], ctx.corpus, not_run="the arm is not built in this run")
    assert result.outcome is Outcome.NOT_RUN and result.reasons == ("the arm is not built in this run",)
    assert not result.verified and builds.corpora == []


class Lying:
    """A target that reports every document retrievable whatever it was told."""

    name = "liar"

    def unsupported(self, op: Op) -> str | None:
        return None

    def apply(self, ops: Sequence[Op]) -> None:
        return None

    def held(self) -> Mapping[str, bool]:
        return {}

    def restore(self) -> tuple[str, ...]:
        return ()


class Refusing(Lying):
    name = "refuser"

    def apply(self, ops: Sequence[Op]) -> None:
        raise MutationError("the system refused the change")


class Crashing(Lying):
    name = "crasher"

    def apply(self, ops: Sequence[Op]) -> None:
        raise ZeroDivisionError("a bug, not a recorded result")


def test_a_system_that_does_not_hold_what_the_patch_declares_is_listed_not_trusted(
    ctx: MutationContext, instances: dict[str, MutationInstance]
) -> None:
    result = apply_instance(Lying(), instances["M01:base"], ctx.corpus)
    assert result.outcome is Outcome.APPLIED and not result.verified
    assert len(result.mismatches) == 1 and "expected retrievable, holds None" in result.mismatches[0]


def test_a_refusal_is_a_failed_result_and_a_bug_is_not_swallowed(
    ctx: MutationContext, instances: dict[str, MutationInstance]
) -> None:
    result = apply_instance(Refusing(), instances["M01:base"], ctx.corpus)
    assert result.outcome is Outcome.FAILED and "the system refused the change" in result.reasons[0]
    with pytest.raises(ZeroDivisionError):
        apply_instance(Crashing(), instances["M01:base"], ctx.corpus)


# --------------------------------------------------------------------------- scoring what an answer did


def test_an_unauthorized_read_of_a_revoked_passage_is_counted(instances: dict[str, MutationInstance]) -> None:
    instance = instances["M09:base"]
    revoked = instance.expectation.must_not_cite[0]
    leaked = violations(instance, [revoked, "ART-other"], "ok", EvidenceStatus.SUPPORTED)
    clean = violations(instance, ["ART-other"], "ok", EvidenceStatus.SUPPORTED)
    assert leaked.cited_forbidden == (revoked,) and leaked.unauthorized_reads == 1
    assert clean.unauthorized_reads == 0 and clean.status_allowed is None
    clause = violations(instance, [f"{revoked}#4.2"], "ok", EvidenceStatus.SUPPORTED)
    assert clause.cited_forbidden == (revoked,), "a clause locator names its document"


def test_an_exposed_canary_and_a_disallowed_status_are_counted(instances: dict[str, MutationInstance]) -> None:
    instance = instances["M14:plain"]
    canary = instance.expectation.must_not_expose[0]
    shown = violations(instance, [], f"The reference is {canary.lower()}.", EvidenceStatus.SUPPORTED)
    assert shown.exposed == (canary,) and shown.unauthorized_reads == 1
    outage = instances["M11:base"]
    assert violations(outage, [], "x", EvidenceStatus.SUPPORTED).status_allowed is False
    assert violations(outage, [], "x", EvidenceStatus.VERIFICATION_UNAVAILABLE).status_allowed is True
    assert violations(instance, [], "x", EvidenceStatus.SUPPORTED).missing_citations == instance.expectation.must_cite


# --------------------------------------------------------------------------- Palladion, over HTTP


@pytest.fixture(scope="module")
def prepared(qdrant_server: str) -> Iterator[None]:
    runtime.prepare(reset=True)
    yield


def test_palladion_takes_an_upload_and_a_revoke_and_reports_the_rest_as_unsupported(
    prepared: None,
    ctx: MutationContext,
    instances: dict[str, MutationInstance],
    s_published: Path,
    tmp_path: Path,
) -> None:
    view = mini_view(PublishedView.load(s_published))
    with runtime.PalladionRuntime() as server:
        arm = PalladionArm(view, server.base_url, runtime.load_tokens(), condition=Condition.C1)
        try:
            arm.load_corpus(tmp_path / TABLE_FILE)
            principal = view.identity.principals[0].principal_id

            def record_for(doc: Document) -> Any:
                return build_records(ctx.world, [doc], 7)[0]

            target = PalladionTarget("E4", arm, record_for)
            base = tuple(Document_for(view, r.doc_id, ctx) for r in view.records)

            # an upload: the added memo is approved and then reachable by its own title
            instance = instances["M14:plain"]
            added = next(op.document for op in instance.patch if op.document)
            assert added
            result = apply_instance(target, instance, base)
            assert result.verified and result.applied == (OpKind.ADD_DOCUMENT,)
            hits = arm.retrieve(request(added.title, principal, 12))
            assert any(h.source_document_id == added.doc_id for h in hits)

            # restoring revokes what the target added, so the next case starts from the base state
            assert target.restore() == ()
            assert arm.held_states()[added.doc_id] == "REVOKED"
            assert not any(
                h.source_document_id == added.doc_id for h in arm.retrieve(request(added.title, principal, 12))
            )

            # a revoke: an approved document is reachable, then not, and the arm's record says revoked
            revoked = next(r for r in view.records if arm.held_states().get(r.doc_id) == "APPROVED")
            probe = " ".join(w for w in revoked.title.split() if w.isalpha())
            assert any(h.source_document_id == revoked.doc_id for h in arm.retrieve(request(probe, principal, 12)))
            withdraw = MutationInstance(
                "M18", "base", instance.base_question_id, (),
                (Op(OpKind.SET_REGISTRY_STATE, revoked.doc_id, "withdrawn"),),
                instance.expectation,
            )  # fmt: skip
            second = apply_instance(target, withdraw, base)
            assert second.verified and arm.held_states()[revoked.doc_id] == "REVOKED"
            assert target.restore() == (f"{revoked.doc_id} revoked and not restorable",)
            assert not any(h.source_document_id == revoked.doc_id for h in arm.retrieve(request(probe, principal, 12)))

            # what Palladion cannot carry is a recorded result, and calls nothing
            states_before = arm.held_states()
            reasons: dict[str, Application] = {}
            for instance_id in ("M07:base", "M08:base", "M09:base", "M12:base", "MT04:base", "MT07:base"):
                reasons[instance_id] = apply_instance(target, instances[instance_id], base)
            assert {r.outcome for r in reasons.values()} == {Outcome.FEATURE_NOT_SUPPORTED}
            assert any("graph is off" in x for x in reasons["M07:base"].reasons)
            assert any("per-role" in x for x in reasons["M09:base"].reasons)
            assert any("clock" in x for x in reasons["M12:base"].reasons)
            assert any("approves a revoked" in x for x in reasons["MT04:base"].reasons)
            assert arm.held_states() == states_before
            with pytest.raises(Exception, match="already in Palladion"):
                arm.publish(record_for(added), added.text)
        finally:
            arm.close()


def Document_for(view: PublishedView, doc_id: str, ctx: MutationContext) -> Document:
    """The corpus document a published record stands for (the base the held states are compared with)."""
    return ctx.document(doc_id)


def test_instantiating_a_missing_mutation_still_refuses(ctx: MutationContext) -> None:
    with pytest.raises(MutationError):
        instantiate(ctx, "M99")
    assert replace(Application("x", "y", Outcome.APPLIED), mismatches=("a",)).verified is False


def test_a_cited_clause_counts_as_its_document_for_the_citations_a_case_requires(
    instances: dict[str, MutationInstance],
) -> None:
    instance = instances["M01:base"]
    cite = instance.expectation.must_cite[0]
    assert violations(instance, [f"{cite}#1.1"], "ok", EvidenceStatus.SUPPORTED).missing_citations == ()
