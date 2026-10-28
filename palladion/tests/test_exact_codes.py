"""P11-T07: exact codes and named versions (ADR-0105 addendum, ADR-0110).

A code in a section title defines that section, the reranker leaves the exact lane's placement alone, and a question
that names a version (`POL-1@v2`) is answered by that version. Every guard has a violating case and a valid case; the
index is the ranked in-memory stand-in and every candidate passes the real registry, catalog, resolver and exact lane.
"""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from evidence_agent.core.errors import PermissionDenied
from evidence_agent.core.retrieval import Candidate, Chunk
from evidence_agent.storage.catalog import CODE_PATTERN
from evidence_agent.storage.exact import ExactIndex

from .search_support import NOW, Corpus, at


@pytest.fixture
def corpus(tmp_path: Path):  # type: ignore[no-untyped-def]
    value = Corpus(tmp_path)
    try:
        yield value
    finally:
        value.close()


class Backwards:
    """A ranker that puts the last candidate first: whatever it sees ends up in the opposite order."""

    max_candidates = 30

    def __init__(self) -> None:
        self.seen: list[str] = []

    def rank(self, query: str, chunks: Sequence[Chunk]) -> tuple[Chunk, ...]:
        self.seen = [chunk.text for chunk in chunks]
        return tuple(reversed(chunks))


# ---------------------------------------------------------------- a code in a title defines the section


def table_of_codes(corpus: Corpus, count: int) -> list[str]:
    return [corpus.add(f"TABLE-{n}", f"# Error table {n}\n\n| ERR-9 | 409 |\n| ERR-{n}0 | 422 |\n", register_aliases=True)
            for n in range(count)]


def test_a_code_in_a_section_title_defines_that_section_and_leads_the_tables_that_list_it(corpus) -> None:
    table_of_codes(corpus, 8)  # more than five chunks list ERR-9: by themselves they identify none
    note = corpus.add("NOTE", "# API note: ERR-9 response\n\nRequests fail with ERR-9 (Currency not enabled).",
                      register_aliases=True)
    hits = ExactIndex(corpus.catalog).hits(corpus.uploader, "case-1", "What status does the gateway give for ERR-9?")
    assert [corpus.catalog.get_chunk(corpus.uploader, c).revision_id for c in hits.leading] == [note]
    assert len(hits.trailing) == 8, "the tables that only list the code still trail the semantic hits"
    found = corpus.search.search(corpus.uploader, "case-1", "What status does the gateway give for ERR-9?")
    assert corpus.revisions_of(found)[0] == note


def test_a_code_named_only_in_the_body_is_not_defined_by_its_title(corpus) -> None:
    corpus.add("NOTE", "# API note: ERR-9 response\n\nBody text.", register_aliases=True)
    other = corpus.add("OTHER", "# Gateway guide\n\nThe guide mentions ERR-9 once.", register_aliases=True)
    chunk = corpus.catalog.chunks_for_revision(corpus.uploader, other)[0]
    hits = corpus.catalog.alias_hits(corpus.uploader, "case-1", "ERR-9")
    assert [h.defining for h in hits if h.chunk_id == chunk.chunk_id] == [False]
    assert [h.defining for h in hits].count(True) == 1


@pytest.mark.parametrize("text, codes", [
    ("The gateway fails with code MS-1817.", ["MS-1817"]),
    ("See POL-001, ISO-9001 and V2.1; also DEMO.DISPUTE.SOP-2025-A.", ["POL-001", "ISO-9001", "V2.1", "DEMO.DISPUTE.SOP-2025-A"]),
    ("Fix ERR-9abc and e.g. nothing-here.", []),
    ("POL-001@v2 and (MS-1817)", ["POL-001", "MS-1817"]),
])
def test_a_code_does_not_take_the_punctuation_that_ends_a_sentence(text, codes) -> None:
    assert CODE_PATTERN.findall(text) == codes


