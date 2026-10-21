"""E2: Google ADK with RAG Engine, recorded as not run (B07-T03.01, OQ07, BADR-0040).

The managed service needs a project, a region on its allowlist, billing, and an access probe, which is an external call
that the owner has not approved. The package is not installed either (BADR-0040 records it and installs nothing). So
this arm never produces an answer: it reports why it cannot, as a run state, in the order a reader would fix it. A
configuration that names access but lacks the owner's approval is still not run, and one that has both would still be
unsupported until an integration exists, because E2 cannot reproduce the four-tool set or the principal filter that
Palladion's arms use (protocol 2.2, 3.1 item 2): the reason says so instead of pretending equivalence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from benchmark.contracts import ArmUnavailable, CapabilityUnsupported, CaseRequest, CaseResponse, UsageReport


@dataclass(frozen=True)
class GoogleAdkConfig:
    """What the owner has arranged for E2. The defaults arrange nothing."""

    project: str | None = None
    region: str | None = None
    probe_approved: bool = False


def unavailable(config: GoogleAdkConfig) -> ArmUnavailable | CapabilityUnsupported:
    """The run state of E2 for a configuration, with the first thing that blocks it."""
    if not config.project or not config.region:
        return ArmUnavailable("E2 has no managed-service project and region configured (OQ07)")
    if not config.probe_approved:
        return ArmUnavailable("E2 names a project, but the owner has not approved an access probe (OQ07)")
    return CapabilityUnsupported(
        "E2 is not built: the ADK package is not installed (BADR-0040), and the managed service cannot reproduce the "
        "four-tool set or the principal filter"
    )


class GoogleAdkSystem:
    """E2 behind the system-arm interface: every question is a recorded run state with the reason, never an answer."""

    arm_id = "E2"

    def __init__(self, config: GoogleAdkConfig | None = None) -> None:
        self._config = config or GoogleAdkConfig()

    def reset_case(self, case_id: str) -> None:
        return None

    def answer(self, request: CaseRequest) -> CaseResponse:
        raise unavailable(self._config)

    def report_usage(self) -> UsageReport:
        return UsageReport(None, None, None, None, None, None)

    def report_trace(self) -> list[dict[str, Any]]:
        return []

    def describe(self) -> dict[str, Any]:
        return {"arm": self.arm_id, "status": "not run", "reason": str(unavailable(self._config))}
