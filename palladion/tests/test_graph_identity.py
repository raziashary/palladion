import pytest

from evidence_agent.core.ids import (
    canonical_entity_key,
    chunk_id,
    digest_bytes,
    evidence_ref_id,
    provisional_entity_key,
    revision_id,
)


def test_revision_chunk_and_evidence_ids_are_stable_and_namespace_scoped() -> None:
    content_hash = digest_bytes(b"immutable source")
    revision = revision_id("tenant-a", "family-1", content_hash)
    assert revision == revision_id("tenant-a", "family-1", content_hash)
    assert revision != revision_id("tenant-b", "family-1", content_hash)
    assert revision != revision_id("tenant-a", "family-2", content_hash)
    assert revision != revision_id("tenant-a", "family-1", digest_bytes(b"changed source"))

    first_chunk = chunk_id("tenant-a", revision, 0, 10)
    assert first_chunk == chunk_id("tenant-a", revision, 0, 10)
    assert first_chunk != chunk_id("tenant-a", revision, 0, 11)
    assert first_chunk != chunk_id("tenant-b", revision, 0, 10)
    assert evidence_ref_id("tenant-a", revision, 0, 10, content_hash) == evidence_ref_id(
        "tenant-a", revision, 0, 10, content_hash
    )


def test_digest_requires_bytes_and_spans_are_validated() -> None:
    with pytest.raises(TypeError):
        digest_bytes("source")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        chunk_id("tenant-a", "rev-1", -1, 2)
    with pytest.raises(ValueError):
        chunk_id("tenant-a", "rev-1", 4, 2)


def test_verified_namespace_id_is_the_only_canonical_entity_identity() -> None:
    key = canonical_entity_key(
        "tenant-a", "merchant-registry", "merchant", "merchant-1042"
    )
    assert key == canonical_entity_key(
        "tenant-a", "merchant-registry", "merchant", "merchant-1042"
    )
    assert key != canonical_entity_key(
        "tenant-b", "merchant-registry", "merchant", "merchant-1042"
    )
    assert key != canonical_entity_key(
        "tenant-a", "different-registry", "merchant", "merchant-1042"
    )

    provisional = provisional_entity_key("tenant-a", "rev-1", 10, 20)
    assert provisional != provisional_entity_key("tenant-a", "rev-2", 10, 20)
    assert provisional != provisional_entity_key("tenant-a", "rev-1", 10, 21)
    assert provisional != key
    # There is deliberately no name/category based merge helper.
