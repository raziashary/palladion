"""R7a: the HTTP-only Palladion adapter against a stand-in server, and against the real isolated runtime."""

from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import replace
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
TOKENS = {
    "reader-a": "tok-reader", "uploader-a": "tok-uploader", "admin-a": "tok-admin",
    "pal-p1": "tok-p1", "pal-p2": "tok-p2",
}  # fmt: skip
READERS = PrincipalMap(overrides={"P-1": ("pal-p1", "case-42"), "P-2": ("pal-p2", "case-42")})
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
        self.bodies: list[dict[str, Any]] = []  # the JSON body of each call, in the same order
        self.search_body: dict[str, Any] = {"status": "OK", "warnings": [], "passages": []}
        self.search_by_token: dict[str, dict[str, Any]] = {}  # an answer for one reader, in place of search_body
        self.search_status = 200
        self.upload_status = 201
        self.counter = 0

    def handle(self, http: httpx.Request) -> httpx.Response:
        token = http.headers.get("authorization", "").removeprefix("Bearer ")
        self.calls.append((http.method, http.url.path, token))
        self.bodies.append(json.loads(http.content) if http.content else {})
        if http.url.path == "/search":
            return httpx.Response(self.search_status, json=self.search_by_token.get(token, self.search_body))
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
    kwargs.setdefault("principals", READERS)
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
        arm(server, tmp_path).retrieve(request(limit=13))
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
        built = PalladionArm(view(tmp_path), "http://palladion.test", TOKENS, client=client, principals=READERS)
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


def test_palladions_output_is_not_masked_and_a_document_the_neutral_filter_refuses_is_counted_as_leaked(
    tmp_path: Path,
) -> None:
    server = Palladion()
    server.search_body = {
        "status": "OK",
        "warnings": [],
        "passages": [passage(TEXTS["D3"], "rev_D3", 0, 10), passage(TEXTS["D1"], "rev_D1", 0, 12)],
    }
    built = arm(server, tmp_path)
    leaked = built.retrieve(request(principal="P-1"))  # D3 is for tenant T-2 only; P-1 is in T-1
    assert [c.source_document_id for c in leaked] == ["D3", "D1"], "the arm does not hide what Palladion returned"
    assert built.last_notes["acl_leaked"] == 1 and "ACL_LEAKED=1" in built.call_flags()
    clean = built.retrieve(request(principal="P-2"))
    assert [c.source_document_id for c in clean] == ["D3", "D1"] and built.last_notes["acl_leaked"] == 0
    assert "ACL_LEAKED" not in " ".join(built.call_flags())


def test_c2_needs_a_reader_for_every_benchmark_principal(tmp_path: Path) -> None:
    with pytest.raises(AdapterError, match="one Palladion reader for every benchmark principal"):
        PalladionArm(view(tmp_path), "http://x.test", TOKENS, condition=Condition.C2)
    partial = PrincipalMap(overrides={"P-1": ("pal-p1", "case-42")})
    with pytest.raises(AdapterError, match="one Palladion reader"):
        PalladionArm(view(tmp_path), "http://x.test", TOKENS, condition=Condition.C2, principals=partial)
    PalladionArm(view(tmp_path), "http://x.test", TOKENS, condition=Condition.C1).close()  # C1 has no access list


def test_the_search_carries_the_cases_evaluation_time_as_as_of(tmp_path: Path) -> None:
    server = Palladion()
    arm(server, tmp_path).retrieve(request())
    search = next(b for (method, path, _), b in zip(server.calls, server.bodies, strict=True) if path == "/search")
    assert search["as_of"] == "2026-10-18T03:00:00Z" and search["limit"] == 10


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
    mapped = arm(
        server, tmp_path, principals=PrincipalMap(overrides={**READERS.overrides, "P-2": ("reader-a", "case-43")})
    )
    mapped.retrieve(request(principal="P-2"))
    assert server.calls[-1][2] == "tok-reader"
    tokenless = PalladionArm(
        view(tmp_path),
        "http://x.test",
        {},
        client=httpx.Client(transport=httpx.MockTransport(server.handle)),
        principals=READERS,
    )
    tokenless.map_revisions({"rev_D1": "D1"})
    with pytest.raises(AdapterError, match="no token"):
        tokenless.retrieve(request())
    assert isinstance(mapped, RetrieverAdapter)
    assert mapped.describe()["max_limit"] == 12 and "as_of" in mapped.describe()["clock"]


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


