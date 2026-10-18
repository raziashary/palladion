"""Bounded allowlisted predicate interpreter. Never executes source expressions."""
from __future__ import annotations

import json
import math
import uuid
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

from evidence_agent.core.errors import PermissionDenied, ResourceConflict
from evidence_agent.core.models import (
    LiveOperationStatus,
    PolicyDecision,
    PolicyDecisionStatus,
    Principal,
)
from evidence_agent.live.gateway import iso, read_observation, read_scope, utc_clock
from evidence_agent.policy.registry import PolicyRegistry
from evidence_agent.policy.temporal import TemporalResolver

_COMPARISONS = {"eq", "in", "lt", "lte", "gt", "gte"}


def validate_predicate(predicate: dict[str, Any], fields: set[str]) -> None:
    work = [0]

    def visit(node: Any, depth: int) -> None:
        work[0] += 1
        if depth > 12 or work[0] > 128 or not isinstance(node, dict):
            raise ValueError("Predicate work/depth/schema bound exceeded")
        if len(node) == 1 and next(iter(node)) in {"all", "any", "not"}:
            key = next(iter(node))
            if key == "not":
                visit(node[key], depth+1)
            else:
                if not isinstance(node[key], list) or not 1 <= len(node[key]) <= 32:
                    raise ValueError("Bounded nonempty predicate list required")
                for child in node[key]:
                    visit(child, depth+1)
            return
        if (set(node) != {"field", "operator", "value"} or not isinstance(node["field"], str) or node["field"] not in fields or
                not isinstance(node["operator"], str) or node["operator"] not in _COMPARISONS):
            raise ValueError("Unknown predicate field/operator/shape")
        value = node["value"]
        values = value if node["operator"] == "in" else [value]
        if not isinstance(values, list) or not 1 <= len(values) <= 32 or any(
                type(item) not in (str, int, float, bool) or isinstance(item, str) and len(item) > 200 or
                isinstance(item, float) and not math.isfinite(item)
                for item in values):
            raise ValueError("Only bounded literal predicate values allowed")
    visit(predicate, 0)


def evaluate_predicate(predicate: dict[str, Any], facts: dict[str, Any]) -> bool:
    validate_predicate(predicate, set(facts))

    def evaluate(node: dict[str, Any]) -> bool:
        if "all" in node:
            return all(evaluate(child) for child in node["all"])
        if "any" in node:
            return any(evaluate(child) for child in node["any"])
        if "not" in node:
            return not evaluate(node["not"])
        actual, expected, operator = facts[node["field"]], node["value"], node["operator"]
        if operator == "in":
            return any(type(actual) is type(value) and actual == value for value in expected)
        if type(actual) is not type(expected):
            raise ValueError("Predicate operands have incompatible types")
        if operator == "eq":
            return bool(actual == expected)
        if type(actual) not in (int, float, str):
            raise ValueError("Ordered operands required")
        if operator == "lt":
            return bool(actual < expected)
        if operator == "lte":
            return bool(actual <= expected)
        if operator == "gt":
            return bool(actual > expected)
        return bool(actual >= expected)
    return evaluate(predicate)


