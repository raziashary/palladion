"""The isolated Palladion runtime and a real R7a call against it (B04-T03.03, B04-T03.01, B04-T03.02)."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

from benchmark.adapters.common import Condition, PublishedView
from benchmark.adapters.palladion import CASE, TABLE_FILE, PalladionArm, PrincipalMap
from benchmark.config import load_comparators_config
from benchmark.contracts import (
    ArmUnavailable,
    CapabilityUnsupported,
    EvidenceCandidate,
    RetrievalRequest,
    RunStatus,
    classify_exception,
)
from benchmark.fixtures.manifest import ManifestRecord

ROOT = Path(__file__).resolve().parents[1]


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("palladion_runtime", ROOT / "scripts" / "palladion_runtime.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # a dataclass in the script resolves its module through sys.modules
    spec.loader.exec_module(module)
    return module


runtime = load_script()


def request(query: str, principal: str, limit: int = 10) -> RetrievalRequest:
    return RetrievalRequest(
        "q-0000000000000001", query, principal, "snap", "2026-10-18T03:00:00Z", None, {}, limit, 4000
    )


# --------------------------------------------------------------------------- safety rules (no server needed)


def test_the_pinned_worktree_is_clean_and_at_the_recorded_commit() -> None:
    runtime.ensure_worktree()
    state = runtime.worktree_state()
    assert state["commit"] == runtime.PINNED_COMMIT and state["dirty"] is False


def test_every_palladion_pin_in_the_config_is_the_commit_the_runtime_checks_out() -> None:
    config = load_comparators_config(ROOT / "configs" / "comparators.yaml")
    pins = {a.arm_id: a.pin for a in config.arms if a.family == "system_under_test"}
    pinned = {arm: pin.value for arm, pin in pins.items() if pin.kind == "commit"}
    assert set(pinned) == {"R7a", "E3", "E4"}  # R7 and R7b are not built, so they carry no pin
    assert set(pinned.values()) == {runtime.PINNED_COMMIT}
    assert config.system_under_test.value == runtime.PINNED_COMMIT


def test_palladions_pins_read_from_its_source_equal_the_benchmarks_pins() -> None:
    runtime.ensure_worktree()
    pins = runtime.pins_from_source()
    shared = load_comparators_config(ROOT / "configs" / "comparators.yaml").shared_models
    assert (pins["embedding_repository"], pins["embedding_revision"]) == (
        shared["embeddings"].value,
        shared["embeddings"].revision,
    )
    assert (pins["reranker_repository"], pins["reranker_revision"]) == (
        shared["reranker"].value,
        shared["reranker"].revision,
    )


def test_palladions_own_root_and_port_are_refused(tmp_path: Path) -> None:
    with pytest.raises(runtime.PalladionRuntimeError, match="own demo root"):
        runtime.seed(root=runtime.REPO / "palladion" / "runtime" / "demo")
    with pytest.raises(runtime.PalladionRuntimeError, match="18080"):
        runtime.PalladionRuntime(port=18080).start()
    assert runtime.PORT != runtime.PALLADION_DEFAULT_PORT and runtime.QDRANT_URL.endswith(":17333")


def test_an_existing_runtime_root_is_not_rebuilt_without_reset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime, "RUNTIME_ROOT", tmp_path)
    monkeypatch.setattr(runtime, "qdrant_healthy", lambda url=runtime.QDRANT_URL: True)
    monkeypatch.setattr(runtime, "sync_environment", lambda worktree=runtime.WORKTREE: None)
    monkeypatch.setattr(runtime, "install_model_cache", lambda worktree=runtime.WORKTREE: None)
    with pytest.raises(runtime.PalladionRuntimeError, match="--reset"):
        runtime.prepare()


def test_prepare_needs_the_benchmarks_qdrant_first(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime, "qdrant_healthy", lambda url=runtime.QDRANT_URL: False)
    with pytest.raises(runtime.PalladionRuntimeError, match="Qdrant first"):
        runtime.prepare(reset=True)


def test_live_state_describes_the_contributors_defaults() -> None:
    state = runtime.live_state()
    assert set(state) == {"default_root", "qdrant_16333_points"}
    assert state == runtime.live_state(), "the observation is stable when nothing touches the defaults"


# --------------------------------------------------------------------------- the real runtime


@pytest.fixture(scope="module")
def prepared(qdrant_server: str) -> Iterator[dict[str, object]]:
    before = runtime.live_state()
    record = runtime.prepare(reset=True)
    yield {"record": record, "before": before}


IDENTIFIER_SHAPE = re.compile(r"(?<![A-Za-z0-9])(?:[A-Z][A-Z0-9_.]*[-.][A-Z0-9_.-]+)(?![A-Za-z0-9])")


def codeless_probe(view: PublishedView) -> tuple[ManifestRecord, str]:
    """A retrievable document and its longest line that holds nothing Palladion would read as an identifier."""
    for record in view.records:
        if record.registry_state not in ("non_normative", "approved") or record.valid_to is not None:
            continue
        lines = [ln for ln in view.document(record.doc_id).text.splitlines() if len(ln.split()) >= 5]
        clean = [ln for ln in lines if not IDENTIFIER_SHAPE.search(ln)]
        if clean:
            return record, max(clean, key=len)
    raise AssertionError("the corpus has no document with an identifier-free line")


def mini_view(full: PublishedView) -> PublishedView:
    wanted = {"approved": 3, "non_normative": 3, "retired": 2, "draft": 1, "unapproved_proposal": 1, "withdrawn": 1}
    chosen = []
    for state, count in wanted.items():
        chosen += [r for r in full.records if r.registry_state == state][:count]
    return PublishedView(full.root, chosen, full.identity, {r.doc_id: full.document(r.doc_id).text for r in chosen})


def test_prepare_built_a_runtime_that_left_the_contributors_defaults_alone(prepared: dict[str, object]) -> None:
    record = prepared["record"]
    assert isinstance(record, dict)
    assert record["live_state_unchanged"] is True and record["demo_revisions_revoked"] == 4
    assert record["worktree"]["dirty"] is False
    assert runtime.live_state() == prepared["before"]


def test_a_real_call_loads_and_retrieves_the_published_corpus_over_http(
    prepared: dict[str, object], s_published: Path, tmp_path: Path
) -> None:
    full = PublishedView.load(s_published)
    view = mini_view(full)
    tokens = runtime.load_tokens()
    with runtime.PalladionRuntime() as server:
        arm = PalladionArm(view, server.base_url, tokens, mode="hybrid", condition=Condition.C1)
        try:
            report = arm.load_corpus(tmp_path / TABLE_FILE)
            assert report.uploaded == 11 and report.left_as_draft == 2 and report.revoked == 1 and report.approved == 9
            check = arm.verify_load(sample=11)
            assert check["documents"] == 11 and check["index_warnings"] is not None
            target, probe = codeless_probe(view)
            hits = arm.retrieve(request(probe, view.identity.principals[0].principal_id))
            assert hits, "a real call must return candidates"
            assert target.doc_id in {c.source_document_id for c in hits}
            assert all(c.native_citation_supported and c.locator and c.locator.startswith("chars:") for c in hits)
            assert {c.source_document_id for c in hits} <= {r.doc_id for r in view.records}
            coded = arm.retrieve(request("what does MS-4021 mean", view.identity.principals[0].principal_id))
            assert coded == [] and arm.last_notes["palladion_warnings"] == ["EXACT_IDENTIFIER_NOT_FOUND"], (
                "HTTP-loaded documents get no identifier aliases, so a code query is answered with nothing (BR24)"
            )
            drafted = {d for d, state in report.states.items() if state in ("DRAFT", "REVOKED")}
            assert not {c.source_document_id for c in hits} & drafted, (
                "unapproved and revoked documents are not retrievable"
            )
            with pytest.raises(CapabilityUnsupported) as caught:
                arm.retrieve(request(probe, view.identity.principals[0].principal_id, limit=41))
            assert classify_exception(caught.value)[0] is RunStatus.FEATURE_NOT_SUPPORTED
            reranked = PalladionArm(view, server.base_url, tokens, mode="reranked", condition=Condition.C1)
            reranked.map_revisions({rev: doc for doc, rev in report.revisions.items()})
            assert reranked.retrieve(request(probe, view.identity.principals[0].principal_id)), "the reranker is loaded"
            reranked.close()
            logged = (runtime.RUNTIME_ROOT.parent / "palladion-serve.log").read_text(encoding="utf-8", errors="replace")
            assert not any(token in logged for token in tokens.values()), "no bearer token may reach the server log"
        finally:
            arm.close()
    assert runtime.live_state() == prepared["before"]


def test_provisioning_readers_grants_read_only_reuses_a_held_token_and_writes_only_new_ones(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "demo_auth.json").write_text(json.dumps({"tok-admin": runtime.ADMIN}), encoding="utf-8")
    sent: list[tuple[str, dict[str, object] | None]] = []

    def fake_post(base_url: str, path: str, token: str, body: dict[str, object] | None = None) -> tuple[int, object]:
        assert token == "tok-admin"
        sent.append((path, body))
        if path == "/v1/admin/principals":
            assert body is not None
            return 200, {"principal_id": "opaque-" + str(body["principal_id"])}
        return 200, {}

    monkeypatch.setattr(runtime, "post", fake_post)
    first = runtime.provision_readers("http://x", ["a", "b"], case_id="case-42", root=tmp_path)
    assert set(first) == {"a", "b"} and first["a"][0] == "opaque-a" and first["a"][1] != first["b"][1]
    grants = [body["grants"] for path, body in sent if path == "/v1/admin/principals" and body]
    assert grants == [["source:read", "case:read"]] * 2, "a reader may read and nothing else"
    assert ("/v1/admin/cases/case-42/memberships", {"principal_id": "opaque-a"}) in sent
    second = runtime.provision_readers("http://x", ["a", "b", "c"], case_id="case-42", root=tmp_path)
    assert second["a"] == first["a"] and second["b"] == first["b"], "a held token is kept"
    stored = json.loads((tmp_path / "demo_auth.json").read_text(encoding="utf-8"))
    assert sorted(stored.values()) == sorted([runtime.ADMIN, "opaque-a", "opaque-b", "opaque-c"])


def test_a_refused_provisioning_names_the_status_and_leaves_the_token_file_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = json.dumps({"tok-admin": runtime.ADMIN})
    (tmp_path / "demo_auth.json").write_text(before, encoding="utf-8")
    monkeypatch.setattr(runtime, "post", lambda *args, **kwargs: (403, None))
    with pytest.raises(runtime.PalladionRuntimeError, match="HTTP 403"):
        runtime.provision_readers("http://x", ["a"], case_id="case-42", root=tmp_path)
    assert (tmp_path / "demo_auth.json").read_text(encoding="utf-8") == before


def test_a_real_palladion_keeps_a_restricted_document_from_a_forbidden_reader_and_honours_as_of(
    prepared: dict[str, object], s_published: Path, tmp_path: Path
) -> None:
    full = PublishedView.load(s_published)
    used = {r.doc_id for r in mini_view(full).records}
    unused = [r for r in reversed(full.records) if r.doc_id not in used and not IDENTIFIER_SHAPE.search(r.title)]
    restricted = next(r for r in unused if r.registry_state == "approved" and r.acl_tenants)
    expired = next(r for r in unused if r.registry_state == "retired" and not r.acl_tenants and r.valid_to)
    view = PublishedView(
        full.root, [restricted, expired], full.identity,
        {r.doc_id: full.document(r.doc_id).text for r in (restricted, expired)},
    )  # fmt: skip
    everyone = [p.principal_id for p in full.identity.principals]
    seeing = next(p for p in full.identity.principals if p.tenant_id in restricted.acl_tenants).principal_id
    blind = next(p for p in full.identity.principals if p.tenant_id not in restricted.acl_tenants).principal_id
    with runtime.PalladionRuntime(rerank=False) as provisioning:
        issued = runtime.provision_readers(provisioning.base_url, everyone, case_id=CASE)
    principals = PrincipalMap(overrides={key: (reader, CASE) for key, (reader, _) in issued.items()})
    with runtime.PalladionRuntime(rerank=False) as server:
        arm = PalladionArm(
            view, server.base_url, runtime.load_tokens(), mode="lexical", condition=Condition.C2, principals=principals
        )  # fmt: skip
        try:
            arm.load_corpus(tmp_path / TABLE_FILE)
            title = " ".join(IDENTIFIER_SHAPE.sub(" ", restricted.title).split())

            def ask(who: str, query: str, when: str) -> list[EvidenceCandidate]:
                return arm.retrieve(
                    RetrievalRequest("q-0000000000000001", query, who, "snap", when, None, {}, 10, 100000)
                )

            assert restricted.doc_id in {c.source_document_id for c in ask(seeing, title, "2026-10-18T03:00:00Z")}
            hidden = ask(blind, title, "2026-10-18T03:00:00Z")
            assert restricted.doc_id not in {c.source_document_id for c in hidden}
            assert arm.last_notes["acl_leaked"] == 0, "Palladion's own access list, not a harness filter, kept it back"
            assert arm.verify_acl()["leaks"] == 0
            lapsed = " ".join(IDENTIFIER_SHAPE.sub(" ", expired.title).split())
            inside = f"{expired.valid_from[:10]}T12:00:00Z" if expired.valid_from else "2025-07-01T12:00:00Z"
            assert expired.valid_to is not None
            after = f"{expired.valid_to[:4]}-12-31T12:00:00Z"
            assert expired.doc_id in {c.source_document_id for c in ask(seeing, lapsed, inside)}
            assert expired.doc_id not in {c.source_document_id for c in ask(seeing, lapsed, after)}
        finally:
            arm.close()


def test_an_unreachable_palladion_is_not_run_never_an_empty_list(
    prepared: dict[str, object], s_published: Path
) -> None:
    view = mini_view(PublishedView.load(s_published))
    arm = PalladionArm(view, f"http://127.0.0.1:{runtime.PORT}", runtime.load_tokens(), condition=Condition.C1)
    arm.map_revisions({"rev_unknown": view.records[0].doc_id})
    with pytest.raises(ArmUnavailable) as caught:
        arm.retrieve(request("anything", view.identity.principals[0].principal_id))
    assert classify_exception(caught.value)[0] is RunStatus.NOT_RUN
    arm.close()


def test_the_runtime_record_names_the_commit_mode_and_pins() -> None:
    state = runtime.worktree_state()
    assert len(state["settings_sha256"]) == 64 and len(state["lock_sha256"]) == 64
    assert (
        json.loads(json.dumps(runtime.pins_from_source()))["embedding_revision"]
        == "faf4aa4225822f3bc6376869cb1164e8e3feedd0"
    )


def test_a_model_snapshot_that_differs_from_the_pin_is_not_copied_into_palladion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from benchmark.adapters.models import ModelIntegrityError, spec_from_pin

    shared = load_comparators_config(ROOT / "configs" / "comparators.yaml").shared_models
    caches = []
    for name in ("embeddings", "reranker"):
        spec = spec_from_pin(shared[name])
        snapshot = tmp_path / name / "models--org--name" / "snapshots" / spec.revision
        for file in spec.files:
            (snapshot / file).parent.mkdir(parents=True, exist_ok=True)
            (snapshot / file).write_bytes(b"not the pinned bytes")
        caches.append(tmp_path / name)
    monkeypatch.setattr(runtime, "MODEL_CACHES", tuple(caches))
    worktree = tmp_path / "worktree"
    with pytest.raises(ModelIntegrityError, match="differ from the pin"):
        runtime.install_model_cache(worktree)
    assert not list((worktree / "palladion" / "runtime" / "model_cache" / "huggingface").glob("models--*"))


def test_a_probe_that_palladion_cannot_answer_does_not_prove_the_demo_sources_are_gone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def answers(status: str, warnings: list[str]) -> object:
        def post(base_url: str, path: str, token: str, body: dict[str, object] | None = None) -> tuple[int, object]:
            if path.endswith("/revoke"):
                return 200, {}
            return 200, {"status": status, "warnings": warnings, "passages": []}

        return post

    tokens = {"admin-a": "x", "reader-a": "y"}
    for status, warnings in (("UNAVAILABLE", []), ("DEGRADED", ["INDEX_UNAVAILABLE"])):
        monkeypatch.setattr(runtime, "post", answers(status, warnings))
        with pytest.raises(runtime.PalladionRuntimeError, match="revocation is unproven"):
            runtime.revoke_demo_sources("http://x", {"d": "rev_1"}, tokens)
    monkeypatch.setattr(runtime, "post", answers("OK", []))
    runtime.revoke_demo_sources("http://x", {"d": "rev_1"}, tokens)


def test_prepare_fails_the_command_when_the_contributors_defaults_changed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    record = {"worktree": {}, "pins": {}, "live_state_unchanged": False, "demo_revisions_revoked": 4}
    monkeypatch.setattr(runtime, "prepare", lambda reset=False: record)
    assert runtime.main(["prepare", "--reset"]) == 1
    assert "changed while preparing" in capsys.readouterr().err
