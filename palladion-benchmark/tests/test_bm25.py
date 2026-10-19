"""R0 lexical arm: hand-computed scores, identifiers, access filter, budgets and determinism (B04-T01.01)."""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

from benchmark.adapters.bm25 import Bm25Arm, identifiers, tokenize
from benchmark.adapters.common import AdapterError, Condition, PublishedView, count_words
from benchmark.contracts import RetrievalRequest, RetrieverAdapter
from benchmark.fixtures.entities import Principal
from benchmark.fixtures.manifest import IdentityManifest, ManifestRecord

ERROR_CODE = re.compile(r"MS-\d{4}")


def request(query: str, principal_id: str = "P-1", limit: int = 10, budget: int = 4000) -> RetrievalRequest:
    return RetrievalRequest(
        question_id="q-0000000000000001",
        query=query,
        principal_id=principal_id,
        corpus_snapshot_id="snap1",
        evaluation_time="2026-10-18T03:00:00Z",
        event_time=None,
        filters={},
        limit=limit,
        max_evidence_tokens=budget,
    )


def record(doc_id: str, tenants: tuple[str, ...] = (), roles: tuple[str, ...] = ()) -> ManifestRecord:
    return ManifestRecord(
        doc_id, f"docs/{doc_id}.md", "0" * 64, doc_id, "policy", "approved", None, None, None, None, None, None, None,
        tenants, roles, 0,
    )  # fmt: skip


def tiny_view(tmp_path: Path) -> PublishedView:
    texts = {
        "A": "refund window is seventy two hours\n",
        "B": "refund refund approvals need level two\n",
        "C": "completely different words here\n",
        "H": "refund secret clause for tenant two\n",
    }
    records = [record("A"), record("B"), record("C"), record("H", tenants=("T-2",))]
    identity = IdentityManifest(
        (), (), (Principal("P-1", "T-1", "engineer", "One"), Principal("P-2", "T-2", "engineer", "Two"))
    )
    return PublishedView(tmp_path, records, identity, texts)


# --------------------------------------------------------------------------- tokens and scores


def test_identifiers_are_kept_whole_beside_their_parts() -> None:
    tokens = tokenize("Error MS-4021 under POL-020@v2 and TXN-ABC-00001")
    for expected in ("ms-4021", "ms", "4021", "pol-020@v2", "pol", "txn-abc-00001"):
        assert expected in tokens
    assert identifiers("MS-4021, ms-4021 and POL-020@v2") == ["ms-4021", "pol-020@v2"]
    assert tokenize("Refund   WINDOW") == ["refund", "window"]
    assert "end-to-end" not in tokenize("an end-to-end check") and identifiers("pre-authorization and end-to-end") == []


def test_scores_match_a_hand_computed_okapi_bm25(tmp_path: Path) -> None:
    arm = Bm25Arm(tiny_view(tmp_path), Condition.C1, chunk_words=50)
    arm.build_index(str(tmp_path), "ns")
    n, df = 4, 3  # four chunks; "refund" is in A, B and H
    idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
    lengths = {"A": 6, "B": 6, "C": 4, "H": 6}
    average = sum(lengths.values()) / 4
    tf = {"A": 1, "B": 2, "H": 1}
    expected = {d: idf * f * 2.2 / (f + 1.2 * (1 - 0.75 + 0.75 * lengths[d] / average)) for d, f in tf.items()}
    got = {s.chunk.doc_id: s.score for s in arm.rank("refund", "P-1")}
    assert got == pytest.approx(expected)
    assert list(got) == ["B", "A", "H"], "higher term frequency first; equal scores break by chunk id"


def test_a_term_in_every_chunk_still_scores_positively_and_unknown_terms_score_nothing(tmp_path: Path) -> None:
    arm = Bm25Arm(tiny_view(tmp_path), Condition.C1, chunk_words=50)
    arm.build_index(str(tmp_path), "ns")
    assert arm.rank("zzzunknown", "P-1") == []
    assert arm.idf("refund") > 0


