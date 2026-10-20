"""Validate the benchmark documentation suite's structure; never imply benchmark correctness.

Standard library only. Reads repository Markdown, performs no network requests, starts no
services, writes no files. --self-test applies planted defects to in-memory copies and
requires every one to be rejected.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

REPO = Path(__file__).resolve().parents[3]
ROOT = "palladion-benchmark/"
DEV = ROOT + "docs/development/"
VISION = ROOT + "docs/vision/palladion_retrieval_benchmark_research_protocol.md"
REQUIRED = (
    ROOT + "README.md",
    ROOT + "AGENTS.md",
    ROOT + "docs/README.md",
    VISION,
    *(DEV + name + ".md" for name in (
        "MASTER_DEV_PLAN", "GOAL", "ADR_LOG", "TESTING_GATES", "RESEARCH_PROTOCOL",
        "REQUIREMENTS_TRACEABILITY", "PROJECT_MAP", "PROJECT_MEMORY", "PROJECT_LEARNING",
        "RISKS_AND_OPEN_QUESTIONS", "PROGRESS", "EVIDENCE_LOG",
    )),
)
# Paths a card may own besides the protocol tree (BADR-0010) and the development suite.
EXTRA_FILES = {
    ROOT + "README.md", ROOT + "AGENTS.md", ROOT + "docs/README.md",
    ROOT + "benchmark/generator.py", ROOT + "tests/test_generator_pool.py", ROOT + "docs/dataset_card.md",
    ROOT + "benchmark/secret_scan.py", ROOT + "tests/test_secret_scan.py", ROOT + "benchmark/config.py",
    ROOT + "scripts/qdrant_server.py", ROOT + "tests/test_qdrant_launcher.py",
    ROOT + "tests/test_world.py", ROOT + "tests/test_documents.py", ROOT + "tests/test_live_api.py",
    ROOT + "tests/test_generate_data.py",
    ROOT + "benchmark/fixtures/answer_gold.py", ROOT + "tests/test_answer_gold.py", ROOT + "tests/test_citations.py",
    ROOT + "benchmark/eval/claims.py", ROOT + "tests/test_claims.py", ROOT + "tests/test_policy.py",
    ROOT + "tests/test_abstention.py", ROOT + "tests/test_judge_audit.py", ROOT + "benchmark/track_b.py",
    ROOT + "tests/test_track_b.py", ROOT + "scripts/score_track_b.py", ROOT + "benchmark/eval/score_answers.py",
    ROOT + "tests/test_score_answers.py",
    ROOT + "tests/test_graph_contracts.py",
    ROOT + "benchmark/adapters/worker.py",
    ROOT + "benchmark/llm_proxy.py",
    ROOT + "tests/test_comparator_worker.py",
    ROOT + "tests/test_llm_proxy.py",
    ROOT + "scripts/comparators.py",
    ROOT + "tests/test_comparators.py",
    ROOT + "comparators/hipporag2/worker.py",
    ROOT + "tests/test_hipporag2.py",
    ROOT + "comparators/graphrag/worker.py",
    ROOT + "tests/test_graphrag.py",
    ROOT + "comparators/lightrag/worker.py",
    ROOT + "tests/test_lightrag.py",
    ROOT + "docs/development/PALLADION_FIXES.md",
    ROOT + "tests/test_graph_arms.py",
    ROOT + "benchmark/eval/graph_metrics.py",
    ROOT + "tests/test_graph_metrics.py",
    ROOT + "benchmark/fixtures/phrasebook.py", ROOT + "benchmark/fixtures/artifacts.py",
    ROOT + "benchmark/fixtures/question_gen.py",
    ROOT + "benchmark/eval/score_run.py", ROOT + "tests/test_score_run.py", ROOT + "tests/test_cost_latency.py", ROOT + "tests/test_tables.py", ROOT + "tests/test_palladion_adapter.py", ROOT + "tests/test_build_indices.py", ROOT + "scripts/score_track_a.py", ROOT + "tests/test_run_track_a.py", ROOT + "tests/test_validate_results.py", ROOT + "tests/test_adapters_common.py", ROOT + "tests/test_adapter_pins.py", ROOT + "tests/test_bm25.py", ROOT + "tests/test_dense.py", ROOT + "tests/test_hybrid.py", ROOT + "scripts/palladion_runtime.py", ROOT + "tests/test_palladion_runtime.py", ROOT + "benchmark/adapters/__init__.py", ROOT + "benchmark/adapters/common.py", ROOT + "benchmark/adapters/models.py", ROOT + "benchmark/track_a.py", ROOT + "benchmark/results_check.py", ROOT + "tests/test_evidence_metrics.py",
    ROOT + "tests/test_retrieval_metrics.py",
    ROOT + "tests/conftest.py",
    ROOT + "benchmark/fixtures/entities.py", ROOT + "benchmark/fixtures/knowledge.py",
    ROOT + "benchmark/fixtures/operations.py",
    ROOT + "benchmark/fixtures/audit.py", ROOT + "tests/test_partitions.py", ROOT + "tests/test_label_audit.py",
    ROOT + "tests/test_config_loader.py", ROOT + "tests/test_run_manifest.py",
    ROOT + "tests/test_runner.py", ROOT + "tests/test_cli.py",
}
PHASES = [f"B{n:02d}" for n in range(10)]
ARMS = {"R0", "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R7a", "R7b", "E0", "E1", "E2", "E3", "E4"}

LINK = re.compile(r"\[[^\]\n]+\]\(([^)\n]+)\)")
REF = re.compile(
    r"\b(?:E-B\d{2}-\d{3}|B\d{2}-T\d{2}(?:\.\d{2})?|BG-[A-Z0-9]+|BADR-\d{4}|BI\d{2}|BR\d{2}|OQ\d{2}"
    r"|MT\d{2}|M\d{2}|A\d{2}|H[1-8]|Q\d{1,2})\b"
)
CARD = re.compile(
    r"^- \[([ x])\] \*\*(B\d{2}-T\d{2}\.\d{2}) — ([^\n]+)\*\*\n(.*?)(?=^- \[[ x]\] \*\*B|\Z)",
    re.MULTILINE | re.DOTALL,
)
FIELDS = ("Files", "Depends", "Change", "Proof")
ADR_FIELDS = ("Status", "Authority", "Question", "Why", "Options", "Recommendation",
              "What affects what", "My answer (editable)", "Verification")


def prose(text: str) -> str:
    """Exclude fenced examples from link and reference parsing."""
    result, fence = [], None
    for line in text.splitlines():
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if match:
            marker = match.group(1)[0]
            fence = marker if fence is None else (None if fence == marker else fence)
            continue
        if fence is None:
            result.append(line)
    return "\n".join(result)


def anchors(text: str) -> set[str]:
    result = set(re.findall(r'<a id="([^"]+)"></a>', text))
    counts: dict[str, int] = {}
    for heading in re.findall(r"^#{1,6}\s+(.+?)\s*#*\s*$", prose(text), re.MULTILINE):
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        result.add(slug if count == 0 else f"{slug}-{count}")
    return result


def atomic_tasks(plan: str) -> dict[str, dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    for _, ident, _, body in CARD.findall(plan):
        found[ident] = dict(re.findall(r"^  - \*\*(Files|Depends|Change|Proof):\*\* (.+)$", body, re.MULTILINE))
    return found


def checked_tasks(plan: str) -> dict[str, bool]:
    return {ident: mark == "x" for mark, ident, _, _ in CARD.findall(plan)}


def protocol_tree(vision: str) -> tuple[list[str], int | None]:
    """Return the file paths in the protocol's repository tree and its stated file count."""
    block = re.search(r"```text\npalladion-benchmark/\n(.*?)```", vision, re.DOTALL)
    if not block:
        return [], None
    stack: list[str] = []
    files: list[str] = []
    for line in block.group(1).splitlines():
        match = re.match(r"^((?:│   |    )*)(?:├── |└── )(\S+?)(/?)\s*(?:#.*)?$", line)
        if not match:
            continue
        depth = len(match.group(1)) // 4
        del stack[depth:]
        if match.group(3):
            stack.append(match.group(2))
        else:
            files.append("/".join([*stack, match.group(2)]))
    claim = re.search(r"\*\*Repository specification count:\*\* (\d+) planned files", vision)
    return files, int(claim.group(1)) if claim else None


