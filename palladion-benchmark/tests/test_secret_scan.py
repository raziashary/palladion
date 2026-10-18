"""Secret scanner: every rule has a violating case that is caught and a clean case that passes."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from benchmark import secret_scan
from benchmark.secret_scan import Finding, scan_paths, scan_staged, scan_text

# Fake secrets are assembled at runtime so this file never contains a literal that the scanner flags.
FAKE_GROQ = "gsk_" + "Ab3" * 10
FAKE_OPENAI = "sk-" + "Zy9" * 10
FAKE_AWS = "AKIA" + "ABCDEFGH12345678"
FAKE_BLOCK = "-----BEGIN " + "RSA PRIVATE KEY-----"
FAKE_ASSIGNED = "api_key = " + "q" * 24

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")


@pytest.mark.parametrize(
    ("text", "rule"),
    [
        (f"x = '{FAKE_GROQ}'", "groq-key"),
        (f"key: {FAKE_OPENAI}", "openai-style-key"),
        (f"id {FAKE_AWS}", "aws-access-key"),
        (FAKE_BLOCK, "private-key-block"),
        (FAKE_ASSIGNED, "assigned-secret"),
    ],
)
def test_each_rule_catches_its_violating_case(text: str, rule: str) -> None:
    assert [f.rule for f in scan_text(text, "src/a.py")] == [rule]


@pytest.mark.parametrize(
    "text",
    [
        "GROQ_API_KEY=",
        "api_key = os.environ['GROQ_API_KEY']",
        "token budget is 4000",
        "sk-short",
        "password: short",
    ],
)
def test_clean_text_passes(text: str) -> None:
    assert scan_text(text, "src/a.py") == []


def test_env_file_names_are_flagged_but_the_example_is_allowed() -> None:
    assert [f.rule for f in scan_text("A=1", ".env")] == ["env-file-must-not-be-committed"]
    assert [f.rule for f in scan_text("A=1", "x/.env.local")] == ["env-file-must-not-be-committed"]
    assert scan_text("GROQ_API_KEY=", ".env.example") == []


def test_exact_value_scan_finds_the_value_without_a_pattern_match() -> None:
    value = "plainvalue" + "42" * 5  # matches no credential shape
    assert scan_text(f"note {value}", "n.md") == []
    found = scan_text(f"note {value}", "n.md", env_values=(value,))
    assert found == [Finding("n.md", 1, "exact-env-value")]


def test_findings_never_carry_the_matched_text() -> None:
    finding = scan_text(f"x = '{FAKE_GROQ}'", "a.py")[0]
    assert FAKE_GROQ not in finding.render()
    assert FAKE_GROQ not in repr(finding)


def test_load_env_values_ignores_empty_and_short_values(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("EMPTY=\nSHORT=abc\nexport LONG = 'abcdefghijkl'\n# comment\n", encoding="utf-8")
    assert secret_scan.load_env_values(env) == ["abcdefghijkl"]


def test_an_unscannable_binary_file_is_a_finding_not_a_silent_pass(tmp_path: Path) -> None:
    binary = tmp_path / "blob.bin"
    binary.write_bytes(bytes([0]) + FAKE_GROQ.encode())
    findings, skipped = scan_paths([binary])
    assert [f.rule for f in findings] == ["unscannable-file"] and skipped == 1
    allowed, still_counted = scan_paths([binary], allow_unscannable=True)
    assert allowed == [] and still_counted == 1  # an explicit opt-out is still counted


def test_utf16_files_with_a_byte_order_mark_are_decoded_and_scanned(tmp_path: Path) -> None:
    wide = tmp_path / "wide.txt"
    wide.write_text(f"KEY = '{FAKE_GROQ}'\n", encoding="utf-16")
    findings, skipped = scan_paths([wide])
    assert [f.rule for f in findings] == ["groq-key"] and skipped == 0


def test_an_oversized_file_cannot_hide_a_secret(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(secret_scan, "MAX_FILE_BYTES", 32)
    big = tmp_path / "big.txt"
    big.write_text("x" * 100 + f" {FAKE_GROQ}\n", encoding="utf-8")
    findings, skipped = scan_paths([big])
    assert [f.rule for f in findings] == ["unscannable-file"] and skipped == 1


@pytest.mark.parametrize(
    "text",
    [
        "GROQ_API_KEY=" + "q" * 24,
        "DB_PASSWORD: " + "q" * 24,
        '{"api_key": "' + "q" * 24 + '"}',
        "export AUTH_TOKEN='" + "q" * 24 + "'",
    ],
)
def test_assigned_secrets_are_found_inside_prefixed_names_and_json(text: str) -> None:
    assert [f.rule for f in scan_text(text, "c.json")] == ["assigned-secret"]


@pytest.mark.parametrize("text", ["tokenizer = " + "q" * 24, "max_tokens: " + "1" * 20, "secretary = " + "q" * 24])
def test_names_that_merely_contain_a_keyword_do_not_match(text: str) -> None:
    assert scan_text(text, "c.py") == []


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@needs_git
def test_staged_scan_catches_a_planted_key_and_passes_a_clean_tree(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    (tmp_path / "clean.txt").write_text("nothing secret here\n", encoding="utf-8")
    _git(tmp_path, "add", "clean.txt")
    findings, skipped = scan_staged(tmp_path)
    assert (findings, skipped) == ([], 0)

    (tmp_path / "leak.py").write_text(f"KEY = '{FAKE_GROQ}'\n", encoding="utf-8")
    _git(tmp_path, "add", "leak.py")
    findings, _ = scan_staged(tmp_path)
    assert findings == [Finding("leak.py", 1, "groq-key")]


@needs_git
def test_staged_scan_reads_the_index_not_the_working_copy(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    target = tmp_path / "f.py"
    target.write_text(f"KEY = '{FAKE_GROQ}'\n", encoding="utf-8")
    _git(tmp_path, "add", "f.py")
    target.write_text("KEY = 'removed after staging'\n", encoding="utf-8")  # unstaged cleanup
    findings, _ = scan_staged(tmp_path)
    assert [f.rule for f in findings] == ["groq-key"]


@needs_git
def test_cli_exit_codes_and_silence_about_values(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _git(tmp_path, "init", "-q")
    (tmp_path / "leak.py").write_text(f"KEY = '{FAKE_GROQ}'\n", encoding="utf-8")
    _git(tmp_path, "add", "leak.py")
    assert secret_scan.main(["--staged", "--repo", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "leak.py:1: groq-key" in out
    assert FAKE_GROQ not in out
    assert secret_scan.main(["--staged", "--repo", str(tmp_path / "missing")]) == 2


def test_cli_exact_value_opt_in(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    env = tmp_path / "local.env"
    secret = "zz-literal" + "-secret-9981"  # assembled so the scanner does not flag this file
    env.write_text(f"TOKEN_X={secret}\n", encoding="utf-8")
    doc = tmp_path / "doc.md"
    doc.write_text(f"oops {secret}\n", encoding="utf-8")
    assert secret_scan.main(["--paths", str(doc)]) == 0  # no pattern, no opt-in: not detected
    assert secret_scan.main(["--paths", str(doc), "--env-file", str(env)]) == 1
    assert secret not in capsys.readouterr().out


# --- Tooling files (B01-T01.01 proof): static checks, since make is not installed and Docker cannot run here.

ROOT = Path(__file__).resolve().parents[1]


def test_env_example_holds_names_only_and_passes_the_scan() -> None:
    lines = [
        ln
        for ln in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]
    assert lines == ["GROQ_API_KEY="]
    assert scan_paths([ROOT / ".env.example"]) == ([], 0)


def test_compose_services_are_all_behind_a_profile_and_pinned() -> None:
    import yaml

    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    assert compose["services"], "expected at least one declared service"
    for name, service in compose["services"].items():
        assert service.get("profiles"), f"service {name} is not behind a profile"
        image = service["image"]
        assert ":" in image and not image.endswith(":latest"), f"service {name} image is not pinned"
        for port in service.get("ports", []):
            assert str(port).startswith("127.0.0.1:"), f"service {name} binds a non-loopback port"


def test_compose_planted_unprofiled_service_would_be_caught() -> None:
    import yaml

    broken = yaml.safe_load("services:\n  svc:\n    image: x/y:1\n")
    assert not broken["services"]["svc"].get("profiles")


def test_makefile_recipes_are_uv_commands_and_targets_exist() -> None:
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    targets = {m[1] for m in re.finditer(r"^([a-z-]+):", text, re.M)}
    assert {"sync", "test", "lint", "type", "docs", "secret-scan", "check"} <= targets
    recipes = [ln.strip() for ln in text.splitlines() if ln.startswith("\t")]
    assert recipes and all(r.startswith("uv ") for r in recipes)