class PolicyEngine:
    """Facts are resolved from gateway event IDs, never caller-owned fact values."""
    def __init__(self, policies: PolicyRegistry, *, clock: Callable[[], datetime] = utc_clock) -> None:
        self.policies, self.registry, self.clock = policies, policies.registry, clock
        self.temporal = TemporalResolver(policies, clock=clock)

    def evaluate(self, principal: Principal, case_id: str, family_id: str,
                  evidence_ids: Sequence[str] = (), *, knowledge_cutoff: datetime | None = None,
                  evaluation_time: datetime | None = None) -> PolicyDecision:
        read_scope(self.registry, principal, case_id)
        if len(evidence_ids) > 32 or len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("Bounded unique evidence IDs required")
        if knowledge_cutoff is not None:
            self.registry.access.authorize(principal, tenant_id=principal.tenant_id,
                                            role="admin", grant="document:approve")
        if evaluation_time is not None and knowledge_cutoff is None:
            raise PermissionDenied
        now = self.clock()
        audit_id = "policy_"+uuid.uuid4().hex
        with self.registry.database.transaction() as connection:
            # Same transaction covers metadata, source/fact reads, execution and trace publication.
            try:
                selected = self.temporal.resolve(principal, case_id, family_id, evidence_ids,
                                                knowledge_cutoff=knowledge_cutoff, evaluation_time=evaluation_time)
                observations = [read_observation(self.registry, principal, case_id, identifier)
                                for identifier in evidence_ids]
            except PermissionDenied:
                # Invalid evidence IDs do not confirm another case's record existence.
                result = PolicyDecision(status=PolicyDecisionStatus.UNVERIFIED_INPUT,
                    policy_family_id=family_id, audit_id=audit_id, evaluated_at=now)
            else:
                spec = selected.spec
                common: dict[str, Any] = dict(policy_family_id=family_id, audit_id=audit_id, evaluated_at=now,
                    temporal_input_refs=tuple(observation.lookup_id for observation in observations),
                    evaluation_mode="historical_audit" if knowledge_cutoff else "current",
                    knowledge_cutoff=knowledge_cutoff, selection_trace=selected.trace,
                    version_id=spec.version_id if spec else None,
                    time_basis=spec.time_basis if spec else None, as_of=selected.as_of,
                    source_clauses=selected.sources,
                    required_fields=tuple(f.name for f in spec.required_facts) if spec else ())
                if spec is None:
                    status = (PolicyDecisionStatus.INCOMPLETE_INPUT if selected.status == "MISSING_TIME_INPUT"
                              else PolicyDecisionStatus.UNVERIFIED_INPUT if selected.status == "UNVERIFIED_TIME_SOURCE"
                              else PolicyDecisionStatus(selected.status))
                    result = PolicyDecision(status=status,
                        missing_fields=("time_input",) if selected.status == "MISSING_TIME_INPUT" else (), **common)
                else:
                    facts: dict[str, Any] = {}
                    refs: list[str] = []
                    missing = []
                    invalid = unavailable = False
                    for requirement in spec.required_facts:
                        matches = [o for o in observations if o.operation_id == requirement.operation]
                        if not matches:
                            missing.append(requirement.name)
                            continue
                        values = []
                        for observation in matches:
                            if observation.operation_status is not LiveOperationStatus.OK:
                                unavailable = True
                                continue
                            age = (now-observation.observed_at).total_seconds()
                            if (not 0 <= age <= requirement.max_age_seconds or
                                observation.data_as_of is not None and not 0 <= (
                                    now-observation.data_as_of).total_seconds() <= requirement.max_age_seconds):
                                invalid = True
                                continue
                            value = observation.data.get(requirement.field)
                            valid_type = {"enum": str, "string": str, "bool": bool, "int": int, "float": float}[requirement.type]
                            if type(value) is not valid_type or (requirement.type == "enum" and value not in requirement.allowed_values):
                                invalid = True
                                continue
                            values.append(value)
                            refs.append(observation.lookup_id)
                        if values:
                            if any(v != values[0] for v in values):
                                invalid = True
                            facts[requirement.name] = values[0]
                        else:
                            missing.append(requirement.name)
                    status = (PolicyDecisionStatus.UNVERIFIED_INPUT if invalid else
                              PolicyDecisionStatus.VERIFICATION_UNAVAILABLE if unavailable else
                              PolicyDecisionStatus.INCOMPLETE_INPUT if missing else PolicyDecisionStatus.DETERMINED)
                    matched, trace = [], []
                    outcome = None
                    if status is PolicyDecisionStatus.DETERMINED:
                        try:
                            for rule in spec.rules:
                                hit = evaluate_predicate(rule.predicate, facts)
                                trace.append(rule.id+ (":MATCH" if hit else ":NO_MATCH"))
                                if hit:
                                    matched.append(rule)
                        except ValueError:
                            status = PolicyDecisionStatus.UNVERIFIED_INPUT
                        else:
                            outcomes = {r.outcome for r in matched}
                            if len(outcomes) > 1:
                                status = PolicyDecisionStatus.POLICY_CONFLICT
                            else:
                                outcome = next(iter(outcomes)) if outcomes else spec.default_outcome
                                if outcome == "INCOMPLETE_INPUT":
                                    status = PolicyDecisionStatus.INCOMPLETE_INPUT
                            if not trace:
                                trace.append("DEFAULT_OUTCOME_EXECUTED")
                    result = PolicyDecision(status=status, outcome=outcome,
                        normalized_inputs=facts, matched_rules=tuple(r.id for r in matched),
                        rule_trace=tuple(trace), input_evidence_refs=tuple(dict.fromkeys(refs)),
                        missing_fields=tuple(missing), **common)
            connection.execute("INSERT INTO case_events VALUES(?,?,?,?,?,?,?)",
                (audit_id, principal.tenant_id, case_id, principal.principal_id,
                 "POLICY_DECISION", result.model_dump_json(), iso(now)))
            connection.execute("INSERT INTO audit_events VALUES(?,?,?,?,?,?,?)",
                ("audit_"+uuid.uuid4().hex, audit_id, principal.principal_id, principal.tenant_id,
                 "POLICY_EVALUATED", json.dumps({"status": result.status.value,
                 "version_id": result.version_id, "mode": result.evaluation_mode}), iso(now)))
            return result

    def replay(self, principal: Principal, case_id: str, audit_id: str) -> PolicyDecision:
        """Authorized domain reader; stored trace is historical, not fresh permission to act."""
        read_scope(self.registry, principal, case_id)
        row = self.registry.database.connection.execute(
            "SELECT payload_json FROM case_events WHERE event_id=? AND tenant_id=? AND case_id=? "
            "AND event_kind='POLICY_DECISION'", (audit_id, principal.tenant_id, case_id)).fetchone()
        if row is None:
            raise PermissionDenied
        decision = PolicyDecision.model_validate_json(row[0])
        if decision.evaluation_mode == "historical_audit":
            self.registry.access.authorize(principal, tenant_id=principal.tenant_id,
                                            role="admin", grant="document:approve")
        for evidence_id in decision.temporal_input_refs:
            read_observation(self.registry, principal, case_id, evidence_id)
        if decision.version_id:
            record = self.registry.database.connection.execute(
                "SELECT decision_table_json FROM policy_versions WHERE tenant_id=? AND version_id=?",
                (principal.tenant_id, decision.version_id)).fetchone()
            if record is None:
                raise ResourceConflict
            from evidence_agent.policy.registry import PolicySpec
            spec = PolicySpec.model_validate_json(record[0])
            for clause in spec.clauses:
                self.policies.clause(principal, clause, knowledge_cutoff=decision.knowledge_cutoff)
            if decision.status is PolicyDecisionStatus.DETERMINED:
                if set(decision.normalized_inputs) != {f.name for f in spec.required_facts}:
                    raise ResourceConflict
                replayed = tuple(rule for rule in spec.rules
                                 if evaluate_predicate(rule.predicate, decision.normalized_inputs))
                outcomes = {rule.outcome for rule in replayed}
                expected = next(iter(outcomes)) if len(outcomes) == 1 else spec.default_outcome
                if (len(outcomes) > 1 or decision.matched_rules != tuple(r.id for r in replayed) or
                        expected != decision.outcome):
                    raise ResourceConflict
                for evidence_id in decision.input_evidence_refs:
                    read_observation(self.registry, principal, case_id, evidence_id)
        return decision