def test_a_code_that_ends_a_sentence_is_found_by_the_code_without_the_full_stop(corpus) -> None:
    note = corpus.add("NOTE", "# Gateway guide\n\nThe gateway fails with code ERR-9.", register_aliases=True)
    assert [h.revision_id for h in corpus.catalog.alias_hits(corpus.uploader, "case-1", "ERR-9")] == [note]


def test_a_longer_code_in_a_title_does_not_define_a_shorter_one(corpus) -> None:
    note = corpus.add("NOTE", "# API note: ERR-90 response\n\nThe note also mentions ERR-9 in passing.",
                      register_aliases=True)
    assert [h.defining for h in corpus.catalog.alias_hits(corpus.uploader, "case-1", "ERR-9")] == [False]
    assert [(h.revision_id, h.defining) for h in corpus.catalog.alias_hits(corpus.uploader, "case-1", "ERR-90")] == [
        (note, True)]


# ---------------------------------------------------------------- the reranker leaves the exact lane in place


def test_the_reranker_orders_what_the_index_found_and_cannot_move_the_exact_lane(tmp_path: Path) -> None:
    ranker = Backwards()
    corpus = Corpus(tmp_path, ranker=ranker)
    try:
        for number in range(8):  # ERR-9 listed by eight tickets: they trail the semantic hits
            corpus.add(f"TICKET-{number}", f"Ticket {number} lists ERR-9 beside other things.", register_aliases=True)
        note = corpus.add("NOTE", "# API note: ERR-9 response\n\nGateway status for ERR-9 is 409.",
                          register_aliases=True)
        faq = corpus.add("FAQ", "Gateway status question answered by support.")
        result = corpus.search.search(corpus.uploader, "case-1", "gateway status ERR-9?", mode="reranked", limit=12)
        revisions = corpus.revisions_of(result)
        assert revisions[0] == note, "the chunk that defines the code stays first however the reranker orders the rest"
        assert revisions.index(faq) < min(i for i, r in enumerate(revisions) if r not in (note, faq)), \
            "the semantic hit stays ahead of the tickets that only cite the code"
        assert all("API note: ERR-9" not in text for text in ranker.seen), "the reranker never sees the placed chunks"
        assert not any(f"Ticket {n}" in text for text in ranker.seen for n in range(8)), "nor the trailing ones"
    finally:
        corpus.close()


def test_a_chunk_that_only_cites_the_code_but_matches_the_question_is_ranked_with_the_semantic_hits(tmp_path: Path) -> None:
    ranker = Backwards()
    corpus = Corpus(tmp_path, ranker=ranker)
    try:
        for number in range(8):
            corpus.add(f"TICKET-{number}", f"Gateway status ticket {number} lists ERR-9.", register_aliases=True)
        corpus.search.search(corpus.uploader, "case-1", "gateway status ERR-9?", mode="reranked", limit=12)
        assert sum(f"ticket {n}" in text for text in ranker.seen for n in range(8)) == 8, "the reranker orders them"
    finally:
        corpus.close()


def test_without_an_exact_hit_the_reranker_orders_everything(tmp_path: Path) -> None:
    ranker = Backwards()
    corpus = Corpus(tmp_path, ranker=ranker)
    try:
        corpus.add("A", "Gateway status first note.")
        corpus.add("B", "Gateway status second note gateway.")
        plain = corpus.search.search(corpus.uploader, "case-1", "gateway status", mode="hybrid")
        reranked = corpus.search.search(corpus.uploader, "case-1", "gateway status", mode="reranked")
        assert corpus.revisions_of(reranked) == list(reversed(corpus.revisions_of(plain)))
    finally:
        corpus.close()


# ---------------------------------------------------------------- a question that names a version


def versions(corpus: Corpus) -> tuple[str, str, str]:
    one = corpus.add("POL-1", "# POL-1\n\nA request may be raised within 24 hours.", register_aliases=True,
                     valid_from="2025-01-01T00:00:00Z", valid_to="2025-06-01T00:00:00Z")
    two = corpus.add("POL-1", "# POL-1\n\nA request may be raised within 48 hours.", register_aliases=True,
                     valid_from="2025-06-01T00:00:00Z", valid_to="2026-01-01T00:00:00Z", supersedes=one)
    three = corpus.add("POL-1", "# POL-1\n\nA request may be raised within 72 hours.", register_aliases=True,
                       valid_from="2026-01-01T00:00:00Z", supersedes=two)
    return one, two, three


