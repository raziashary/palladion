import asyncio
from datetime import timedelta

import pytest
from pydantic import ValidationError

from evidence_agent.core.errors import PermissionDenied, ResourceConflict
from evidence_agent.core.models import TimeBasis
from evidence_agent.live.contracts import LookupRequest, Snapshot
from evidence_agent.live.gateway import LiveGateway, read_scope
from evidence_agent.live.mock import MockAdapter
from evidence_agent.policy.registry import PolicySpec
from evidence_agent.policy.temporal import TemporalResolver


def specs(p03):
    return [PolicySpec.model_validate_json(row[0]) for row in p03.registry.database.connection.execute(
        "SELECT decision_table_json FROM policy_versions WHERE family_id='DEMO.REVERSAL.CHECK' ORDER BY valid_from")]


def evidence(p03, when="2026-08-15T10:20:00+00:00"):
    snapshot = Snapshot(status="OK", data={"transaction_id": "TX-DEMO-102", "state": "FAILED",
                                          "transaction_occurred_at": when})
    service = LiveGateway(p03.registry, MockAdapter({("get_transaction_status", "TX-DEMO-102"): (snapshot,)}),
                          p03.config, clock=lambda: p03.now)
    result = asyncio.run(service.lookup(p03.reader, LookupRequest(operation="get_transaction_status",
                             case_id="case-42", target_id="TX-DEMO-102")))
    return (result.lookup_id,)


def resolver(p03):
    return TemporalResolver(p03.policies, clock=lambda: p03.now)


@pytest.mark.parametrize("instant,expected", [
    ("2025-01-01T00:00:00+00:00", "demo-reversal-2025-a"),
    ("2026-06-30T23:59:59+00:00", "demo-reversal-2025-a"),
    ("2026-07-01T00:00:00+00:00", "demo-reversal-2026-b"),
    ("2024-12-31T23:59:59+00:00", None)])
def test_event_time_and_half_open_boundaries(p03, instant, expected):
    selected = resolver(p03).resolve(p03.reader, "case-42", "DEMO.REVERSAL.CHECK", evidence(p03, instant))
    assert (selected.spec.version_id if selected.spec else None) == expected
    assert selected.status == ("SELECTED" if expected else "NO_APPLICABLE_POLICY")


def test_all_four_bases_have_real_backend_producers(p03):
    event = resolver(p03).resolve(p03.reader, "case-42", "DEMO.REVERSAL.CHECK",
                                 evidence(p03, "2025-06-20T11:30:00+00:00"))
    handling = resolver(p03).resolve(p03.reader, "case-42", "DEMO.HANDLING")
    assert event.spec.version_id == "demo-reversal-2025-a"
    assert handling.spec.version_id == "demo-handling-2026-a" and handling.as_of == p03.now
    base = specs(p03)[1]
    for basis, source, domain in [(TimeBasis.CASE_OPENED_AT, "case_event.opened_at", None),
                                 (TimeBasis.DOMAIN_EVENT_AT, "verified_case.domain_event_at", "dispute_submitted")]:
        spec = base.model_copy(update={"version_id": basis.value, "family_id": basis.value,
                                      "time_basis": basis, "timestamp_source": source, "domain_event": domain})
        p03.policies.register(p03.admin, spec)
        selected = resolver(p03).resolve(p03.reader, "case-42", basis.value)
        assert selected.status == "SELECTED"
        if domain:
            expected = read_scope(p03.registry, p03.reader, "case-42").domain_events[domain]
        else:
            from datetime import datetime
            expected = datetime.fromisoformat(p03.registry.database.connection.execute(
                "SELECT created_at FROM cases WHERE case_id='case-42'").fetchone()[0])
        assert selected.as_of == expected


