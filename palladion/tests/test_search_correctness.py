"""P11-T01: search that returns the governing evidence (ADR-0102 to ADR-0105).

Each guard has a violating case that fails without the fix and a valid case that passes. The index is a ranked
in-memory stand-in that honours the revision filter; every candidate still passes the real registry, catalog,
resolver and exact lane.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from evidence_agent.core.errors import PermissionDenied
from evidence_agent.core.ids import digest_bytes, revision_id
from evidence_agent.core.retrieval import Candidate
from evidence_agent.storage.applicability import Applicability
from evidence_agent.storage.exact import ExactIndex

from .search_support import NOW, Corpus, at


@pytest.fixture
def corpus(tmp_path: Path):  # type: ignore[no-untyped-def]
    value = Corpus(tmp_path)
    try:
        yield value
    finally:
        value.close()


# ---------------------------------------------------------------- ADR-0103: eligibility reaches the index


def test_expired_near_duplicates_cannot_take_the_candidate_slots_from_the_current_revision(corpus):
    query = "reversal window hours settled merchant request"
    for number in range(45):
        corpus.add(f"OLD-{number}", f"Reversal window hours settled merchant request old copy {number}.",
                   valid_from="2020-01-01T00:00:00Z", valid_to="2021-01-01T00:00:00Z")
    current = corpus.add("CURRENT", "Reversal window is 48 hours.", valid_from="2024-01-01T00:00:00Z")
    result = corpus.search.search(corpus.uploader, "case-1", query, as_of=at("2026-10-18T00:00:00"), limit=5)
    assert corpus.revisions_of(result) == [current]
    assert set(corpus.index.generation_filters[-1]) == {corpus.generation_of(current)}
    assert result.excluded == {"NOT_ELIGIBLE": 0, "INTEGRITY_CONFLICT": 0}, "the prefilter, not the resolver, removed them"


def test_without_the_prefilter_the_same_corpus_loses_the_current_revision(corpus, monkeypatch):
    """Negative control: the fix, not the corpus, is what returns the current revision."""
    for number in range(45):
        corpus.add(f"OLD-{number}", f"Reversal window hours settled merchant request old copy {number}.",
                   valid_from="2020-01-01T00:00:00Z", valid_to="2021-01-01T00:00:00Z")
    current = corpus.add("CURRENT", "Reversal window is 48 hours.", valid_from="2024-01-01T00:00:00Z")
    monkeypatch.setattr(corpus.catalog, "eligible_generations", lambda *a, **k: None)
    result = corpus.search.search(corpus.uploader, "case-1", "reversal window hours settled merchant request",
                                  as_of=at("2026-10-18T00:00:00"), limit=5)
    assert current not in corpus.revisions_of(result)
    assert "ELIGIBILITY_PREFILTER_BOUNDED" in result.warnings


def test_a_revision_revoked_after_indexing_is_never_offered_or_returned(corpus):
    revision = corpus.add("SOP", "Hold settlement until confirmation arrives.")
    assert corpus.revisions_of(corpus.search.search(corpus.uploader, "case-1", "hold settlement confirmation")) == [
        revision]
    asked = len(corpus.index.generation_filters)
    corpus.registry.revoke_source(corpus.admin, revision)
    result = corpus.search.search(corpus.uploader, "case-1", "hold settlement confirmation")
    assert result.passages == () and "NO_ELIGIBLE_SOURCES" in result.warnings
    assert len(corpus.index.generation_filters) == asked, "with nothing that could apply the index is not asked"


def test_a_search_with_only_ineligible_hits_says_so_instead_of_returning_a_clean_empty_ok(corpus):
    revision = corpus.add("SOP", "Hold settlement until confirmation arrives.")
    chunk = corpus.catalog.chunks_for_revision(corpus.uploader, revision)[0]
    frozen = (Candidate(chunk_id=chunk.chunk_id, generation=corpus.generation_of(revision), score=1,
                        channel="frozen"),)
    assert corpus.search.search(corpus.uploader, "case-1", "hold", evaluator_candidates=frozen).passages
    corpus.registry.revoke_source(corpus.admin, revision)
    result = corpus.search.search(corpus.uploader, "case-1", "hold", evaluator_candidates=frozen)
    assert result.passages == () and result.status == "DEGRADED"
    assert "ALL_CANDIDATES_EXCLUDED" in result.warnings
    assert result.excluded == {"NOT_ELIGIBLE": 1, "INTEGRITY_CONFLICT": 0} and result.stage_counts["excluded"] == 1


def test_a_tampered_original_is_an_integrity_conflict_not_a_silent_miss(corpus):
    revision = corpus.add("SOP", "Hold settlement until confirmation arrives.")
    chunk = corpus.catalog.chunks_for_revision(corpus.uploader, revision)[0]
    row = corpus.database.connection.execute(
        "SELECT content_sha256, index_generation FROM document_revisions WHERE revision_id=?", (revision,)).fetchone()
    frozen = (Candidate(chunk_id=chunk.chunk_id, generation=row[1], score=1, channel="frozen"),)
    assert corpus.search.search(corpus.uploader, "case-1", "hold", evaluator_candidates=frozen).passages
    corpus.registry.originals.path_for(row[0]).write_bytes(b"tampered")
    result = corpus.search.search(corpus.uploader, "case-1", "hold", evaluator_candidates=frozen)
    assert result.passages == ()
    assert "INTEGRITY_CONFLICT" in result.warnings and result.excluded["INTEGRITY_CONFLICT"] == 1


def test_eligible_revisions_follow_window_supersession_and_the_readers_access(corpus, monkeypatch):
    old = corpus.add("POL", "Old rule.", valid_from="2025-01-01T00:00:00Z", valid_to="2026-03-01T00:00:00Z")
    new = corpus.add("POL", "New rule.", valid_from="2026-03-01T00:00:00Z", supersedes=old)
    expired = corpus.add("GONE", "Expired rule.", valid_from="2020-01-01T00:00:00Z", valid_to="2024-01-01T00:00:00Z")
    fingerprint = corpus.index.fingerprint

    def eligible(primary, *also):  # type: ignore[no-untyped-def]
        return set(corpus.catalog.eligible_generations(corpus.uploader, "case-1", Applicability.at(primary, also),
                                                       fingerprint=fingerprint))

    gen = corpus.generation_of
    assert eligible(NOW) == {gen(new)}
    assert eligible(at("2025-06-01T00:00:00")) == {gen(old)}
    assert eligible(NOW, at("2025-06-01T00:00:00")) == {gen(old), gen(new)}
    now = Applicability.at(NOW)
    assert gen(expired) not in eligible(NOW, at("2025-06-01T00:00:00")), "an expired revision stays out"
    assert corpus.catalog.eligible_generations(corpus.uploader, "case-1", now, fingerprint="b" * 64) == ()
    monkeypatch.setattr("evidence_agent.storage.catalog.MAX_ELIGIBLE_REVISIONS", 1)
    assert corpus.catalog.eligible_generations(corpus.uploader, "case-1", now, fingerprint=fingerprint) is None


# ---------------------------------------------------------------- ADR-0102: trusted case instants


def test_the_older_version_is_found_when_a_trusted_case_instant_precedes_its_successor(corpus):
    old = corpus.add("POL", "Reversal window policy twenty four hours.", valid_from="2025-01-01T00:00:00Z",
                     valid_to="2026-03-01T00:00:00Z")
    new = corpus.add("POL", "Reversal window policy forty eight hours.", valid_from="2026-03-01T00:00:00Z",
                     supersedes=old)
    query = "reversal window policy hours"
    now_only = corpus.search.search(corpus.uploader, "case-1", query, as_of=at("2026-10-18T00:00:00"))
    assert corpus.revisions_of(now_only) == [new]
    both = corpus.search.search(corpus.uploader, "case-1", query, as_of=at("2026-10-18T00:00:00"),
                                also_at=(at("2025-06-01T00:00:00"),))
    assert set(corpus.revisions_of(both)) == {old, new}
    before_anything = corpus.search.search(corpus.uploader, "case-1", query, as_of=at("2026-10-18T00:00:00"),
                                           also_at=(at("2024-01-01T00:00:00"),))
    assert corpus.revisions_of(before_anything) == [new], "a revision valid at no instant stays excluded"


def test_instants_must_be_aware_and_bounded(corpus):
    corpus.add("POL", "Reversal window.")
    with pytest.raises(ValueError, match="aware"):
        corpus.search.search(corpus.uploader, "case-1", "reversal", also_at=(datetime(2025, 1, 1),))
    many = tuple(at(f"2025-01-{day:02d}T00:00:00") for day in range(1, 10))
    with pytest.raises(ValueError, match="bound"):
        corpus.search.search(corpus.uploader, "case-1", "reversal", also_at=many)


# ---------------------------------------------------------------- ADR-0104: context never displaces ranked hits


def sectioned(count: int) -> str:
    return "# Packet\n\n" + "\n\n".join(
        f"## Section {i}\n\n" + " ".join(["clause"] * (count - i) + [f"unique{i}"]) for i in range(count))


def test_ranked_passages_keep_every_slot_a_neighbour_in_another_section_cannot_take(corpus):
    revision = corpus.add("PACKET", sectioned(12))
    plain = corpus.search.search(corpus.uploader, "case-1", "clause", mode="hybrid", limit=8)
    expanded = corpus.search.search(corpus.uploader, "case-1", "clause", mode="reranked", limit=8)
    assert len(plain.passages) == len(expanded.passages) == 8
    assert [p.citation_id for p in expanded.passages] == [p.citation_id for p in plain.passages]
    assert set(corpus.revisions_of(expanded)) == {revision}


def test_same_section_context_follows_the_ranked_passages_and_uses_only_the_reserved_share(corpus):
    long_section = " ".join(f"word{i}" for i in range(700))  # splits into two chunks of one section
    corpus.add("LONG", f"# Rule\n\n## Terms\n\nclause {long_section}\n\n## Other\n\nclause alone")
    plain = corpus.search.search(corpus.uploader, "case-1", "clause", mode="hybrid", limit=4)
    expanded = corpus.search.search(corpus.uploader, "case-1", "clause", mode="reranked", limit=4)
    ranked = [p.citation_id for p in plain.passages]
    shown = [p.citation_id for p in expanded.passages]
    assert len(ranked) == 2, "only two chunks contain the query word"
    assert shown[:2] == ranked, "ranked passages come first and in rank order"
    assert len(shown) == 3, "limit 4 reserves one context slot, and only the same-section continuation is eligible"
    sections = {p.citation_id: p.section_id for p in expanded.passages}
    assert sections[shown[2]] in {sections[c] for c in ranked}


# ---------------------------------------------------------------- ADR-0105: defining chunks first, semantic kept


def test_the_policy_that_defines_a_code_ranks_before_tickets_that_only_cite_it(corpus):
    tickets = [corpus.add(f"TICKET-{n}", f"Ticket {n} says reversal under POL-1 was refused.", register_aliases=True)
               for n in range(3)]
    # Revision IDs are digests; pick a policy text whose ID sorts after every ticket, so only the rule can put it first.
    texts = (f"# POL-1\n\nReversal requests are allowed within {hours} hours." for hours in range(24, 200))
    text = next(t for t in texts if revision_id("tenant-a", "POL-1", digest_bytes(t.encode())) > max(tickets))
    policy = corpus.add("POL-1", text, register_aliases=True)
    first = corpus.search.search(corpus.uploader, "case-1", "POL-1", mode="hybrid")
    assert corpus.revisions_of(first)[0] == policy
    assert corpus.revisions_of(corpus.search.search(corpus.uploader, "case-1", "POL-1")) == corpus.revisions_of(first)


def test_a_code_cited_by_many_chunks_identifies_none_of_them_and_trails_the_semantic_hits(corpus):
    policy = corpus.add("POL-1", "# POL-1\n\nReversal requests are allowed within 24 hours.", register_aliases=True)
    tickets = [corpus.add(f"TICKET-{n}", f"Ticket {n} cites POL-1 for something else entirely.", register_aliases=True)
               for n in range(8)]
    answer = corpus.add("FAQ", "Reversal requests allowed hours question and answer.")
    faq = corpus.catalog.chunks_for_revision(corpus.uploader, answer)[0]
    frozen = (Candidate(chunk_id=faq.chunk_id, generation=corpus.generation_of(answer), score=1, channel="frozen"),)
    # Only the exact lane and one frozen semantic hit: the order is policy, the semantic hit, then the citing tickets.
    result = corpus.search.search(corpus.uploader, "case-1", "POL-1", evaluator_candidates=frozen)
    revisions = corpus.revisions_of(result)
    assert revisions[0] == policy and revisions[1] == answer and set(revisions[2:]) == set(tickets)
    hits = ExactIndex(corpus.catalog).hits(corpus.uploader, "case-1", "POL-1")
    assert len(hits.trailing) == 8 and len(hits.leading) == 1 and hits.unmatched == ()


@pytest.mark.parametrize("cited, trails", [(5, False), (6, True)])
def test_a_code_cited_by_five_chunks_still_identifies_them_and_by_six_does_not(corpus, cited, trails):
    for number in range(cited):
        corpus.add(f"TICKET-{number}", f"Ticket {number} cites ERR-77 here.", register_aliases=True)
    hits = ExactIndex(corpus.catalog).hits(corpus.uploader, "case-1", "ERR-77")
    assert (len(hits.trailing), len(hits.leading)) == ((cited, 0) if trails else (0, cited))


def test_an_unregistered_code_inside_a_question_keeps_the_semantic_hits_and_names_the_code(corpus):
    revision = corpus.add("SOP", "Changes between releases are listed in the notes.")
    result = corpus.search.search(corpus.uploader, "case-1", "what changed between releases V2.1 notes")
    assert corpus.revisions_of(result) == [revision]
    assert "EXACT_IDENTIFIER_NOT_FOUND" in result.warnings and result.unmatched_identifiers == ("V2.1",)


def test_a_bare_unregistered_code_is_a_lookup_nothing_answers(corpus):
    corpus.add("SOP", "Changes between releases V2.1 are listed in the notes.")
    result = corpus.search.search(corpus.uploader, "case-1", "V2.1")
    assert result.passages == () and result.unmatched_identifiers == ("V2.1",)
    assert "EXACT_IDENTIFIER_NOT_FOUND" in result.warnings


def test_alias_hits_are_ordered_by_definition_then_document_position_not_by_hash(corpus):
    first = corpus.add("POL-9", "# POL-9\n\nAlpha.\n\n## Part\n\nBeta.", register_aliases=True)
    corpus.add("OTHER", "Cites POL-9 once.", register_aliases=True)
    hits = corpus.catalog.alias_hits(corpus.uploader, "case-1", "pol-9")
    assert [h.defining for h in hits] == [True] * (len(hits) - 1) + [False]
    starts = [corpus.catalog.get_chunk(corpus.uploader, h.chunk_id).start_byte for h in hits if h.defining]
    assert starts == sorted(starts) and all(h.revision_id == first for h in hits if h.defining)


# ---------------------------------------------------------------- execution: reads take no write lock


def test_releasing_evidence_does_not_wait_for_a_writer(corpus):
    revision = corpus.add("SOP", "Hold settlement until confirmation arrives.")
    chunk = corpus.catalog.chunks_for_revision(corpus.uploader, revision)[0]
    writer = sqlite3.connect(corpus.database.path, isolation_level=None, timeout=0)
    try:
        writer.execute("BEGIN IMMEDIATE")
        passage = corpus.search.resolver.resolve(corpus.uploader, "case-1", chunk.chunk_id)
        assert passage.text == chunk.text
    finally:
        writer.execute("ROLLBACK")
        writer.close()


def test_a_revoked_source_is_refused_by_the_read_only_resolver(corpus):
    revision = corpus.add("SOP", "Hold settlement until confirmation arrives.")
    chunk = corpus.catalog.chunks_for_revision(corpus.uploader, revision)[0]
    corpus.registry.revoke_source(corpus.admin, revision)
    with pytest.raises(PermissionDenied):
        corpus.search.resolver.resolve(corpus.uploader, "case-1", chunk.chunk_id)


# ---------------------------------------------------------------- ADR-0102: the backend, never the model, supplies instants


def test_the_search_tool_offers_the_model_no_time_argument():
    from evidence_agent.agent.tools import definitions
    search = next(d for d in definitions() if d["function"]["name"] == "search_knowledge")
    properties = set(search["function"]["parameters"]["properties"])
    assert properties == {"schema_version", "query", "search_mode", "limit", "require_graph"}


def test_the_ledger_derives_instants_from_the_case_and_fresh_verified_transaction_times(corpus):
    from evidence_agent.retrieval.evidence import RequestLedger
    ledger = RequestLedger(corpus.search, corpus.reader, "case-1", "trace-1")
    opened = ledger.applicability().also
    assert len(opened) == 1 and opened[0].tzinfo is not None, "the case opening is always a trusted instant"
    assert ledger.applicability().primary == NOW, "the evaluation instant is the registry's injected clock"
    fresh = {"kind": "LIVE_OBSERVATION", "operation": "get_transaction_status", "valid": True,
             "data": {"transaction_occurred_at": "2025-06-01T00:00:00+00:00"}}
    stale = {**fresh, "valid": False, "data": {"transaction_occurred_at": "2024-01-01T00:00:00+00:00"}}
    other = {**fresh, "operation": "get_settlement_status", "data": {"transaction_occurred_at": "2023-01-01T00:00:00+00:00"}}
    ledger.records.update(live_a=fresh, live_b=stale, live_c=other)
    instants = ledger.applicability().also
    assert at("2025-06-01T00:00:00") in instants
    assert at("2024-01-01T00:00:00") not in instants and at("2023-01-01T00:00:00") not in instants


def test_a_cited_older_version_stays_readable_by_the_ledger_at_the_same_instants(corpus):
    from evidence_agent.retrieval.evidence import RequestLedger
    old = corpus.add("POL", "Reversal window policy twenty four hours.", valid_from="2025-01-01T00:00:00Z",
                     valid_to="2026-03-01T00:00:00Z")
    corpus.add("POL", "Reversal window policy forty eight hours.", valid_from="2026-03-01T00:00:00Z", supersedes=old)
    chunk = corpus.catalog.chunks_for_revision(corpus.uploader, old)[0]
    ledger = RequestLedger(corpus.search, corpus.reader, "case-1", "trace-2")
    fresh = {"kind": "LIVE_OBSERVATION", "operation": "get_transaction_status", "valid": True,
             "data": {"transaction_occurred_at": "2025-06-01T00:00:00+00:00"}}
    with pytest.raises(PermissionDenied):
        ledger.add(chunk.chunk_id)
    ledger.records["live_a"] = fresh
    assert ledger.add(chunk.chunk_id)["revision_id"] == old
    assert chunk.chunk_id in ledger.records


# ---------------------------------------------------------------- ADR-0107: what the agent asks for and sees


def test_the_search_tool_asks_for_enough_ranked_passages_and_tells_the_model_its_defaults():
    from evidence_agent.agent.tools import DEFAULT_SEARCH_LIMIT, KnowledgeArgs, definitions
    args = KnowledgeArgs(query="reversal window")
    assert (args.limit, args.search_mode) == (DEFAULT_SEARCH_LIMIT, "reranked") and DEFAULT_SEARCH_LIMIT == 8
    schema = next(d for d in definitions() if d["function"]["name"] == "search_knowledge")["function"]["parameters"]
    assert schema["properties"]["limit"]["default"] == DEFAULT_SEARCH_LIMIT
    assert schema["properties"]["search_mode"]["default"] == "reranked"


def test_the_model_sees_which_policy_a_passage_comes_from_and_when_it_applies(corpus):
    from evidence_agent.retrieval.evidence import RequestLedger, model_view
    revision = corpus.add("POL-7", "# Reversal policy\n\n## Window\n\nA request after 24 hours is refused.",
                          valid_from="2025-01-01T00:00:00Z", valid_to="2030-01-01T00:00:00Z")
    chunk = corpus.catalog.chunks_for_revision(corpus.uploader, revision)[0]
    data = RequestLedger(corpus.search, corpus.reader, "case-1", "trace-3").add(chunk.chunk_id)
    view = model_view(data)
    assert view["family_id"] == "POL-7" and view["heading_path"] == ["Reversal policy", "Window"]
    assert view["valid_from"].startswith("2025-01-01") and view["valid_to"].startswith("2030-01-01")
    assert "A request after 24 hours" in view["text_preview"] and "text" not in view
    assert "content_sha256" not in view


# ---------------------------------------------------------------- the Applicability value object


def test_applicability_deduplicates_requires_aware_instants_and_stays_bounded():
    now, earlier = at("2026-10-18T00:00:00"), at("2025-06-01T00:00:00")
    assert Applicability.at(now, [earlier, now]).instants == (now, earlier)
    assert (Applicability.at(now, [earlier]).primary, Applicability.at(now, [earlier]).also) == (now, (earlier,))
    with pytest.raises(ValueError, match="aware"):
        Applicability.at(datetime(2026, 1, 1))
    with pytest.raises(ValueError, match="bound"):
        Applicability.at(now, [at(f"2025-01-{day:02d}T00:00:00") for day in range(1, 9)])


def test_applicability_admits_inside_the_half_open_window_and_before_a_successor():
    on = Applicability.at(at("2026-03-01T00:00:00"))
    assert on.admits("2026-03-01T00:00:00+00:00", None, ()), "valid_from is inclusive"
    assert not on.admits(None, "2026-03-01T00:00:00+00:00", ()), "valid_to is exclusive"
    assert not on.admits(None, None, ["2026-03-01T00:00:00+00:00"]), "a successor effective now has taken over"
    assert on.admits(None, None, ["2026-03-01T00:00:00.000001+00:00"])
    both = Applicability.at(at("2026-03-01T00:00:00"), [at("2025-06-01T00:00:00")])
    assert both.admits("2025-01-01T00:00:00+00:00", "2026-03-01T00:00:00+00:00", ["2026-03-01T00:00:00+00:00"])


# ---------------------------------------------------------------- ADR-0108: publication is atomic and fails closed


def test_a_predecessor_keeps_answering_while_its_approved_successor_is_still_indexing(corpus):
    old = corpus.add("POL", "Reversal window policy twenty four hours.", valid_from="2025-01-01T00:00:00Z")
    new = corpus.registry.register_source(corpus.uploader, tenant_id="tenant-a", case_id="case-1", family_id="POL",
        content=b"Reversal window policy forty eight hours.", source_path="new.md", owner_id="uploader",
        valid_from="2026-01-01T00:00:00Z")
    corpus.registry.approve_source(corpus.admin, new, supersedes_revision_id=old,
                                   applicability_scope={"tenant_id": "tenant-a", "case_id": "case-1"})
    during = corpus.search.search(corpus.uploader, "case-1", "reversal window policy hours",
                                  as_of=at("2026-10-18T00:00:00"))
    assert corpus.revisions_of(during) == [old], "the successor is approved but not servable yet"
    corpus.pipeline.index(corpus.uploader, new)
    after = corpus.search.search(corpus.uploader, "case-1", "reversal window policy hours",
                                 as_of=at("2026-10-18T00:00:00"))
    assert corpus.revisions_of(after) == [new]


def test_a_revoked_successor_still_retires_its_predecessor(corpus):
    old = corpus.add("POL", "Reversal window policy twenty four hours.", valid_from="2025-01-01T00:00:00Z")
    new = corpus.add("POL", "Reversal window policy forty eight hours.", valid_from="2026-01-01T00:00:00Z",
                     supersedes=old)
    corpus.registry.revoke_source(corpus.admin, new)
    result = corpus.search.search(corpus.uploader, "case-1", "reversal window policy hours",
                                  as_of=at("2026-10-18T00:00:00"))
    assert result.passages == (), "withdrawing a rule does not silently reinstate the one it replaced"


def test_aliases_of_a_revision_are_all_registered_or_none(corpus):
    from evidence_agent.core.errors import ValidationFailure
    revision = corpus.add("POL-3", "# POL-3\n\nCites ERR-1 and ERR-2.")
    chunk = corpus.catalog.chunks_for_revision(corpus.uploader, revision)[0]
    before = corpus.database.connection.execute("SELECT count(*) FROM exact_aliases").fetchone()[0]
    with pytest.raises(ValidationFailure):
        corpus.catalog.add_aliases(corpus.admin, revision, [("GOOD-1", chunk.chunk_id), ("BAD-1", "chunk_unknown")])
    assert corpus.database.connection.execute("SELECT count(*) FROM exact_aliases").fetchone()[0] == before


def test_a_revision_past_the_alias_bounds_keeps_the_aliases_inside_them_and_says_so(corpus):
    codes = " ".join(f"CODE-{n}" for n in range(80))
    revision = corpus.add("POL-4", f"# POL-4\n\nMany codes: {codes}.")
    registration = ExactIndex(corpus.catalog).register_approved(corpus.admin, revision)
    assert registration.truncated and registration.registered == 64
    inside = corpus.catalog.alias_hits(corpus.uploader, "case-1", "POL-4")
    assert inside and all(hit.defining for hit in inside), "the family alias is registered before any code"
    ordinary = corpus.add("POL-5", "# POL-5\n\nOne code ERR-9.")
    assert not ExactIndex(corpus.catalog).register_approved(corpus.admin, ordinary).truncated
