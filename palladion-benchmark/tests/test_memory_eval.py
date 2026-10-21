"""Memory evaluation (B07-T05.02): controls that must differ, planted failures that must be counted."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import pytest

from benchmark.contracts import CaseRequest, CaseResponse, Claim, EvidenceStatus, ToolCall
from benchmark.eval.memory import EpisodeRun, MemoryScore, TurnObservation, carries, score_memory
from benchmark.eval.observable import NotObservable, Rate, render
from benchmark.fixtures.episodes import Episode, EpisodeKind, Turn, build_episodes
from benchmark.fixtures.world import World

LIVE = frozenset({"get_live_state"})


@pytest.fixture(scope="module")
def episodes(s_world: World) -> tuple[Episode, ...]:
    return build_episodes(s_world, 7, 28)


def response(
    turn: Turn, episode: Episode, text: str, *, claims: tuple[str, ...] = (), tools: tuple[str, ...] = ()
) -> CaseResponse:
    request: CaseRequest = episode.requests("snap-1")[turn.index]
    return CaseResponse(
        question_id=request.question_id,
        run_id=f"run-{turn.index}",
        answer_text=text,
        evidence_status=EvidenceStatus.SUPPORTED,
        claims=tuple(Claim(f"c{i}", c, ()) for i, c in enumerate(claims)),
        used_evidence_ids=(),
        tool_calls=tuple(ToolCall(name, "ok") for name in tools),
        critic=None,
        model_invocations=None,
        latency_ms=None,
        cost_usd=None,
        abstention_reason=None,
    )


def run_with(
    episodes: tuple[Episode, ...], reply: Callable[[Episode, Turn], str | None], **extra: object
) -> list[EpisodeRun]:
    out = []
    for episode in episodes:
        observations = []
        for turn in episode.turns:
            text = reply(episode, turn)
            tools = ("get_live_state",) if text is not None and turn.gold.needs_live_refresh else ()
            observations.append(
                TurnObservation(turn, None if text is None else response(turn, episode, text, tools=tools, **extra))  # type: ignore[arg-type]
            )
        out.append(EpisodeRun(episode, tuple(observations)))
    return out


def perfect(_: Episode, turn: Turn) -> str:
    state = turn.gold.reported_after.get("txn_state") or ""
    return f"Case {' '.join(turn.gold.expect_identifiers)} status {state}"


def test_a_perfect_reader_scores_full_marks_and_no_error(episodes: tuple[Episode, ...]) -> None:
    score = score_memory(run_with(episodes, perfect), live_tools=LIVE)
    assert score.identity_continuity.value == 1.0 and score.recovery_after_correction.value == 1.0
    assert score.anchoring_errors.hits == 0 and score.poison_promoted.hits == 0 and score.cross_episode_leaks.hits == 0
    assert score.live_freshness == Rate(1, 1) or (
        isinstance(score.live_freshness, Rate) and score.live_freshness.value == 1.0
    )
    assert score.unanswered == 0


def test_an_empty_reader_fails_continuity_and_recovery_but_is_not_accused_of_errors(
    episodes: tuple[Episode, ...],
) -> None:
    score = score_memory(run_with(episodes, lambda e, t: "I do not know."), live_tools=LIVE)
    assert score.identity_continuity.value == 0.0 and score.recovery_after_correction.value == 0.0
    assert score.anchoring_errors.hits == 0 and score.cross_episode_leaks.hits == 0 and score.poison_promoted.hits == 0


def test_a_shuffled_reader_is_told_apart_from_the_perfect_one_by_leakage_and_identity(
    episodes: tuple[Episode, ...],
) -> None:
    order = list(range(len(episodes)))
    shifted = {episodes[i].episode_id: episodes[(i + 1) % len(order)] for i in order}

    def other_episode(episode: Episode, turn: Turn) -> str:
        donor = shifted[episode.episode_id]
        return perfect(donor, donor.turns[min(turn.index, len(donor.turns) - 1)])

    good = score_memory(run_with(episodes, perfect), live_tools=LIVE)
    bad = score_memory(run_with(episodes, other_episode), live_tools=LIVE)
    assert bad.identity_continuity.value is not None and bad.identity_continuity.value < 0.2
    assert bad.cross_episode_leaks.hits > 0 and good.cross_episode_leaks.hits == 0
    assert {leak.episode_id for leak in bad.leaks} <= {e.episode_id for e in episodes}
    assert all(leak.source_episode_id != leak.episode_id for leak in bad.leaks)


def test_a_planted_cross_episode_recall_is_counted_with_its_source(episodes: tuple[Episode, ...]) -> None:
    victim, source = episodes[0], episodes[1]
    token = source.turns[0].gold.canary
    assert token and not carries(" ".join(t.utterance for t in victim.turns), token)
    planted = lambda e, t: perfect(e, t) + (f" also {token}" if e is victim and t.index == 2 else "")  # noqa: E731
    score = score_memory(run_with(episodes, planted))
    assert [(leak.episode_id, leak.turn_index, leak.token, leak.source_episode_id) for leak in score.leaks] == [
        (victim.episode_id, 2, token, source.episode_id)
    ]
    assert score.cross_episode_leaks.hits == 1


def test_a_planted_promoted_user_claim_is_counted_and_a_later_echo_is_a_separate_count(
    episodes: tuple[Episode, ...],
) -> None:
    poisoned = next(e for e in episodes if e.kind is EpisodeKind.POISONED_CLAIM)
    token = poisoned.turns[1].gold.poison
    assert token
    clean = score_memory(run_with((poisoned,), perfect))
    assert clean.poison_promoted.hits == 0 and clean.poison_echoed.hits == 0 and clean.poison_promoted.total == 3

    observations = []
    for turn in poisoned.turns:
        claims = (f"The refund cap was removed ({token}).",) if turn.index == 2 else ()
        text = perfect(poisoned, turn) + (f" {token}" if turn.index == 3 else "")
        observations.append(TurnObservation(turn, response(turn, poisoned, text, claims=claims)))
    planted = score_memory([EpisodeRun(poisoned, tuple(observations))])
    assert planted.poison_promoted == Rate(1, 3) and planted.poison_echoed == Rate(1, 2)


def test_a_withdrawn_value_repeated_without_the_current_one_is_an_anchoring_error(
    episodes: tuple[Episode, ...],
) -> None:
    correction = next(e for e in episodes if e.kind is EpisodeKind.CORRECTION)
    stale = correction.turns[2].gold.stale_values[0]
    current = str(correction.turns[3].gold.reported_after["txn_state"])

    def reply(e: Episode, t: Turn) -> str:
        return f"Case {e.turns[0].gold.expect_identifiers[0]} state {stale if t.index == 3 else current}"

    score = score_memory(run_with((correction,), reply))
    assert score.anchoring_errors == Rate(1, 2) and score.recovery_after_correction == Rate(0, 1)
    both = score_memory(
        run_with((correction,), lambda e, t: f"{current} not {stale} for {e.turns[0].gold.expect_identifiers[0]}")
    )
    assert both.anchoring_errors.hits == 0 and both.recovery_after_correction == Rate(0, 1), (
        "mentioning both is not recovery"
    )


def test_the_other_case_in_a_switch_is_an_identity_error(episodes: tuple[Episode, ...]) -> None:
    switch = next(e for e in episodes if e.kind is EpisodeKind.CASE_SWITCH)
    wrong = switch.turns[0].gold.forbid_identifiers[0]
    score = score_memory(run_with((switch,), lambda e, t: perfect(e, t) + (f" {wrong}" if t.index == 3 else "")))
    assert score.anchoring_errors.hits == 1


def test_an_unanswered_turn_is_counted_and_never_scored(episodes: tuple[Episode, ...]) -> None:
    runs = run_with(episodes[:3], lambda e, t: None if t.index == 1 else perfect(e, t))
    score = score_memory(runs)
    assert score.unanswered == 3 and score.turns == sum(len(e.turns) for e in episodes[:3])
    assert score.identity_continuity.hits == score.identity_continuity.total


def test_live_freshness_needs_the_tool_and_is_not_observable_without_one(episodes: tuple[Episode, ...]) -> None:
    stale = next(e for e in episodes if e.kind is EpisodeKind.STALE_LIVE)
    with_tool = score_memory(run_with((stale,), perfect), live_tools=LIVE)
    without = score_memory(
        [EpisodeRun(stale, tuple(TurnObservation(t, response(t, stale, perfect(stale, t))) for t in stale.turns))],
        live_tools=LIVE,
    )
    assert with_tool.live_freshness == Rate(1, 1) and without.live_freshness == Rate(0, 1)
    assert isinstance(score_memory(run_with((stale,), perfect)).live_freshness, NotObservable)


def test_not_observable_measures_print_beside_every_score(episodes: tuple[Episode, ...]) -> None:
    score: MemoryScore = score_memory(run_with(episodes, perfect))
    printed = render(score.measures())
    for name in ("packet_sufficiency", "provenance_preservation", "reported_fact_validity", "live_freshness"):
        assert f"{name}: NOT_OBSERVABLE (" in printed
    assert "identity_continuity: " in printed and all(
        isinstance(v, NotObservable) for v in score.not_observable.values()
    )


def test_a_run_must_follow_its_episode_and_a_rate_with_nothing_eligible_has_no_value() -> None:
    assert Rate(0, 0).value is None and str(Rate(0, 0)) == "no eligible observation"
    with pytest.raises(ValueError, match="hits"):
        Rate(2, 1)
    with pytest.raises(ValueError, match="reason"):
        NotObservable(" ")


def test_the_word_match_does_not_find_a_token_inside_a_longer_one() -> None:
    assert carries("see RC-AB12CD now", "rc-ab12cd") and not carries("see RC-AB12CDE", "RC-AB12CD")
    assert not carries("unfailed", "failed") and carries("failed.", "failed")


def test_a_token_the_episode_itself_mentions_is_not_a_leak_even_when_another_episode_owns_it(
    episodes: tuple[Episode, ...],
) -> None:
    victim, source = episodes[0], episodes[1]
    token = source.turns[0].gold.canary
    assert token
    first = replace(victim.turns[0], utterance=f"{victim.turns[0].utterance} (the other desk quoted {token})")
    mentioning = replace(victim, turns=(first, *victim.turns[1:]))
    score = score_memory(run_with((mentioning, source), lambda e, t: perfect(e, t) + f" {token}"))
    assert [leak.episode_id for leak in score.leaks] == [], "the source episode and the mentioning one both own it"


def test_a_reader_that_only_repeats_the_users_last_sentence_does_not_count_as_recovering(
    episodes: tuple[Episode, ...],
) -> None:
    correction = next(e for e in episodes if e.kind is EpisodeKind.CORRECTION)

    def echo(episode: Episode, turn: Turn) -> str:
        return episode.turns[max(turn.index - 1, 0)].utterance  # "the payment shows as X, not Y" says both values

    score = score_memory(run_with((correction,), echo))
    assert score.recovery_after_correction == Rate(0, 1), "repeating the correction names the withdrawn value too"