def phase_of(ident: str) -> int:
    return int(ident[1:3])


def validate_atomic_register(plan: str, vision: str, parents: set[str]) -> list[str]:
    errors: list[str] = []
    cards = CARD.findall(plan)
    tasks = atomic_tasks(plan)
    if len(cards) != len(tasks):
        errors.append("Atomic register has duplicate child task IDs")
    for parent in sorted(parents):
        if not any(ident.startswith(parent + ".") for ident in tasks):
            errors.append(f"Work package has no atomic execution tasks: {parent}")
    tree, claimed = protocol_tree(vision)
    planned = {ROOT + path for path in tree}
    if not tree:
        errors.append("Cannot locate the protocol repository tree")
    elif claimed is not None and claimed != len(tree):
        errors.append(f"Protocol states {claimed} planned files but its tree lists {len(tree)}")
    owned: set[str] = set()
    graph: dict[str, set[str]] = {}
    for ident, fields in tasks.items():
        missing = set(FIELDS) - fields.keys()
        if missing:
            errors.append(f"{ident}: missing atomic fields: {sorted(missing)}")
            continue
        if ident.split(".")[0] not in parents:
            errors.append(f"Atomic task has unknown parent: {ident}")
        files = re.findall(r"`([^`]+)`", fields["Files"])
        if not files:
            errors.append(f"{ident}: no exact owning file paths")
        for path in files:
            in_scope = path.startswith(ROOT) and ".." not in Path(path).parts
            allowed = path in planned or path in REQUIRED or path in EXTRA_FILES or path == DEV + "check_docs.py" or path in {
                ROOT + "pyproject.toml", ROOT + "uv.lock", ROOT + ".gitignore"}
            if not in_scope:
                errors.append(f"{ident}: owning file outside the benchmark folder: {path}")
            elif not allowed:
                errors.append(f"{ident}: owning file is neither in the protocol tree nor a recorded addition: {path}")
            owned.add(path)
        if not re.match(r"(?:DOC|UNIT|INTEGRATION|SMOKE|MEASUREMENT);", fields["Proof"]):
            errors.append(f"{ident}: missing proof kind")
        if not re.search(r"\bBG-[A-Z0-9]+\b", fields["Proof"]):
            errors.append(f"{ident}: missing named gate")
        deps = set(re.findall(r"\bB\d{2}-T\d{2}(?:\.\d{2})?\b", fields["Depends"]))
        if not deps and not fields["Depends"].startswith("None"):
            errors.append(f"{ident}: no explicit prerequisite")
        for dep in deps:
            if dep not in tasks and dep not in parents:
                errors.append(f"{ident}: unknown dependency {dep}")
            elif phase_of(dep) > phase_of(ident):
                errors.append(f"{ident}: depends on a later phase: {dep}")
        graph[ident] = set()
        for dep in deps:
            graph[ident].update([dep] if dep in tasks else [c for c in tasks if c.startswith(dep + ".")])
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
        visiting.discard(ident)
        visited.add(ident)

    for ident in graph:
        visit(ident)
    for path in sorted(planned - owned):
        errors.append(f"Protocol tree file lacks an atomic owner: {path}")
    # Cards sharing a file are sequential: a dependency path must order every pair of writers.
    reach: dict[str, set[str]] = {}

    def ancestors(ident: str) -> set[str]:
        if ident not in reach:
            reach[ident] = set()
            for dep in graph.get(ident, set()):
                reach[ident] |= {dep} | ancestors(dep)
        return reach[ident]

    writers: dict[str, list[str]] = {}
    for ident, fields in tasks.items():
        for path in re.findall(r"`([^`]+)`", fields.get("Files", "")):
            if path in (DEV + "EVIDENCE_LOG.md", DEV + "PROGRESS.md"):
                continue  # Append-only status records.
            writers.setdefault(path, []).append(ident)
    for path, idents in sorted(writers.items()):
        for i, first in enumerate(idents):
            for second in idents[i + 1:]:
                if first not in ancestors(second) and second not in ancestors(first):
                    errors.append(f"Unordered writers of {path}: {first} and {second}")
    return errors


