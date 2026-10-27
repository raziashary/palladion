"""The per-model token ledger read from saved books (B08-T08.09)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from benchmark.quota import (
    Call,
    QuotaError,
    Spend,
    days_needed,
    main,
    read_generation_records,
    read_proxy_book,
    read_run,
    remaining,
    remaining_today,
    window_spend,
)

QWEN, GPT = "qwen/qwen3.8-27b", "openai/gpt-oss-120b"
NOW = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)


def stamp(delta: timedelta) -> str:
    return (NOW + delta).isoformat().replace("+00:00", "Z")


def write(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


def generation(model: str, delta: timedelta, prompt: int | None, completion: int | None) -> dict[str, Any]:
    return {
        "requested_model": model,
        "served_model": model if prompt is not None else None,
        "started_at_utc": stamp(delta),
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "status": "OK" if prompt is not None else "RATE_LIMITED",
    }


def proxy(model: str, delta: timedelta, prompt: int, completion: int) -> dict[str, Any]:
    return {
        "at": stamp(delta),
        "model": model,
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "outcome": "OK",
    }


def test_generation_records_give_the_serving_model_and_a_refused_request_costs_nothing(tmp_path: Path) -> None:
    path = write(
        tmp_path / "generation_records.jsonl",
        [generation(QWEN, -timedelta(hours=1), 2000, 300), generation(GPT, -timedelta(minutes=5), None, None)],
    )
    calls = read_generation_records(path)
    assert [(c.model, c.tokens) for c in calls] == [(QWEN, 2300), (GPT, 0)]


def test_a_local_embedding_call_reaches_no_provider_and_is_not_spend(tmp_path: Path) -> None:
    embedding = {"at": stamp(-timedelta(minutes=4)), "outcome": "EMBEDDING", "inputs": 256}
    rows = [proxy(QWEN, -timedelta(minutes=5), 1000, 10), embedding]
    assert [c.tokens for c in read_proxy_book(write(tmp_path / "proxy-E0.jsonl", rows))] == [1010]


def test_an_offline_stand_in_never_counts_against_a_real_model(tmp_path: Path) -> None:
    row = generation(QWEN, -timedelta(minutes=5), 2000, 300) | {"served_model": "offline-stub"}
    spend = window_spend(read_generation_records(write(tmp_path / "generation_records.jsonl", [row])), NOW)
    assert remaining(spend, [QWEN], 200_000) == {QWEN: 200_000}


def test_a_proxy_book_is_read_the_same_way(tmp_path: Path) -> None:
    path = write(tmp_path / "proxy-E3.jsonl", [proxy(QWEN, -timedelta(minutes=30), 5600, 219)])
    assert [(c.model, c.prompt_tokens, c.completion_tokens) for c in read_proxy_book(path)] == [(QWEN, 5600, 219)]


def test_the_window_counts_the_trailing_day_and_excludes_the_start_and_the_future() -> None:
    calls = [
        Call(QWEN, NOW - timedelta(hours=24), 1000, 0, "a"),  # exactly at the start: out
        Call(QWEN, NOW - timedelta(hours=23, minutes=59), 100, 10, "a"),
        Call(QWEN, NOW, 50, 5, "a"),  # at the instant: in
        Call(QWEN, NOW + timedelta(seconds=1), 9999, 0, "a"),  # after it: out
        Call(GPT, NOW - timedelta(hours=2), 400, 40, "a"),
    ]
    spend = window_spend(calls, NOW)
    assert spend[QWEN] == Spend(2, 150, 15) and spend[GPT] == Spend(1, 400, 40)
    assert spend[QWEN].tokens == 165 and window_spend(calls, NOW, hours=1) == {QWEN: Spend(1, 50, 5)}


def test_what_is_left_is_never_negative_and_an_unseen_model_has_the_whole_limit() -> None:
    spend = {QWEN: Spend(10, 190_000, 20_000)}
    assert remaining(spend, [QWEN, GPT], 200_000) == {QWEN: 0, GPT: 200_000}
    assert remaining({QWEN: Spend(1, 100, 0)}, [QWEN], 200_000) == {QWEN: 199_900}
    with pytest.raises(QuotaError, match="at least 1"):
        remaining({}, [QWEN], 0)


def test_days_needed_rounds_up_and_refuses_nonsense() -> None:
    assert days_needed({QWEN: 200_000, GPT: 200_001, "x": 0}, 200_000) == {QWEN: 1, GPT: 2, "x": 0}
    with pytest.raises(QuotaError, match="not negative"):
        days_needed({QWEN: -1}, 200_000)
    with pytest.raises(QuotaError, match="at least 1"):
        days_needed({QWEN: 1}, 0)


def test_a_run_directory_is_read_from_its_generator_records_and_every_proxy_book(tmp_path: Path) -> None:
    write(tmp_path / "generation_records.jsonl", [generation(QWEN, -timedelta(hours=3), 1000, 100)])
    write(tmp_path / "proxy-E3.jsonl", [proxy(QWEN, -timedelta(hours=2), 2000, 200)])
    write(tmp_path / "proxy-E4.jsonl", [proxy(GPT, -timedelta(hours=1), 3000, 300)])
    (tmp_path / "ledger.jsonl").write_text("not a book\n", encoding="utf-8")  # other files are not read
    spend = window_spend(read_run(tmp_path), NOW)
    assert spend[QWEN].tokens == 3300 and spend[GPT].tokens == 3300
    assert read_run(tmp_path / "nowhere") == []


@pytest.mark.parametrize(
    ("row", "message"),
    [
        ({"requested_model": QWEN, "started_at_utc": "yesterday"}, "ISO 8601"),
        ({"requested_model": QWEN, "started_at_utc": "2026-10-27T10:00:00"}, "without a zone"),
        ({"requested_model": QWEN}, "no timestamp"),
        ({"started_at_utc": "2026-10-27T10:00:00Z"}, "names no model"),
    ],
)
def test_a_row_that_cannot_be_read_is_refused_by_name(tmp_path: Path, row: dict[str, Any], message: str) -> None:
    with pytest.raises(QuotaError, match=message):
        read_generation_records(write(tmp_path / "generation_records.jsonl", [row]))


def test_a_book_that_is_not_json_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "proxy-E3.jsonl"
    path.write_text("{broken\n", encoding="utf-8")
    with pytest.raises(QuotaError, match="line 1 is not JSON"):
        read_proxy_book(path)


def test_the_command_line_reports_spent_remaining_and_days(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write(tmp_path / "proxy-E3.jsonl", [proxy(QWEN, -timedelta(hours=1), 150_000, 10_000)])
    code = main(
        [
            "--runs", str(tmp_path), "--daily-limit", "200000", "--at", stamp(timedelta(0)),
            "--models", QWEN, GPT, "--demand", f"{GPT}=450000",
        ]
    )  # fmt: skip
    report = json.loads(capsys.readouterr().out)
    assert code == 0 and report["spent"][QWEN] == {"calls": 1, "tokens": 160_000}
    assert report["remaining"] == {QWEN: 40_000, GPT: 200_000} and report["days_needed"] == {GPT: 3}


def test_the_command_line_refuses_a_bad_book_and_a_bad_demand(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "proxy-E3.jsonl").write_text("[1]\n", encoding="utf-8")
    assert main(["--runs", str(tmp_path), "--daily-limit", "1000"]) == 2
    assert "refused" in capsys.readouterr().err
    good = tmp_path / "ok"
    good.mkdir()
    assert main(["--runs", str(good), "--daily-limit", "1000", "--demand", "no-equals-sign"]) == 2


def test_what_a_model_may_still_spend_today_is_the_cap_less_the_books_of_every_run(tmp_path: Path) -> None:
    books, out = tmp_path / "books", tmp_path / "out"
    other = books / "other-run"
    other.mkdir(parents=True)
    out.mkdir()
    write(other / "proxy-E3.jsonl", [proxy(QWEN, -timedelta(hours=2), 70_000, 5_000)])
    own = generation(QWEN, -timedelta(minutes=30), 20_000, 0)
    write(out / "generation_records.jsonl", [own, generation(GPT, -timedelta(days=2), 99_000, 0)])  # a day-old call
    caps = remaining_today(books, [out], [QWEN, GPT], 150_000, NOW)
    assert caps == {QWEN: 55_000, GPT: 150_000}
    assert remaining_today(tmp_path / "missing", [], [QWEN], 150_000, NOW) == {QWEN: 150_000}


def test_a_directory_named_twice_or_by_another_spelling_is_counted_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    books = tmp_path / "books"
    run = books / "run"
    run.mkdir(parents=True)
    write(run / "generation_records.jsonl", [generation(QWEN, -timedelta(minutes=30), 40_000, 0)])
    monkeypatch.chdir(tmp_path)
    relative = Path("books") / "run"  # the same directory, spelled relative to the working directory
    assert remaining_today(books, [relative, run], [QWEN], 100_000, NOW) == {QWEN: 60_000}