def test_a_restricted_document_is_uploaded_with_its_readers_and_an_open_one_with_none(tmp_path: Path) -> None:
    server = Palladion()
    arm(server, tmp_path).load_corpus(tmp_path / TABLE_FILE)
    uploads = {
        b["filename"]: b["allowed_principal_ids"]
        for (_, path, _), b in zip(server.calls, server.bodies, strict=True)
        if path == "/sources"
    }
    assert uploads["D1.md"] == [] and uploads["D2.md"] == [] and uploads["DRAFT.md"] == []  # everyone may read these
    assert uploads["D3.md"] == ["admin-a", "pal-p2", "uploader-a"]  # tenant T-2 only, and the two who must approve it


def test_under_c1_nothing_is_restricted(tmp_path: Path) -> None:
    server = Palladion()
    arm(server, tmp_path, condition=Condition.C1).load_corpus(tmp_path / TABLE_FILE)
    lists = [
        b["allowed_principal_ids"]
        for (_, path, _), b in zip(server.calls, server.bodies, strict=True)
        if path == "/sources"
    ]
    assert lists == [[]] * 5


def test_a_document_published_later_gets_the_same_access_list(tmp_path: Path) -> None:
    server = Palladion()
    built = arm(server, tmp_path)
    built.load_corpus(tmp_path / TABLE_FILE)
    extra = replace(record("D3", "approved", tenants=("T-1",)), doc_id="D3B")
    built.publish(extra, TEXTS["D3"])
    sent = next(
        b for (_, path, _), b in reversed(list(zip(server.calls, server.bodies, strict=True))) if path == "/sources"
    )
    assert sent["filename"] == "D3B.md" and sent["allowed_principal_ids"] == ["admin-a", "pal-p1", "uploader-a"]


def acl_server(leak: bool = False, silent: bool = False) -> Palladion:
    """A stand-in that serves D3 (tenant T-2 only) to the reader of P-2, and to P-1 too when it leaks."""
    server = Palladion()
    found = {"status": "OK", "warnings": [], "passages": [passage(TEXTS["D3"], "rev_3", 0, 10)]}  # the third upload
    empty = {"status": "OK", "warnings": [], "passages": []}
    server.search_by_token = {"tok-p2": empty if silent else found, "tok-p1": found if leak else empty}
    return server


def test_the_access_lists_are_read_back_with_a_positive_control(tmp_path: Path) -> None:
    built = arm(acl_server(), tmp_path)
    built.load_corpus(tmp_path / TABLE_FILE)
    report = built.verify_acl()
    assert report == {
        "condition": "C2", "restricted_checked": 1, "reachable_by_allowed": 1, "forbidden_probes": 1, "leaks": 0,
    }  # fmt: skip


def test_a_leak_through_palladions_access_list_is_counted_not_hidden_or_raised(tmp_path: Path) -> None:
    built = arm(acl_server(leak=True), tmp_path)
    built.load_corpus(tmp_path / TABLE_FILE)
    assert built.verify_acl()["leaks"] == 1


def test_a_silent_search_cannot_pass_the_access_list_check(tmp_path: Path) -> None:
    built = arm(acl_server(silent=True), tmp_path)
    built.load_corpus(tmp_path / TABLE_FILE)
    with pytest.raises(AdapterError, match="no restricted document could be found"):
        built.verify_acl()


def test_the_access_list_check_has_nothing_to_check_under_c1(tmp_path: Path) -> None:
    built = arm(Palladion(), tmp_path, condition=Condition.C1)
    assert built.verify_acl() == {"condition": "C1", "restricted_checked": 0, "note": "C1 has no access list"}


def test_a_version_is_approved_after_the_one_it_supersedes_and_names_it(tmp_path: Path) -> None:
    successor = replace(record("D1", "approved"), supersedes="OLD")
    older = record("OLD", "withdrawn")
    server = Palladion()
    built = PalladionArm(
        PublishedView(tmp_path, [successor, older], IDENTITY, TEXTS),
        "http://palladion.test",
        TOKENS,
        client=httpx.Client(transport=httpx.MockTransport(server.handle)),
        principals=READERS,
    )
    report = built.load_corpus(tmp_path / TABLE_FILE)
    steps = [
        (path.rsplit("/", 1)[1], path.split("/")[2]) for _, path, _ in server.calls if path.startswith("/sources/")
    ]
    old, new = report.revisions["OLD"], report.revisions["D1"]
    assert steps == [("approve", old), ("approve", new), ("revoke", old)], "predecessor first; the revoke waits"
    body_of = {path: body for (_, path, _), body in zip(server.calls, server.bodies, strict=True)}
    assert body_of[f"/sources/{new}/approve"] == {"supersedes_revision_id": old}
    assert body_of[f"/sources/{old}/approve"] == {}
    assert report.superseded == 1 and report.states == {"D1": "APPROVED", "OLD": "REVOKED"}


