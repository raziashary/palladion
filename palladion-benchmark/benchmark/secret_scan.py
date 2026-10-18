"""Standard-library secret scanner for staged or listed files.

Two checks, neither of which ever prints matched text:

* pattern scan for well-known credential shapes and assigned secrets;
* an opt-in exact-value scan that looks for the literal values held in a local ``.env``.

Only file paths, line numbers and the name of the matching rule are reported.
"""

from __future__ import annotations

import argparse
import codecs
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

MAX_FILE_BYTES = 2 * 1024 * 1024
NUL = bytes([0])
MIN_EXACT_VALUE_LENGTH = 12  # shorter values would match innocent text everywhere

PATTERNS: dict[str, re.Pattern[str]] = {
    "groq-key": re.compile(r"gsk_[A-Za-z0-9]{20,}"),
    "openai-style-key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    "aws-access-key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "private-key-block": re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"),
    "assigned-secret": re.compile(
        r"(?i)(?<![A-Za-z0-9])(?:api[_-]?key|secret|token|passwd|password)[\"']?\s*[=:]\s*[\"']?[A-Za-z0-9_\-/+=]{16,}"
    ),
}
ENV_FILE_NAME = re.compile(r"(?:^|/)\.env(?:\.[A-Za-z0-9_-]+)?$")
ENV_EXAMPLE_NAME = re.compile(r"(?:^|/)\.env\.example$")


@dataclass(frozen=True)
class Finding:
    """A located problem. It deliberately carries no matched text."""

    path: str
    line: int
    rule: str

    def render(self) -> str:
        return f"{self.path}:{self.line}: {self.rule}"


def load_env_values(env_file: Path) -> list[str]:
    """Return the non-trivial literal values in a local env file, for exact-value matching."""
    values: list[str] = []
    for raw in env_file.read_text(encoding="utf-8-sig").splitlines():
        match = re.fullmatch(r"\s*(?:export\s+)?[A-Za-z_][A-Za-z0-9_]*\s*=\s*(.*?)\s*", raw)
        if not match:
            continue
        value = match[1].strip().strip("\"'")
        if len(value) >= MIN_EXACT_VALUE_LENGTH:
            values.append(value)
    return values


def scan_text(text: str, path: str, *, env_values: tuple[str, ...] = ()) -> list[Finding]:
    """Scan one file's text. ``path`` is only a label for the report."""
    findings: list[Finding] = []
    if ENV_FILE_NAME.search(path) and not ENV_EXAMPLE_NAME.search(path):
        findings.append(Finding(path, 1, "env-file-must-not-be-committed"))
    for number, line in enumerate(text.splitlines(), start=1):
        for rule, pattern in PATTERNS.items():
            if pattern.search(line):
                findings.append(Finding(path, number, rule))
        if any(value in line for value in env_values):
            findings.append(Finding(path, number, "exact-env-value"))
    return findings


def _git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(repo), *args],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {args[0]} failed with exit status {result.returncode}")
    return result.stdout


def staged_files(repo: Path) -> list[str]:
    """Paths added, copied, modified or renamed in the index."""
    raw = _git(repo, "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
    return [item for item in raw.decode("utf-8").split("\0") if item]


def scan_bytes(
    data: bytes, path: str, *, env_values: tuple[str, ...] = (), allow_unscannable: bool = False
) -> tuple[list[Finding], bool]:
    """Scan raw file content. Returns findings and whether the file could not be scanned.

    UTF-16 files with a byte-order mark are decoded and scanned. Any other file that is too large or holds
    NUL bytes cannot be scanned; that is a finding unless the caller explicitly allows it, so a secret cannot
    hide in a file the scanner silently skips.
    """
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)) and len(data) <= MAX_FILE_BYTES:
        return scan_text(data.decode("utf-16", errors="replace"), path, env_values=env_values), False
    if len(data) > MAX_FILE_BYTES or NUL in data:
        return ([] if allow_unscannable else [Finding(path, 1, "unscannable-file")]), True
    return scan_text(data.decode("utf-8", errors="replace"), path, env_values=env_values), False


def scan_staged(
    repo: Path, *, env_values: tuple[str, ...] = (), allow_unscannable: bool = False
) -> tuple[list[Finding], int]:
    """Scan the staged content (not the working copy). Returns findings and the unscannable-file count."""
    findings: list[Finding] = []
    skipped = 0
    for path in staged_files(repo):
        found, unscannable = scan_bytes(
            _git(repo, "show", f":{path}"), path, env_values=env_values, allow_unscannable=allow_unscannable
        )
        findings.extend(found)
        skipped += unscannable
    return findings, skipped


def scan_paths(
    paths: list[Path], *, env_values: tuple[str, ...] = (), allow_unscannable: bool = False
) -> tuple[list[Finding], int]:
    findings: list[Finding] = []
    skipped = 0
    for path in paths:
        found, unscannable = scan_bytes(
            path.read_bytes(), path.as_posix(), env_values=env_values, allow_unscannable=allow_unscannable
        )
        findings.extend(found)
        skipped += unscannable
    return findings, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--staged", action="store_true", help="scan the git index of the enclosing repository")
    target.add_argument("--paths", nargs="+", type=Path, help="scan these files")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="opt in: also look for the literal values stored in this local env file",
    )
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="repository for --staged")
    parser.add_argument(
        "--allow-unscannable",
        action="store_true",
        help="do not fail on binary or oversized files (they are still counted in the summary)",
    )
    options = parser.parse_args(argv)
    try:
        env_values = tuple(load_env_values(options.env_file)) if options.env_file else ()
        if options.staged:
            findings, skipped = scan_staged(
                options.repo, env_values=env_values, allow_unscannable=options.allow_unscannable
            )
        else:
            findings, skipped = scan_paths(
                options.paths, env_values=env_values, allow_unscannable=options.allow_unscannable
            )
    except (OSError, RuntimeError, UnicodeDecodeError) as exc:
        print(f"ERROR: secret scan could not run ({type(exc).__name__})", file=sys.stderr)
        return 2
    for finding in findings:
        print(finding.render())
    verdict = "FAIL" if findings else "PASS"
    print(f"{verdict}: {len(findings)} finding(s); {skipped} file(s) could not be scanned (binary or large)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
