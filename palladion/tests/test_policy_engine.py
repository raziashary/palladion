import asyncio
from datetime import timedelta

import pytest

from evidence_agent.core.errors import PermissionDenied
from evidence_agent.core.models import PolicyDecision, PolicyDecisionStatus
from evidence_agent.live.contracts import LookupRequest, Snapshot
from evidence_agent.live.gateway import LiveGateway
from evidence_agent.live.mock import MockAdapter
from evidence_agent.policy.engine import PolicyEngine, evaluate_predicate, validate_predicate
from evidence_agent.policy.registry import PolicySpec, Rule


def engine(p03, clock=None):
    return PolicyEngine(p03.policies, clock=clock or (lambda: p03.now))


def observations(p03, *, settlement="UNSETTLED", failed=False):
    snapshots = {
        ("get_transaction_status", "TX-DEMO-102"): (Snapshot(status="OK", data={
            "transaction_id": "TX-DEMO-102", "state": "FAILED",
            "transaction_occurred_at": "2026-08-15T10:20:00Z"}),),
        ("get_settlement_status", "SET-DEMO-102"): (
            Snapshot(status="TIMEOUT") if failed else Snapshot(status="OK", data={
                "settlement_id": "SET-DEMO-102", "settlement_state": settlement}),)}
    service = LiveGateway(p03.registry, MockAdapter(snapshots), p03.config, clock=lambda: p03.now)

    async def run():
        return [await service.lookup(p03.reader, LookupRequest(operation=op, case_id="case-42", target_id=target))
                for op, target in snapshots]
    return asyncio.run(run())


def test_missing_is_not_false_then_real_observations_drive_decision_and_replay(p03):
    transaction, settlement = observations(p03)
    partial = engine(p03).evaluate(p03.reader, "case-42", "DEMO.REVERSAL.CHECK", (transaction.lookup_id,))
    assert partial.status is PolicyDecisionStatus.INCOMPLETE_INPUT
    assert partial.missing_fields == ("settlement_state",) and partial.outcome is None
    ids = (transaction.lookup_id, settlement.lookup_id)
    result = engine(p03).evaluate(p03.reader, "case-42", "DEMO.REVERSAL.CHECK", ids)
    assert result.status is PolicyDecisionStatus.DETERMINED
    assert result.outcome == "FOLLOW_INVESTIGATION_SOP"
    assert result.normalized_inputs == {"transaction_state": "FAILED", "settlement_state": "UNSETTLED"}
    assert result.input_evidence_refs == ids and result.selection_trace and result.source_clauses
    assert engine(p03).replay(p03.reader, "case-42", result.audit_id) == result
    with pytest.raises(PermissionDenied):
        engine(p03).replay(p03.uploader, "case-43", result.audit_id)


def test_pending_exception_and_unavailable_settlement_cannot_grant_outcome(p03):
    ids = tuple(o.lookup_id for o in observations(p03, settlement="PENDING"))
    result = engine(p03).evaluate(p03.reader, "case-42", "DEMO.REVERSAL.CHECK", ids)
    assert result.status is PolicyDecisionStatus.INCOMPLETE_INPUT
    assert result.matched_rules == ("settlement-not-confirmed",)
    ids = tuple(o.lookup_id for o in observations(p03, failed=True))
    result = engine(p03).evaluate(p03.reader, "case-42", "DEMO.REVERSAL.CHECK", ids)
    assert result.status is PolicyDecisionStatus.VERIFICATION_UNAVAILABLE and result.outcome is None


def test_unverified_and_stale_evidence_are_not_authority(p03):
    result = engine(p03).evaluate(p03.reader, "case-42", "DEMO.REVERSAL.CHECK", ("caller-says-verified",))
    assert result.status is PolicyDecisionStatus.UNVERIFIED_INPUT
    ids = tuple(o.lookup_id for o in observations(p03))
    stale = engine(p03, lambda: p03.now+timedelta(seconds=301)).evaluate(
        p03.reader, "case-42", "DEMO.REVERSAL.CHECK", ids)
    assert stale.status is PolicyDecisionStatus.UNVERIFIED_INPUT
    with pytest.raises(TypeError):
        engine(p03).evaluate(p03.reader, "case-42", "DEMO.REVERSAL.CHECK", facts={"verified": True})


def test_zero_input_policy_has_real_outcome_without_fake_evidence(p03):
    result = engine(p03).evaluate(p03.reader, "case-42", "DEMO.HANDLING")
    assert result.status is PolicyDecisionStatus.DETERMINED
    assert result.outcome == "FOLLOW_CURRENT_HANDLING_SOP"
    assert result.required_fields == result.input_evidence_refs == ()
    assert result.normalized_inputs == {} and result.rule_trace == ("DEFAULT_OUTCOME_EXECUTED",)
    assert PolicyDecision.model_validate_json(result.model_dump_json()) == result


def test_unknown_policy_and_wrong_scope_are_distinct(p03):
    assert engine(p03).evaluate(p03.reader, "case-42", "UNKNOWN").status is PolicyDecisionStatus.NO_APPLICABLE_POLICY
    base = PolicySpec.model_validate_json(p03.registry.database.connection.execute(
        "SELECT decision_table_json FROM policy_versions WHERE version_id='demo-handling-2026-a'").fetchone()[0])
    p03.policies.register(p03.admin, base.model_copy(update={"version_id": "other-product", "family_id": "OTHER",
                                                          "product": "OTHER_PRODUCT"}))
    assert engine(p03).evaluate(p03.reader, "case-42", "OTHER").status is PolicyDecisionStatus.NOT_APPLICABLE


