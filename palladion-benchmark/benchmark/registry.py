"""Arm registry: every arm declares what it can do, and an unverified claim blocks a run.

A declaration is ``SUPPORTED``, ``UNSUPPORTED`` or ``UNVERIFIED`` with a source note. Facts that
follow from the definition of a method may be declared directly; anything about behavior stays
``UNVERIFIED`` until the phase that builds the adapter verifies it. The matrix prints words, never blanks.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from benchmark.config import ComparatorsConfig
from benchmark.contracts import (
    ArmUnavailable,
    CapabilityUnsupported,
    ContractError,
    RunStatus,
    Track,
    require_ident,
    require_text,
)


class Capability(StrEnum):
    NATIVE_CITATION = "native_citation"
    ACL_FILTER = "acl_filter"
    TEMPORAL_FILTER = "temporal_filter"
    GRAPH = "graph"
    OFFLINE_COST = "offline_cost"


class Support(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNVERIFIED = "UNVERIFIED"


class CapabilityNotVerified(ArmUnavailable):
    """A run needs a capability that no one has verified yet, so it is refused rather than assumed."""


@dataclass(frozen=True)
class Declaration:
    support: Support
    source: str

    def __post_init__(self) -> None:
        if not isinstance(self.support, Support):
            raise ContractError("Declaration.support must be a Support value")
        object.__setattr__(self, "source", require_text("Declaration.source", self.source, max_len=300))


@dataclass(frozen=True)
class ArmSpec:
    arm_id: str
    name: str
    tracks: tuple[Track, ...]
    capabilities: Mapping[Capability, Declaration]
    # Set when the arm cannot run today for a documented reason; the status is the recorded result.
    forced_status: RunStatus | None = None
    forced_reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "arm_id", require_ident("ArmSpec.arm_id", self.arm_id))
        object.__setattr__(self, "name", require_text("ArmSpec.name", self.name, max_len=120))
        if not self.tracks or not all(isinstance(t, Track) for t in self.tracks):
            raise ContractError("ArmSpec.tracks must be a non-empty tuple of Track values")
        if (self.forced_status is None) != (self.forced_reason is None):
            raise ContractError("ArmSpec: forced_status and forced_reason go together")
        if self.forced_status not in (None, RunStatus.NOT_RUN, RunStatus.FEATURE_NOT_SUPPORTED):
            raise ContractError("ArmSpec.forced_status must be NOT_RUN or FEATURE_NOT_SUPPORTED")
        declared = set(self.capabilities)
        if declared != set(Capability):
            missing = sorted(c.value for c in set(Capability) - declared)
            raise ContractError(f"ArmSpec {self.arm_id}: undeclared capabilities: {', '.join(missing)}")
        object.__setattr__(self, "capabilities", MappingProxyType(dict(self.capabilities)))


class ArmRegistry:
    def __init__(self) -> None:
        self._arms: dict[str, ArmSpec] = {}

    def register(self, spec: ArmSpec) -> None:
        if spec.arm_id in self._arms:
            raise ContractError(f"arm {spec.arm_id} is already registered")
        self._arms[spec.arm_id] = spec

    def get(self, arm_id: str) -> ArmSpec:
        try:
            return self._arms[arm_id]
        except KeyError:
            raise ContractError(f"unknown arm: {arm_id}") from None

    def ids(self) -> list[str]:
        return list(self._arms)

    def require_runnable(self, arm_id: str, needs: Iterable[Capability] = ()) -> ArmSpec:
        """Return the spec, or raise the exception that records the right run state."""
        spec = self.get(arm_id)
        if spec.forced_status is RunStatus.FEATURE_NOT_SUPPORTED:
            raise CapabilityUnsupported(f"{arm_id}: {spec.forced_reason}")
        if spec.forced_status is RunStatus.NOT_RUN:
            raise ArmUnavailable(f"{arm_id}: {spec.forced_reason}")
        for capability in needs:
            declaration = spec.capabilities[capability]
            if declaration.support is Support.UNSUPPORTED:
                raise CapabilityUnsupported(f"{arm_id} does not support {capability.value}")
            if declaration.support is Support.UNVERIFIED:
                raise CapabilityNotVerified(f"{arm_id}: {capability.value} is not verified yet")
        return spec

    def check_against_config(self, config: ComparatorsConfig) -> None:
        configured = {arm.arm_id for arm in config.arms}
        if configured != set(self._arms):
            only_registry = sorted(set(self._arms) - configured)
            only_config = sorted(configured - set(self._arms))
            raise ContractError(
                f"registry and comparators.yaml differ: registry-only {only_registry}, config-only {only_config}"
            )

    def render_matrix(self, arm_ids: Iterable[str] | None = None) -> str:
        """A Markdown table with one word per cell; unsupported and unverified never print blank."""
        chosen = list(arm_ids) if arm_ids is not None else self.ids()
        header = ["arm", "name", *(c.value for c in Capability), "status today"]
        lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
        for arm_id in chosen:
            spec = self.get(arm_id)
            cells = [spec.capabilities[c].support.value for c in Capability]
            status = spec.forced_status.value if spec.forced_status else "runnable once verified"
            lines.append("| " + " | ".join([spec.arm_id, spec.name, *cells, status]) + " |")
        return "\n".join(lines)


def _declare(**by_capability: tuple[Support, str]) -> Mapping[Capability, Declaration]:
    return {Capability(key): Declaration(*value) for key, value in by_capability.items()}


_BY_DEFINITION = "follows from the definition of the method"


def _unverified(phase: str) -> tuple[Support, str]:
    return Support.UNVERIFIED, f"behavior is verified when the adapter is built ({phase})"


def _harness_arm(test_file: str) -> Mapping[str, tuple[Support, str]]:
    """Capabilities of an arm built on the shared Track A harness (BADR-0025), each proven in ``test_file``."""
    return {
        "native_citation": (
            Support.UNSUPPORTED,
            "provenance comes from the harness chunker, not from the method itself",
        ),
        "acl_filter": (Support.SUPPORTED, f"the neutral filter acts inside ranking and is tested in {test_file}"),
        "temporal_filter": (Support.UNSUPPORTED, "no as-of selection; the method ranks text and the clock is not used"),
        "offline_cost": (Support.SUPPORTED, f"index_stats reports build time and size, tested in {test_file}"),
    }


def _comparator_arm(arm_id: str) -> Mapping[str, tuple[Support, str]]:
    """Capabilities of a third-party comparator run in a worker behind the counting proxy (BADR-0031, BR35)."""
    return {
        "native_citation": (
            Support.UNSUPPORTED,
            f"{arm_id} returns entities, relations or text units; the adapter maps them to the shared chunks",
        ),
        "acl_filter": (
            Support.UNSUPPORTED,
            "graph outputs carry no document id to filter on, so a principal filter cannot be enforced inside the "
            "method; the harness filters the mapped chunks and reports the gap (BR35)",
        ),
        "temporal_filter": (Support.UNSUPPORTED, "the method has no as-of selection; the clock is not used (BR35)"),
        "offline_cost": (
            Support.SUPPORTED,
            "extraction calls and tokens are metered by the counting proxy; tested in tests/test_comparator_worker.py",
        ),
    }


def _framework_arm(test_file: str) -> Mapping[str, tuple[Support, str]]:
    """Capabilities of an end-to-end arm built from LangChain components in a worker behind the proxy (BADR-0040)."""
    return {
        "native_citation": (
            Support.UNSUPPORTED,
            "provenance comes from the harness chunker and the shared prompt's citation ids, not from the framework",
        ),
        "acl_filter": (
            Support.UNSUPPORTED,
            "the in-memory store has no principal filter; the harness filters what the retriever returns after ranking",
        ),
        "temporal_filter": (Support.UNSUPPORTED, "no as-of selection; the store ranks text and the clock is not used"),
        "offline_cost": (
            Support.SUPPORTED,
            f"index_stats reports build time, embeddings counted by the proxy and size, tested in {test_file}",
        ),
    }


def _palladion_system_graph() -> tuple[Support, str]:
    return Support.UNSUPPORTED, "Palladion's graph expansion is off by default and is not enabled for E3 or E4 (OQ12)"


def _palladion_system() -> Mapping[str, tuple[Support, str]]:
    """Capabilities of E3 and E4 over Palladion's message interface (BADR-0039), proven in the system-arm tests."""
    return {
        "native_citation": (
            Support.SUPPORTED,
            "citations carry revision ids and byte offsets that map to published locators; "
            "tested in tests/test_palladion_system.py",
        ),
        "acl_filter": (
            Support.UNSUPPORTED,
            "every benchmark principal maps to one Palladion reader in one case; an answer's use of an unreadable "
            "source is scored, not filtered",
        ),
        "temporal_filter": (
            Support.UNSUPPORTED,
            "the evaluation time is fixed when the server starts; a request with another time is refused",
        ),
        "offline_cost": (Support.UNSUPPORTED, "indexing happens inside Palladion at approval and is not reported"),
    }


