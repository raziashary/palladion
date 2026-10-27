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
REF = re.compile(r"\b(?:P\d{2}-T\d{2}(?:\.\d{2})?|G-[A-Z0-9]+|ADR-\d{4}|I\d{2}|T\d{2}|Q\d{2})\b")
CARD = re.compile(
    r"^- \[([ x])\] \*\*(P\d{2}-T\d{2}\.\d{2}) — ([^\n]+)\*\*\n"
    r"(.*?)(?=^- \[[ x]\] \*\*P|\Z)", re.M | re.S,
)


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
    result = set(re.findall(r'<a id="([^"]+)"></a>', text))
    counts: dict[str, int] = {}
    for heading in re.findall(r"^#{1,6}\s+(.+?)\s*#*\s*$", prose(text), re.M):
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        result.add(slug if count == 0 else f"{slug}-{count}")
    return result


def atomic_tasks(plan: str) -> dict[str, dict[str, str]]:
    return {match[1]: dict(re.findall(
        r"^  - \*\*(Files|Depends|Change|Proof):\*\* (.+)$", match[3], re.M,
    )) for match in CARD.findall(plan)}


def validate_atomic_register(plan: str, vision: str, parents: set[str]) -> list[str]:
    errors = []
    cards = CARD.findall(plan)
    tasks = atomic_tasks(plan)
    if len(cards) != len(tasks):
        errors.append("Atomic register has duplicate child task IDs")
    for parent in parents - {"P00-T01", "P00-T02", "P00-T03"}:
        if not any(ident.startswith(parent + ".") for ident in tasks):
            errors.append(f"Work package has no atomic execution tasks: {parent}")
    owned_files: set[str] = set()
    graph: dict[str, set[str]] = {}
    for ident, fields in tasks.items():
        missing = {"Files", "Depends", "Change", "Proof"} - fields.keys()
        if missing:
            errors.append(f"{ident}: missing atomic fields: {sorted(missing)}")
            continue
        if ident.split(".")[0] not in parents:
            errors.append(f"Atomic task has unknown parent: {ident}")
        files = re.findall(r"`([^`]+)`", fields["Files"])
        if not files:
            errors.append(f"{ident}: no exact owning file paths")
        for path in files:
            root_doc = (ident.startswith("P00-") and path in {"README.md", ".gitignore"}) or (
                ident in {"P09-T05.01", "P10-T05.02"} and path == "README.md")
            handoff_doc = ident in {"P09-T05.01", "P10-T06.01"} and path == "palladion-benchmark/docs/development/PALLADION_FIXES.md"
            if ".." in Path(path).parts or not (path.startswith("palladion/") or path == "AGENTS.md" or root_doc or handoff_doc):
                errors.append(f"{ident}: owning file outside planned project scope: {path}")
            owned_files.add(path)
        if not re.match(r"(?:DOC|UNIT|INTEGRATION|SMOKE|MEASUREMENT);", fields["Proof"]):
            errors.append(f"{ident}: missing proof kind")
        if not re.search(r"\bG-[A-Z0-9]+\b", fields["Proof"]):
            errors.append(f"{ident}: missing named gate")
        deps = set(re.findall(r"\bP\d{2}-T\d{2}(?:\.\d{2})?\b", fields["Depends"]))
        if not deps:
            errors.append(f"{ident}: no explicit prerequisite")
        for dep in deps:
            if dep not in tasks and dep not in parents:
                errors.append(f"{ident}: unknown dependency {dep}")
        graph[ident] = set()
        for dep in deps:
            graph[ident].update([dep] if dep in tasks else
                                [child for child in tasks if child.startswith(dep + ".")])
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(ident: str) -> None:
        if ident in visiting:
            errors.append(f"Atomic dependency cycle includes {ident}")
            return
        if ident in visited:
            return
        visiting.add(ident)
        for dep in graph.get(ident, set()):
            visit(dep)
        visiting.remove(ident)
        visited.add(ident)

    for ident in graph:
        visit(ident)
    sections = vision.split("### 12.2 Every file and its responsibility", 1)
    if len(sections) != 2:
        return errors + ["Cannot locate blueprint planned-file responsibility table"]
    table = sections[1].split("### 12.3", 1)[0]
    planned = {"palladion/" + path for path in re.findall(r"^\| `([^`]+)` \|", table, re.M)}
    if not planned:
        errors.append("Cannot locate blueprint planned-file responsibility table")
    for path in sorted(planned - owned_files):
        errors.append(f"Blueprint planned file lacks an atomic owner: {path}")
    return errors


def load_documents() -> dict[str, str]:
    paths = (list(REPO.glob("*.md")) + list((REPO / "palladion").glob("*.md"))
             + list((REPO / "palladion/docs").rglob("*.md")))
    return {path.relative_to(REPO).as_posix(): path.read_text(encoding="utf-8-sig")
            for path in paths}


