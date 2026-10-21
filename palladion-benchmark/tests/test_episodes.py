"""Episodes and the document update stream (B07-T05.01): determinism, whole-unit splits, valid lifecycles."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from benchmark.adapters.common import PublishedView
from benchmark.fixtures.episodes import (
    STALE_GAP_HOURS,
    Episode,
    EpisodeError,
    EpisodeKind,
    Turn,
    build_episodes,
    digest,
    validate_episodes,
)
from benchmark.fixtures.knowledge import parse_ts
from benchmark.fixtures.manifest import ManifestRecord, Split
from benchmark.fixtures.operations import case_view
from benchmark.fixtures.questions import GoldError
from benchmark.fixtures.updates import (
    DEFAULT_EVENTS,
    DocEvent,
    EventKind,
    UpdateError,
    build_events,
    replay,
    snapshot_times,
    stream_digest,
    validate_events,
    visible,
)
from benchmark.fixtures.world import World

SEED = 7

# --------------------------------------------------------------------------- episodes


@pytest.fixture(scope="module")
def episodes(s_world: World) -> tuple[Episode, ...]:
    return build_episodes(s_world, SEED, 28)


def test_the_same_seed_gives_the_same_episodes_and_another_seed_gives_others(
    s_world: World, episodes: tuple[Episode, ...]
) -> None:
    assert digest(build_episodes(s_world, SEED, 28)) == digest(episodes)
    assert digest(build_episodes(s_world, SEED + 1, 28)) != digest(episodes)


def test_every_kind_appears_and_every_episode_has_three_to_six_turns(episodes: tuple[Episode, ...]) -> None:
    assert {e.kind for e in episodes} == set(EpisodeKind)
    assert {len(e.turns) for e in episodes} <= {3, 4, 5, 6}
    assert len({e.episode_id for e in episodes}) == len(episodes) and all(
        e.episode_id.startswith("ep-") for e in episodes
    )


def test_an_episode_is_one_unit_in_one_split_and_its_family_is_apart_from_question_families(
    episodes: tuple[Episode, ...],
) -> None:
    assert {e.split for e in episodes} == set(Split)
    assert all(e.family.startswith("ep:") for e in episodes)
    assert len({e.family for e in episodes}) == len(episodes), "one family per episode: no turn can be split off"


def test_the_clock_moves_forward_and_a_stale_episode_leaves_a_long_gap(episodes: tuple[Episode, ...]) -> None:
    for episode in episodes:
        times = [parse_ts(t.evaluation_time) for t in episode.turns]
        assert times == sorted(set(times))
        if episode.kind is EpisodeKind.STALE_LIVE:
            assert (times[2] - times[1]).total_seconds() == STALE_GAP_HOURS * 3600
        else:
            assert (times[-1] - times[0]).total_seconds() < 3600


def test_the_arm_visible_side_carries_neither_gold_nor_the_kind(episodes: tuple[Episode, ...]) -> None:
    for episode in episodes:
        requests = episode.requests("snap-1")
        assert [r.turn_index for r in requests] == list(range(len(episode.turns)))
        assert {r.episode_id for r in requests} == {episode.episode_id}
        assert len({r.question_id for r in requests}) == len(requests)
        for request, turn in zip(requests, episode.turns, strict=True):
            assert request.query == turn.utterance and dict(request.filters) == {}
            assert episode.kind.value not in request.query and episode.family not in request.query


def test_a_correction_demotes_the_wrong_value_and_a_poisoned_claim_is_never_expected(
    s_world: World, episodes: tuple[Episode, ...]
) -> None:
    correction = next(e for e in episodes if e.kind is EpisodeKind.CORRECTION)
    case = s_world.operations.case(correction.case_id)
    wrong = correction.turns[2].gold.stale_values[0]
    view = case_view(case, "2026-12-31T00:00:00Z")
    assert correction.turns[3].gold.reported_after["txn_state"] == correction.turns[2].gold.reported_after["txn_state"]
    assert (
        correction.turns[1].gold.reported_after["txn_state"]
        == wrong
        != correction.turns[3].gold.reported_after["txn_state"]
    )
    assert view.reported.get("txn_state") is None or isinstance(view.reported["txn_state"], str)
    poisoned = next(e for e in episodes if e.kind is EpisodeKind.POISONED_CLAIM)
    token = poisoned.turns[1].gold.poison
    assert token and token in poisoned.turns[1].utterance
    assert all(token not in t.gold.expect_identifiers for t in poisoned.turns)


def test_a_case_switch_expects_one_case_and_forbids_the_other(episodes: tuple[Episode, ...]) -> None:
    switch = next(e for e in episodes if e.kind is EpisodeKind.CASE_SWITCH)
    first, second, back = switch.turns[0].gold, switch.turns[2].gold, switch.turns[3].gold
    assert first.expect_identifiers == back.expect_identifiers == second.forbid_identifiers
    assert second.expect_identifiers == first.forbid_identifiers and first.case_id == back.case_id != second.case_id


def test_a_superseding_episode_names_a_mutation_between_its_turns(episodes: tuple[Episode, ...]) -> None:
    supersede = next(e for e in episodes if e.kind is EpisodeKind.SUPERSEDE)
    assert [t.before for t in supersede.turns] == [None, None, "M10"]
    assert all(t.before is None for e in episodes if e.kind is not EpisodeKind.SUPERSEDE for t in e.turns)


@pytest.mark.parametrize(
    "damage",
    [
        lambda e: replace(e, turns=e.turns[:2]),
        lambda e: replace(e, turns=(*e.turns, *e.turns, *e.turns)),
        lambda e: replace(e, turns=tuple(replace(t, evaluation_time=e.turns[0].evaluation_time) for t in e.turns)),
        lambda e: replace(e, turns=(replace(e.turns[0], utterance="this is the expected answer"), *e.turns[1:])),
        lambda e: replace(e, turns=(replace(e.turns[0], utterance=f"about {e.kind.value}"), *e.turns[1:])),
    ],
)
def test_validation_rejects_each_broken_episode(episodes: tuple[Episode, ...], damage: object) -> None:
    broken = damage(episodes[0])  # type: ignore[operator]
    with pytest.raises((EpisodeError, GoldError)):
        validate_episodes([broken])


def test_validation_rejects_duplicate_ids_and_a_family_that_spans_two_splits(episodes: tuple[Episode, ...]) -> None:
    with pytest.raises(EpisodeError, match="duplicate"):
        validate_episodes([episodes[0], episodes[0]])
    other = next(s for s in Split if s is not episodes[0].split)
    with pytest.raises(EpisodeError, match="spans two splits"):
        validate_episodes([episodes[0], replace(episodes[1], family=episodes[0].family, split=other)])


def test_too_many_episodes_are_refused(s_world: World) -> None:
    with pytest.raises(EpisodeError, match="cases"):
        build_episodes(s_world, SEED, len(s_world.operations.cases) + 1)


def test_a_turn_is_a_plain_value_object() -> None:
    assert Turn.__dataclass_params__.frozen  # type: ignore[attr-defined]


# --------------------------------------------------------------------------- the update stream


@pytest.fixture(scope="module")
def records(s_published: Path) -> tuple[ManifestRecord, ...]:
    return tuple(PublishedView.load(s_published).records)


@pytest.fixture(scope="module")
def events(records: tuple[ManifestRecord, ...]) -> tuple[DocEvent, ...]:
    return build_events(records, SEED)


def test_the_stream_has_exactly_a_thousand_valid_ordered_events_of_every_kind(
    records: tuple[ManifestRecord, ...], events: tuple[DocEvent, ...]
) -> None:
    assert len(events) == DEFAULT_EVENTS == 1000
    assert {e.kind for e in events} == set(EventKind)
    assert [e.at for e in events] == sorted(e.at for e in events) and len({e.event_id for e in events}) == 1000
    validate_events(events, records)
    assert parse_ts(events[0].at).year == 2026 and (parse_ts(events[-1].at) - parse_ts(events[0].at)).days > 30


def test_the_same_seed_gives_the_same_stream_and_replay_is_deterministic(
    records: tuple[ManifestRecord, ...], events: tuple[DocEvent, ...]
) -> None:
    assert (
        stream_digest(build_events(records, SEED))
        == stream_digest(events)
        != stream_digest(build_events(records, SEED + 1))
    )
    at = events[500].at
    assert replay(events, at) == replay(events, at)


def record(doc_id: str, **over: object) -> ManifestRecord:
    base: dict[str, object] = {
        "doc_id": doc_id, "path": f"p/{doc_id}", "sha256": "0" * 64, "title": doc_id, "source_type": "sop",
        "registry_state": "approved", "version_id": f"{doc_id}@v1", "family_id": "F", "approved_by": "A",
        "valid_from": None, "valid_to": None, "recorded_from": None, "supersedes": None,
        "acl_tenants": ("T",), "acl_roles": ("support_l1", "support_l2"), "tokens": 10,
    }  # fmt: skip
    return ManifestRecord(**{**base, **over})  # type: ignore[arg-type]


def event(number: int, at: str, kind: EventKind, doc: str, **detail: str) -> DocEvent:
    return DocEvent(f"ev-{number:04d}", at, kind, doc, detail)


def test_committed_state_follows_the_lifecycle_by_hand() -> None:
    old, new = record("D1"), record("D2", version_id="D2@v2", supersedes="D1@v1")
    by_id = {r.doc_id: r for r in (old, new)}
    stream = (
        event(1, "2026-06-01T00:00:00Z", EventKind.CREATE, "D1"),
        event(2, "2026-06-01T01:00:00Z", EventKind.APPROVE, "D1"),
        event(3, "2026-06-02T00:00:00Z", EventKind.CREATE, "D2"),
        event(4, "2026-06-02T01:00:00Z", EventKind.APPROVE, "D2"),
        event(5, "2026-06-02T01:00:01Z", EventKind.SUPERSEDE, "D1", by="D2"),
        event(6, "2026-06-03T00:00:00Z", EventKind.REVOKE_ACL, "D2", role="support_l1"),
        event(7, "2026-06-04T00:00:00Z", EventKind.DELETE, "D2"),
    )
    validate_events(stream, [old, new])
    assert visible(replay(stream, "2026-06-01T00:30:00Z"), by_id, "support_l1") == frozenset(), "not yet approved"
    assert visible(replay(stream, "2026-06-01T02:00:00Z"), by_id, "support_l1") == {"D1"}
    assert visible(replay(stream, "2026-06-02T01:00:00Z"), by_id, "support_l1") == {"D1", "D2"}
    assert visible(replay(stream, "2026-06-02T01:00:01Z"), by_id, "support_l1") == {"D2"}, (
        "the predecessor is superseded"
    )
    after_revoke = replay(stream, "2026-06-03T12:00:00Z")
    assert visible(after_revoke, by_id, "support_l1") == frozenset() and visible(after_revoke, by_id, "support_l2") == {
        "D2"
    }
    assert visible(replay(stream, "2026-06-05T00:00:00Z"), by_id, "support_l2") == frozenset(), "deleted"
    assert visible(replay(stream, "2026-06-02T12:00:00Z"), by_id, "outsider") == frozenset(), "not in the access list"


@pytest.mark.parametrize(
    ("stream", "reason"),
    [
        ((event(1, "2026-06-01T00:00:00Z", EventKind.APPROVE, "D1"),), "does not exist"),
        (
            (
                event(1, "2026-06-01T00:00:00Z", EventKind.CREATE, "D1"),
                event(2, "2026-06-01T00:01:00Z", EventKind.CREATE, "D1"),
            ),
            "created twice",
        ),
        (
            (
                event(1, "2026-06-01T00:00:00Z", EventKind.CREATE, "D1"),
                event(2, "2026-06-01T00:01:00Z", EventKind.DELETE, "D1"),
                event(3, "2026-06-01T00:02:00Z", EventKind.AMEND, "D1"),
            ),
            "does not exist",
        ),
        (
            (
                event(1, "2026-06-02T00:00:00Z", EventKind.CREATE, "D1"),
                event(2, "2026-06-01T00:00:00Z", EventKind.APPROVE, "D1"),
            ),
            "backwards",
        ),
        ((event(1, "2026-06-01T00:00:00Z", EventKind.CREATE, "ZZ"),), "unknown document"),
        (
            (
                event(1, "2026-06-01T00:00:00Z", EventKind.CREATE, "D1"),
                event(1, "2026-06-01T00:01:00Z", EventKind.APPROVE, "D1"),
            ),
            "duplicate",
        ),
    ],
)
def test_a_stream_that_breaks_the_lifecycle_is_refused_for_that_reason(
    stream: tuple[DocEvent, ...], reason: str
) -> None:
    with pytest.raises(UpdateError, match=reason):
        validate_events(stream, [record("D1")])


def test_a_stream_cannot_be_longer_than_the_documents_allow_and_a_looping_chain_is_refused() -> None:
    with pytest.raises(UpdateError):
        build_events([record("D1")], SEED, count=500)
    loop = [record("D1", supersedes="D2@v1", version_id="D1@v1"), record("D2", supersedes="D1@v1", version_id="D2@v1")]
    with pytest.raises(UpdateError, match="loops"):
        build_events(loop, SEED, count=5)
    with pytest.raises(UpdateError):
        build_events([], SEED)


def test_snapshots_are_evenly_spaced_and_end_at_the_last_event(events: tuple[DocEvent, ...]) -> None:
    times = snapshot_times(events, 8)
    assert len(times) == 8 and list(times) == sorted(times) and times[-1] == events[-1].at
    with pytest.raises(UpdateError):
        snapshot_times(events, 0)