R7B_REASON = (
    "Palladion's route for typed links (PF07) exists since P10, but no graph store runs here (OQ12) and no rule "
    "selects the links from published text, so the arm has no graph to expand (BR34)"
)


def _arm(
    arm_id: str,
    name: str,
    tracks: tuple[Track, ...],
    phase: str,
    *,
    graph: tuple[Support, str] | None = None,
    forced: tuple[RunStatus, str] | None = None,
    overrides: Mapping[str, tuple[Support, str]] | None = None,
) -> ArmSpec:
    declared = {
        "native_citation": _unverified(phase),
        "acl_filter": _unverified(phase),
        "temporal_filter": _unverified(phase),
        "graph": graph or (Support.UNSUPPORTED, _BY_DEFINITION),
        "offline_cost": _unverified(phase),
    }
    declared.update(overrides or {})
    return ArmSpec(
        arm_id=arm_id,
        name=name,
        tracks=tracks,
        capabilities=_declare(**declared),
        forced_status=forced[0] if forced else None,
        forced_reason=forced[1] if forced else None,
    )


def default_registry() -> ArmRegistry:
    """The fifteen arms from protocol section 2, declared honestly for the state of the project."""
    a, b, c = Track.RETRIEVAL_ONLY, Track.CONTROLLED_QA, Track.NATIVE_END_TO_END
    graph_by_definition = (Support.SUPPORTED, _BY_DEFINITION)
    palladion_graph = (
        Support.UNVERIFIED,
        "Palladion exposes a graph hop setting; whether /search uses it is read at B04 (OQ03)",
    )
    registry = ArmRegistry()
    for spec in (
        _arm("R0", "BM25 lexical", (a,), "B04", overrides=_harness_arm("tests/test_bm25.py")),
        _arm("R1", "Dense", (a,), "B04", overrides=_harness_arm("tests/test_dense.py")),
        _arm("R2", "Hybrid RRF", (a, b), "B04", overrides=_harness_arm("tests/test_hybrid.py")),
        _arm("R3", "Hybrid plus reranker", (a, b), "B04", overrides=_harness_arm("tests/test_hybrid.py")),
        _arm("R0x", "BM25 lexical plus exact lane", (a,), "B08", overrides=_harness_arm("tests/test_exact_lane.py")),
        _arm(
            "R3f",
            "Hybrid plus reranker plus eligibility rule",
            (a, b),
            "B08",
            overrides={
                **_harness_arm("tests/test_eligibility.py"),
                "temporal_filter": (
                    Support.SUPPORTED,
                    "approval, validity window and supersession are applied before ranking at the question's "
                    "times, tested in tests/test_eligibility.py",
                ),
            },
        ),
        _arm("R4", "HippoRAG 2", (a,), "B06", graph=graph_by_definition, overrides=_comparator_arm("R4")),
        _arm("R5", "GraphRAG Local", (a,), "B06", graph=graph_by_definition, overrides=_comparator_arm("R5")),
        _arm("R6", "LightRAG", (a,), "B06", graph=graph_by_definition, overrides=_comparator_arm("R6")),
        _arm("R7", "Palladion retriever", (a, b), "B04", graph=palladion_graph),
        _arm(
            "R7a",
            "Palladion retriever without graph",
            (a, b),
            "B04",
            overrides={
                "native_citation": (
                    Support.SUPPORTED,
                    "Palladion returns citation ids and exact byte offsets; checked in tests/test_palladion_adapter.py",
                ),
                "acl_filter": (
                    Support.UNSUPPORTED,
                    "Palladion's principals cannot express the benchmark's; the harness filters its output (BADR-0025)",
                ),
                "temporal_filter": (Support.UNSUPPORTED, "Palladion's search has no as-of parameter (BR22)"),
                "offline_cost": (
                    Support.UNSUPPORTED,
                    "indexing happens inside Palladion at approval and is not reported",
                ),
            },
        ),
        _arm(
            "R7b",
            "Palladion retriever with bounded graph",
            (a,),
            "B06",
            graph=palladion_graph,
            forced=(RunStatus.FEATURE_NOT_SUPPORTED, R7B_REASON),
        ),
        _arm("E0", "Plain LangChain two-step", (c,), "B07", overrides=_framework_arm("tests/test_langchain.py")),
        _arm("E1", "LangGraph agentic", (c,), "B07", overrides=_framework_arm("tests/test_langgraph.py")),
        _arm(
            "E2",
            "Google ADK with RAG Engine",
            (c,),
            "B07",
            graph=(Support.UNVERIFIED, "managed service internals are not documented to us"),
            forced=(RunStatus.NOT_RUN, "no managed-service access is configured and no probe is approved (OQ07)"),
        ),
        _arm(
            "E3",
            "Palladion without critic",
            (c,),
            "B07",
            graph=_palladion_system_graph(),
            overrides=_palladion_system(),
        ),
        _arm(
            "E4",
            "Full Palladion with critic",
            (c,),
            "B07",
            graph=_palladion_system_graph(),
            overrides=_palladion_system(),
        ),
    ):
        registry.register(spec)
    return registry