def validate_decisions(documents: dict[str, str]) -> list[str]:
    errors = []
    ledger = prose(documents[DEV + "ADR_LOG.md"])
    records = re.findall(r"^## (ADR-\d{4}) — [^\n]+\n(.*?)(?=^## |\Z)", ledger, re.M | re.S)
    fields = ("Status", "Authority", "Question", "Why", "Options", "Recommendation",
              "What affects what", "My answer (editable)", "Verification")
    answers: dict[str, str] = {}
    for ident, body in records:
        values = {}
        for field in fields:
            found = re.findall(rf"^\*\*{re.escape(field)}:\*\*[ \t]*([^\n]*)$", body, re.M)
            if len(found) != 1 or not found[0].strip():
                errors.append(f"{ident}: missing, duplicate or empty ADR field: {field}")
            else:
                values[field] = found[0].strip()
        if values.get("Status", "").startswith("ACCEPTED") and not values.get("My answer (editable)"):
            errors.append(f"{ident}: accepted decision has no owner answer")
        answers[ident] = values.get("My answer (editable)", "")
    if not records:
        errors.append("ADR ledger has no structured decision records")
    for row in documents[DEV + "RISKS_AND_OPEN_QUESTIONS.md"].splitlines():
        if re.match(r"^\| Q\d{2} \|", row):
            linked = re.findall(r"\bADR-\d{4}\b", row)
            if not linked or not all(answers.get(ident) for ident in linked):
                errors.append("Risk row lacks an answered decision: " + row.split("|")[1].strip())
    return errors


def validate(documents: dict[str, str]) -> list[str]:
    errors = [f"Missing required document: {path}" for path in REQUIRED if path not in documents]
    if errors:
        return errors
    errors.extend(validate_decisions(documents))
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
        ("TESTING_GATES.md", r"^\| (G-[A-Z0-9]+) \|", "gate"),
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
    plan = documents[DEV + "MASTER_DEV_PLAN.md"]
    for phase in range(9):
        if not any(task.startswith(f"P{phase:02d}-") for task in groups["task"]):
            errors.append(f"Task catalog lacks phase P{phase:02d}")
    errors.extend(validate_atomic_register(plan, documents[VISION], groups["task"]))
    definitions.update(atomic_tasks(plan))
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
                if not re.search(r"\bP\d{2}-T\d{2}\b", line) or not re.search(r"\bG-[A-Z0-9]+\b", line):
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
    plan_key = DEV + "MASTER_DEV_PLAN.md"
    plan = documents[plan_key]
    adr_key = DEV + "ADR_LOG.md"
    ledger = documents[adr_key]
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
        "missing atomic metadata": (plan_key, plan.replace("  - **Files:**", "  - **Omitted:**", 1)),
        "atomic dependency cycle": (plan_key, plan.replace(
            "**Depends:** P00-T03.", "**Depends:** P00-T04.01.", 1)),
        "unowned blueprint file": (plan_key, plan.replace(
            "`palladion/src/evidence_agent/storage/exact.py`",
            "`palladion/src/evidence_agent/storage/not_the_owner.py`")),
        "unknown atomic dependency": (plan_key, plan.replace(
            "**Depends:** P00-T03.", "**Depends:** P99-T99.99.", 1)),
        "missing atomic proof kind": (plan_key, plan.replace("**Proof:** DOC;", "**Proof:** unexplained;", 1)),
        "undefined numeric gate": (key, documents[key] + "\nG-MISSING2\n"),
        "missing ADR question": (adr_key, ledger.replace("**Question:**", "**Omitted question:**", 1)),
        "missing ADR authority": (adr_key, ledger.replace("**Authority:**", "**Omitted authority:**", 1)),
        "missing ADR impact": (adr_key, ledger.replace("**What affects what:**", "**Omitted impact:**", 1)),
        "empty accepted ADR answer": (adr_key, re.sub(
            r"(?m)^\*\*My answer \(editable\):\*\*[^\n]*", "**My answer (editable):**", ledger, count=1)),
        "unanswered risk decision": (DEV + "RISKS_AND_OPEN_QUESTIONS.md", documents[
            DEV + "RISKS_AND_OPEN_QUESTIONS.md"].replace("ADR-0012", "ADR-9999", 1)),
        "unapproved root file owner": (plan_key, plan.replace(
            "`AGENTS.md`, `README.md`, `.gitignore`", "`AGENTS.md`, `unrelated.txt`, `.gitignore`", 1)),
        "runtime task owning root navigation": (plan_key, plan.replace(
            "`palladion/.gitignore`, `palladion/.gitattributes`, `palladion/pyproject.toml`",
            "`README.md`, `palladion/.gitattributes`, `palladion/pyproject.toml`", 1)),
        "handoff exception cannot own benchmark code": (plan_key, plan.replace(
            "`palladion-benchmark/docs/development/PALLADION_FIXES.md`",
            "`palladion-benchmark/benchmark/track_b.py`", 1)),
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
    print(f"PASS: {len(atomic_tasks(documents[DEV + 'MASTER_DEV_PLAN.md']))} atomic tasks; "
          "required fields, dependencies/cycles and blueprint planned-file ownership checked")
    print("Structural check only: no runtime correctness, semantic fidelity or research claim verified")
    return self_test(documents) if options.self_test else 0


if __name__ == "__main__":
    sys.exit(main())