def test_a_question_without_a_version_is_answered_by_the_governing_one_as_before(corpus) -> None:
    _, _, three = versions(corpus)
    assert set(corpus.revisions_of(corpus.search.search(corpus.uploader, "case-1", "POL-1 hours", as_of=NOW))) == {three}


@pytest.mark.parametrize("name, wanted", [("POL-1@v1", {0}), ("POL-1@v2", {1}), ("POL-1@v3", {2}),
                                         ("POL-1@v1 against POL-1@v2", {0, 1})])
def test_a_question_that_names_a_version_is_answered_by_that_version_alone(corpus, name, wanted) -> None:
    revisions = versions(corpus)
    result = corpus.search.search(corpus.uploader, "case-1", f"According to {name}, how many hours?", as_of=NOW)
    assert set(corpus.revisions_of(result)) == {revisions[i] for i in wanted}
    assert "NAMED_VERSION_NOT_FOUND" not in result.warnings


def test_a_version_the_family_does_not_have_answers_nothing_and_says_so(corpus) -> None:
    versions(corpus)
    result = corpus.search.search(corpus.uploader, "case-1", "According to POL-1@v9, how many hours?", as_of=NOW)
    assert result.passages == () and "NAMED_VERSION_NOT_FOUND" in result.warnings, "no near version is substituted"


def test_a_version_number_counts_revoked_versions_so_the_numbers_stay_put(corpus) -> None:
    one, two, three = versions(corpus)
    corpus.registry.revoke_source(corpus.admin, two)
    assert corpus.catalog.family_version(corpus.uploader, "case-1", "POL-1", 3) == ("POL-1", three)
    assert corpus.catalog.family_version(corpus.uploader, "case-1", "POL-1", 2) == ("POL-1", None), "revoked: not served"
    assert corpus.catalog.family_version(corpus.uploader, "case-1", "POL-1", 1) == ("POL-1", one)


def test_a_draft_has_no_version_number_and_does_not_shift_the_others(corpus) -> None:
    one, two, three = versions(corpus)
    corpus.registry.register_source(corpus.uploader, tenant_id="tenant-a", case_id="case-1", family_id="POL-1",
                                    content=b"A draft.", source_path="draft.md", owner_id="uploader",
                                    valid_from="2025-03-01T00:00:00Z")
    assert corpus.catalog.family_version(corpus.uploader, "case-1", "POL-1", 4) == ("POL-1", None)
    assert [corpus.catalog.family_version(corpus.uploader, "case-1", "POL-1", n)[1] for n in (1, 2, 3)] == [one, two, three]


def test_a_hidden_version_looks_like_a_missing_one(corpus) -> None:
    one = corpus.add("POL-2", "# POL-2\n\nFirst.", valid_from="2025-01-01T00:00:00Z", valid_to="2025-06-01T00:00:00Z",
                     allowed=("approver",))
    two = corpus.add("POL-2", "# POL-2\n\nSecond.", valid_from="2025-06-01T00:00:00Z", supersedes=one)
    assert corpus.catalog.family_version(corpus.uploader, "case-1", "POL-2", 1) == ("POL-2", None)
    assert corpus.catalog.family_version(corpus.uploader, "case-1", "POL-2", 7) == ("POL-2", None)
    assert corpus.catalog.family_version(corpus.uploader, "case-1", "POL-2", 2) == ("POL-2", two)


def test_a_family_of_another_case_names_nothing(corpus) -> None:
    corpus.add("POL-3", "# POL-3\n\nOther case.", case_id="case-2", valid_from="2025-01-01T00:00:00Z")
    assert corpus.catalog.family_version(corpus.uploader, "case-1", "POL-3", 1) is None
    result = corpus.search.search(corpus.uploader, "case-1", "POL-3@v1 hours", as_of=NOW)
    assert result.passages == () and "NAMED_VERSION_NOT_FOUND" not in result.warnings