def test_invalid_parameters_and_order_of_calls_are_refused(tmp_path: Path) -> None:
    view = tiny_view(tmp_path)
    with pytest.raises(AdapterError):
        Bm25Arm(view, k1=0)
    with pytest.raises(AdapterError):
        Bm25Arm(view, b=1.5)
    arm = Bm25Arm(view)
    with pytest.raises(AdapterError, match="build_index"):
        arm.retrieve(request("refund"))
    with pytest.raises(AdapterError, match="published directory"):
        arm.build_index(str(tmp_path / "elsewhere"), "ns")


# --------------------------------------------------------------------------- access and budget


def test_the_neutral_filter_hides_a_tenants_documents_and_c1_does_not(tmp_path: Path) -> None:
    view = tiny_view(tmp_path)
    governed = Bm25Arm(view, Condition.C2, chunk_words=50)
    governed.build_index(str(tmp_path), "ns")
    open_arm = Bm25Arm(view, Condition.C1, chunk_words=50)
    open_arm.build_index(str(tmp_path), "ns")
    assert "H" not in {c.source_document_id for c in governed.retrieve(request("refund", "P-1"))}
    assert "H" in {c.source_document_id for c in governed.retrieve(request("refund", "P-2"))}
    assert "H" in {c.source_document_id for c in open_arm.retrieve(request("refund", "P-1"))}


def test_the_budget_limit_and_ranks_are_enforced(tmp_path: Path) -> None:
    arm = Bm25Arm(tiny_view(tmp_path), Condition.C1, chunk_words=50)
    arm.build_index(str(tmp_path), "ns")
    assert len(arm.retrieve(request("refund", limit=2))) == 2
    result = arm.retrieve(request("refund", budget=8))
    assert sum(count_words(c.content) for c in result) <= 8
    assert arm.last_notes["truncated"] is True and arm.last_notes["dropped"] > 0
    assert [c.rank for c in result] == list(range(1, len(result) + 1))
    full = arm.retrieve(request("refund", budget=1000))
    assert arm.last_notes["truncated"] is False and len(full) == 3


def test_the_arm_satisfies_the_adapter_contract(tmp_path: Path) -> None:
    assert isinstance(Bm25Arm(tiny_view(tmp_path)), RetrieverAdapter)


# --------------------------------------------------------------------------- the real corpus


@pytest.fixture(scope="module")
def arm(s_published: Path) -> Bm25Arm:
    built = Bm25Arm(PublishedView.load(s_published), Condition.C1)
    built.build_index(str(s_published), "S")
    return built


def test_an_exact_error_code_query_ranks_a_chunk_naming_it_first(arm: Bm25Arm) -> None:
    codes: dict[str, str] = {}
    for chunk in arm.chunks:
        for code in ERROR_CODE.findall(chunk.text):
            codes.setdefault(code, chunk.chunk_id)
    assert len(codes) >= 5, "the fixture should name several error codes"
    principal = arm.view.identity.principals[0].principal_id
    for code in sorted(codes)[:30]:
        top = arm.retrieve(request(code, principal, limit=5))[0]
        assert code in top.content, code


def test_index_stats_are_complete_and_a_rebuild_is_identical(arm: Bm25Arm, s_published: Path) -> None:
    stats = arm.index_stats()
    assert stats["documents"] == 1200 and stats["chunks"] > 1200 and stats["terms"] > 1000
    other = Bm25Arm(PublishedView.load(s_published), Condition.C1)
    other.build_index(str(s_published), "S")
    comparable = ("documents", "chunks", "words", "characters", "terms")
    assert {k: other.index_stats()[k] for k in comparable} == {k: stats[k] for k in comparable}
    principal = arm.view.identity.principals[0].principal_id
    query = "refund window hours transaction"
    assert [c.content for c in other.retrieve(request(query, principal))] == [
        c.content for c in arm.retrieve(request(query, principal))
    ]


def test_c2_never_returns_a_document_the_manifest_denies(s_published: Path) -> None:
    governed = Bm25Arm(PublishedView.load(s_published), Condition.C2)
    governed.build_index(str(s_published), "S")
    checked = 0
    for principal in governed.view.identity.principals:
        denied = {r.doc_id for r in governed.view.records} - governed.access.visible_documents(principal.principal_id)
        for query in ("refund window", "approval exception", "settlement dispute"):
            ids = {c.source_document_id for c in governed.retrieve(request(query, principal.principal_id, limit=10))}
            assert not ids & denied
            checked += 1
    assert checked >= 6
