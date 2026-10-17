"""Validate Palladion's documentation structure; never imply runtime correctness.

Standard library only. Reads repository Markdown, performs no network requests,
starts no services, writes no files. --self-test mutates copies in memory.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


REPO = Path(__file__).resolve().parents[3]
DEV = "palladion/docs/development/"
VISION = "palladion/docs/vision/palladion-blueprint-v2.md"
REQUIRED = (
    "AGENTS.md",
    "README.md",
    "palladion/docs/README.md",
    VISION,
    *(DEV + name + ".md" for name in (
        "MASTER_DEV_PLAN", "GOAL", "ADR_LOG", "TESTING_GATES",
        "RESEARCH_PROTOCOL", "REQUIREMENTS_TRACEABILITY", "PROJECT_MAP",
        "PROJECT_MEMORY", "PROJECT_LEARNING", "RISKS_AND_OPEN_QUESTIONS",
        "PROGRESS", "EVIDENCE_LOG",
    )),
)
LINK = re.compile(r"\[[^\]\n]+\]\(([^)\n]+)\)")
REF = re.compile(r"\b(?:P\d{2}-T\d{2}|G-[A-Z]+|ADR-\d{4}|I\d{2}|T\d{2}|Q\d{2})\b")


def prose(text: str) -> str:
    """Exclude fenced examples from link/heading parsing."""
    result = []
    fence = None
    for line in text.splitlines():
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if match:
            marker = match.group(1)[0]
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
            continue
        if fence is None:
            result.append(line)
    return "\n".join(result)


def anchors(text: str) -> set[str]:
    result: set[str] = set()
    counts: dict[str, int] = {}
    for heading in re.findall(r"^#{1,6}\s+(.+?)\s*#*\s*$", prose(text), re.M):
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        result.add(slug if count == 0 else f"{slug}-{count}")
    return result


def load_documents() -> dict[str, str]:
    paths = list(REPO.glob("*.md")) + list((REPO / "palladion/docs").rglob("*.md"))
    return {path.relative_to(REPO).as_posix(): path.read_text(encoding="utf-8-sig")
            for path in paths}


def validate(documents: dict[str, str]) -> list[str]:
    errors = [f"Missing required document: {path}" for path in REQUIRED if path not in documents]
    if errors:
        return errors
    for name, body in documents.items():
        for raw in LINK.findall(prose(body)):
            target = raw.strip().strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc:
                continue  # Remote URLs are deliberately not fetched.
            path = (REPO / name).parent / unquote(parsed.path) if parsed.path else REPO / name
            path = path.resolve()
            if not path.is_relative_to(REPO):
                errors.append(f"{name}: local link leaves repository: {target}")
                continue
            key = path.relative_to(REPO).as_posix()
            if key not in documents and not path.exists():
                errors.append(f"{name}: broken local link: {target}")
            elif parsed.fragment and key in documents and unquote(parsed.fragment) not in anchors(documents[key]):
                errors.append(f"{name}: missing heading anchor: {target}")

    # Definitions have dedicated owners; mentions elsewhere do not create a definition.
    specs = (
        ("MASTER_DEV_PLAN.md", r"^\| (P\d{2}-T\d{2}) \|", "task"),
        ("TESTING_GATES.md", r"^\| (G-[A-Z]+) \|", "gate"),
        ("TESTING_GATES.md", r"^\| (T\d{2}) \|", "hard case"),
        ("REQUIREMENTS_TRACEABILITY.md", r"^\| (I\d{2}) \|", "invariant"),
        ("ADR_LOG.md", r"^## (ADR-\d{4}) [—–-]", "ADR"),
        ("RISKS_AND_OPEN_QUESTIONS.md", r"^\| (Q\d{2}) \|", "open question"),
    )
    definitions: set[str] = set()
    groups: dict[str, set[str]] = {}
    for file, pattern, kind in specs:
        found = re.findall(pattern, prose(documents[DEV + file]), re.M)
        if len(found) != len(set(found)):
            errors.append(f"{file}: duplicate {kind} definition")
        if not found:
            errors.append(f"{file}: no {kind} definitions")
        groups[kind] = set(found)
        definitions.update(found)
    expected_cases = {f"T{i:02d}" for i in range(1, 25)}
    expected_invariants = {f"I{i:02d}" for i in range(1, 16)}
    if groups["hard case"] != expected_cases:
        errors.append("Hard-case definitions must cover exactly T01–T24")
    if groups["invariant"] != expected_invariants:
        errors.append("Invariant definitions must cover exactly I01–I15")
    expected_tasks = {f"P{phase:02d}-T{task:02d}"
                      for phase, count in enumerate((3, 4, 4, 3, 4, 3, 3, 3, 4))
                      for task in range(1, count + 1)}
    if groups["task"] != expected_tasks:
        errors.append("Task catalog differs from the documented P00–P08 task inventory")
    plan = documents[DEV + "MASTER_DEV_PLAN.md"]
    if not re.search(r"^## X01 .*deferred", plan, re.M):
        errors.append("Missing deferred external comparison phase X01")
    for name, body in documents.items():
        if name == VISION:
            continue  # Vision has its own illustrative IDs; do not retrofit it.
        for token in set(REF.findall(prose(body))):
            if token not in definitions:
                errors.append(f"{name}: undefined stable ID: {token}")

    # Each coverage row must name a real owner task and a gate.
    for file, prefix in (("TESTING_GATES.md", r"T\d{2}"),
                         ("REQUIREMENTS_TRACEABILITY.md", r"I\d{2}")):
        for line in documents[DEV + file].splitlines():
            if re.match(rf"^\| {prefix} \|", line):
                if not re.search(r"\bP\d{2}-T\d{2}\b", line) or not re.search(r"\bG-[A-Z]+\b", line):
                    errors.append(f"{file}: coverage row lacks task/gate: {line}")
    memory_files = [name for name in documents if name.endswith("/PROJECT_MEMORY.md")]
    if memory_files != [DEV + "PROJECT_MEMORY.md"]:
        errors.append("Exactly one canonical PROJECT_MEMORY.md is required")
    for number in range(1, 19):
        if f"| §{number} " not in documents[DEV + "REQUIREMENTS_TRACEABILITY.md"]:
            errors.append(f"Missing blueprint section coverage: §{number}")
    return errors


def self_test(documents: dict[str, str]) -> int:
    key = DEV + "TESTING_GATES.md"
    mutations = {
        "broken local link": (key, documents[key] + "\n[bad](missing-proof.md)\n"),
        "broken heading": (key, documents[key] + "\n[bad](GOAL.md#absent-heading)\n"),
        "missing document": (DEV + "PROJECT_MEMORY.md", None),
        "missing hard-case ID": (key, documents[key].replace("| T24 |", "| removed |")),
        "duplicate gate ID": (key, documents[key] + "\n| G-DOC | duplicate |\n"),
        "unknown task reference": (key, documents[key] + "\nP99-T99\n"),
        "missing task/gate mapping": (key, documents[key].replace(
            "| T01 | Similar old SOP cannot win against applicable approved policy | P02-T03 | G-RETRIEVAL, G-GATE |",
            "| T01 | Similar old SOP | none | none |")),
    }
    for label, (path, replacement) in mutations.items():
        altered = dict(documents)
        if replacement is None:
            del altered[path]
        else:
            altered[path] = replacement
        if altered == documents or not validate(altered):
            print(f"FAIL: validator did not reject {label}")
            return 1
    print(f"PASS: {len(mutations)} in-memory negative checks rejected; repository unchanged")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    options = parser.parse_args()
    documents = load_documents()
    errors = validate(documents)
    if errors:
        print("FAIL: documentation structural checks")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"PASS: {len(documents)} Markdown files; local links/anchors and stable IDs resolve; "
          "18 sections, 15 invariants, 24 hard cases mapped")
    print("Structural check only: no runtime correctness, semantic fidelity or research claim verified")
    return self_test(documents) if options.self_test else 0


if __name__ == "__main__":
    sys.exit(main())
