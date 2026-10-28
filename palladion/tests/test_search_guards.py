"""P11-T01 negative controls: what the search must refuse, and the bounds it must keep (ADR-0102 to ADR-0108)."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from pydantic import ValidationError

from evidence_agent.core.errors import PermissionDenied, ResourceConflict
from evidence_agent.core.retrieval import Candidate
from evidence_agent.ingest.pipeline import IngestPipeline
from evidence_agent.retrieval.evidence import RequestLedger
from evidence_agent.retrieval.hybrid import HybridSearch
from evidence_agent.storage.applicability import MAX_APPLICABILITY_INSTANTS, Applicability
from evidence_agent.storage.catalog import Catalog
from evidence_agent.storage.exact import ExactIndex

from .search_support import FILLER, NOW, Corpus, LeakyIndex, at
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
    revision = corpus.add("RULE", f"# Rule\n\n## Terms\n\nalpha applies to reversals. {FILLER}\n\n## Charities\n\n"
                          f"Merchants that are charities follow the schedule in the annex. {FILLER}")
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
    assert set(ledger.applicability().also) == {opened, event}


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
    corpus.add("POL-A", f"# POL-A\n\n## One\n\nFirst part. {FILLER}\n\n## Two\n\nSecond part. {FILLER}\n\n"
                        f"## Three\n\nThird part. {FILLER}", register_aliases=True)
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


# ------------------------------------------------ the agent path: instants, bounds, defaults


class _Store:
    """The two members of the case store the knowledge tool uses."""

    def authorize(self) -> None:
        return None

    def append(self, *args: object, **kwargs: object) -> None:
        return None


def test_two_default_searches_fill_the_ledger_and_tell_the_model_what_did_not_fit(corpus, monkeypatch) -> None:
    from evidence_agent.agent import tools as tools_module
    for number in range(16):
        corpus.add(f"DOC-{number}", f"{'first' if number < 8 else 'second'} rule number{number} applies.")
    ledger = RequestLedger(corpus.search, corpus.reader, "case-1", "trace-tools")
    seen: list[Applicability] = []

    async def in_process(owner, principal_id, case_id, query, mode, limit, applicability, *, require_graph=False):  # type: ignore[no-untyped-def]
        seen.append(applicability)
        return owner.search(corpus.reader, case_id, query, mode=mode, limit=limit, as_of=applicability.primary,
                            also_at=applicability.also)

    monkeypatch.setattr(tools_module, "search", in_process)
    tools = tools_module.Tools(ledger, None, _Store())  # type: ignore[arg-type]
    first = asyncio.run(tools.execute("search_knowledge", '{"query": "first rule"}'))
    second = asyncio.run(tools.execute("search_knowledge", '{"query": "second rule"}'))
    assert first["status"] == second["status"] == "SUCCEEDED"
    assert len(first["data"]) == 8 and first["omitted_passages"] == 0
    assert len(second["data"]) == 4 and second["omitted_passages"] == 4, "twelve documents is the ledger bound"
    assert [a.also for a in seen] == [ledger.applicability().also] * 2, "the worker is given the ledger instants"


def test_a_ledger_that_cannot_bound_its_instants_fails_the_call_in_plain_words(corpus, monkeypatch) -> None:
    from evidence_agent.agent import tools as tools_module
    ledger = RequestLedger(corpus.search, corpus.reader, "case-1", "trace-bound")
    for number in range(MAX_APPLICABILITY_INSTANTS):
        ledger.records[f"live_{number}"] = {
            "kind": "LIVE_OBSERVATION", "operation": "get_transaction_status", "valid": True,
            "data": {"transaction_occurred_at": f"2025-01-0{number + 1}T00:00:00+00:00"}}

    async def never(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("the worker must not be started for a request that cannot be bounded")

    monkeypatch.setattr(tools_module, "search", never)
    tools = tools_module.Tools(ledger, None, _Store())  # type: ignore[arg-type]
    result = asyncio.run(tools.execute("search_knowledge", '{"query": "rule"}'))
    assert result["status"] == "FAILED" and result["error_code"] == "VALIDATION_ERROR"


# ------------------------------------------------ chunks of an earlier chunking, generations and integrity


def test_points_left_by_an_earlier_generation_are_offered_by_a_careless_index_and_still_refused(tmp_path: Path) -> None:
    corpus = Corpus(tmp_path, LeakyIndex())
    try:
        revision = corpus.add("SOP", "Hold settlement until confirmation arrives.")
        corpus.index.fingerprint = "b" * 64  # the search representation changed: the revision is indexed again
        changed = HybridSearch(corpus.catalog, corpus.index, corpus.search.ranker)
        IngestPipeline(corpus.catalog, corpus.index).index(corpus.uploader, revision)
        result = changed.search(corpus.uploader, "case-1", "hold settlement confirmation", as_of=NOW)
        assert corpus.revisions_of(result) == [revision]
        assert {p.generation for p in result.passages} == {corpus.generation_of(revision)}
        assert result.excluded["NOT_ELIGIBLE"] == 1, "the earlier generation had a point; it was offered and refused"
    finally:
        corpus.close()


def test_a_chunk_that_is_not_part_of_the_served_generation_is_not_released(corpus) -> None:
    revision = corpus.add("SOP", "Hold settlement until confirmation arrives.\n\nA second paragraph follows here.")
    kept = corpus.catalog.chunks_for_revision(corpus.uploader, revision)[0]
    assert corpus.search.resolver.resolve(corpus.uploader, "case-1", kept.chunk_id)
    corpus.database.connection.execute("DELETE FROM index_generation_chunks WHERE chunk_id = ?", (kept.chunk_id,))
    with pytest.raises(PermissionDenied):
        corpus.search.resolver.resolve(corpus.uploader, "case-1", kept.chunk_id)


def test_a_stored_chunk_hash_that_no_longer_matches_its_bytes_is_an_integrity_conflict(corpus) -> None:
    revision = corpus.add("SOP", "Hold settlement until confirmation arrives.")
    chunk = corpus.catalog.chunks_for_revision(corpus.uploader, revision)[0]
    assert corpus.search.resolver.resolve(corpus.uploader, "case-1", chunk.chunk_id).text == chunk.text
    corpus.database.connection.execute(
        "UPDATE p02_chunks SET content_sha256 = ? WHERE chunk_id = ?", ("0" * 64, chunk.chunk_id))
    with pytest.raises(ResourceConflict):
        corpus.search.resolver.resolve(corpus.uploader, "case-1", chunk.chunk_id)


# ------------------------------------------------ supersession needs a successor servable under the fingerprint


def test_a_successor_not_yet_indexed_under_a_new_representation_retires_nobody(corpus) -> None:
    old = corpus.add("POL", "Reversal window policy twenty four hours.", valid_from="2025-01-01T00:00:00Z")
    corpus.add("POL", "Reversal window policy forty eight hours.", valid_from="2026-01-01T00:00:00Z", supersedes=old)
    corpus.index.fingerprint = "b" * 64  # the representation changed; only the predecessor is indexed again so far
    IngestPipeline(corpus.catalog, corpus.index).index(corpus.uploader, old)
    changed = HybridSearch(corpus.catalog, corpus.index, corpus.search.ranker)
    served = changed.search(corpus.uploader, "case-1", "reversal window policy hours", as_of=NOW)
    assert corpus.revisions_of(served) == [old]


# ------------------------------------------------ the exact lane spends its bound on what can apply


def test_a_superseded_version_cannot_use_up_the_exact_lane_candidate_bound(corpus, monkeypatch) -> None:
    monkeypatch.setattr("evidence_agent.storage.exact.MAX_EXACT_CANDIDATES", 2)
    old = corpus.add("POL-6", "# POL-6\n\n## A\n\nOld one.\n\n## B\n\nOld two.\n\n## C\n\nOld three.",
                     valid_from="2025-01-01T00:00:00Z", register_aliases=True)
    new = corpus.add("POL-6", "# POL-6\n\nThe rule that applies now.", valid_from="2026-01-01T00:00:00Z",
                     supersedes=old, register_aliases=True)
    exact = ExactIndex(corpus.catalog)
    unfiltered = exact.hits(corpus.uploader, "case-1", "POL-6")
    eligible = corpus.catalog.eligible_generations(corpus.uploader, "case-1", Applicability.at(NOW),
                                                   fingerprint=corpus.index.fingerprint)
    filtered = exact.hits(corpus.uploader, "case-1", "POL-6", eligible)
    new_chunks = {c.chunk_id for c in corpus.catalog.chunks_for_revision(corpus.uploader, new)}
    assert set(filtered.leading) == new_chunks and not filtered.truncated
    assert set(unfiltered.leading) != new_chunks, "without the filter the bound is spent on the superseded version"


# ------------------------------------------------ what the reranker reads, and many generations in one answer


def test_the_reranker_is_given_the_heading_path_and_its_order_is_the_result(tmp_path: Path) -> None:
    from evidence_agent.core.retrieval import index_text
    from evidence_agent.retrieval.rerank import FastEmbedReranker

    class Ascending:
        def __init__(self) -> None:
            self.texts: list[str] = []

        def rerank(self, query: str, texts: list[str], batch_size: int) -> list[float]:
            self.texts = list(texts)
            return [float(n) for n in range(len(texts))]  # the last input scores highest

    model = Ascending()
    ranker = FastEmbedReranker(enabled=True)
    ranker._load = lambda: model  # type: ignore[method-assign]  # a test double for the loaded cross-encoder
    corpus = Corpus(tmp_path, ranker=ranker)
    try:
        for family in ("ALPHA", "BETA", "GAMMA"):
            corpus.add(family, f"# Policy {family}\n\n## Window\n\nreversal window clause for {family}.")
        result = corpus.search.search(corpus.uploader, "case-1", "reversal window clause", mode="reranked",
                                      as_of=NOW, limit=3)
        chunks = {c.chunk_id: c for row in corpus.database.connection.execute(
            "SELECT revision_id FROM document_revisions").fetchall()
            for c in corpus.catalog.chunks_for_revision(corpus.admin, row[0])}
        assert sorted(model.texts) == sorted(index_text(c) for c in chunks.values())
        assert all(text.startswith("Policy ") for text in model.texts), "each text begins with its heading path"
        assert [index_text(chunks[p.citation_id]) for p in result.passages] == list(reversed(model.texts))
    finally:
        corpus.close()


def test_an_answer_may_draw_on_more_than_twelve_generations(corpus) -> None:
    for number in range(14):
        corpus.add(f"DOC-{number}", f"Reversal rule everybody shares number{number}.")
    result = corpus.search.search(corpus.uploader, "case-1", "reversal rule everybody shares", limit=14, as_of=NOW)
    assert len(result.passages) == 14 and len({p.generation for p in result.passages}) == 14


def test_an_offer_made_twice_is_judged_and_counted_once(corpus) -> None:
    revision = corpus.add("SOP", "Hold settlement until confirmation arrives.")
    chunk = corpus.catalog.chunks_for_revision(corpus.uploader, revision)[0]
    offer = Candidate(chunk_id=chunk.chunk_id, generation=corpus.generation_of(revision), score=1, channel="frozen")
    corpus.registry.revoke_source(corpus.admin, revision)
    result = corpus.search.search(corpus.uploader, "case-1", "hold", evaluator_candidates=(offer, offer, offer))
    assert result.excluded["NOT_ELIGIBLE"] == 1 and result.stage_counts["excluded"] == 1
