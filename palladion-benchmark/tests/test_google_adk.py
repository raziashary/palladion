"""E2: Google ADK is recorded as not run, with the first blocking reason, and never answers (B07-T03.01, OQ07)."""

from __future__ import annotations

import pytest

from benchmark.adapters.google_adk import GoogleAdkConfig, GoogleAdkSystem, unavailable
from benchmark.contracts import ArmUnavailable, CapabilityUnsupported, CaseRequest, RunStatus, classify_exception
from benchmark.registry import default_registry

REQUEST = CaseRequest(
    "q-0123456789abcdef", "refund window", "P-1", "snap", "2026-10-18T03:00:00Z", None, {}, 4000, None, 0
)


def test_with_nothing_configured_the_arm_is_not_run_and_says_what_is_missing() -> None:
    state = unavailable(GoogleAdkConfig())
    assert isinstance(state, ArmUnavailable) and "project and region" in str(state)
    assert classify_exception(state)[0] is RunStatus.NOT_RUN


@pytest.mark.parametrize(
    "config",
    [
        GoogleAdkConfig(project="p"),
        GoogleAdkConfig(region="r"),
        GoogleAdkConfig(project="p", region="r"),  # access named, probe not approved: the negative control
    ],
)
def test_access_that_is_named_but_not_approved_is_still_not_run(config: GoogleAdkConfig) -> None:
    state = unavailable(config)
    assert isinstance(state, ArmUnavailable)
    assert classify_exception(state)[0] is RunStatus.NOT_RUN


def test_with_access_and_approval_the_arm_is_unsupported_not_run_and_not_faked() -> None:
    state = unavailable(GoogleAdkConfig(project="p", region="r", probe_approved=True))
    assert isinstance(state, CapabilityUnsupported) and "not installed" in str(state)
    assert classify_exception(state)[0] is RunStatus.FEATURE_NOT_SUPPORTED


def test_the_system_never_returns_an_answer_and_reports_nothing_as_zero() -> None:
    system = GoogleAdkSystem()
    system.reset_case("q-0123456789abcdef")
    with pytest.raises(ArmUnavailable):
        system.answer(REQUEST)
    usage = system.report_usage()
    assert (usage.main_calls, usage.prompt_tokens, usage.cost_usd) == (None, None, None), "unknown, not zero"
    assert system.report_trace() == [] and system.describe()["status"] == "not run"


def test_the_registry_forces_the_same_result_for_every_pair() -> None:
    registry = default_registry()
    spec = registry.get("E2")
    assert spec.forced_status is RunStatus.NOT_RUN and spec.forced_reason and "OQ07" in spec.forced_reason
