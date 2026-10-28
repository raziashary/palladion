"""The eligibility rule behind R3f: approval, validity window, supersession and named versions (BADR-0047)."""

from __future__ import annotations

from pathlib import Path

from benchmark.adapters.common import PublishedView
from benchmark.adapters.eligibility import Eligibility
from benchmark.contracts import RetrievalRequest
from benchmark.fixtures.entities import Principal
from benchmark.fixtures.manifest import IdentityManifest, ManifestRecord

EVALUATED = "2026-10-18T03:00:00Z"


def record(
    doc_id: str,
    state: str = "approved",
    *,
    family: str | None = None,
    start: str | None = None,
    end: str | None = None,
    supersedes: str | None = None,
) -> ManifestRecord:
    version = doc_id if family else None
    return ManifestRecord(
        doc_id, f"docs/{doc_id}.md", "0" * 64, doc_id, "policy", state, version, family, None, start, end, None,
        supersedes, (), (), 0,
    )  # fmt: skip


def view(tmp_path: Path, *records: ManifestRecord) -> PublishedView:
    identity = IdentityManifest((), (), (Principal("P-1", "T-1", "engineer", "One"),))
    return PublishedView(tmp_path, list(records), identity, {r.doc_id: "text\n" for r in records})


def ask(rule: Eligibility, query: str = "what applies", at: str = EVALUATED, event: str | None = None) -> set[str]:
    request = RetrievalRequest(
        question_id="q-0000000000000001",
        query=query,
        principal_id="P-1",
        corpus_snapshot_id="snap1",
        evaluation_time=at,
        event_time=event,
        filters={},
        limit=10,
        max_evidence_tokens=4000,
    )
    return set(rule.documents(request))


def test_only_the_states_palladion_approves_are_retrievable(tmp_path: Path) -> None:
    states = ("approved", "retired", "non_normative", "withdrawn", "draft", "unapproved_proposal")
    rule = Eligibility(view(tmp_path, *(record(f"D-{s}", s) for s in states)))
    assert ask(rule) == {"D-approved", "D-retired", "D-non_normative"}


def test_a_window_is_half_open_start_inclusive_and_end_exclusive(tmp_path: Path) -> None:
    rule = Eligibility(view(tmp_path, record("W", start="2026-01-01T00:00:00Z", end="2026-06-01T00:00:00Z")))
    assert ask(rule, at="2026-01-01T00:00:00Z") == {"W"}
    assert ask(rule, at="2025-12-31T23:59:59Z") == set()
    assert ask(rule, at="2026-05-31T23:59:59Z") == {"W"}
    assert ask(rule, at="2026-06-01T00:00:00Z") == set()


def test_a_document_without_a_window_always_applies(tmp_path: Path) -> None:
    assert ask(Eligibility(view(tmp_path, record("T")))) == {"T"}


def versions(tmp_path: Path, successor_state: str = "approved") -> Eligibility:
    return Eligibility(
        view(
            tmp_path,
            record("POL-1@v1", "retired", family="POL-1", start="2026-01-01T00:00:00Z", end="2027-01-01T00:00:00Z"),
            record("POL-1@v2", successor_state, family="POL-1", start="2026-06-01T00:00:00Z", supersedes="POL-1@v1"),
            record("POL-2@v1", family="POL-2", start="2026-01-01T00:00:00Z"),
        )
    )


def test_a_predecessor_stops_applying_when_its_successor_takes_effect(tmp_path: Path) -> None:
    rule = versions(tmp_path)
    assert ask(rule, at="2026-03-01T00:00:00Z") == {"POL-1@v1", "POL-2@v1"}, "before the successor: v1 governs"
    assert ask(rule, at="2026-07-01T00:00:00Z") == {"POL-1@v2", "POL-2@v1"}, "after it: v1 is out of effect"


