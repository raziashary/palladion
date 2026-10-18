"""Top-level command line: configuration checks, arm listing and the capability matrix.

Exit status: 0 success, 1 a validation failure, 2 a usage error such as an unknown arm.
Nothing here contacts a provider or reads credentials.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from benchmark import __version__
from benchmark.config import ConfigError, config_digest, load_all
from benchmark.contracts import ContractError
from benchmark.registry import ArmRegistry, default_registry

DEFAULT_CONFIG_DIR = Path(__file__).resolve().parents[1] / "configs"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="benchmark", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version", help="print the package version")
    for name, help_text in (
        ("validate-config", "load and validate every configuration file"),
        ("list-arms", "list the registered arms and check them against comparators.yaml"),
        ("capability-matrix", "print the declared capabilities of the arms"),
    ):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("--config-dir", type=Path, default=DEFAULT_CONFIG_DIR)
        if name == "validate-config":
            command.add_argument("--confirmatory", action="store_true", help="refuse any unpinned entry")
        if name == "capability-matrix":
            command.add_argument("--arm", action="append", default=None, help="limit to this arm id (repeatable)")
    return parser


def _checked_registry(config_dir: Path) -> ArmRegistry:
    registry = default_registry()
    registry.check_against_config(load_all(config_dir).comparators)
    return registry


def main(argv: list[str] | None = None) -> int:
    options = _parser().parse_args(argv)
    try:
        if options.command == "version":
            print(__version__)
            return 0
        if options.command == "validate-config":
            bundle = load_all(options.config_dir, confirmatory=options.confirmatory)
            mode = "confirmatory" if options.confirmatory else "exploratory"
            print(
                f"PASS: configuration valid ({mode}); {len(bundle.comparators.arms)} arms; "
                f"digest {config_digest(bundle)[:16]}"
            )
            return 0
        registry = _checked_registry(options.config_dir)
        if options.command == "list-arms":
            for arm_id in registry.ids():
                print(f"{arm_id}\t{registry.get(arm_id).name}")
            return 0
        wanted = options.arm
        unknown = sorted(set(wanted or []) - set(registry.ids()))
        if unknown:
            print(f"ERROR: unknown arm: {', '.join(unknown)}", file=sys.stderr)
            return 2
        print(registry.render_matrix(wanted))
        return 0
    except (ConfigError, ContractError, OSError) as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
