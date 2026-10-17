from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from evidence_agent.settings import Settings, load_settings


def test_selected_configuration_and_explicit_enablement() -> None:
    settings = load_settings(Path(__file__).parents[1] / "config/settings.yaml")
    assert settings.model == "qwen/qwen3.8-27b"
    with pytest.raises(PermissionError, match="disabled"):
        settings.require_live_llm(api_key_present=True)
    enabled = Settings(enable_live_llm=True)
    with pytest.raises(PermissionError, match="credentials"):
        enabled.require_live_llm(api_key_present=False)
    enabled.require_live_llm(api_key_present=True)


@pytest.mark.parametrize(
    "values",
    [
        {"main_max_calls": 6},
        {"critic_max_calls": 4},
        {"critic_search_max_calls": 3},
        {"main_max_calls": "5"},
        {"enable_live_llm": "true"},
        {"provider": "other"},
        {"model": "alternate"},
        {"unknown_setting": True},
        {"request_timeout_seconds": 0},
        {"schema_version": "2.0"},
    ],
)
def test_invalid_or_unknown_settings_fail(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate(values)


def test_yaml_does_not_construct_objects_or_accept_nonmapping(tmp_path: Path) -> None:
    path = tmp_path / "invalid.yaml"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        load_settings(path)
    path.write_text("!!python/object:builtins.object {}", encoding="utf-8")
    with pytest.raises(yaml.constructor.ConstructorError):
        load_settings(path)
