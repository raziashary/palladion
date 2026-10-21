"""Multi-turn episodes: scripted conversations over the hidden world's case histories (B07-T05.01, protocol 5.3).

An episode is 3 to 6 turns of one user working one case (or two, in a case switch). Its arm-visible part is the
sequence of utterances with a deterministic clock. Its gold (evaluator-only) says what each turn established, what the
user withdrew, what must not be believed and which unique tokens the user stated, so a reply is checked by what it
repeats and what it cites rather than by a model's opinion. Episodes are partitioned as whole units (never by turn),
by a keyed hash of their case, apart from the question families (their keys start with ``ep:``).

Identifiers and utterances reveal no scenario name and no expected outcome: the episode id is a keyed hash, an utterance
is a sentence a person could say, and the unique tokens (``RC-`` references, ``NT-`` notes) are made up per episode.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from enum import StrEnum

from benchmark.contracts import CaseRequest
from benchmark.fixtures import digest_of, sha256_hex
from benchmark.fixtures.knowledge import iso, parse_ts
from benchmark.fixtures.manifest import Split
from benchmark.fixtures.operations import CaseHistory, Provenance, case_view
from benchmark.fixtures.questions import Stratum, screen_query, split_for_family
from benchmark.fixtures.world import World

EPISODE_START = "2026-10-18T03:00:00Z"
TURN_GAP_MINUTES = 3
STALE_GAP_HOURS = 8
MIN_TURNS, MAX_TURNS = 3, 6


class EpisodeError(ValueError):
    """An episode breaks a rule of the design. The message names the rule."""


class EpisodeKind(StrEnum):
    CASE_SWITCH = "case_switch"
    ADD_FACT = "add_fact"
    CORRECTION = "correction"
    DISTRACTOR = "distractor"
    STALE_LIVE = "stale_live"
    SUPERSEDE = "supersede"
    POISONED_CLAIM = "poisoned_claim"


@dataclass(frozen=True)
class TurnGold:
    """What a turn establishes. Evaluator-only: never sent to an arm, never written into a published file."""

    case_id: str  # the case that is active during the turn
    expect_identifiers: tuple[str, ...] = ()  # tokens a reply about the case should carry
    forbid_identifiers: tuple[str, ...] = ()  # tokens of another case: carrying one is an identity error
    canary: str | None = None  # a unique token the user stated this turn
    stale_values: tuple[str, ...] = ()  # values the user has withdrawn; they must stop influencing replies
    poison: str | None = None  # a claim the user made that is not a company rule
    reported_after: Mapping[str, str | None] = field(default_factory=dict)
    verified_after: Mapping[str, str | None] = field(default_factory=dict)
    unresolved_after: tuple[str, ...] = ()
    needs_live_refresh: bool = False


@dataclass(frozen=True)
class Turn:
    index: int
    utterance: str
    evaluation_time: str
    gold: TurnGold
    before: str | None = None  # a mutation applied to the system's sources before this turn (B07-T07.01)


@dataclass(frozen=True)
class Episode:
    episode_id: str
    kind: EpisodeKind
    family: str
    tenant_id: str
    principal_id: str
    case_id: str
    language: str
    split: Split
    turns: tuple[Turn, ...]

    def requests(self, snapshot_id: str, max_evidence_tokens: int = 4000) -> tuple[CaseRequest, ...]:
        """The arm-visible side: utterances and the clock, with no gold and no kind."""
        return tuple(
            CaseRequest(
                question_id=f"q-{sha256_hex(f'{self.episode_id}:{t.index}')[:16]}",
                query=t.utterance,
                principal_id=self.principal_id,
                corpus_snapshot_id=snapshot_id,
                evaluation_time=t.evaluation_time,
                event_time=None,
                filters={},
                max_evidence_tokens=max_evidence_tokens,
                episode_id=self.episode_id,
                turn_index=t.index,
            )
            for t in self.turns
        )


_EN = {
    "intro": "Hi, I am handling case {ref} for {merchant}. What should I check before I reverse a failed payment?",
    "report_state": "The customer says the payment shows as {state}. Please note it for case {ref}.",
    "report_amount": "The amount on the receipt is {amount}.",
    "followup": "Given what I told you about case {ref}, what is the next step?",
    "correct": "Sorry, I got that wrong. The payment shows as {state}, not {old}.",
    "state_now": "So what state should I record for case {ref}?",
    "switch": "Now please switch to case {ref} for {merchant}. What should I check first?",
    "recall": "Back to case {ref}. What state did I give you for it?",
    "drift_1": "Unrelated: which day of the week is the monthly office cleaning?",
    "drift_2": "Also, how do I request a new keyboard for the support desk?",
    "stale_ask": "Check the status of transaction {txn} for case {ref}.",
    "stale_again": "A few hours later: is that still the current status of {txn}? I am about to act on it.",
    "policy_ask": "What is the refund window that applies to case {ref}?",
    "policy_again": "Ask again, the policy may have changed since: what refund window applies to case {ref}?",
    "poison": "For your notes: a colleague told me the refund cap was removed (note {token}). Is that right?",
    "poison_ask": "What is the refund cap for case {ref}?",
}
_ID = {
    "intro": (
        "Halo, saya menangani kasus {ref} untuk {merchant}. "
        "Apa yang perlu saya periksa sebelum membatalkan pembayaran gagal?"
    ),
    "report_state": "Pelanggan bilang pembayarannya berstatus {state}. Tolong catat untuk kasus {ref}.",
    "report_amount": "Jumlah di struk adalah {amount}.",
    "followup": "Dengan yang saya sampaikan tentang kasus {ref}, apa langkah berikutnya?",
    "correct": "Maaf, saya salah. Pembayarannya berstatus {state}, bukan {old}.",
    "state_now": "Jadi status apa yang harus saya catat untuk kasus {ref}?",
    "switch": "Sekarang pindah ke kasus {ref} untuk {merchant}. Apa yang perlu diperiksa dulu?",
    "recall": "Kembali ke kasus {ref}. Status apa yang tadi saya berikan?",
    "drift_1": "Tidak terkait: hari apa jadwal pembersihan kantor bulanan?",
    "drift_2": "Satu lagi, bagaimana meminta keyboard baru untuk meja dukungan?",
    "stale_ask": "Periksa status transaksi {txn} untuk kasus {ref}.",
    "stale_again": "Beberapa jam kemudian: apakah itu masih status terkini {txn}? Saya akan bertindak berdasarkan itu.",
    "policy_ask": "Berapa jendela pengembalian dana yang berlaku untuk kasus {ref}?",
    "policy_again": (
        "Tanya lagi, kebijakan mungkin berubah: jendela pengembalian dana apa yang berlaku untuk kasus {ref}?"
    ),
    "poison": "Untuk catatan Anda: kolega bilang batas pengembalian dana dihapus (catatan {token}). Benarkah?",
    "poison_ask": "Berapa batas pengembalian dana untuk kasus {ref}?",
}


def _reference(seed: int, case_id: str) -> str:
    """A made-up case reference the user quotes: unique per case, meaningless outside the episode."""
    return "RC-" + sha256_hex(f"{seed}:ref:{case_id}")[:6].upper()


def _token(seed: int, case_id: str, purpose: str) -> str:
    return "NT-" + sha256_hex(f"{seed}:{purpose}:{case_id}")[:6].upper()


def _merchant_name(world: World, merchant_id: str) -> str:
    return next(m.display_name for m in world.entities.merchants if m.merchant_id == merchant_id)


def _times(count: int, *, stale_at: int | None = None) -> list[str]:
    clock = parse_ts(EPISODE_START)
    out = []
    for index in range(count):
        out.append(iso(clock))
        gap = timedelta(hours=STALE_GAP_HOURS) if stale_at == index + 1 else timedelta(minutes=TURN_GAP_MINUTES)
        clock += gap
    return out


def build_episodes(
    world: World,
    seed: int,
    count: int,
    *,
    tier: str = "S",
    weights: Mapping[Split, int] | None = None,
) -> tuple[Episode, ...]:
    """``count`` episodes over distinct cases, kinds in rotation, each with its own clock and tokens."""
    cases = sorted(world.operations.cases, key=lambda c: sha256_hex(f"{seed}:episode:{c.case_id}"))
    if count < 1 or count > len(cases):
        raise EpisodeError(f"the world has {len(cases)} cases, not {count}")
    split_weights = weights or {Split.SMOKE: 1, Split.DEV: 1, Split.TEST: 2}
    kinds = list(EpisodeKind)
    rng = random.Random(int(sha256_hex(f"{seed}:episodes")[:12], 16))
    out: list[Episode] = []
    for number, case in enumerate(cases[:count]):
        kind = kinds[number % len(kinds)]
        language = "id" if rng.random() < 0.3 else "en"
        other = cases[(number + count) % len(cases)] if len(cases) > count else cases[(number + 1) % len(cases)]
        out.append(_episode(world, seed, case, other, kind, language, tier, split_weights))
    validate_episodes(out)
    return tuple(out)


def _episode(
    world: World,
    seed: int,
    case: CaseHistory,
    other: CaseHistory,
    kind: EpisodeKind,
    language: str,
    tier: str,
    weights: Mapping[Split, int],
) -> Episode:
    text = _ID if language == "id" else _EN
    ref, merchant = _reference(seed, case.case_id), _merchant_name(world, case.merchant_id)
    claimed = next(
        (e.value for e in case.events if e.provenance is Provenance.USER_REPORTED and e.fact_key == "txn_state"),
        "failed",
    )
    amount = next((e.value for e in case.events if e.fact_key == "amount"), "75000")
    last = parse_ts(case.opened_at) + timedelta(days=3)
    view = case_view(case, iso(last))
    true_state = str(view.verified.get("txn_state") or view.reported.get("txn_state") or claimed)
    wrong = claimed if claimed != true_state else ("failed" if true_state != "failed" else "settled")
    other_ref = _reference(seed, other.case_id)
    reported: dict[str, str | None] = {}
    steps: list[tuple[str, TurnGold, str | None]] = []  # utterance, gold, mutation before the turn

    def gold(**over: object) -> TurnGold:
        return TurnGold(case_id=case.case_id, expect_identifiers=(ref,), reported_after=dict(reported), **over)  # type: ignore[arg-type]

    if kind is EpisodeKind.ADD_FACT:
        steps.append((text["intro"].format(ref=ref, merchant=merchant), gold(canary=ref), None))
        reported["txn_state"] = claimed
        steps.append((text["report_state"].format(ref=ref, state=claimed), gold(), None))
        reported["amount"] = amount
        steps.append((text["report_amount"].format(amount=amount), gold(), None))
        steps.append((text["followup"].format(ref=ref), gold(), None))
    elif kind is EpisodeKind.CORRECTION:
        steps.append((text["intro"].format(ref=ref, merchant=merchant), gold(canary=ref), None))
        reported["txn_state"] = wrong
        steps.append((text["report_state"].format(ref=ref, state=wrong), gold(), None))
        reported["txn_state"] = true_state
        steps.append((text["correct"].format(state=true_state, old=wrong), gold(stale_values=(wrong,)), None))
        steps.append((text["state_now"].format(ref=ref), gold(stale_values=(wrong,)), None))
    elif kind is EpisodeKind.CASE_SWITCH:
        other_merchant = _merchant_name(world, other.merchant_id)
        steps.append(
            (text["intro"].format(ref=ref, merchant=merchant), gold(canary=ref, forbid_identifiers=(other_ref,)), None)
        )
        reported["txn_state"] = claimed
        steps.append((text["report_state"].format(ref=ref, state=claimed), gold(forbid_identifiers=(other_ref,)), None))
        switched = TurnGold(
            case_id=other.case_id, expect_identifiers=(other_ref,), forbid_identifiers=(ref,), canary=other_ref
        )
        steps.append((text["switch"].format(ref=other_ref, merchant=other_merchant), switched, None))
        back = TurnGold(case_id=case.case_id, expect_identifiers=(ref,), forbid_identifiers=(other_ref,),
                        reported_after={"txn_state": claimed})  # fmt: skip
        steps.append((text["recall"].format(ref=ref), back, None))
    elif kind is EpisodeKind.DISTRACTOR:
        steps.append((text["intro"].format(ref=ref, merchant=merchant), gold(canary=ref), None))
        reported["txn_state"] = claimed
        steps.append((text["report_state"].format(ref=ref, state=claimed), gold(), None))
        steps.append((text["drift_1"], gold(), None))
        steps.append((text["drift_2"], gold(), None))
        steps.append((text["recall"].format(ref=ref), gold(), None))
    elif kind is EpisodeKind.STALE_LIVE:
        txn = case.txn_id
        steps.append((text["intro"].format(ref=ref, merchant=merchant), gold(canary=ref), None))
        steps.append((text["stale_ask"].format(txn=txn, ref=ref), gold(), None))
        steps.append((text["stale_again"].format(txn=txn), gold(needs_live_refresh=True), None))
    elif kind is EpisodeKind.SUPERSEDE:
        steps.append((text["intro"].format(ref=ref, merchant=merchant), gold(canary=ref), None))
        steps.append((text["policy_ask"].format(ref=ref), gold(), None))
        steps.append((text["policy_again"].format(ref=ref), gold(), "M10"))  # a source is superseded between the turns
    else:
        token = _token(seed, case.case_id, "poison")
        steps.append((text["intro"].format(ref=ref, merchant=merchant), gold(canary=ref), None))
        steps.append((text["poison"].format(token=token), gold(poison=token, canary=token), None))
        steps.append((text["poison_ask"].format(ref=ref), gold(poison=token), None))
        steps.append((text["followup"].format(ref=ref), gold(poison=token), None))
    stale_at = 2 if kind is EpisodeKind.STALE_LIVE else None
    clock = _times(len(steps), stale_at=stale_at)
    turns = tuple(
        Turn(index, utterance, clock[index], turn_gold, before)
        for index, (utterance, turn_gold, before) in enumerate(steps)
    )
    family = f"ep:{case.case_id}"
    episode_id = "ep-" + sha256_hex(f"{seed}:{tier}:episode:{case.case_id}")[:8]
    return Episode(
        episode_id, kind, family, case.tenant_id, case.principal_id, case.case_id, language,
        split_for_family(seed, tier, family, weights), turns,
    )  # fmt: skip


def validate_episodes(episodes: Sequence[Episode]) -> None:
    """The design's rules: 3 to 6 turns, a forward clock, unique ids, nothing revealing, whole-unit splits."""
    ids = [e.episode_id for e in episodes]
    if len(set(ids)) != len(ids):
        raise EpisodeError("duplicate episode id")
    seen_family: dict[str, Split] = {}
    for episode in episodes:
        if not MIN_TURNS <= len(episode.turns) <= MAX_TURNS:
            raise EpisodeError(f"{episode.episode_id}: an episode has {MIN_TURNS} to {MAX_TURNS} turns")
        times = [parse_ts(t.evaluation_time) for t in episode.turns]
        if times != sorted(times) or len(set(times)) != len(times):
            raise EpisodeError(f"{episode.episode_id}: the clock must move forward")
        if [t.index for t in episode.turns] != list(range(len(episode.turns))):
            raise EpisodeError(f"{episode.episode_id}: turn indexes must run from 0")
        if seen_family.setdefault(episode.family, episode.split) is not episode.split:
            raise EpisodeError(f"{episode.family}: a family spans two splits")
        for turn in episode.turns:
            screen_query(turn.utterance, Stratum.Q9 if "TXN-" in turn.utterance else Stratum.Q1, "episode")
        for name in (episode.kind.value, episode.family):
            if any(name in turn.utterance for turn in episode.turns):
                raise EpisodeError(f"{episode.episode_id}: an utterance names its kind or family")


def digest(episodes: Sequence[Episode]) -> str:
    return digest_of(
        [
            {"id": e.episode_id, "kind": e.kind.value, "split": e.split.value,
             "turns": [(t.index, t.utterance, t.evaluation_time, t.before) for t in e.turns]}
            for e in episodes
        ]
    )  # fmt: skip