def test_the_predecessor_is_out_at_the_very_instant_its_successor_takes_effect(tmp_path: Path) -> None:
    rule = versions(tmp_path)
    assert ask(rule, at="2026-05-31T23:59:59Z") == {"POL-1@v1", "POL-2@v1"}
    assert ask(rule, at="2026-06-01T00:00:00Z") == {"POL-1@v2", "POL-2@v1"}


def test_a_successor_that_is_not_retrievable_does_not_retire_its_predecessor(tmp_path: Path) -> None:
    assert ask(versions(tmp_path, "draft"), at="2026-07-01T00:00:00Z") == {"POL-1@v1", "POL-2@v1"}


def test_the_event_time_is_a_second_instant_so_a_replaced_version_governs_what_happened_then(tmp_path: Path) -> None:
    rule = versions(tmp_path)
    assert ask(rule, at="2026-07-01T00:00:00Z", event="2026-03-01T00:00:00Z") == {"POL-1@v1", "POL-1@v2", "POL-2@v1"}


def test_a_named_version_is_answered_by_that_version_alone_whatever_its_window(tmp_path: Path) -> None:
    rule = versions(tmp_path)
    assert ask(rule, "According to POL-1@v1, how many hours?", at="2026-07-01T00:00:00Z") == {"POL-1@v1", "POL-2@v1"}
    assert ask(rule, "According to pol-1@v2, how many hours?", at="2026-03-01T00:00:00Z") == {"POL-1@v2", "POL-2@v1"}


def test_a_named_version_that_does_not_exist_leaves_its_family_with_nothing_and_other_families_alone(
    tmp_path: Path,
) -> None:
    rule = versions(tmp_path)
    assert ask(rule, "What is POL-1@v9?", at="2026-07-01T00:00:00Z") == {"POL-2@v1"}
    assert ask(rule, "What is ZZZ-9@v1?", at="2026-07-01T00:00:00Z") == ask(rule, at="2026-07-01T00:00:00Z")


def test_a_revoked_successor_still_ends_its_predecessor_as_palladion_does(tmp_path: Path) -> None:
    rule = Eligibility(
        view(
            tmp_path,
            record("POL-1@v1", "retired", family="POL-1", start="2026-01-01T00:00:00Z"),
            record("POL-1@v2", "withdrawn", family="POL-1", start="2026-06-01T00:00:00Z", supersedes="POL-1@v1"),
        )
    )
    assert ask(rule, at="2026-03-01T00:00:00Z") == {"POL-1@v1"}
    assert ask(rule, at="2026-07-01T00:00:00Z") == set(), "the withdrawn v2 is not served and v1 is retired by it"


def test_a_named_version_that_is_withdrawn_gives_its_family_nothing(tmp_path: Path) -> None:
    rule = Eligibility(
        view(
            tmp_path,
            record("POL-1@v1", "retired", family="POL-1", start="2026-01-01T00:00:00Z"),
            record("POL-1@v2", "withdrawn", family="POL-1", start="2026-06-01T00:00:00Z", supersedes="POL-1@v1"),
        )
    )
    assert ask(rule, "What did POL-1@v2 say?", at="2026-07-01T00:00:00Z") == set()
    assert ask(rule, "What did POL-1@v1 say?", at="2026-07-01T00:00:00Z") == {"POL-1@v1"}


def test_the_cache_is_keyed_by_the_instants_and_the_names(tmp_path: Path) -> None:
    rule = versions(tmp_path)
    early, late = ask(rule, at="2026-03-01T00:00:00Z"), ask(rule, at="2026-07-01T00:00:00Z")
    assert early != late and ask(rule, at="2026-03-01T00:00:00Z") == early
    assert ask(rule, "POL-1@v1", at="2026-07-01T00:00:00Z") != late


def test_the_rule_describes_itself_as_a_mirror_computed_from_the_manifest(tmp_path: Path) -> None:
    described = Eligibility(view(tmp_path, record("T"))).describe()
    assert "manifest only" in str(described["mirrors"]) and "withdrawn" not in described["retrievable_states"]