def test_a_predecessor_that_was_never_approved_is_not_named(tmp_path: Path) -> None:
    successor = replace(record("D1", "approved"), supersedes="DRAFT")
    server = Palladion()
    built = PalladionArm(
        PublishedView(tmp_path, [record("DRAFT", "draft"), successor], IDENTITY, TEXTS),
        "http://palladion.test",
        TOKENS,
        client=httpx.Client(transport=httpx.MockTransport(server.handle)),
        principals=READERS,
    )
    report = built.load_corpus(tmp_path / TABLE_FILE)
    assert report.superseded == 0
    assert all("supersedes_revision_id" not in body for body in server.bodies)


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
        principals=READERS,
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


@pytest.mark.parametrize(
    "body",
    [
        {"status": "DEGRADED", "warnings": [], "passages": []},
        {"status": "DEGRADED", "warnings": ["SOMETHING_NEW"], "passages": []},
        {"status": "MAYBE", "warnings": [], "passages": []},
    ],
)
def test_a_status_or_warning_the_adapter_does_not_know_is_a_fault_not_an_empty_answer(
    tmp_path: Path, body: dict[str, Any]
) -> None:
    server = Palladion()
    server.search_body = body
    with pytest.raises(TransientInfrastructureError, match="unknown status or warning"):
        arm(server, tmp_path).retrieve(request())


def test_a_passage_boundary_inside_a_character_is_a_contract_error() -> None:
    with pytest.raises(ContractError, match="inside a character"):
        utf8_to_character_offsets("Ünï", 1, 3)  # byte 1 is the middle of the two-byte Ü


def test_the_arm_reports_what_it_did_to_a_call_as_flags(tmp_path: Path) -> None:
    server = Palladion()
    server.search_body = {
        "status": "DEGRADED",
        "warnings": ["COVERAGE_SCOPE_TRUNCATED"],
        "passages": [passage(TEXTS["D3"], "rev_D3", 0, 10), passage(TEXTS["D1"], "rev_D1", 0, 12)],
    }
    built = arm(server, tmp_path)
    built.retrieve(request(principal="P-1", budget=2))
    flags = built.call_flags()
    assert "ACL_LEAKED=1" in flags and "PALLADION_WARNING=COVERAGE_SCOPE_TRUNCATED" in flags
    assert any(f.startswith("BUDGET_") for f in flags)


def test_verify_load_refuses_when_none_of_the_sampled_documents_can_be_found(tmp_path: Path) -> None:
    server = Palladion()
    built = arm(server, tmp_path)
    built.load_corpus(tmp_path / TABLE_FILE)
    server.search_body = {"status": "OK", "warnings": [], "passages": []}  # Palladion holds something else entirely
    with pytest.raises(AdapterError, match="does not describe it"):
        built.verify_load(sample=5)


def test_the_load_probe_never_sends_a_code_that_palladion_would_refuse(tmp_path: Path) -> None:
    sent: list[str] = []

    def handler(http: httpx.Request) -> httpx.Response:
        if http.url.path == "/search":
            sent.append(json.loads(http.content)["query"])
            return httpx.Response(
                200, json={"status": "OK", "warnings": [], "passages": [passage(TEXTS["D1"], "rev_1", 0, 12)]}
            )
        if http.url.path == "/index-health":
            return httpx.Response(200, json={"warnings": []})
        return Palladion().handle(http)

    coded = replace(record("D1", "approved"), title="Memo: change to POL-020 window")
    built = PalladionArm(
        PublishedView(tmp_path, [coded], IDENTITY, TEXTS),
        "http://palladion.test",
        TOKENS,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        principals=READERS,
    )
    built.map_revisions({"rev_1": "D1"})
    report = built.verify_load(sample=1)
    assert sent == ["Memo: change to window"] and report["reachable_by_title"] == 1