def test_a_family_is_matched_exactly_like_everywhere_else_in_the_system(corpus) -> None:
    corpus.add("POL-7", "# POL-7\n\nUpper case family.", valid_from="2025-01-01T00:00:00Z")
    assert corpus.catalog.family_version(corpus.uploader, "case-1", "POL-7", 1)[0] == "POL-7"
    assert corpus.catalog.family_version(corpus.uploader, "case-1", "pol-7", 1) is None


def test_the_version_syntax_needs_a_code_and_a_number(corpus) -> None:
    exact = ExactIndex(corpus.catalog)
    versions(corpus)
    assert exact.named_versions(corpus.uploader, "case-1", "POL-1 version 1").resolved == ()
    assert exact.named_versions(corpus.uploader, "case-1", "POL-1@v0").resolved == ()
    assert exact.named_versions(corpus.uploader, "case-1", "POL-1@vx").resolved == ()
    assert exact.named_versions(corpus.uploader, "case-1", "POL-1@v2").resolved[0][0] == "POL-1"


def test_a_revoked_version_is_not_served_even_when_named(corpus) -> None:
    one, _, _ = versions(corpus)
    corpus.registry.revoke_source(corpus.admin, one)
    result = corpus.search.search(corpus.uploader, "case-1", "According to POL-1@v1, how many hours?", as_of=NOW)
    assert result.passages == () and "NAMED_VERSION_NOT_FOUND" in result.warnings


def test_naming_a_version_does_not_change_other_families(corpus) -> None:
    _, _, three = versions(corpus)
    other = corpus.add("POL-5", "# POL-5\n\nOther family hours.", register_aliases=True, valid_from="2025-01-01T00:00:00Z")
    result = corpus.search.search(corpus.uploader, "case-1", "POL-1@v1 and POL-5 hours", as_of=at("2026-10-18T00:00:00"))
    revisions = set(corpus.revisions_of(result))
    assert other in revisions and three not in revisions


def test_candidates_are_unaffected_when_a_frozen_list_is_given(corpus) -> None:
    one, _, _ = versions(corpus)
    chunk = corpus.catalog.chunks_for_revision(corpus.uploader, one)[0]
    frozen = (Candidate(chunk_id=chunk.chunk_id, generation=corpus.generation_of(one), score=1, channel="frozen"),)
    result = corpus.search.search(corpus.uploader, "case-1", "POL-1@v1 hours", as_of=NOW, evaluator_candidates=frozen)
    assert corpus.revisions_of(result) == [one]


def test_a_question_naming_nine_versions_reads_eight_says_so_and_does_not_fail(corpus) -> None:
    versions(corpus)
    query = " ".join(f"POL-1@v{n}" for n in range(1, 10))
    named = ExactIndex(corpus.catalog).named_versions(corpus.uploader, "case-1", query)
    assert len(named.resolved) == 8 and named.truncated
    result = corpus.search.search(corpus.uploader, "case-1", query, as_of=NOW)
    assert result.status == "DEGRADED" and "NAMED_VERSIONS_TRUNCATED" in result.warnings


def test_a_family_the_caller_cannot_read_looks_like_one_the_case_does_not_hold(corpus) -> None:
    corpus.add("POL-8", "# POL-8\n\nHidden family.", valid_from="2025-01-01T00:00:00Z", allowed=("approver",))
    assert corpus.catalog.family_version(corpus.uploader, "case-1", "POL-8", 1) is None
    assert corpus.catalog.family_version(corpus.uploader, "case-1", "POL-404", 1) is None
    hidden = corpus.search.search(corpus.uploader, "case-1", "POL-8@v1 hours", as_of=NOW)
    missing = corpus.search.search(corpus.uploader, "case-1", "POL-404@v1 hours", as_of=NOW)
    assert hidden.warnings == missing.warnings and hidden.passages == missing.passages == ()


