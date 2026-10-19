"""Stratified pilot label audit (B02-T07.02): packet blinding, statistics and the model pass through the real pool."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from benchmark.config import load_benchmark_config
from benchmark.fixtures import canonical_json
from benchmark.fixtures.audit import (
    CONTEXT_CHARS,
    LABELS,
    MAX_LLM_CALLS,
    AuditError,
    AuditItem,
    Packet,
    assignment_for,
    audit_folder,
    build_packet,
    build_report,
    calls_used,
    cohens_kappa,
    excerpt,
    load_packet,
    main,
    parse_label,
    prompt_for,
    read_labels,
    run_llm_pass,
    sample_questions,
    summarise,
    write_packet,
)
from benchmark.fixtures.documents import Category, Document, make_document
from benchmark.fixtures.manifest import find_barrier_markers
from benchmark.fixtures.questions import Answerability, GoldRecord, Stratum
from benchmark.fixtures.world import World
from benchmark.generator import GeneratorPool, TransportResponse

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = load_benchmark_config(ROOT / "configs" / "benchmark.yaml").generator
SEED = 7


@pytest.fixture(scope="module")
def packet(s_world: World, s_corpus: tuple[Document, ...], s_questions: tuple[GoldRecord, ...]) -> Packet:
    return build_packet(s_questions, s_corpus, s_world, SEED)


# --------------------------------------------------------------------------- statistics


def test_kappa_matches_hand_computed_cases() -> None:
    assert cohens_kappa(["a", "b", "a", "b"], ["a", "b", "a", "b"]) == 1.0
    assert cohens_kappa(["a", "b"], ["b", "a"]) == -1.0
    # observed 3/4, expected (2*1 + 2*3)/16 = 1/2, so kappa = (0.75 - 0.5) / 0.5
    assert cohens_kappa(["x", "x", "y", "y"], ["x", "y", "y", "y"]) == pytest.approx(0.5)


def test_kappa_is_undefined_when_both_sides_always_say_the_same_thing() -> None:
    assert cohens_kappa(["a", "a", "a"], ["a", "a", "a"]) is None


def test_kappa_rejects_mismatched_or_empty_input() -> None:
    with pytest.raises(AuditError):
        cohens_kappa(["a"], ["a", "b"])
    with pytest.raises(AuditError):
        cohens_kappa([], [])


def test_a_shuffled_annotator_scores_lower_than_a_perfect_one() -> None:
    gold = {f"a-{i}": LABELS[i % 3] for i in range(30)}
    perfect = summarise(gold, dict(gold), dict(gold), {})
    shuffled_labels = [LABELS[(i + 1) % 3] for i in range(30)]
    shuffled = summarise(gold, dict(zip(gold, shuffled_labels, strict=True)), dict(gold), {})
    assert perfect.owner_vs_gold == 1.0 and perfect.kappa_owner_llm == 1.0 and perfect.status == "COMPLETE"
    assert shuffled.owner_vs_gold == 0.0 and (shuffled.kappa_owner_llm or 0) < 0.1 and shuffled.disagreements


def test_the_report_states_denominators_and_leaves_out_invalid_model_labels() -> None:
    gold = {"a-1": "ANSWERABLE", "a-2": "CONFLICT", "a-3": "UNANSWERABLE", "a-4": "PARTIAL"}
    owner = {"a-1": "ANSWERABLE", "a-2": "CONFLICT", "a-3": "ANSWERABLE"}
    llm = {"a-1": "ANSWERABLE", "a-2": "INVALID", "a-3": "UNANSWERABLE", "a-4": "PARTIAL"}
    report = summarise(gold, owner, llm, {"a-1": "sufficient", "a-2": "partial"})
    assert (report.items, report.owner_labelled, report.llm_labelled, report.llm_invalid) == (4, 3, 3, 1)
    assert report.owner_vs_gold == pytest.approx(2 / 3)  # three owner labels, two agree with gold
    assert report.llm_vs_gold == 1.0  # the invalid label is excluded, not counted as wrong
    assert report.owner_vs_llm == pytest.approx(0.5)  # a-1 and a-3 are the only items both labelled validly
    assert report.evidence_checks == {"sufficient": 1, "partial": 1}
    assert [d["item_id"] for d in report.disagreements] == ["a-3"]
    assert report.status == "PARTIAL"


@pytest.mark.parametrize(
    "owner,llm,status",
    [
        ({}, {}, "PENDING_OWNER_LABELS"),
        ({"a-1": "ANSWERABLE"}, {}, "PENDING_MODEL_LABELS"),
        ({"a-1": "ANSWERABLE"}, {"a-1": "ANSWERABLE"}, "COMPLETE"),
    ],
)
def test_status_reflects_which_pass_is_missing(owner: dict[str, str], llm: dict[str, str], status: str) -> None:
    assert summarise({"a-1": "ANSWERABLE"}, owner, llm, {}).status == status


# --------------------------------------------------------------------------- the packet


def test_the_sample_is_stratified_seeded_and_covers_each_answerability_present(
    s_questions: tuple[GoldRecord, ...],
) -> None:
    sample = sample_questions(s_questions, SEED, 3)
    assert Counter(r.stratum for r in sample) == {s: 3 for s in Stratum}
    for stratum in Stratum:
        present = {r.answerability for r in s_questions if r.stratum is stratum}
        taken = {r.answerability for r in sample if r.stratum is stratum}
        assert taken == present or len(taken) == 3
    assert sample == sample_questions(s_questions, SEED, 3)
    assert sample != sample_questions(s_questions, SEED + 1, 3)


def test_the_packet_has_no_gold_field_and_nothing_the_barrier_forbids(packet: Packet) -> None:
    assert len(packet.items) == 30 and len(packet.key) == 30
    for item in packet.items:
        plain = item.to_dict()
        assert set(plain) == {
            "item_id",
            "query",
            "principal_role",
            "principal_tenant",
            "evaluation_time",
            "live_read",
            "context",
        }
        assert find_barrier_markers(json.dumps(plain)) == []
        assert item.item_id.startswith("a-") and not item.item_id.startswith("q-")


def test_blocked_items_show_an_internal_document_as_not_visible_to_the_principal(
    packet: Packet, s_questions: tuple[GoldRecord, ...]
) -> None:
    by_question = {r.question_id: r for r in s_questions}
    blocked = [
        i for i in packet.items if by_question[packet.key[i.item_id]].answerability is Answerability.BLOCKED_BY_ACL
    ]
    assert blocked and all(any(not c.visible_to_principal for c in i.context) for i in blocked)


def test_live_items_carry_the_tool_output_and_not_the_expected_result(
    packet: Packet, s_questions: tuple[GoldRecord, ...]
) -> None:
    by_question = {r.question_id: r for r in s_questions}
    live = [i for i in packet.items if by_question[packet.key[i.item_id]].stratum is Stratum.Q9]
    assert live and all(i.live_read and "mode" not in i.live_read and "status" in i.live_read for i in live)
    assert all(i.live_read is None for i in packet.items if i not in live)


def test_the_prompt_shows_what_the_owner_sees_and_none_of_the_gold(
    packet: Packet, s_questions: tuple[GoldRecord, ...]
) -> None:
    by_question = {r.question_id: r for r in s_questions}
    for item in packet.items:
        gold = by_question[packet.key[item.item_id]]
        text = " ".join(m["content"] for m in prompt_for(item))
        assert (item.query in text and "NOT visible" in text) or all(c.visible_to_principal for c in item.context)
        assert gold.question_id not in text and not any(claim in text for claim in gold.required_claims)


def test_the_packet_round_trips_through_its_files(
    tmp_path: Path, packet: Packet, s_questions: tuple[GoldRecord, ...]
) -> None:
    write_packet(tmp_path, packet, s_questions)
    assert load_packet(tmp_path) == list(packet.items)
    key = json.loads((audit_folder(tmp_path) / "key.json").read_text(encoding="utf-8"))
    assert set(key) == set(packet.key) and all("answerability" in v and "cited" in v for v in key.values())
    assert "answerability" not in (audit_folder(tmp_path) / "packet.jsonl").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- parsing


@pytest.mark.parametrize("label", LABELS)
def test_each_known_label_parses(label: str) -> None:
    assert parse_label(json.dumps({"answerability": label})) == label


@pytest.mark.parametrize(
    "reply",
    [
        None,
        "",
        "ANSWERABLE",
        '{"answerability": "MAYBE"}',
        '{"label": "ANSWERABLE"}',
        '["ANSWERABLE"]',
        '{"answerability": 3}',
    ],
)
def test_anything_else_is_invalid_rather_than_guessed(reply: str | None) -> None:
    assert parse_label(reply) == "INVALID"


# --------------------------------------------------------------------------- the model pass through the real pool


@dataclass
class EchoTransport:
    """Answers every call with a fixed label for the model that was asked, and records the payloads."""

    reply: str = '{"answerability": "ANSWERABLE"}'
    payloads: list[dict[str, Any]] = field(default_factory=list)

    def post(self, payload: Any) -> TransportResponse:
        self.payloads.append(dict(payload))
        body = {
            "model": payload["model"],
            "choices": [{"message": {"content": self.reply}}],
            "usage": {"prompt_tokens": 900, "completion_tokens": 12, "total_tokens": 912},
        }
        return TransportResponse(200, {}, json.dumps(body).encode())


def pool_for(items: list[AuditItem], transport: EchoTransport, budget: int = MAX_LLM_CALLS) -> GeneratorPool:
    return GeneratorPool(
        SETTINGS, transport, enabled=True, assignment=assignment_for(items, SETTINGS, SEED), call_budget=budget
    )


def test_assignment_spreads_items_evenly_over_the_approved_models(packet: Packet) -> None:
    counts = Counter(assignment_for(list(packet.items), SETTINGS, SEED).values())
    assert set(counts) == set(SETTINGS.models) and max(counts.values()) - min(counts.values()) <= 1


def test_one_call_per_item_goes_through_the_pool_with_the_assigned_model(packet: Packet) -> None:
    items = list(packet.items)
    transport = EchoTransport()
    pool = pool_for(items, transport)
    labels = run_llm_pass(items, pool)
    assert len(transport.payloads) == 30 == len(pool.records) and set(labels.values()) == {"ANSWERABLE"}
    assert {r.requested_model for r in pool.records} == set(SETTINGS.models)
    assert all(r.status == "OK" and r.model_matches_request for r in pool.records)
    assert all(p["messages"][1]["content"].startswith("Question: ") for p in transport.payloads)


def test_a_reply_that_is_not_a_label_is_recorded_as_invalid(packet: Packet) -> None:
    items = list(packet.items)[:3]
    labels = run_llm_pass(items, pool_for(items, EchoTransport(reply="I think so")))
    assert set(labels.values()) == {"INVALID"}


def test_the_call_budget_is_enforced_and_over_budget_items_are_invalid_not_dropped(packet: Packet) -> None:
    items = list(packet.items)[:5]
    transport = EchoTransport()
    labels = run_llm_pass(items, pool_for(items, transport, budget=2))
    assert len(transport.payloads) == 2 and len(labels) == 5
    assert Counter(labels.values()) == {"ANSWERABLE": 2, "INVALID": 3}


# --------------------------------------------------------------------------- command line


def test_the_model_pass_is_refused_without_the_enable_flag_and_reads_no_credential(
    tmp_path: Path, packet: Packet, s_questions: tuple[GoldRecord, ...], capsys: pytest.CaptureFixture[str]
) -> None:
    write_packet(tmp_path, packet, s_questions)
    missing_env = tmp_path / "no.env"
    assert main(["llm", "--root", str(tmp_path), "--env-file", str(missing_env)]) == 2
    assert "REFUSED" in capsys.readouterr().err and not (audit_folder(tmp_path) / "llm_labels.jsonl").exists()


def test_the_model_pass_refuses_a_packet_over_the_authorised_budget(
    tmp_path: Path, packet: Packet, s_questions: tuple[GoldRecord, ...], capsys: pytest.CaptureFixture[str]
) -> None:
    write_packet(tmp_path, packet, s_questions)
    big = (audit_folder(tmp_path) / "packet.jsonl").read_text(encoding="utf-8")
    (audit_folder(tmp_path) / "packet.jsonl").write_text(big * 2, encoding="utf-8")
    assert main(["llm", "--root", str(tmp_path), "--enable-live", "--env-file", str(tmp_path / "no.env")]) == 2
    assert "leaves 40 calls" in capsys.readouterr().err


def gold_sha(root: Path, item: str) -> str:
    key = json.loads((audit_folder(root) / "key.json").read_text(encoding="utf-8"))
    digest: str = key[item]["gold_sha256"]
    return digest


def test_the_report_command_reads_owner_and_model_labels_and_writes_the_statistics(
    tmp_path: Path, packet: Packet, s_questions: tuple[GoldRecord, ...], capsys: pytest.CaptureFixture[str]
) -> None:
    write_packet(tmp_path, packet, s_questions)
    assert build_report(tmp_path).status == "PENDING_OWNER_LABELS"
    key = json.loads((audit_folder(tmp_path) / "key.json").read_text(encoding="utf-8"))
    owner = "".join(
        canonical_json(
            {
                "item_id": i,
                "answerability": v["answerability"],
                "evidence_check": "sufficient",
                "gold_sha256": v["gold_sha256"],
            }
        )
        + "\n"
        for i, v in key.items()
    )
    llm = "".join(canonical_json({"item_id": i, "answerability": "ANSWERABLE"}) + "\n" for i in key)
    (audit_folder(tmp_path) / "owner_labels.jsonl").write_text(owner, encoding="utf-8")
    (audit_folder(tmp_path) / "llm_labels.jsonl").write_text(llm, encoding="utf-8")
    assert main(["report", "--root", str(tmp_path)]) == 0
    written = json.loads((audit_folder(tmp_path) / "audit_report.json").read_text(encoding="utf-8"))
    assert (
        written["status"] == "COMPLETE"
        and written["owner_vs_gold"] == 1.0
        and written["evidence_checks"] == {"sufficient": 30}
    )
    assert 0 < written["llm_vs_gold"] < 1 and written["disagreements"]
    assert '"owner_labelled": 30' in capsys.readouterr().out


def test_labels_for_an_unknown_item_are_refused(
    tmp_path: Path, packet: Packet, s_questions: tuple[GoldRecord, ...]
) -> None:
    write_packet(tmp_path, packet, s_questions)
    (audit_folder(tmp_path) / "owner_labels.jsonl").write_text(
        canonical_json({"item_id": "a-nope", "answerability": "CONFLICT"}) + "\n", encoding="utf-8"
    )
    with pytest.raises(AuditError, match="not in the packet"):
        build_report(tmp_path)


# --------------------------------------------------------------------------- excerpts


def test_an_authoritative_excerpt_keeps_its_status_and_rule_clauses(s_corpus: tuple[Document, ...]) -> None:
    doc = next(d for d in s_corpus if d.authoritative and "\n4.1 " in d.text)
    shown = excerpt(doc, "unrelated words only")
    assert "- Status:" in shown and any(line.startswith("4.1 ") for line in shown.split("\n"))
    assert len(shown) <= CONTEXT_CHARS and "FICTIONAL" not in shown


def test_a_support_excerpt_prefers_lines_that_match_the_question(s_corpus: tuple[Document, ...]) -> None:
    doc = next(d for d in s_corpus if d.title.startswith("Support ticket") and not d.tags)
    marker = doc.text.split("\n")[-4]
    query = " ".join(marker.split()[:6])
    assert marker in excerpt(doc, query)
    assert len(excerpt(doc, query)) <= CONTEXT_CHARS


def test_every_authoritative_document_in_a_packet_shows_its_rule_clause(packet: Packet) -> None:
    shown = [c for item in packet.items for c in item.context if c.registry_state in ("approved", "retired", "draft")]
    assert shown and all("\n4." in "\n" + c.excerpt for c in shown)


# --------------------------------------------------------------------------- the owner's worksheet and label file


def test_writing_a_packet_creates_a_readable_worksheet_and_a_blank_label_file(
    tmp_path: Path, packet: Packet, s_questions: tuple[GoldRecord, ...]
) -> None:
    write_packet(tmp_path, packet, s_questions)
    sheet = (audit_folder(tmp_path) / "worksheet.md").read_text(encoding="utf-8")
    assert all(item.item_id in sheet and item.query in sheet for item in packet.items)
    assert "Labels: ANSWERABLE" in sheet and "key.json" in sheet
    blank = read_labels(audit_folder(tmp_path) / "owner_labels.jsonl")
    assert set(blank) == {i.item_id for i in packet.items} and all(r["answerability"] == "" for r in blank.values())
    assert build_report(tmp_path).status == "PENDING_OWNER_LABELS"


def test_a_rewritten_packet_never_overwrites_the_owners_labels(
    tmp_path: Path, packet: Packet, s_questions: tuple[GoldRecord, ...]
) -> None:
    write_packet(tmp_path, packet, s_questions)
    labels = audit_folder(tmp_path) / "owner_labels.jsonl"
    labels.write_text(
        canonical_json({"item_id": packet.items[0].item_id, "answerability": "CONFLICT"}) + "\n", encoding="utf-8"
    )
    write_packet(tmp_path, packet, s_questions)
    assert "CONFLICT" in labels.read_text(encoding="utf-8")


def test_an_owner_label_outside_the_six_is_refused_and_a_blank_one_is_ignored(
    tmp_path: Path, packet: Packet, s_questions: tuple[GoldRecord, ...]
) -> None:
    write_packet(tmp_path, packet, s_questions)
    labels = audit_folder(tmp_path) / "owner_labels.jsonl"
    first, second = packet.items[0].item_id, packet.items[1].item_id
    labels.write_text(
        canonical_json(
            {
                "item_id": first,
                "answerability": "CONFLICT",
                "evidence_check": "partial",
                "gold_sha256": gold_sha(tmp_path, first),
            }
        )
        + "\n"
        + canonical_json({"item_id": second, "answerability": ""})
        + "\n",
        encoding="utf-8",
    )
    report = build_report(tmp_path)
    assert report.owner_labelled == 1 and report.evidence_checks == {"partial": 1}
    labels.write_text(canonical_json({"item_id": first, "answerability": "Maybe"}) + "\n", encoding="utf-8")
    with pytest.raises(AuditError, match="six answerability labels"):
        build_report(tmp_path)
    bad_check = {
        "item_id": first,
        "answerability": "CONFLICT",
        "evidence_check": "ok",
        "gold_sha256": gold_sha(tmp_path, first),
    }
    labels.write_text(canonical_json(bad_check) + "\n", encoding="utf-8")
    with pytest.raises(AuditError, match="evidence check"):
        build_report(tmp_path)


def test_packet_excerpts_are_the_selected_lines_not_a_prefix(packet: Packet, s_corpus: tuple[Document, ...]) -> None:
    docs = {d.doc_id: d for d in s_corpus}
    checked = 0
    for item in packet.items:
        for c in item.context:
            assert c.excerpt == excerpt(docs[c.doc_id], item.query)
            checked += c.excerpt != docs[c.doc_id].text[: len(c.excerpt)]
    assert checked > 20  # most excerpts differ from the document's opening, so a prefix cut would be caught


def test_an_authoritative_rule_clause_far_from_the_top_is_still_shown() -> None:
    filler = "\n".join(f"{n} {'filler ' * 30}" for n in range(1, 8))
    text = f"> FICTIONAL notice\n\n# Title\n\n- Status: approved\n\n{filler}\n4.1 The rule says seventy two hours.\n"
    deep = make_document("POL-1@v1", Category.POLICY_CLAUSES, "Title", text, "en", source_version_id="POL-1@v1")
    assert text.index("\n4.1 ") > CONTEXT_CHARS
    shown = excerpt(deep, "anything").split("\n")
    assert "- Status: approved" in shown and "4.1 The rule says seventy two hours." in shown
    assert not any(line.startswith(("> ", "# ")) for line in shown)


def test_an_owner_label_made_against_changed_gold_is_refused(
    tmp_path: Path, packet: Packet, s_questions: tuple[GoldRecord, ...]
) -> None:
    write_packet(tmp_path, packet, s_questions)
    item = packet.items[0].item_id
    labels = audit_folder(tmp_path) / "owner_labels.jsonl"
    row = {"item_id": item, "answerability": "CONFLICT", "evidence_check": "", "gold_sha256": gold_sha(tmp_path, item)}
    labels.write_text(canonical_json(row) + "\n", encoding="utf-8")
    assert build_report(tmp_path).owner_labelled == 1
    labels.write_text(canonical_json({**row, "gold_sha256": "0" * 64}) + "\n", encoding="utf-8")
    with pytest.raises(AuditError, match="gold that has since changed"):
        build_report(tmp_path)
    labels.write_text(canonical_json({k: v for k, v in row.items() if k != "gold_sha256"}) + "\n", encoding="utf-8")
    with pytest.raises(AuditError, match="lacks its gold_sha256"):
        build_report(tmp_path)


def test_a_second_model_pass_cannot_overwrite_the_first_or_exceed_the_cumulative_budget(
    tmp_path: Path, packet: Packet, s_questions: tuple[GoldRecord, ...], capsys: pytest.CaptureFixture[str]
) -> None:
    write_packet(tmp_path, packet, s_questions)
    folder = audit_folder(tmp_path)
    (folder / "llm_labels.jsonl").write_text("", encoding="utf-8")
    assert main(["llm", "--root", str(tmp_path), "--enable-live", "--env-file", str(tmp_path / "no.env")]) == 2
    assert "already recorded" in capsys.readouterr().err
    (folder / "llm_labels.jsonl").unlink()
    earlier = folder / "pass1"
    earlier.mkdir()
    (earlier / "llm_calls.jsonl").write_text("{}\n" * 60, encoding="utf-8")
    assert calls_used(folder) == 60
    assert main(["llm", "--root", str(tmp_path), "--enable-live", "--env-file", str(tmp_path / "no.env")]) == 2
    assert "leaves 20 calls" in capsys.readouterr().err
