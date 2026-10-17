"""Offline P01 entry point: real registry/access/original readers, temporary state only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable

from evidence_agent.core.errors import PermissionDenied
from evidence_agent.core.fixtures import load_fixtures
from evidence_agent.settings import load_settings
from evidence_agent.storage.originals import OriginalStore
from evidence_agent.storage.registry import Registry
from evidence_agent.storage.sqlite import Database


def _expect_denied(operation: Callable[[], object]) -> None:
    try:
        operation()
    except PermissionDenied:
        return
    raise AssertionError("Expected access denial did not occur")


def _verify_bytes(actual: bytes, expected: bytes) -> None:
    if actual != expected:
        raise ValueError("Original source readback differs from fixture bytes")


def validate_foundation(root: Path) -> dict[str, object]:
    """Validate pilot inputs and demonstrate their actual persistent domain consumers."""
    root = root.resolve()
    settings = load_settings(root / "config/settings.yaml")
    if settings.enable_live_llm:
        raise ValueError("The P01 smoke must keep live model calls disabled")
    bundle = load_fixtures(root)
    expected_reads: list[tuple[str, str, bytes, int, int, str, str]] = []
    denied_reads = 0

    with TemporaryDirectory(prefix="palladion-p01-") as directory:
        temporary = Path(directory)
        originals = OriginalStore(temporary / "originals")
        database_path = temporary / "registry.sqlite"
        with Database(database_path) as database:
            registry = Registry(database, originals)
            for principal in bundle.principals:
                registry.bootstrap_principal(principal)
            for case in bundle.cases:
                registry.bootstrap_case(case.tenant_id, case.case_id)
                for principal_id in case.allowed_principal_ids:
                    principal = next(p for p in bundle.principals if p.principal_id == principal_id)
                    registry.bootstrap_membership(principal, case.case_id)

            for source in bundle.sources:
                uploader_id = next(
                    p.principal_id
                    for p in bundle.principals
                    if p.tenant_id == source.tenant_id and "document:upload" in p.grants
                )
                uploader = registry.access.authenticate(uploader_id)
                content = (root / source.path).read_bytes()
                revision = registry.register_source(
                    uploader,
                    tenant_id=source.tenant_id,
                    case_id=source.case_ids[0],
                    family_id=source.family_id,
                    content=content,
                    source_path=source.path,
                    owner_id=source.approved_by or uploader_id,
                    valid_from=source.valid_from.isoformat() if source.valid_from else None,
                    valid_to=source.valid_to.isoformat() if source.valid_to else None,
                    allowed_principal_ids=source.allowed_principal_ids,
                )
                reader_id = next(
                    p.principal_id
                    for p in bundle.principals
                    if p.tenant_id == source.tenant_id
                    and "reader" in p.roles
                    and source.case_ids[0] in p.allowed_case_ids
                    and (
                        not source.allowed_principal_ids
                        or p.principal_id in source.allowed_principal_ids
                    )
                )
                reader = registry.access.authenticate(reader_id)
                _expect_denied(lambda: registry.read_source(reader, revision))
                denied_reads += 1
                _expect_denied(lambda: registry.approve_source(uploader, revision))
                if source.approval_state != "APPROVED":
                    continue
                approver = registry.access.authenticate(source.approved_by or "")
                registry.approve_source(approver, revision)
                _verify_bytes(registry.read_source(reader, revision), content)
                clause = next(iter(source.clauses.values()))
                _verify_bytes(
                    registry.read_source(
                        reader,
                        revision,
                        start_byte=clause.span_start,
                        end_byte=clause.span_end,
                    ),
                    content[clause.span_start : clause.span_end],
                )
                expected_reads.append(
                    (
                        reader_id,
                        revision,
                        content,
                        clause.span_start,
                        clause.span_end,
                        source.case_ids[0],
                        approver.principal_id,
                    )
                )
                foreign = next(p for p in bundle.principals if p.tenant_id != source.tenant_id)
                _expect_denied(lambda: registry.read_source(foreign, revision))
                denied_reads += 1
                if source.allowed_principal_ids:
                    excluded_id = next(
                        p.principal_id
                        for p in bundle.principals
                        if p.tenant_id == source.tenant_id
                        and "reader" in p.roles
                        and source.case_ids[0] in p.allowed_case_ids
                        and p.principal_id not in source.allowed_principal_ids
                    )
                    limited = registry.access.authenticate(excluded_id)
                    _expect_denied(lambda: registry.read_source(limited, revision))
                    denied_reads += 1

        if not expected_reads:
            raise ValueError("Foundation proof requires at least one approved source reader")
        # Reopen through the same application owners, not ad hoc test/CLI SQL.
        with Database(database_path) as database:
            registry = Registry(database, originals)
            for reader_id, revision, content, start, end, _, _ in expected_reads:
                reader = registry.access.authenticate(reader_id)
                _verify_bytes(registry.read_source(reader, revision), content)
                _verify_bytes(
                    registry.read_source(reader, revision, start_byte=start, end_byte=end),
                    content[start:end],
                )
            if expected_reads:
                reader_id, revision, _, _, _, case_id, admin_id = expected_reads[-1]
                reader = registry.access.authenticate(reader_id)
                admin = registry.access.authenticate(admin_id)
                registry.revoke_membership(admin, reader_id, case_id)
                _expect_denied(lambda: registry.read_source(reader, revision))
                denied_reads += 1

    return {
        "status": "PASS",
        "phase": "P01",
        "fixtures": bundle.summary().model_dump(mode="json"),
        "approved_original_readbacks": len(expected_reads),
        "denied_reads": denied_reads,
        "reopened_registry": True,
        "model_calls": 0,
        "temporary_state_cleaned": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(validate_foundation(args.root), indent=2))


if __name__ == "__main__":
    main()
