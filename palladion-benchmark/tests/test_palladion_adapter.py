"""R7a: the HTTP-only Palladion adapter against a stand-in server, and against the real isolated runtime."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any, cast

import httpx
import pytest

from benchmark.adapters.common import AdapterError, Condition, PublishedView
from benchmark.adapters.palladion import (
    TABLE_FILE,
    PalladionArm,
    PrincipalMap,
    utf8_to_character_offsets,
)
from benchmark.contracts import (
    ArmUnavailable,
    CapabilityUnsupported,
    ContractError,
    RetrievalRequest,
    RetrieverAdapter,
    RunStatus,
    TransientInfrastructureError,
    classify_exception,
)
from benchmark.fixtures.entities import Principal
from benchmark.fixtures.manifest import IdentityManifest, ManifestRecord

ROOT = Path(__file__).resolve().parents[1]
TOKENS = {"reader-a": "tok-reader", "uploader-a": "tok-uploader", "admin-a": "tok-admin"}
IDENTITY = IdentityManifest(
    (), (), (Principal("P-1", "T-1", "engineer", "One"), Principal("P-2", "T-2", "engineer", "Two"))
)
TEXTS = {
    "D1": "Rule one: refunds within 72 hours.\n",
    "D2": "Ünïcode ✓ rule two: escalate above five million.\n",
    "D3": "Restricted to tenant two.\n",
    "DRAFT": "A draft memo.\n",
    "OLD": "Withdrawn policy text.\n",
}


def record(doc_id: str, state: str, tenants: tuple[str, ...] = (), valid_to: str | None = None) -> ManifestRecord:
    return ManifestRecord(
        doc_id, f"docs/{doc_id}.md", hashlib.sha256(TEXTS[doc_id].encode()).hexdigest(),
        f"Title {doc_id}", "policy", state, None, None, None, None, valid_to, None, None, tenants, (), 0,
    )  # fmt: skip


def view(tmp_path: Path) -> PublishedView:
    records = [
        record("D1", "approved"),
        record("D2", "non_normative"),
        record("D3", "approved", tenants=("T-2",)),
        record("DRAFT", "draft"),
        record("OLD", "withdrawn"),
    ]
    return PublishedView(tmp_path, records, IDENTITY, TEXTS)


def passage(doc_text: str, revision: str, start_char: int, end_char: int) -> dict[str, Any]:
    text = doc_text[start_char:end_char]
    start = len(doc_text[:start_char].encode())
    return {
        "citation_id": f"chunk_{revision}_{start}",
        "revision_id": revision,
        "section_id": "root",
        "start_byte": start,
        "end_byte": start + len(text.encode()),
        "text": text,
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
    }


def request(query: str = "refund", principal: str = "P-1", limit: int = 10, budget: int = 4000) -> RetrievalRequest:
    return RetrievalRequest(
        "q-0000000000000001", query, principal, "snap", "2026-10-18T03:00:00Z", None, {}, limit, budget
    )


class Palladion:
    """A stand-in HTTP server: records calls, answers searches from a script, hands out revision ids."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []  # (method, path, token)
        self.search_body: dict[str, Any] = {"status": "OK", "warnings": [], "passages": []}
        self.search_status = 200
        self.upload_status = 201
        self.counter = 0

    def handle(self, http: httpx.Request) -> httpx.Response:
        token = http.headers.get("authorization", "").removeprefix("Bearer ")
        self.calls.append((http.method, http.url.path, token))
        if http.url.path == "/search":
            return httpx.Response(self.search_status, json=self.search_body)
        if http.url.path == "/sources":
            self.counter += 1
            return httpx.Response(self.upload_status, json={"revision_id": f"rev_{self.counter}", "state": "STORED"})
        if http.url.path.endswith(("/approve", "/revoke")):
            return httpx.Response(200, json={})
        if http.url.path == "/index-health":
            return httpx.Response(200, json={"warnings": ["COVERAGE_SCOPE_TRUNCATED"], "accepted_source_count": 3})
        return httpx.Response(404)


def arm(server: Palladion, tmp_path: Path, **kwargs: Any) -> PalladionArm:
    client = httpx.Client(transport=httpx.MockTransport(server.handle))
    built = PalladionArm(view(tmp_path), "http://palladion.test", TOKENS, client=client, **kwargs)
    built.map_revisions({"rev_D1": "D1", "rev_D2": "D2", "rev_D3": "D3"})
    return built


# --------------------------------------------------------------------------- no import of Palladion