def test_an_approved_version_that_was_never_indexed_is_named_but_not_served_and_the_search_says_so(corpus) -> None:
    one, _, _ = versions(corpus)
    unindexed = corpus.add("POL-9", "# POL-9\n\nNot indexed.", valid_from="2025-01-01T00:00:00Z", index=False)
    result = corpus.search.search(corpus.uploader, "case-1", "According to POL-9@v1, how many hours?", as_of=NOW)
    assert result.passages == () and "NAMED_VERSION_NOT_SERVED" in result.warnings
    assert unindexed not in corpus.revisions_of(result) and one


def test_the_agent_reads_a_named_version_back_under_the_terms_it_was_found(corpus) -> None:
    from evidence_agent.retrieval.evidence import RequestLedger

    one, _, three = versions(corpus)
    result = corpus.search.search(corpus.reader, "case-1", "According to POL-1@v1, how many hours?", as_of=NOW)
    passage = result.passages[0]
    ledger = RequestLedger(corpus.search, corpus.reader, "case-1", "trace-named")
    with pytest.raises(PermissionDenied):
        ledger.add(passage.citation_id)  # without the version the question named, the replaced version is not readable
    data = ledger.add(passage.citation_id, result.named_versions)
    assert data["revision_id"] == one and data["replaced_from"] is not None and data["valid_to"] is not None
    assert ledger.read(passage.citation_id)["revision_id"] == one, "the gate reads it back the same way"
    current = corpus.search.search(corpus.reader, "case-1", "POL-1 hours", as_of=NOW).passages[0]
    assert ledger.add(current.citation_id)["revision_id"] == three, "a later plain search of the family is not widened"
    assert ledger.add(current.citation_id)["replaced_from"] is None


def test_the_agent_tool_hands_the_versions_a_search_named_to_the_ledger(corpus, monkeypatch) -> None:
    import asyncio
    import json

    from evidence_agent.agent import tools as agent_tools
    from evidence_agent.memory.store import CaseStore
    from evidence_agent.retrieval.evidence import RequestLedger

    one, _, _ = versions(corpus)

    async def in_process(owner, principal_id, case_id, query, mode, limit, *, applicability, require_graph=False):
        return corpus.search.search(corpus.reader, case_id, query, mode=mode, limit=limit, as_of=applicability.primary,
                                    also_at=applicability.also)

    monkeypatch.setattr(agent_tools, "search", in_process)
    ledger = RequestLedger(corpus.search, corpus.reader, "case-1", "trace-tool")
    tools = agent_tools.Tools(ledger, None, CaseStore(corpus.registry, corpus.reader, "case-1"))  # type: ignore[arg-type]
    arguments = json.dumps({"query": "According to POL-1@v1, how many hours?", "search_mode": "hybrid"})
    answer = asyncio.run(tools.execute("search_knowledge", arguments))
    assert answer["status"] != "ERROR" if "status" in answer else True
    assert {data["revision_id"] for data in ledger.records.values()} == {one}, "the replaced version is on the ledger"
    assert ledger.named, "and the ledger remembers the versions it was found for"


def test_family_defining_rows_survive_the_alias_row_cap_ahead_of_mentions(corpus, monkeypatch) -> None:
    from evidence_agent.core.ids import digest_bytes, revision_id
    from evidence_agent.storage import catalog as catalog_module

    tickets = [corpus.add(f"TICKET-{number}", f"Ticket {number} cites POL-4 once.", register_aliases=True)
               for number in range(4)]
    # Revision IDs are digests: pick a policy text whose ID sorts after every ticket, so only the defining-first order
    # (and not the order of the IDs) can keep it inside the cap.
    texts = ("# POL-4" + chr(10) + chr(10) + f"Reversal rule within {hours} hours." for hours in range(24, 400))
    text = next(x for x in texts if revision_id("tenant-a", "POL-4", digest_bytes(x.encode())) > max(tickets))
    policy = corpus.add("POL-4", text, register_aliases=True)
    monkeypatch.setattr(catalog_module, "MAX_ALIAS_ROWS", 2)
    hits = corpus.catalog.alias_hits(corpus.uploader, "case-1", "POL-4")
    assert policy in [h.revision_id for h in hits if h.defining], "the cap drops mentions, not the defining chunk"
