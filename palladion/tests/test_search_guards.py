"""P11-T01 negative controls: what the search must refuse, and the bounds it must keep (ADR-0102 to ADR-0108)."""
from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from evidence_agent.core.errors import ResourceConflict
from evidence_agent.ingest.pipeline import IngestPipeline
from evidence_agent.retrieval.evidence import RequestLedger
from evidence_agent.retrieval.hybrid import HybridSearch
from evidence_agent.storage.applicability import MAX_APPLICABILITY_INSTANTS, Applicability
from evidence_agent.storage.catalog import Catalog
from evidence_agent.storage.exact import ExactIndex

from .search_support import NOW, Corpus, LeakyIndex, at
from .test_pipeline import MemoryIndex


@pytest.fixture
def corpus(tmp_path: Path):  # type: ignore[no-untyped-def]
    value = Corpus(tmp_path)
    try:
        yield value
    finally:
        value.close()


# ------------------------------------------------ the resolver, not the index, decides what is released


def test_an_index_that_offers_every_chunk_cannot_make_the_resolver_release_an_ineligible_one(tmp_path: Path) -> None:
    corpus = Corpus(tmp_path, LeakyIndex())
    try:
        query = "reversal rule hours"
        current = corpus.add("CURRENT", "Reversal rule is 48 hours.", valid_from="2024-01-01T00:00:00Z")
        corpus.add("EXPIRED", "Reversal rule was 12 hours.", valid_from="2020-01-01T00:00:00Z",
                   valid_to="2021-01-01T00:00:00Z")
        old = corpus.add("SUPERSEDED", "Reversal rule was 24 hours.", valid_from="2022-01-01T00:00:00Z")
        corpus.add("SUPERSEDED", "Reversal rule is now 36 hours.", valid_from="2025-01-01T00:00:00Z", supersedes=old)
        revoked = corpus.add("REVOKED", "Reversal rule was withdrawn, 60 hours.")
        corpus.registry.revoke_source(corpus.admin, revoked)
        result = corpus.search.search(corpus.uploader, "case-1", query, as_of=NOW, limit=12)
        released = set(corpus.revisions_of(result))
        assert current in released and old not in released and revoked not in released
        assert len(released) == 2, "only the current rule and the successor of the superseded one"
        assert result.excluded["NOT_ELIGIBLE"] >= 3, "the index offered the ineligible chunks and the resolver said no"
    finally:
        corpus.close()


def test_a_restricted_revision_is_offered_and_released_only_to_those_it_names(corpus) -> None:
    open_rule = corpus.add("OPEN", "Reversal rule for everyone, 24 hours.")
    private = corpus.add("PRIVATE", "Reversal rule for approvers, 24 hours.", allowed=("approver",))
    query = "reversal rule hours"
    reader = corpus.search.search(corpus.reader, "case-1", query, as_of=NOW)
    assert corpus.revisions_of(reader) == [open_rule]
    assert corpus.generation_of(private) not in (corpus.index.generation_filters[-1] or ())
    approver = corpus.search.search(corpus.admin, "case-1", query, as_of=NOW)
    assert set(corpus.revisions_of(approver)) == {open_rule, private}
    assert corpus.catalog.alias_hits(corpus.reader, "case-1", "PRIVATE") == ()


def test_a_revision_of_another_case_is_neither_offered_nor_released(corpus) -> None:
    here = corpus.add("HERE", "Reversal rule in this case, 24 hours.")
    there = corpus.add("THERE", "Reversal rule in the other case, 24 hours.", case_id="case-2")
    result = corpus.search.search(corpus.uploader, "case-1", "reversal rule hours", as_of=NOW)
    assert corpus.revisions_of(result) == [here]
    assert corpus.generation_of(there) not in (corpus.index.generation_filters[-1] or ())


def test_a_revoked_revision_no_longer_leads_the_exact_lane(corpus) -> None:
    policy = corpus.add("POL-8", "# POL-8\n\nA request after 24 hours is refused.", register_aliases=True)
    assert [h.revision_id for h in corpus.catalog.alias_hits(corpus.uploader, "case-1", "POL-8")] == [policy]
    corpus.registry.revoke_source(corpus.admin, policy)
    assert corpus.catalog.alias_hits(corpus.uploader, "case-1", "POL-8") == ()


# ------------------------------------------------ ADR-0104: the context share is bounded and needs a reason


def paragraphs(marked: set[int], count: int = 10) -> str:
    filler = " ".join(f"fill{n}" for n in range(190))  # about 1,300 characters: one chunk per paragraph
    return "# Packet\n\n## Terms\n\n" + "\n\n".join(
        f"{'alpha ' if n in marked else ''}paragraph{n} {filler}" for n in range(count))