def load_documents() -> dict[str, str]:
    base = REPO / "palladion-benchmark"
    paths = list(base.glob("*.md")) + list((base / "docs").rglob("*.md"))
    return {path.relative_to(REPO).as_posix(): path.read_text(encoding="utf-8-sig") for path in paths}


def validate_decisions(documents: dict[str, str]) -> list[str]:
    errors: list[str] = []
    ledger = prose(documents[DEV + "ADR_LOG.md"])
    records = re.findall(r"^## (BADR-\d{4}) — [^\n]+\n(.*?)(?=^## |\Z)", ledger, re.MULTILINE | re.DOTALL)
    if not records:
        errors.append("ADR ledger has no structured decision records")
    for ident, body in records:
        values: dict[str, str] = {}
        for field in ADR_FIELDS:
            found = re.findall(rf"^\*\*{re.escape(field)}:\*\*[ \t]*([^\n]*)$", body, re.MULTILINE)
            if len(found) != 1 or not found[0].strip():
                errors.append(f"{ident}: missing, duplicate or empty ADR field: {field}")
            else:
                values[field] = found[0].strip()
        status = values.get("Status", "")
        answer = values.get("My answer (editable)", "")
        if not re.match(r"(ACCEPTED|PROPOSED|SUPERSEDED|REJECTED)\b", status):
            errors.append(f"{ident}: unknown status")
        if status.startswith("ACCEPTED") and (not answer or answer.startswith("OPEN")):
            errors.append(f"{ident}: accepted decision has no owner answer")
        if status.startswith("PROPOSED") and not answer.startswith("OPEN"):
            errors.append(f"{ident}: proposed decision must show an OPEN answer")
    ids = [ident for ident, _ in records]
    if len(ids) != len(set(ids)):
        errors.append("ADR ledger has duplicate decision IDs")
    for row in documents[DEV + "RISKS_AND_OPEN_QUESTIONS.md"].splitlines():
        if re.match(r"^\| OQ\d{2} \|", row) and not re.search(r"\bBADR-\d{4}\b", row):
            errors.append("Open question lacks a linked decision: " + row.split("|")[1].strip())
    return errors