def test_no_module_of_the_benchmark_imports_palladion() -> None:
    offenders: list[str] = []
    for path in sorted((ROOT / "benchmark").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else []
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names.append(node.module)
            offenders += [f"{path.name}: {n}" for n in names if n.split(".")[0] in ("evidence_agent", "palladion")]
    assert offenders == []


# --------------------------------------------------------------------------- limits and run states


def test_k_above_palladions_limit_is_unsupported_not_capped(tmp_path: Path) -> None:
    server = Palladion()
    with pytest.raises(CapabilityUnsupported) as caught:
        arm(server, tmp_path).retrieve(request(limit=20))
    assert classify_exception(caught.value)[0] is RunStatus.FEATURE_NOT_SUPPORTED
    assert server.calls == [], "no call is made for a request that cannot be honoured"


def test_an_unreachable_server_is_not_run_and_a_timeout_is_a_timeout(tmp_path: Path) -> None:
    def refuse(http: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=http)

    def slow(http: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=http)

    for handler, error, status in (
        (refuse, ArmUnavailable, RunStatus.NOT_RUN),
        (slow, TimeoutError, RunStatus.TIMEOUT),
    ):
        client = httpx.Client(transport=httpx.MockTransport(handler))
        built = PalladionArm(view(tmp_path), "http://palladion.test", TOKENS, client=client)
        built.map_revisions({"rev_D1": "D1"})
        with pytest.raises(error) as caught:
            built.retrieve(request())
        assert classify_exception(caught.value)[0] is status


@pytest.mark.parametrize(
    ("body", "mode", "error"),
    [
        ({"status": "UNAVAILABLE", "warnings": ["INDEX_UNAVAILABLE"], "passages": []}, "hybrid", ArmUnavailable),
        ({"status": "DEGRADED", "warnings": ["INDEX_MANIFEST_MISMATCH"], "passages": []}, "hybrid", ArmUnavailable),
        ({"status": "DEGRADED", "warnings": ["RERANK_UNAVAILABLE"], "passages": []}, "reranked", ArmUnavailable),
        (
            {"status": "DEGRADED", "warnings": ["ACCEPTED_BUT_UNINDEXED"], "passages": []},
            "hybrid",
            TransientInfrastructureError,
        ),
    ],
)
def test_a_response_that_is_not_a_usable_answer_is_a_run_state_never_an_empty_list(
    tmp_path: Path, body: dict[str, Any], mode: str, error: type[Exception]
) -> None:
    server = Palladion()
    server.search_body = body
    with pytest.raises(error):
        arm(server, tmp_path, mode=mode).retrieve(request())


def test_http_errors_map_to_run_states(tmp_path: Path) -> None:
    server = Palladion()
    server.search_status = 503
    with pytest.raises(TransientInfrastructureError):
        arm(server, tmp_path).retrieve(request())
    server.search_status = 403
    with pytest.raises(ContractError):
        arm(server, tmp_path).retrieve(request())


def test_warnings_that_do_not_invalidate_the_answer_are_notes(tmp_path: Path) -> None:
    server = Palladion()
    server.search_body = {
        "status": "DEGRADED",
        "warnings": ["COVERAGE_SCOPE_TRUNCATED"],
        "passages": [passage(TEXTS["D1"], "rev_D1", 0, 12)],
    }
    built = arm(server, tmp_path)
    assert len(built.retrieve(request())) == 1 and built.last_notes["palladion_warnings"] == [
        "COVERAGE_SCOPE_TRUNCATED"
    ]
    server.search_body = {"status": "DEGRADED", "warnings": ["EXACT_IDENTIFIER_NOT_FOUND"], "passages": []}
    assert built.retrieve(request("MS-9999")) == [] and built.last_notes["palladion_warnings"] == [
        "EXACT_IDENTIFIER_NOT_FOUND"
    ]


def test_a_reranked_request_to_a_server_with_a_reranker_is_accepted(tmp_path: Path) -> None:
    server = Palladion()
    server.search_body = {"status": "OK", "warnings": [], "passages": [passage(TEXTS["D1"], "rev_D1", 0, 12)]}
    hits = arm(server, tmp_path, mode="reranked").retrieve(request())
    assert hits[0].retrieval_channel == "palladion_reranked"


# --------------------------------------------------------------------------- mapping


def test_passages_map_to_published_documents_with_character_offsets_and_native_citation(tmp_path: Path) -> None:
    server = Palladion()
    text = TEXTS["D2"]
    server.search_body = {"status": "OK", "warnings": [], "passages": [passage(text, "rev_D2", 6, 20)]}
    (hit,) = arm(server, tmp_path).retrieve(request())
    assert hit.source_document_id == "D2" and hit.locator == "chars:6-20" and hit.content == text[6:20]
    assert hit.native_citation_supported is True and hit.source_sha256 == hashlib.sha256(text.encode()).hexdigest()
    assert hit.additional_metadata["revision_id"] == "rev_D2" and hit.retrieval_channel == "palladion_hybrid"


def test_byte_offsets_convert_to_character_offsets() -> None:
    text = "Ünï ✓ end"
    start = len("Ünï ".encode())
    assert utf8_to_character_offsets(text, start, start + len("✓".encode())) == (4, 5)
    with pytest.raises(ContractError):
        utf8_to_character_offsets(text, 0, 10_000)


def test_a_passage_that_differs_from_the_published_bytes_is_refused(tmp_path: Path) -> None:
    server = Palladion()
    bad = passage(TEXTS["D1"], "rev_D1", 0, 12)
    bad["text"] = "tampered text"
    server.search_body = {"status": "OK", "warnings": [], "passages": [bad]}
    with pytest.raises(ContractError, match="differs from the published bytes"):
        arm(server, tmp_path).retrieve(request())


def test_a_passage_from_a_revision_outside_the_corpus_is_foreign_and_hidden_under_c2(tmp_path: Path) -> None:
    server = Palladion()
    server.search_body = {
        "status": "OK",
        "warnings": [],
        "passages": [
            {
                "citation_id": "c",
                "revision_id": "rev_other",
                "section_id": "s",
                "start_byte": 0,
                "end_byte": 5,
                "text": "alien",
                "sha256": "0" * 64,
            },
            passage(TEXTS["D1"], "rev_D1", 0, 12),
        ],
    }
    governed = arm(server, tmp_path, condition=Condition.C2).retrieve(request())
    assert [c.source_document_id for c in governed] == ["D1"]
    opened = arm(server, tmp_path, condition=Condition.C1)
    shown = opened.retrieve(request())
    assert shown[0].additional_metadata["foreign"] is True and shown[0].source_document_id is None


def test_the_neutral_filter_acts_after_palladions_ranking_and_says_how_many_it_dropped(tmp_path: Path) -> None:
    server = Palladion()
    server.search_body = {
        "status": "OK",
        "warnings": [],
        "passages": [passage(TEXTS["D3"], "rev_D3", 0, 10), passage(TEXTS["D1"], "rev_D1", 0, 12)],
    }
    built = arm(server, tmp_path)
    assert [c.source_document_id for c in built.retrieve(request(principal="P-1"))] == ["D1"]
    assert built.last_notes["filtered_after_ranking"] == 1
    assert [c.source_document_id for c in built.retrieve(request(principal="P-2"))] == ["D3", "D1"]


def test_the_budget_is_applied_on_the_harness_side(tmp_path: Path) -> None:
    server = Palladion()
    server.search_body = {
        "status": "OK",
        "warnings": [],
        "passages": [passage(TEXTS["D1"], "rev_D1", 0, 34), passage(TEXTS["D2"], "rev_D2", 0, 45)],
    }
    built = arm(server, tmp_path)
    hits = built.retrieve(request(budget=6))
    assert sum(len(c.content.split()) for c in hits) <= 6 and built.last_notes["truncated"] is True


def test_the_principal_map_and_tokens(tmp_path: Path) -> None:
    server = Palladion()
    server.search_body = {"status": "OK", "warnings": [], "passages": []}
    mapped = arm(server, tmp_path, principals=PrincipalMap(overrides={"P-2": ("reader-a", "case-43")}))
    mapped.retrieve(request(principal="P-2"))
    assert server.calls[-1][2] == "tok-reader"
    tokenless = PalladionArm(
        view(tmp_path), "http://x.test", {}, client=httpx.Client(transport=httpx.MockTransport(server.handle))
    )
    tokenless.map_revisions({"rev_D1": "D1"})
    with pytest.raises(AdapterError, match="no token"):
        tokenless.retrieve(request())
    assert isinstance(mapped, RetrieverAdapter)
    assert mapped.describe()["max_limit"] == 12 and "wall clock" in mapped.describe()["clock"]


# --------------------------------------------------------------------------- loading


def test_loading_mirrors_the_registry_states_with_a_distinct_uploader_and_approver(tmp_path: Path) -> None:
    server = Palladion()
    built = arm(server, tmp_path)
    report = built.load_corpus(tmp_path / TABLE_FILE)
    assert (report.uploaded, report.approved, report.revoked, report.left_as_draft) == (5, 4, 1, 1)
    assert report.states == {"D1": "APPROVED", "D2": "APPROVED", "D3": "APPROVED", "DRAFT": "DRAFT", "OLD": "REVOKED"}
    uploads = [c for c in server.calls if c[1] == "/sources"]
    assert {token for _, _, token in uploads} == {"tok-uploader"}
    approvals = [c for c in server.calls if c[1].endswith("/approve")]
    assert {token for _, _, token in approvals} == {"tok-admin"} and len(approvals) == 4
    draft_revision = report.revisions["DRAFT"]
    assert not [c for c in server.calls if draft_revision in c[1]], "a draft is never approved or revoked"
    assert any(c[1] == f"/sources/{report.revisions['OLD']}/revoke" for c in server.calls)
    table = json.loads((tmp_path / TABLE_FILE).read_text(encoding="utf-8"))
    assert table["revisions"] == dict(report.revisions)


def test_a_second_load_is_refused_and_a_failed_upload_stops_the_load(tmp_path: Path) -> None:
    server = Palladion()
    built = arm(server, tmp_path)
    built.load_corpus(tmp_path / TABLE_FILE)
    with pytest.raises(AdapterError, match="already loaded"):
        built.load_corpus(tmp_path / TABLE_FILE)
    failing = Palladion()
    failing.upload_status = 409
    with pytest.raises(AdapterError, match="HTTP 409"):
        arm(failing, tmp_path).load_corpus(tmp_path / "other.json")
    assert not (tmp_path / "other.json").exists(), "a failed load leaves no table behind"


def test_an_oversized_document_is_refused_by_name(tmp_path: Path) -> None:
    texts = {**TEXTS, "D1": "x" * 70_000}
    server = Palladion()
    built = PalladionArm(
        PublishedView(tmp_path, [record("D1", "approved")], IDENTITY, texts),
        "http://palladion.test",
        TOKENS,
        client=httpx.Client(transport=httpx.MockTransport(server.handle)),
    )
    with pytest.raises(AdapterError, match="D1 exceeds"):
        built.load_corpus(tmp_path / TABLE_FILE)


def test_verify_load_checks_the_table_and_the_index_and_reports_reachability(tmp_path: Path) -> None:
    server = Palladion()
    built = arm(server, tmp_path)
    built.load_corpus(tmp_path / TABLE_FILE)
    server.search_body = {"status": "OK", "warnings": [], "passages": [passage(TEXTS["D1"], "rev_1", 0, 12)]}
    report = built.verify_load(sample=5)
    assert report["documents"] == 5 and report["index_warnings"] == ["COVERAGE_SCOPE_TRUNCATED"]
    assert report["sampled"] >= 1 and 0 <= report["reachable_by_title"] <= report["sampled"]
    built.map_revisions({"rev_2": "D2", "rev_3": "D3", "rev_4": "DRAFT", "rev_5": "OLD"})
    with pytest.raises(AdapterError, match="does not cover exactly"):
        built.verify_load()


def test_verify_load_refuses_an_index_that_reports_a_blocking_warning(tmp_path: Path) -> None:
    def handler(http: httpx.Request) -> httpx.Response:
        if http.url.path == "/index-health":
            return httpx.Response(200, json={"warnings": ["ACCEPTED_BUT_UNINDEXED"]})
        return Palladion().handle(http)

    server = Palladion()
    built = arm(server, tmp_path)
    built.load_corpus(tmp_path / TABLE_FILE)
    built._client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(AdapterError, match="ACCEPTED_BUT_UNINDEXED"):
        built.verify_load()


def test_build_index_checks_the_corpus_and_records_the_mapping(tmp_path: Path) -> None:
    built = arm(Palladion(), tmp_path)
    built.build_index(str(tmp_path), "S")
    assert built.index_stats()["mapped_revisions"] == 3 and built.index_stats()["mode"] == "hybrid"
    with pytest.raises(AdapterError, match="published directory"):
        built.build_index(str(tmp_path / "elsewhere"), "S")


def test_construction_refuses_an_unknown_mode(tmp_path: Path) -> None:
    with pytest.raises(AdapterError):
        PalladionArm(view(tmp_path), "http://x.test", TOKENS, mode=cast(Any, "nearest"))


def test_each_half_of_the_passage_integrity_check_can_refuse_on_its_own(tmp_path: Path) -> None:
    server = Palladion()
    altered_text = passage(TEXTS["D1"], "rev_D1", 0, 12)
    altered_text["text"] = "Rule one: XX"  # same length, different bytes, with a hash that matches the new text
    altered_text["sha256"] = hashlib.sha256(b"Rule one: XX").hexdigest()
    wrong_hash = passage(TEXTS["D1"], "rev_D1", 0, 12)
    wrong_hash["sha256"] = "0" * 64  # the text is exactly the published slice; only the hash lies
    for body in (altered_text, wrong_hash):
        server.search_body = {"status": "OK", "warnings": [], "passages": [body]}
        with pytest.raises(ContractError, match="differs from the published bytes"):
            arm(server, tmp_path).retrieve(request())
