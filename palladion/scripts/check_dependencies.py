"""Check direct imports against declared runtime/dev dependencies, including literal dynamic imports."""
from __future__ import annotations

import argparse
import ast
import re
import sys
import tomllib
from importlib.metadata import packages_distributions
from pathlib import Path
from typing import Mapping


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def imports(source: str) -> set[str]:
    result: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [item.name for item in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module]
        elif isinstance(node, ast.Call):
            dynamic = (isinstance(node.func, ast.Attribute) and node.func.attr == "import_module") or (
                isinstance(node.func, ast.Name) and node.func.id == "__import__")
            if dynamic and node.args and isinstance(node.args[0], ast.Constant):
                value = node.args[0].value
                if isinstance(value, str) and not value.startswith("."):
                    names = [value]
        result.update(name.split(".")[0] for name in names)
    return result - sys.stdlib_module_names - {"__future__", "evidence_agent"}


def missing(source: str, declared: set[str], owners: Mapping[str, list[str]]) -> set[str]:
    return {module for module in imports(source)
            if not {normalize(owner) for owner in owners.get(module, [])} & declared}


def self_test() -> None:
    owners = {"yaml": ["PyYAML"], "huggingface_hub": ["huggingface-hub"],
              "onnxruntime": ["onnxruntime"], "starlette": ["starlette"]}
    controls = ["import yaml", "from huggingface_hub import snapshot_download",
                'importlib.import_module("onnxruntime.capi.onnxruntime_pybind11_state")',
                "from starlette.responses import JSONResponse"]
    for source in controls:
        assert missing(source, set(), owners), source
        assert not missing(source, {normalize(n) for v in owners.values() for n in v}, owners)
    assert not missing("import pathlib; from typing import Protocol", set(), owners)
    assert missing("import unknown_external", set(), owners) == {"unknown_external"}
    assert not imports("from .local import thing")
    print("PASS: four undeclared direct/static/dynamic import controls rejected; declared/stdlib/relative controls pass")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    runtime = {normalize(re.split(r"[<>=!~\[; ]", requirement)[0])
               for requirement in manifest["project"]["dependencies"]}
    dev = runtime | {normalize(re.split(r"[<>=!~\[; ]", requirement)[0])
                     for requirement in manifest["dependency-groups"]["dev"]}
    owners = packages_distributions()
    failures = []
    count = 0
    for directory in ("src", "scripts", "tests"):
        for path in sorted((root / directory).rglob("*.py")):
            count += 1
            absent = missing(path.read_text(encoding="utf-8-sig"), dev if directory == "tests" else runtime, owners)
            if absent:
                failures.append(f"{path.relative_to(root)}: {', '.join(sorted(absent))}")
    if failures:
        print("FAIL: undeclared or unmapped direct imports\n" + "\n".join(failures))
        return 1
    print(f"PASS: direct dependency declarations for {count} Python source/script/test files")
    if args.self_test:
        self_test()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
