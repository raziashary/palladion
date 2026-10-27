"""A per-model token ledger for the free tier, read from the saved books of every live run (BADR-0044, B08-T08.09).

The provider limits each model to about 200,000 tokens a day. Every live run saves what it spent: the shared generator
writes ``generation_records.jsonl`` (one row per provider request) and a counting proxy writes ``proxy-<arm>.jsonl``.
This module reads those rows, nothing else, and answers three questions before a live day starts: how much each model
has spent in the trailing day, how much is left, and how many days a stated demand needs.

The window is a rolling 24 hours. That is an estimate of the provider's own accounting, which is the authority: a
refusal from the provider is what stops a run (``QUOTA_BLOCKED``), and a ledger that says there is room does not
promise a call will be accepted. A refused request spent nothing and costs nothing here.

``python -m benchmark.quota --runs DIR ... --daily-limit 200000`` prints the state as JSON.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from benchmark.contracts import ContractError

WINDOW_HOURS = 24.0
GENERATION_RECORDS = "generation_records.jsonl"
PROXY_BOOK_GLOB = "proxy-*.jsonl"


class QuotaError(ContractError):
    """A book could not be read as a record of spend."""


@dataclass(frozen=True)
class Call:
    model: str
    at: datetime
    prompt_tokens: int
    completion_tokens: int
    source: str

    @property
    def tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True)
class Spend:
    calls: int
    prompt_tokens: int
    completion_tokens: int

    @property
    def tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


def _moment(value: object, source: str) -> datetime:
    if not isinstance(value, str):
        raise QuotaError(f"{source}: a row has no timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise QuotaError(f"{source}: a row has a timestamp that is not ISO 8601") from None
    if parsed.tzinfo is None:
        raise QuotaError(f"{source}: a row has a timestamp without a zone")
    return parsed.astimezone(UTC)


def _count(value: object) -> int:
    """A token count; a missing one (a refused request) spent nothing."""
    return value if type(value) is int and value >= 0 else 0


def _rows(path: Path) -> Iterable[tuple[int, dict[str, Any]]]:
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            raise QuotaError(f"{path.name} line {number} is not JSON") from None
        if not isinstance(row, dict):
            raise QuotaError(f"{path.name} line {number} is not a record")
        yield number, row


def read_generation_records(path: Path) -> list[Call]:
    """The shared generator's rows: the model the provider served (else the one asked for) and the usage it reported."""
    calls = []
    for number, row in _rows(path):
        model = row.get("served_model") or row.get("requested_model")
        if not isinstance(model, str):
            raise QuotaError(f"{path.name} line {number} names no model")
        calls.append(
            Call(
                model,
                _moment(row.get("started_at_utc"), f"{path.name} line {number}"),
                _count(row.get("prompt_tokens")),
                _count(row.get("completion_tokens")),
                path.name,
            )
        )
    return calls


def read_proxy_book(path: Path) -> list[Call]:
    """A counting proxy's rows."""
    calls = []
    for number, row in _rows(path):
        model = row.get("model")
        if not isinstance(model, str):
            raise QuotaError(f"{path.name} line {number} names no model")
        calls.append(
            Call(
                model,
                _moment(row.get("at"), f"{path.name} line {number}"),
                _count(row.get("prompt_tokens")),
                _count(row.get("completion_tokens")),
                path.name,
            )
        )
    return calls


def read_run(run_dir: Path) -> list[Call]:
    """Every call a run directory saved, from its generator records and every proxy book in it."""
    calls: list[Call] = []
    records = run_dir / GENERATION_RECORDS
    if records.exists():
        calls += read_generation_records(records)
    for book in sorted(run_dir.glob(PROXY_BOOK_GLOB)):
        calls += read_proxy_book(book)
    return calls


def window_spend(calls: Iterable[Call], now: datetime, *, hours: float = WINDOW_HOURS) -> dict[str, Spend]:
    """Per model, what the calls in the trailing window cost. A call after ``now`` is not counted."""
    start = now - timedelta(hours=hours)
    totals: dict[str, list[int]] = {}
    for call in calls:
        if start < call.at <= now:
            row = totals.setdefault(call.model, [0, 0, 0])
            row[0] += 1
            row[1] += call.prompt_tokens
            row[2] += call.completion_tokens
    return {model: Spend(*row) for model, row in sorted(totals.items())}


def remaining(spend: Mapping[str, Spend], models: Sequence[str], daily_limit: int) -> dict[str, int]:
    """Tokens each named model may still spend in the window; never negative."""
    if daily_limit < 1:
        raise QuotaError("the daily limit is at least 1 token")
    return {model: max(0, daily_limit - spend[model].tokens) if model in spend else daily_limit for model in models}


def days_needed(demand: Mapping[str, int], daily_limit: int) -> dict[str, int]:
    """Whole days each model's demand needs at the daily limit (a model with no demand needs none)."""
    if daily_limit < 1:
        raise QuotaError("the daily limit is at least 1 token")
    if any(tokens < 0 for tokens in demand.values()):
        raise QuotaError("a demand is not negative")
    return {model: math.ceil(tokens / daily_limit) for model, tokens in sorted(demand.items())}


def _demand(items: Sequence[str]) -> dict[str, int]:
    demand: dict[str, int] = {}
    for item in items:
        model, _, tokens = item.rpartition("=")
        if not model or not tokens.isdigit():
            raise QuotaError(f"a demand reads MODEL=TOKENS, not {item!r}")
        demand[model] = demand.get(model, 0) + int(tokens)
    return demand


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--runs", type=Path, nargs="+", required=True, help="run directories whose books are read")
    parser.add_argument("--daily-limit", type=int, required=True)
    parser.add_argument("--models", nargs="+", default=None, help="models to report on (default: every model seen)")
    parser.add_argument("--at", default=None, help="the instant to measure at, ISO 8601 with a zone (default: now)")
    parser.add_argument("--demand", nargs="*", default=(), metavar="MODEL=TOKENS", help="work still to do")
    options = parser.parse_args(argv)
    try:
        now = _moment(options.at, "--at") if options.at else datetime.now(UTC)
        calls = [call for run in options.runs for call in read_run(run)]
        spend = window_spend(calls, now)
        models = list(options.models) if options.models else sorted(spend)
        report: dict[str, Any] = {
            "at": now.isoformat().replace("+00:00", "Z"),
            "window_hours": WINDOW_HOURS,
            "daily_limit": options.daily_limit,
            "spent": {m: {"calls": s.calls, "tokens": s.tokens} for m, s in spend.items()},
            "remaining": remaining(spend, models, options.daily_limit),
        }
        if options.demand:
            report["days_needed"] = days_needed(_demand(options.demand), options.daily_limit)
    except (QuotaError, OSError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
