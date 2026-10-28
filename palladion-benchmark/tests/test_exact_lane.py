"""R0x: keyword search plus the rule that a section named by its code comes first (BADR-0047)."""

from __future__ import annotations

from pathlib import Path

from benchmark.adapters.bm25 import Bm25Arm
from benchmark.adapters.common import Chunk, Condition, PublishedView
from benchmark.adapters.exact_lane import ExactLaneArm, defines
from benchmark.contracts import RetrievalRequest, RetrieverAdapter
from benchmark.fixtures.entities import Principal
from benchmark.fixtures.manifest import IdentityManifest, ManifestRecord

TEXTS = {
    # The table lists the code three times: plain BM25 scores it above the article that is titled with the code.
    "TABLE": "# Error table\n\nMS-1019 MS-1019 MS-1019 retry codes list the code MS-1019 again and again\n",
    "ARTICLE": "# Runbook: MS-1019 duplicate reference\n\nCheck the reference before any retry.\n",
    "OTHER": "# Notes\n\nretry codes are listed elsewhere and MS-2000 is unrelated\n",
}


def record(doc_id: str) -> ManifestRecord:
    return ManifestRecord(
        doc_id, f"docs/{doc_id}.md", "0" * 64, doc_id, "runbook", "approved", None, None, None, None, None, None,
        None, (), (), 0,
    )  # fmt: skip


def view(tmp_path: Path) -> PublishedView:
    identity = IdentityManifest((), (), (Principal("P-1", "T-1", "engineer", "One"),))
    return PublishedView(tmp_path, [record(d) for d in TEXTS], identity, dict(TEXTS))


def request(query: str) -> RetrievalRequest:
    return RetrievalRequest(
        question_id="q-0000000000000001", query=query, principal_id="P-1", corpus_snapshot_id="snap1",
        evaluation_time="2026-10-18T03:00:00Z", event_time=None, filters={}, limit=10, max_evidence_tokens=4000,
    )  # fmt: skip


def built(tmp_path: Path, arm_class: type[Bm25Arm]) -> Bm25Arm:
    arm = arm_class(view(tmp_path), Condition.C1, chunk_words=60)
    arm.build_index(str(tmp_path), "ns")
    return arm


def documents(arm: Bm25Arm, query: str) -> list[str | None]:
    return [c.source_document_id for c in arm.retrieve(request(query))]


def test_plain_keyword_search_ranks_the_table_that_repeats_the_code_above_the_article_titled_with_it(
    tmp_path: Path,
) -> None:
    assert documents(built(tmp_path, Bm25Arm), "what does MS-1019 mean")[:2] == ["TABLE", "ARTICLE"]


def test_the_exact_lane_puts_the_article_titled_with_the_code_first_and_keeps_the_rest_in_bm25_order(
    tmp_path: Path,
) -> None:
    plain, lane = built(tmp_path, Bm25Arm), built(tmp_path, ExactLaneArm)
    assert documents(lane, "what does MS-1019 mean") == [
        "ARTICLE",
        *[d for d in documents(plain, "what does MS-1019 mean") if d != "ARTICLE"],
    ]


def test_a_query_without_a_code_ranks_exactly_as_r0(tmp_path: Path) -> None:
    query = "retry codes listed"
    assert documents(built(tmp_path, ExactLaneArm), query) == documents(built(tmp_path, Bm25Arm), query)


def test_a_code_that_no_heading_names_changes_nothing(tmp_path: Path) -> None:
    query = "what is MS-2000"
    ranked = documents(built(tmp_path, Bm25Arm), query)
    assert ranked[0] == "OTHER" and documents(built(tmp_path, ExactLaneArm), query) == ranked


def test_defines_reads_headings_only_and_case_folds(tmp_path: Path) -> None:
    chunk = Chunk("c", "d", 0, 10, "# Runbook: MS-1019 duplicate\n\nbody names MS-2000\n", ())
    assert defines(chunk, ["ms-1019"]) and not defines(chunk, ["ms-2000"]), "a code in the body is a mention"
    assert not defines(Chunk("c", "d", 0, 5, "text with #MS-1019 inline\n", ()), ["ms-1019"])


def test_the_arm_keeps_the_contract_and_says_what_it_mirrors(tmp_path: Path) -> None:
    arm = built(tmp_path, ExactLaneArm)
    described = arm.describe()
    assert isinstance(arm, RetrieverAdapter) and described["arm"] == "R0x" and "not mirrored" in described["exact_lane"]
    assert arm.index_stats()["arm"] == "R0x"


def test_an_eligible_set_limits_the_ranking_and_the_exact_chunks(tmp_path: Path) -> None:
    arm = built(tmp_path, ExactLaneArm)
    only = frozenset({"TABLE"})
    assert [s.chunk.doc_id for s in arm.rank("what does MS-1019 mean", "P-1", only)] == ["TABLE"]
    assert {c.doc_id for c in arm.chunks_naming(["ms-1019"], "P-1", only)} == {"TABLE"}
    assert {c.doc_id for c in arm.chunks_naming(["ms-1019"], "P-1")} == {"TABLE", "ARTICLE"}


def test_chunks_that_define_the_code_keep_their_own_bm25_order(tmp_path: Path) -> None:
    texts = {
        "A-LOW": "# MS-1019 note\n\nsee the table\n",
        "Z-HIGH": "# MS-1019 retry runbook\n\nMS-1019 MS-1019 retry the request after the reference check\n",
    }
    view = PublishedView(
        tmp_path,
        [record(d) for d in texts],
        IdentityManifest((), (), (Principal("P-1", "T-1", "engineer", "One"),)),
        texts,
    )
    arm = ExactLaneArm(view, Condition.C1, chunk_words=60)
    arm.build_index(str(tmp_path), "ns")
    ranked = [s.chunk.doc_id for s in arm.rank("MS-1019 retry", "P-1")]
    # Both define the code; the one BM25 scores higher stays first, not the one whose id sorts first.
    assert ranked == ["Z-HIGH", "A-LOW"]


def test_a_code_is_matched_as_a_whole_identifier_not_as_the_start_of_a_longer_one() -> None:
    longer = Chunk("c", "d", 0, 10, "# MS-4021 lockout" + chr(10) + chr(10) + "body" + chr(10), ())
    assert not defines(longer, ["ms-402"]) and defines(longer, ["ms-4021"])