def table_ids(text: str, pattern: str) -> list[str]:
    return re.findall(pattern, prose(text), re.MULTILINE)


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

    gates_doc, trace = documents[DEV + "TESTING_GATES.md"], documents[DEV + "REQUIREMENTS_TRACEABILITY.md"]
    risks, plan = documents[DEV + "RISKS_AND_OPEN_QUESTIONS.md"], documents[DEV + "MASTER_DEV_PLAN.md"]
    specs = (
        (plan, r"^\| (B\d{2}-T\d{2}) \|", "task"),
        (gates_doc, r"^\| (BG-[A-Z0-9]+) \|", "gate"),
        (gates_doc, r"^\| (M\d{2}) \|", "mutation"),
        (gates_doc, r"^\| (MT\d{2}) \|", "metamorphic invariant"),
        (trace, r"^\| (BI\d{2}) \|", "invariant"),
        (trace, r"^\| (H\d) \|", "hypothesis"),
        (trace, r"^\| (A\d{2}) \|", "ablation"),
        (trace, r"^\| (Q\d{1,2}) \|", "stratum"),
        (risks, r"^\| (OQ\d{2}) \|", "open question"),
        (risks, r"^\| (BR\d{2}) \|", "risk"),
        (documents[DEV + "ADR_LOG.md"], r"^## (BADR-\d{4}) [—-]", "ADR"),
        (documents[DEV + "EVIDENCE_LOG.md"], r"^## (E-B\d{2}-\d{3}) [—-]", "evidence entry"),
    )
    definitions: set[str] = set()
    groups: dict[str, set[str]] = {}
    for text, pattern, kind in specs:
        found = table_ids(text, pattern)
        if len(found) != len(set(found)):
            errors.append(f"duplicate {kind} definition")
        if not found:
            errors.append(f"no {kind} definitions")
        groups[kind] = set(found)
        definitions.update(found)
    expectations = {
        "mutation": {f"M{i:02d}" for i in range(1, 20)},
        "metamorphic invariant": {f"MT{i:02d}" for i in range(1, 8)},
        "invariant": {f"BI{i:02d}" for i in range(1, 19)},
        "hypothesis": {f"H{i}" for i in range(1, 9)},
        "ablation": {f"A{i:02d}" for i in range(1, 17)},
        "stratum": {f"Q{i}" for i in range(1, 11)},
    }
    for kind, expected in expectations.items():
        if groups[kind] != expected:
            errors.append(f"{kind} definitions must be exactly {min(expected)}..{max(expected)}")
    for phase in PHASES:
        if not any(task.startswith(phase + "-") for task in groups["task"]):
            errors.append(f"Task catalog lacks phase {phase}")
    arms = set(table_ids(documents[DEV + "RESEARCH_PROTOCOL.md"], r"^\| ((?:R\d[ab]?|E\d)) \|"))
    if arms != ARMS:
        errors.append(f"Arm registry must define exactly {sorted(ARMS)}")
    errors.extend(validate_atomic_register(plan, documents[VISION], groups["task"]))
    tasks = atomic_tasks(plan)
    definitions.update(tasks)
    for name, body in documents.items():
        if name == VISION:
            continue  # The protocol has its own illustrative IDs; do not retrofit them.
        for token in sorted(set(REF.findall(prose(body)))):
            if token not in definitions:
                errors.append(f"{name}: undefined stable ID: {token}")

    # Coverage rows must name an owner task and a gate.
    for text in (gates_doc, trace):
        for line in text.splitlines():
            is_row = re.match(r"^\| (?:M\d{2}|MT\d{2}|BI\d{2}|H\d|A\d{2}|Q\d{1,2}|§\d+) \|", line)
            if is_row and (not re.search(r"\bB\d{2}-T\d{2}", line) or not re.search(r"\bBG-[A-Z0-9]+\b", line)):
                errors.append(f"coverage row lacks task or gate: {line[:60]}")
    sections = {int(n) for n in re.findall(r"^\| §(\d+) \|", trace, re.MULTILINE)}
    for number in range(1, 23):
        if number not in sections:
            errors.append(f"Missing protocol section coverage: §{number}")
    memory = [n for n in documents if n.endswith("/PROJECT_MEMORY.md")]
    if memory != [DEV + "PROJECT_MEMORY.md"]:
        errors.append("Exactly one canonical PROJECT_MEMORY.md is required")

    # Status consistency between the plan, GOAL and PROGRESS.
    state = checked_tasks(plan)
    progress = documents[DEV + "PROGRESS.md"]
    rows = dict(re.findall(r"^\| (B\d{2}) \| ([A-Z_]+) \|", progress, re.MULTILINE))
    for phase in PHASES:
        if phase not in rows:
            errors.append(f"PROGRESS phase table lacks {phase}")
            continue
        children = [i for i in state if i.startswith(phase + "-")]
        done = [i for i in children if state[i]]
        if rows[phase] == "DONE" and len(done) != len(children):
            errors.append(f"{phase} is DONE in PROGRESS but has unchecked cards")
        if rows[phase] in {"PLANNED", "DEFERRED"} and done:
            errors.append(f"{phase} is {rows[phase]} in PROGRESS but has checked cards")
    gate_rows = set(re.findall(r"^\| (BG-[A-Z0-9]+) \| (?:NOT_RUN|PARTIAL|PASS|FAIL|BLOCKED) \|", progress, re.MULTILINE))
    if gate_rows != groups["gate"]:
        errors.append("PROGRESS gate table must list every defined gate with a valid state")
    goal = documents[DEV + "GOAL.md"]
    for phase in PHASES:
        if not re.search(rf"^- \[[ x]\] {phase} ", goal, re.MULTILINE):
            errors.append(f"GOAL phase checklist lacks {phase}")
    # A checked card must have its owning files on disk (documents and tooling only exist today).
    for ident, fields in tasks.items():
        if state.get(ident) and "Files" in fields:
            for path in re.findall(r"`([^`]+)`", fields["Files"]):
                if not (REPO / path).exists():
                    errors.append(f"{ident}: checked but file does not exist: {path}")
    return errors