def test_context_takes_exactly_its_reserved_share_after_the_ranked_passages(corpus) -> None:
    corpus.add("PACKET", paragraphs({0, 3, 6, 9}))
    result = corpus.search.search(corpus.uploader, "case-1", "alpha", mode="reranked", limit=8, as_of=NOW)
    texts = [p.text for p in result.passages]
    assert len(texts) == 6, "four ranked passages plus the two context slots limit 8 reserves"
    assert all("alpha" in text for text in texts[:4]) and not any("alpha" in text for text in texts[4:])
    assert len({p.section_id for p in result.passages}) == 1


def test_a_chunk_in_another_section_is_context_only_when_it_is_linked(corpus) -> None:
    revision = corpus.add("RULE", "# Rule\n\n## Terms\n\nalpha applies to reversals.\n\n## Charities\n\n"
                          "Merchants that are charities follow the schedule in the annex.")
    terms, exception = corpus.catalog.chunks_for_revision(corpus.uploader, revision)
    assert terms.section_id != exception.section_id
    before = corpus.search.search(corpus.uploader, "case-1", "alpha", mode="reranked", limit=4, as_of=NOW)
    assert [p.citation_id for p in before.passages] == [terms.chunk_id]
    corpus.catalog.add_context_link(corpus.admin, terms.chunk_id, exception.chunk_id)
    after = corpus.search.search(corpus.uploader, "case-1", "alpha", mode="reranked", limit=4, as_of=NOW)
    assert [p.citation_id for p in after.passages] == [terms.chunk_id, exception.chunk_id]
    hybrid = corpus.search.search(corpus.uploader, "case-1", "alpha", mode="hybrid", limit=4, as_of=NOW)
    assert [p.citation_id for p in hybrid.passages] == [terms.chunk_id], "only the reranked mode adds context"


# ------------------------------------------------ ADR-0102: how many instants, and who supplies them


def test_exactly_eight_instants_are_accepted_and_nine_are_not() -> None:
    others = [at(f"2025-01-{day:02d}T00:00:00") for day in range(1, MAX_APPLICABILITY_INSTANTS)]
    assert len(Applicability.at(NOW, others).instants) == MAX_APPLICABILITY_INSTANTS
    with pytest.raises(ValueError, match="exceed the bound"):
        Applicability.at(NOW, [*others, at("2025-02-01T00:00:00")])
    with pytest.raises(ValueError, match="requires an aware instant"):
        Applicability((NOW.replace(tzinfo=None),))
    with pytest.raises(ValueError, match="requires an instant"):
        Applicability(())
    with pytest.raises(ValueError, match="distinct"):
        Applicability((NOW, NOW))


def test_the_http_request_takes_seven_extra_instants_and_not_eight() -> None:
    from evidence_agent.api.schemas import Search
    base = {"case_id": "case-1", "query": "reversal"}
    seven = [f"2025-01-0{day}T00:00:00Z" for day in range(1, 8)]
    assert len(Search.model_validate({**base, "applicability_instants": seven}).applicability_instants) == 7
    with pytest.raises(ValidationError):
        Search.model_validate({**base, "applicability_instants": [*seven, "2025-01-08T00:00:00Z"]})


def test_a_model_cannot_pass_a_time_to_the_search_tool() -> None:
    from evidence_agent.agent.tools import KnowledgeArgs
    for field in ("as_of", "applicability_instants", "also_at"):
        with pytest.raises(ValidationError):
            KnowledgeArgs.model_validate_json(f'{{"query": "reversal", "{field}": "2025-01-01T00:00:00Z"}}')


def test_a_case_with_more_trusted_instants_than_the_bound_fails_instead_of_dropping_one(corpus) -> None:
    revision = corpus.add("SOP", "Hold settlement until confirmation arrives.")
    chunk = corpus.catalog.chunks_for_revision(corpus.uploader, revision)[0]
    ledger = RequestLedger(corpus.search, corpus.reader, "case-1", "trace-cap")
    for number in range(MAX_APPLICABILITY_INSTANTS):
        ledger.records[f"live_{number}"] = {
            "kind": "LIVE_OBSERVATION", "operation": "get_transaction_status", "valid": True,
            "data": {"transaction_occurred_at": f"2025-01-0{number + 1}T00:00:00+00:00"}}
    with pytest.raises(ValueError, match="exceed the bound"):
        ledger.add(chunk.chunk_id)