def test_unknown_untrusted_naive_and_mismatched_time_fail(p03):
    assert resolver(p03).resolve(p03.reader, "case-42", "DEMO.REVERSAL.CHECK").status == "MISSING_TIME_INPUT"
    with pytest.raises(PermissionDenied):
        resolver(p03).resolve(p03.reader, "case-42", "DEMO.REVERSAL.CHECK", ("caller-verified",))
    base = specs(p03)[1].model_dump()
    base["timestamp_source"] = "user_report.transaction_occurred_at"
    with pytest.raises(ValidationError):
        PolicySpec.model_validate(base)
    base = specs(p03)[1].model_dump()
    base["valid_from"] = p03.now.replace(tzinfo=None)
    with pytest.raises(ValidationError):
        PolicySpec.model_validate(base)
    spec = specs(p03)[1].model_copy(update={"version_id": "domain-missing", "family_id": "domain-missing",
        "time_basis": TimeBasis.DOMAIN_EVENT_AT, "timestamp_source": "verified_case.domain_event_at",
        "domain_event": "unknown_event"})
    p03.policies.register(p03.admin, spec)
    assert resolver(p03).resolve(p03.reader, "case-42", "domain-missing").status == "MISSING_TIME_INPUT"


def test_overlap_explicit_scoped_precedence_and_knowledge_cutoff(p03):
    base = specs(p03)[1]
    newer = base.model_copy(update={"version_id": "overlap-newer-name"})
    p03.policies.register(p03.admin, newer)
    ids = evidence(p03)
    assert resolver(p03).resolve(p03.reader, "case-42", base.family_id, ids).status == "POLICY_CONFLICT"
    p03.policies.supersede(p03.admin, base.version_id, newer.version_id, case_id="case-42",
                          valid_from=base.valid_from, reason="fictional approved correction")
    assert resolver(p03).resolve(p03.reader, "case-42", base.family_id, ids).spec.version_id == newer.version_id
    service = LiveGateway(p03.registry, MockAdapter({("get_transaction_status", "TX-DEMO-143"):
        (Snapshot(status="OK", data={"transaction_id": "TX-DEMO-143", "state": "FAILED",
                                   "transaction_occurred_at": "2026-08-15T10:20:00Z"}),)}),
        p03.config, clock=lambda: p03.now)
    other = asyncio.run(service.lookup(p03.uploader, LookupRequest(operation="get_transaction_status",
                                case_id="case-43", target_id="TX-DEMO-143")))
    assert resolver(p03).resolve(p03.uploader, "case-43", base.family_id,
                                 (other.lookup_id,)).status == "POLICY_CONFLICT"
    cutoff = p03.registered+timedelta(days=1)
    historical = resolver(p03).resolve(p03.admin, "case-42", base.family_id, ids, knowledge_cutoff=cutoff)
    assert historical.spec.version_id == base.version_id
    with pytest.raises(PermissionDenied):
        resolver(p03).resolve(p03.reader, "case-42", base.family_id, ids, knowledge_cutoff=cutoff)
    # A cycle cannot turn either policy into an arbitrary winner.
    p03.policies.supersede(p03.admin, newer.version_id, base.version_id, case_id="case-42",
                          valid_from=base.valid_from, reason="deliberate synthetic cycle")
    assert resolver(p03).resolve(p03.reader, "case-42", base.family_id, ids).status == "POLICY_CONFLICT"


def test_current_revocation_and_authorized_prior_audit_remain_distinct(p03, monkeypatch):
    base = specs(p03)[1]
    ids = evidence(p03)
    cutoff = p03.registered+timedelta(days=1)
    p03.policies.revoke(p03.admin, base.version_id)
    assert resolver(p03).resolve(p03.reader, "case-42", base.family_id, ids).status == "NO_APPLICABLE_POLICY"
    assert resolver(p03).resolve(p03.admin, "case-42", base.family_id, ids,
                                 knowledge_cutoff=cutoff).spec.version_id == base.version_id
    monkeypatch.setattr("evidence_agent.storage.registry.utc_now", lambda: p03.now.isoformat())
    p03.registry.revoke_source(p03.admin, base.clauses[0].revision_id)
    assert resolver(p03).resolve(p03.admin, "case-42", base.family_id, ids,
                                 knowledge_cutoff=cutoff).spec.version_id == base.version_id
    assert resolver(p03).resolve(p03.admin, "case-42", base.family_id, ids).spec is None
    import hashlib
    raw = p03.policies.read_clause(p03.admin, base.clauses[0], knowledge_cutoff=cutoff)
    assert hashlib.sha256(raw.encode()).hexdigest() == base.clauses[0].sha256
    with pytest.raises(PermissionDenied):
        p03.policies.read_clause(p03.reader, base.clauses[0], knowledge_cutoff=cutoff)
    with pytest.raises(PermissionDenied):
        p03.policies.read_clause(p03.admin, base.clauses[0])