def test_legacy_policy_payload_remains_readable(p03):
    result = engine(p03).evaluate(p03.reader, "case-42", "DEMO.REVERSAL.CHECK",
                                  tuple(o.lookup_id for o in observations(p03)))
    old = result.model_dump(mode="json", exclude={"outcome", "normalized_inputs", "required_fields",
        "selection_trace", "evaluation_mode", "knowledge_cutoff", "evaluated_at"})
    parsed = PolicyDecision.model_validate_json(__import__("json").dumps(old))
    assert parsed.status is PolicyDecisionStatus.DETERMINED and parsed.outcome is None


def test_conflicting_rows_no_priority_by_order_or_name(p03):
    base = PolicySpec.model_validate_json(p03.registry.database.connection.execute(
        "SELECT decision_table_json FROM policy_versions WHERE version_id='demo-reversal-2026-b'").fetchone()[0])
    first = base.rules[0]
    conflict = Rule(id="conflicting", predicate=first.predicate, outcome="NO_DECISION_REQUIRES_REVIEW",
                    clause=first.clause)
    p03.policies.register(p03.admin, base.model_copy(update={"version_id": "conflict-rows", "family_id": "ROWS",
                                                          "rules": (first, conflict)}))
    result = engine(p03).evaluate(p03.reader, "case-42", "ROWS", tuple(o.lookup_id for o in observations(p03)))
    assert result.status is PolicyDecisionStatus.POLICY_CONFLICT and result.outcome is None


@pytest.mark.parametrize("operator,expected,truth", [("eq", 2, True), ("in", [1, 2], True),
    ("lt", 3, True), ("lte", 2, True), ("gt", 3, False), ("gte", 2, True)])
def test_allowlisted_comparisons_and_boolean_composition(operator, expected, truth):
    leaf = {"field": "n", "operator": operator, "value": expected}
    assert evaluate_predicate(leaf, {"n": 2}) is truth
    assert evaluate_predicate({"not": leaf}, {"n": 2}) is not truth
    assert evaluate_predicate({"all": [leaf, {"any": [leaf]}]}, {"n": 2}) is truth


@pytest.mark.parametrize("node", [{"field": "missing", "operator": "eq", "value": 1},
    {"field": "n", "operator": "eval", "value": "__import__('os')"}, {"sql": "select 1"},
    {"any": []}, {"field": "n", "operator": "eq", "value": float("nan")},
    {"field": "n", "operator": "in", "value": list(range(33))}])
def test_invalid_ast_rejected_before_execution(node):
    with pytest.raises(ValueError):
        validate_predicate(node, {"n"})


def test_depth_work_missing_and_bool_int_coercion_are_rejected():
    deep = {"field": "n", "operator": "eq", "value": 2}
    for _ in range(14):
        deep = {"not": deep}
    with pytest.raises(ValueError):
        validate_predicate(deep, {"n"})
    leaf = {"field": "n", "operator": "eq", "value": 2}
    with pytest.raises(ValueError):
        validate_predicate({"all": [{"all": [leaf]*32}]*5}, {"n"})
    with pytest.raises(ValueError):
        evaluate_predicate(leaf, {})
    with pytest.raises(ValueError):
        evaluate_predicate(leaf, {"n": True})


def test_audit_mode_needs_admin_and_does_not_become_current_authority(p03):
    with pytest.raises(PermissionDenied):
        engine(p03).evaluate(p03.reader, "case-42", "DEMO.HANDLING",
                             knowledge_cutoff=p03.registered+timedelta(days=1))
    result = engine(p03).evaluate(p03.admin, "case-42", "DEMO.HANDLING",
                                  knowledge_cutoff=p03.registered+timedelta(days=1))
    assert result.evaluation_mode == "historical_audit"
    assert engine(p03).replay(p03.admin, "case-42", result.audit_id) == result
    with pytest.raises(PermissionDenied):
        engine(p03).replay(p03.reader, "case-42", result.audit_id)
    earlier = p03.now-timedelta(hours=1)
    with pytest.raises(PermissionDenied):
        engine(p03).evaluate(p03.reader, "case-42", "DEMO.HANDLING", evaluation_time=earlier)
    simulated = engine(p03).evaluate(p03.admin, "case-42", "DEMO.HANDLING",
        knowledge_cutoff=p03.registered+timedelta(days=1), evaluation_time=earlier)
    assert simulated.as_of == earlier and simulated.evaluation_mode == "historical_audit"
    assert simulated.evaluated_at == p03.now


def test_reopen_reader_reexecutes_stored_trace_and_source_revocation_blocks_current_replay(p03):
    from evidence_agent.policy.registry import PolicyRegistry
    from evidence_agent.storage.originals import OriginalStore
    from evidence_agent.storage.registry import Registry
    from evidence_agent.storage.sqlite import Database

    result = engine(p03).evaluate(p03.reader, "case-42", "DEMO.REVERSAL.CHECK",
                                  tuple(o.lookup_id for o in observations(p03)))
    with Database(p03.registry.database.path) as database:
        registry = Registry(database, OriginalStore(p03.registry.originals.root))
        reader = registry.access.authenticate("reader-a")
        reopened = PolicyEngine(PolicyRegistry(registry), clock=lambda: p03.now)
        assert reopened.replay(reader, "case-42", result.audit_id) == result
    p03.registry.revoke_source(p03.admin, result.source_clauses[0].revision_id)
    with pytest.raises(PermissionDenied):
        engine(p03).replay(p03.reader, "case-42", result.audit_id)