def test_the_case_opening_and_its_named_domain_events_are_trusted_instants(p03) -> None:
    from evidence_agent.live.gateway import read_scope
    ledger = RequestLedger(HybridSearch(Catalog(p03.registry), MemoryIndex()), p03.reader, "case-42", "trace-scope")
    event = read_scope(p03.registry, p03.reader, "case-42").domain_events["dispute_submitted"]
    opened = p03.registry.case_opened_at(p03.reader, "case-42")
    assert set(ledger.applicability_instants()) == {opened, event}


# ------------------------------------------------ ADR-0108: a successor that never became servable retires nobody


def test_a_successor_whose_indexing_failed_leaves_its_predecessor_answering(corpus) -> None:
    old = corpus.add("POL", "Reversal window policy twenty four hours.", valid_from="2025-01-01T00:00:00Z")
    new = corpus.add("POL", "Reversal window policy forty eight hours.", valid_from="2026-01-01T00:00:00Z",
                     supersedes=old, index=False)
    corpus.index.readback_mode = "missing"
    with pytest.raises(ResourceConflict):
        corpus.pipeline.index(corpus.uploader, new)
    served = corpus.search.search(corpus.uploader, "case-1", "reversal window policy hours", as_of=NOW)
    assert corpus.revisions_of(served) == [old]
    corpus.index.readback_mode = "actual"
    corpus.pipeline.index(corpus.uploader, new)
    assert corpus.revisions_of(
        corpus.search.search(corpus.uploader, "case-1", "reversal window policy hours", as_of=NOW)) == [new]


# ------------------------------------------------ ADR-0106: a changed representation is not served until indexed again


def test_documents_indexed_before_a_representation_change_are_not_served_until_indexed_again(corpus) -> None:
    revision = corpus.add("SOP", "Hold settlement until confirmation arrives.")
    query = "hold settlement confirmation"
    assert corpus.revisions_of(corpus.search.search(corpus.uploader, "case-1", query, as_of=NOW)) == [revision]
    corpus.index.fingerprint = "b" * 64  # the search representation changed (new embedder, tokenizer or text form)
    changed = HybridSearch(corpus.catalog, corpus.index, corpus.search.ranker)
    unserved = changed.search(corpus.uploader, "case-1", query, as_of=NOW)
    assert unserved.passages == () and "NO_ELIGIBLE_SOURCES" in unserved.warnings
    IngestPipeline(corpus.catalog, corpus.index).index(corpus.uploader, revision)
    assert corpus.revisions_of(changed.search(corpus.uploader, "case-1", query, as_of=NOW)) == [revision]


# ------------------------------------------------ ADR-0105: what the exact lane did not look up is not "not found"


def test_an_identifier_past_the_candidate_bound_is_reported_as_truncated_not_as_unknown(corpus, monkeypatch) -> None:
    corpus.add("POL-A", "# POL-A\n\n## One\n\nFirst part.\n\n## Two\n\nSecond part.\n\n## Three\n\nThird part.",
               register_aliases=True)
    corpus.add("ERR-B", "# ERR-B\n\nA registered code the lane never reaches.", register_aliases=True)
    monkeypatch.setattr("evidence_agent.storage.exact.MAX_EXACT_CANDIDATES", 2)
    exact = ExactIndex(corpus.catalog).hits(corpus.uploader, "case-1", "POL-A ERR-B")
    assert exact.truncated and exact.unmatched == () and not exact.unknown_lookup
    result = corpus.search.search(corpus.uploader, "case-1", "POL-A ERR-B", as_of=NOW)
    assert "EXACT_CANDIDATES_TRUNCATED" in result.warnings and "EXACT_IDENTIFIER_NOT_FOUND" not in result.warnings


# ------------------------------------------------ ADR-0109: a slow stage names itself


def test_a_search_reports_the_time_of_each_stage_it_ran(corpus) -> None:
    corpus.add("SOP", "Hold settlement until confirmation arrives.", register_aliases=True)
    result = corpus.search.search(corpus.uploader, "case-1", "hold settlement SOP", mode="reranked", as_of=NOW)
    assert {"eligibility", "index", "exact", "resolve", "rerank", "context", "release", "coverage"} == set(result.stage_ms)
    assert all(ms >= 0 for ms in result.stage_ms.values()) and sum(result.stage_ms.values()) <= result.elapsed_ms + 1
    hybrid = corpus.search.search(corpus.uploader, "case-1", "hold settlement", mode="hybrid", as_of=NOW)
    assert "rerank" not in hybrid.stage_ms and "context" not in hybrid.stage_ms