def test_mixed_time_bases_are_conflict_not_revision_ranking(p03):
    base = specs(p03)[1]
    p03.policies.register(p03.admin, base.model_copy(update={"version_id": "mixed", "time_basis": TimeBasis.EVALUATION_AT,
        "timestamp_source": "server_clock.evaluation_time"}))
    assert resolver(p03).resolve(p03.reader, "case-42", base.family_id, evidence(p03)).status == "POLICY_CONFLICT"
    with pytest.raises(ResourceConflict):
        p03.policies.supersede(p03.admin, base.version_id, "mixed", case_id="case-42",
                              valid_from=base.valid_from, reason="undefined migration")


def test_unapproved_or_missing_or_restricted_source_cannot_register(p03):
    base = specs(p03)[1]
    from evidence_agent.core.fixtures import load_fixtures
    from evidence_agent.policy.registry import Clause
    bundle = load_fixtures(p03.app)
    draft = next(source for source in bundle.sources if source.source_id == "MEMO-DRAFT-1")
    span = next(iter(draft.clauses.values()))
    clause = Clause(revision_id=p03.revisions[draft.source_id], section_id=span.clause_id,
                    start_byte=span.span_start, end_byte=span.span_end, sha256=span.text_sha256)
    for invalid in (clause, clause.model_copy(update={"revision_id": "missing-source"})):
        with pytest.raises(PermissionDenied):
            p03.policies.register(p03.admin, base.model_copy(update={"version_id": "unapproved",
                "clauses": (invalid,), "rules": ()}))
    with pytest.raises(PermissionDenied):
        p03.policies.register(p03.uploader, base.model_copy(update={"version_id": "not-admin"}))
    with pytest.raises(PermissionDenied):
        p03.policies.register(p03.admin, base.model_copy(update={"version_id": "self", "author_id": "admin-a"}))
    p03.registry.revoke_source(p03.admin, base.clauses[0].revision_id)
    with pytest.raises(PermissionDenied):
        p03.policies.register(p03.admin, base.model_copy(update={"version_id": "revoked"}))
    limited = p03.registry.access.authenticate("reader-a-limited")
    assert resolver(p03).resolve(limited, "case-42", base.family_id, evidence(p03)).spec is None


def test_concurrent_overlap_registration_is_visible_to_selection(p03):
    from concurrent.futures import ThreadPoolExecutor

    from evidence_agent.policy.registry import PolicyRegistry
    from evidence_agent.storage.originals import OriginalStore
    from evidence_agent.storage.registry import Registry
    from evidence_agent.storage.sqlite import Database

    base = specs(p03)[1]
    path = p03.registry.database.path
    originals = p03.registry.originals.root

    def register(identifier):
        with Database(path) as database:
            registry = Registry(database, OriginalStore(originals))
            policies = PolicyRegistry(registry, clock=lambda: p03.now)
            policies.register(registry.access.authenticate("admin-a"),
                              base.model_copy(update={"version_id": identifier}))
    with ThreadPoolExecutor(max_workers=2) as workers:
        list(workers.map(register, ("concurrent-a", "concurrent-b")))
    result = resolver(p03).resolve(p03.reader, "case-42", base.family_id, evidence(p03))
    assert result.status == "POLICY_CONFLICT"
