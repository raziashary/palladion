"""Manifests, ACL visibility and the four physically separate namespaces (B02-T03.01)."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from benchmark.config import load_fixtures_config
from benchmark.fixtures.artifacts import CorpusPlan, build_corpus, plan_from_config
from benchmark.fixtures.documents import Category, Document
from benchmark.fixtures.entities import WorldError
from benchmark.fixtures.knowledge import DocumentState
from benchmark.fixtures.manifest import (
    Namespace,
    Split,
    build_records,
    dev_annotation_files,
    read_identity,
    read_records,
    scan_published,
    snapshot_id,
    verify_published,
    visible_records,
    write_annotations,
    write_namespaces,
)
from benchmark.fixtures.world import World, build_world

CONFIGS = Path(__file__).resolve().parents[1] / "configs"
SEED = 7


@pytest.fixture(scope="module")
def world() -> World:
    return build_world(SEED)


@pytest.fixture(scope="module")
def plan(world: World) -> CorpusPlan:
    drafts = sum(v.state is DocumentState.DRAFT for v in world.knowledge.versions)
    return plan_from_config(load_fixtures_config(CONFIGS / "fixtures.yaml"), 10, authoritative_drafts=drafts)


@pytest.fixture(scope="module")
def corpus(world: World, plan: CorpusPlan) -> tuple[Document, ...]:
    return build_corpus(world, plan)


@pytest.fixture(scope="module")
def written(tmp_path_factory: pytest.TempPathFactory, world: World, corpus: tuple[Document, ...]) -> Path:
    """The full S-tier corpus written once; tests that only read share it."""
    root = tmp_path_factory.mktemp("full") / "out"
    write_namespaces(root, world, corpus, SEED)
    return root


@pytest.fixture
def small(tmp_path: Path, world: World, corpus: tuple[Document, ...]) -> Path:
    """A 40-document slice (authoritative and support) for tests that change files or write repeatedly."""
    sample = (*corpus[:10], *corpus[300:320], *corpus[900:910])
    write_namespaces(tmp_path / "out", world, sample, SEED)
    return tmp_path / "out"


def published(root: Path) -> Path:
    return root / Namespace.PUBLISHED.value


# --------------------------------------------------------------------------- the four namespaces


def test_four_physically_separate_namespaces_are_created(written: Path) -> None:
    dirs = {ns: written / ns.value for ns in Namespace}
    assert all(d.is_dir() for d in dirs.values())
    assert len({d.resolve() for d in dirs.values()}) == 4
    for a in dirs.values():
        for b in dirs.values():
            assert a == b or a not in b.parents  # no namespace nests inside another
    assert {p.name for p in written.iterdir()} == {ns.value for ns in Namespace}


def test_the_published_tree_holds_only_documents_and_the_three_manifests(written: Path) -> None:
    pub = published(written)
    names = {p.relative_to(pub).as_posix() for p in pub.rglob("*") if p.is_file()}
    assert {"corpus_manifest.jsonl", "identity_manifest.json", "snapshot.json"} <= names
    docs = names - {"corpus_manifest.jsonl", "identity_manifest.json", "snapshot.json"}
    assert len(docs) == 1200 and all(n.startswith("docs/") and n.endswith(".md") and len(n) == 24 for n in docs)
    assert list((written / Namespace.GENERATOR.value).iterdir())  # the hidden world lives elsewhere
    assert not list((written / Namespace.DEV_ANNOTATIONS.value).iterdir())
    assert not list((written / Namespace.TEST_ANNOTATIONS.value).iterdir())


def test_the_generator_namespace_holds_the_tags_and_the_published_one_does_not(written: Path) -> None:
    tags = (written / "generator" / "document_tags.jsonl").read_text(encoding="utf-8")
    assert "near_duplicate_of" in tags and '"injection"' in tags and '"stale"' in tags
    text = "".join(p.read_text(encoding="utf-8") for p in published(written).rglob("*") if p.is_file())
    assert "near_duplicate_of" not in text and '"tags"' not in text and '"language"' not in text


def test_a_non_empty_output_directory_is_not_overwritten_silently(
    small: Path, world: World, corpus: tuple[Document, ...]
) -> None:
    with pytest.raises(WorldError, match="not empty"):
        write_namespaces(small, world, corpus[:5], SEED)
    write_namespaces(small, world, corpus[:5], SEED, overwrite=True)


# --------------------------------------------------------------------------- no gold in the published namespace


def test_the_published_namespace_contains_no_gold_split_or_question_marker(written: Path) -> None:
    assert scan_published(published(written), forbidden=["scenario_family", "q-0123abcd"]) == []


def test_planted_leaks_are_each_caught(small: Path) -> None:
    pub = published(small)
    doc = next(p for p in (pub / "docs").iterdir())
    original = doc.read_text(encoding="utf-8")
    plants = {
        "gold marker": original + "\nrequired_evidence: SOP-1@v1 clause 4.1\n",
        "split word": original + "\nThis item belongs to the smoke partition.\n",
        "question id": original + "\nquestion q-3f9a1c2b answered here\n",
        "forbidden token": original + "\nnorthwave-reversal family\n",
    }
    for expected, text in plants.items():
        doc.write_text(text, encoding="utf-8")
        found = scan_published(pub, forbidden=["northwave-reversal"])
        assert any(expected in f for f in found), (expected, found)
    doc.write_text(original, encoding="utf-8")
    assert scan_published(pub, forbidden=["northwave-reversal"]) == []
    (pub / "questions_dev.jsonl").write_text("{}", encoding="utf-8")
    assert any("unexpected file" in f for f in scan_published(pub))
    (pub / "questions_dev.jsonl").unlink()
    manifest = pub / "corpus_manifest.jsonl"
    saved = manifest.read_text(encoding="utf-8")
    manifest.write_text(saved.replace('"title"', '"gold_answer": "x", "title"', 1), encoding="utf-8")
    assert any("gold marker" in f for f in scan_published(pub))
    manifest.write_text(saved, encoding="utf-8")


# --------------------------------------------------------------------------- hashes and readback


def test_every_manifest_hash_matches_the_file_on_disk(written: Path) -> None:
    assert verify_published(published(written)) == []
    assert len(read_records(published(written))) == 1200


def test_tampering_with_a_published_file_is_caught(small: Path) -> None:
    pub = published(small)
    records = read_records(pub)
    victim = pub / records[0].path
    original = victim.read_bytes()
    victim.write_bytes(original + b"x")
    assert verify_published(pub) == [f"hash mismatch for {records[0].doc_id}"]
    victim.write_bytes(original)
    victim.unlink()
    assert verify_published(pub) == [f"missing file for {records[0].doc_id}"]
    victim.write_bytes(original)
    (pub / "docs" / "ffffffffffffffff.md").write_bytes(b"extra")
    assert verify_published(pub) == ["unlisted file docs/ffffffffffffffff.md"]


def test_the_manifest_reads_back_with_the_authority_metadata_for_authoritative_documents(
    written: Path, world: World
) -> None:
    records = read_records(published(written))
    by_id = {r.doc_id: r for r in records}
    version = next(v for v in world.knowledge.versions if v.supersedes and v.in_force)
    record = by_id[version.version_id]
    assert (record.approved_by, record.valid_from, record.valid_to, record.supersedes) == (
        version.approved_by, version.valid.start, version.valid.end, version.supersedes,
    )  # fmt: skip
    support = next(r for r in records if r.version_id is None)
    assert support.approved_by is None and support.valid_from is None and support.registry_state != "approved"
    assert {"sop", "policy", "exception", "runbook", "faq", "manual", "support_ticket"} <= {
        r.source_type for r in records
    }


def test_identity_manifest_matches_the_world(written: Path, world: World) -> None:
    identity = read_identity(published(written))
    assert identity.principals == world.entities.principals
    assert {t["tenant_id"] for t in identity.tenants} == {t.tenant_id for t in world.entities.tenants}


def test_writing_twice_gives_identical_digests_and_a_different_seed_does_not(
    tmp_path: Path, world: World, corpus: tuple[Document, ...]
) -> None:
    first = write_namespaces(tmp_path / "a", world, corpus[:60], SEED)
    second = write_namespaces(tmp_path / "b", world, corpus[:60], SEED)
    assert first == second
    assert (tmp_path / "a" / "published" / "corpus_manifest.jsonl").read_bytes() == (
        tmp_path / "b" / "published" / "corpus_manifest.jsonl"
    ).read_bytes()
    reordered = write_namespaces(tmp_path / "c", world, corpus[:60], SEED + 1)
    assert reordered["corpus_manifest_sha256"] != first["corpus_manifest_sha256"]
    assert reordered["snapshot_id"] == first["snapshot_id"]  # the snapshot id depends on content, not order


def test_manifest_order_does_not_follow_generation_order(world: World, corpus: tuple[Document, ...]) -> None:
    records = build_records(world, corpus, SEED)
    generated = [d.doc_id for d in corpus]
    assert [r.doc_id for r in records] != generated
    first_twenty = Counter(next(d.category for d in corpus if d.doc_id == r.doc_id) for r in records[:20])
    assert len(first_twenty) >= 4  # no category is bunched at the front


def test_the_snapshot_id_is_opaque_and_changes_with_content(world: World, corpus: tuple[Document, ...]) -> None:
    records = build_records(world, corpus, SEED)
    sid = snapshot_id(records)
    assert sid.startswith("snap-") and len(sid) == 21
    changed = [records[0].__class__(**{**records[0].__dict__, "sha256": "0" * 64}), *records[1:]]
    assert snapshot_id(changed) != sid


# --------------------------------------------------------------------------- tenant and role isolation


def test_a_tenant_b_document_is_not_visible_to_a_tenant_a_principal(world: World, corpus: tuple[Document, ...]) -> None:
    records = build_records(world, corpus, SEED)
    by_id = {r.doc_id: r for r in records}
    tickets = [d for d in corpus if d.category is Category.TICKETS_AND_CASES]
    internal = next(t.tenant_id for t in world.entities.tenants if t.internal)
    for principal in world.entities.principals:
        seen = {r.doc_id for r in visible_records(records, principal)}
        for ticket in tickets:
            tenant = next(t for t in ticket.acl_tenants if t != internal)
            assert (ticket.doc_id in seen) == (principal.tenant_id in (tenant, internal))
        assert not any(by_id[i].acl_tenants and principal.tenant_id not in by_id[i].acl_tenants for i in seen)


def test_role_restrictions_hide_internal_runbooks_from_partner_support(
    world: World, corpus: tuple[Document, ...]
) -> None:
    records = build_records(world, corpus, SEED)
    l1 = next(p for p in world.entities.principals if p.role_id == "support_l1")
    engineer = next(p for p in world.entities.principals if p.role_id == "engineer")
    runbooks = {r.doc_id for r in records if r.source_type == "runbook"}
    assert runbooks
    assert not runbooks & {r.doc_id for r in visible_records(records, l1)}
    assert runbooks <= {r.doc_id for r in visible_records(records, engineer)}
    manuals = {r.doc_id for r in records if r.source_type == "manual"}
    assert manuals <= {r.doc_id for r in visible_records(records, l1)}  # unrestricted documents stay visible


def test_same_named_merchants_in_two_tenants_never_share_a_visible_ticket(
    world: World, corpus: tuple[Document, ...]
) -> None:
    names: dict[str, list[str]] = {}
    for merchant in world.entities.merchants:
        names.setdefault(merchant.display_name, []).append(merchant.tenant_id)
    shared = {n: t for n, t in names.items() if len(t) > 1}
    assert shared
    records = build_records(world, corpus, SEED)
    for name, tenants in shared.items():
        merchants = [m for m in world.entities.merchants if m.display_name == name]
        assert len({m.merchant_id for m in merchants}) == len(merchants)  # distinct identities behind one display name
        for ticket in (d for d in corpus if d.category is Category.TICKETS_AND_CASES and name in d.text):
            owner = next(m for m in merchants if m.merchant_id in ticket.text)
            for principal in world.entities.principals:
                allowed = {r.doc_id for r in visible_records(records, principal)}
                other_partner = principal.tenant_id in tenants and principal.tenant_id != owner.tenant_id
                if other_partner:
                    assert ticket.doc_id not in allowed


# --------------------------------------------------------------------------- annotation namespaces


def gold(question: str, split: str) -> dict[str, object]:
    return {"question_id": question, "split": split, "answerability": "ANSWERABLE"}


def test_dev_and_test_annotations_are_written_to_different_directories(small: Path) -> None:
    written = small
    dev = write_annotations(written, Split.DEV, [gold("q-00000001", "dev")])
    smoke = write_annotations(written, Split.SMOKE, [gold("q-00000002", "smoke")])
    test = write_annotations(written, Split.TEST, [gold("q-00000003", "test")])
    assert dev.parent == smoke.parent == written / "annotations_dev" and test.parent == written / "annotations_test"
    assert dev_annotation_files(written) == sorted([dev, smoke])  # the locked test file is never listed for dev use
    assert "q-00000003" not in "".join(p.read_text(encoding="utf-8") for p in dev_annotation_files(written))


def test_an_annotation_record_from_another_split_is_refused(small: Path) -> None:
    written = small
    with pytest.raises(WorldError, match="does not belong"):
        write_annotations(written, Split.DEV, [gold("q-00000001", "test")])
    with pytest.raises(WorldError, match="does not belong"):
        write_annotations(written, Split.TEST, [gold("q-00000001", "dev")])
    assert json.loads(write_annotations(written, Split.TEST, []).read_text(encoding="utf-8") or "null") is None


def test_regenerating_over_a_previous_output_leaves_no_stale_documents_and_keeps_audit_files(
    tmp_path: Path, world: World, corpus: tuple[Document, ...]
) -> None:
    out = tmp_path / "out"
    write_namespaces(out, world, corpus[:30], SEED)
    audit = out / "generator" / "audit"
    audit.mkdir()
    (audit / "owner_labels.jsonl").write_text("owner work\n", encoding="utf-8")
    stale = {p.name for p in (out / "published" / "docs").iterdir()}
    write_namespaces(out, world, corpus[100:130], SEED, overwrite=True)
    fresh = {p.name for p in (out / "published" / "docs").iterdir()}
    assert stale.isdisjoint(fresh) and verify_published(out / "published") == []
    assert (audit / "owner_labels.jsonl").read_text(encoding="utf-8") == "owner work\n"