def self_test(documents: dict[str, str]) -> int:
    gates, plan = DEV + "TESTING_GATES.md", DEV + "MASTER_DEV_PLAN.md"
    adr, trace = DEV + "ADR_LOG.md", DEV + "REQUIREMENTS_TRACEABILITY.md"
    risks, progress = DEV + "RISKS_AND_OPEN_QUESTIONS.md", DEV + "PROGRESS.md"
    open_cards = {ident for ident, done in checked_tasks(documents[plan]).items() if not done}
    # Checking a card whose files already exist would not be rejected, so plant the mutation on one that lacks a file.
    open_card = next(
        ident
        for ident, fields in atomic_tasks(documents[plan]).items()
        if ident in open_cards
        and any(not (REPO / path).exists() for path in re.findall(r"`([^`]+)`", fields.get("Files", "")))
    )
    planned = next(p for p in PHASES if re.search(rf"^\| {p} \| PLANNED \|", documents[progress], re.M))
    vision_tree = documents[VISION].replace("│   ├── tracing.py", "│   ├── tracing_renamed.py", 1)
    mutations = {
        "broken local link": (gates, documents[gates] + "\n[bad](missing-proof.md)\n"),
        "broken heading anchor": (gates, documents[gates] + "\n[bad](GOAL.md#absent-heading)\n"),
        "missing document": (DEV + "PROJECT_MEMORY.md", None),
        "duplicate gate": (gates, documents[gates].replace("| BG-HARNESS |", "| BG-DOC |", 1)),
        "undefined task reference": (gates, documents[gates] + "\nB99-T99\n"),
        "undefined gate reference": (gates, documents[gates] + "\nBG-MISSING\n"),
        "undefined decision reference": (gates, documents[gates] + "\nBADR-9999\n"),
        "undefined evidence reference": (gates, documents[gates] + "\nE-B99-999\n"),
        "removed mutation row": (gates, documents[gates].replace("| M19 |", "| removed |", 1)),
        "mutation row without gate": (gates, documents[gates].replace(
            "| M01 | Wrong latest version: newer but not yet effective SOP | B07-T07.01 | BG-FIXTURE, BG-GOLD |",
            "| M01 | Wrong latest version | B07-T07.01 | none |")),
        "removed protocol section row": (trace, documents[trace].replace("| §22 |", "| removed |", 1)),
        "removed invariant row": (trace, documents[trace].replace("| BI18 |", "| removed |", 1)),
        "missing atomic field": (plan, documents[plan].replace("  - **Files:**", "  - **Omitted:**", 1)),
        "missing proof kind": (plan, documents[plan].replace("**Proof:** DOC;", "**Proof:** unexplained;", 1)),
        "missing proof gate": (plan, documents[plan].replace("**Proof:** SMOKE; BG-HARNESS;", "**Proof:** SMOKE; none;", 1)),
        "unknown dependency": (plan, documents[plan].replace("**Depends:** B00-T01.01.", "**Depends:** B99-T99.99.", 1)),
        "atomic dependency cycle": (plan, documents[plan].replace(
            "**Depends:** B00-T01.01.", "**Depends:** B00-T01.02.", 1)),
        "dependency on a later phase": (plan, documents[plan].replace(
            "**Depends:** B01-T01.01.", "**Depends:** B03-T01.01.", 1)),
        "card owns file outside the benchmark": (plan, documents[plan].replace(
            "`palladion-benchmark/benchmark/cli.py`", "`palladion/src/evidence_agent/cli.py`", 1)),
        "card owns unrecorded file": (plan, documents[plan].replace(
            "`palladion-benchmark/benchmark/cli.py`", "`palladion-benchmark/benchmark/surprise.py`", 1)),
        "unowned protocol tree file": (plan, documents[plan].replace("`palladion-benchmark/benchmark/cli.py`", "")),
        "protocol tree changed": (VISION, vision_tree),
        "unordered writers of a shared file": (plan, documents[plan].replace(
            "**Depends:** B04-T01.04, B04-T03.02, B06-T00.03.\n  - **Change:** At 6444345",
            "**Depends:** B04-T01.04, B04-T03.02.\n  - **Change:** At 6444345", 1)),
        "checked card with missing file": (plan, documents[plan].replace(
            f"- [ ] **{open_card} ", f"- [x] **{open_card} ", 1)),
        "missing ADR question": (adr, documents[adr].replace("**Question:**", "**Omitted question:**", 1)),
        "missing ADR authority": (adr, documents[adr].replace("**Authority:**", "**Omitted authority:**", 1)),
        "accepted ADR with OPEN answer": (adr, documents[adr].replace(
            "**My answer (editable):** In this repo, own uv project", "**My answer (editable):** OPEN own uv project", 1)),
        "proposed ADR with an answer": (adr, documents[adr].replace(
            "**Status:** ACCEPTED; 2026-10-18.", "**Status:** PROPOSED; 2026-10-18.", 1)),
        "open question without decision": (risks, documents[risks].replace("| BADR-0006 | OPEN", "| none | OPEN", 1)),
        "PROGRESS done with unchecked cards": (progress, documents[progress].replace(
            f"| {planned} | PLANNED |", f"| {planned} | DONE |", 1)),
        "PROGRESS gate removed": (progress, documents[progress].replace("| BG-TRACKC | NOT_RUN |", "| removed | NOT_RUN |", 1)),
        "second PROJECT_MEMORY": (ROOT + "docs/PROJECT_MEMORY.md", "# copy\n"),
        "arm registry row removed": (DEV + "RESEARCH_PROTOCOL.md", documents[DEV + "RESEARCH_PROTOCOL.md"].replace("| E2 |", "| removed |", 1)),
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
    plan = documents[DEV + "MASTER_DEV_PLAN.md"]
    state = checked_tasks(plan)
    tree, _ = protocol_tree(documents[VISION])
    trace = documents[DEV + "REQUIREMENTS_TRACEABILITY.md"]
    counts = {name: len(table_ids(trace, pat)) for name, pat in (
        ("sections", r"^\| §(\d+) \|"), ("hypotheses", r"^\| (H\d) \|"),
        ("ablations", r"^\| (A\d{2}) \|"), ("strata", r"^\| (Q\d{1,2}) \|"),
        ("invariants", r"^\| (BI\d{2}) \|"))}
    counts["mutations"] = len(table_ids(documents[DEV + "TESTING_GATES.md"], r"^\| (M\d{2}) \|"))
    print(f"PASS: {len(documents)} Markdown files; local links, anchors and stable IDs resolve; "
          + ", ".join(f"{n} {k}" for k, n in counts.items()) + " mapped")
    statuses = dict(re.findall(r"^## (BADR-\d{4}) [^\n]*\n\n\*\*Status:\*\* (\w+)", documents[DEV + "ADR_LOG.md"], re.MULTILINE))
    answered = set(re.findall(r"^\| (OQ\d{2}) \|.*\| ANSWERED", documents[DEV + "RISKS_AND_OPEN_QUESTIONS.md"], re.M))
    for ident, fields in atomic_tasks(plan).items():
        blockers = sorted({d for d in re.findall(r"\b(?:BADR-\d{4}|OQ\d{2})\b", fields.get("Depends", ""))
                           if (d.startswith("OQ") and d not in answered) or (d.startswith("BADR") and statuses.get(d) != "ACCEPTED")})
        if blockers and not state.get(ident):
            print(f"NOTICE: {ident} waits on unanswered {', '.join(blockers)}")
    print(f"PASS: {len(state)} atomic tasks ({sum(state.values())} checked); fields, acyclic dependencies and "
          f"ownership of all {len(tree)} protocol-tree files verified")
    print("Structural check only: no benchmark behavior, semantic fidelity or research claim is verified")
    return self_test(documents) if options.self_test else 0


if __name__ == "__main__":
    sys.exit(main())
