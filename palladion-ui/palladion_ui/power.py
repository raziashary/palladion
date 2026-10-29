# ruff: noqa: E501  (this module is mostly sentences that a person reads)
"""Palladion's power: what is on, what the person may turn off, and what each choice costs.

Only levers Palladion itself supports are used: its validated settings file, the reranker switch on its server, and
the evaluator arm that skips the independent critic. Palladion states that those arms are "not switches granting
serving bypasses": the final gate, current access checks, canonical sources, trusted policy time, the safe parser and
the preflight have no switch at all, so this module lists them as locked and never offers one.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

from palladion_ui.settings import Settings

# Palladion's own list of boundaries it refuses to make optional (agent/experiments.py: mandatory_boundaries).
LOCKED = (
    ("final_gate", "The final gate", "Re-reads every claim against its original evidence before anything is released."),
    ("current_acl", "Current access checks", "Who may see what is checked again at every read, never from a cache of an earlier answer."),
    ("canonical_source", "Canonical sources", "Approval, validity window, replacement and original bytes are re-checked for every passage."),
    ("trusted_policy_time", "Trusted policy time", "A policy's date comes from the system's own records, never from the customer or the agent."),
    ("safe_parser", "The safe rule interpreter", "Rules are plain code over fixed operators. Nothing a document says is ever executed."),
    ("preflight", "Deterministic preflight", "Case context and exact codes are read without a model, before the agent starts."),
    ("read_only_tools", "Four read-only tools", "The agent can search, read live data, run a policy and recall memory. It cannot change anything."),
)


@dataclass(frozen=True)
class PowerOptions:
    rerank: bool = True            # the cross-encoder that re-reads the best passages
    critic: bool = True            # the independent second opinion on the draft
    memory: bool = True            # continuity: earlier turns, open gaps, preferences
    critic_searches: int = 2       # counter-searches the critic may run, 0 to 2
    tool_budget: int = 8           # tool calls per question, 1 to 8
    persistent_search: bool = True  # search workers that keep the models loaded

    def __post_init__(self) -> None:
        for name in ("rerank", "critic", "memory", "persistent_search"):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be true or false")
        if not isinstance(self.critic_searches, int) or isinstance(self.critic_searches, bool) \
                or not 0 <= self.critic_searches <= 2:
            raise ValueError("critic_searches must be 0, 1 or 2")
        if not isinstance(self.tool_budget, int) or isinstance(self.tool_budget, bool) or not 1 <= self.tool_budget <= 8:
            raise ValueError("tool_budget must be between 1 and 8")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PowerOptions:
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"Unknown option: {', '.join(sorted(unknown))}")
        return cls(**data)

    @classmethod
    def load(cls, path: Path) -> PowerOptions:
        try:
            return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            return cls()  # a missing or damaged file means full power, never a silently reduced one

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=1), encoding="utf-8")

    @property
    def full(self) -> bool:
        return self == PowerOptions()

    def reductions(self) -> list[str]:
        """Plain words for what is turned down, for banners and the top bar."""
        defaults = PowerOptions()
        words = {"rerank": "reranker off", "critic": "independent review off", "memory": "memory off",
                 "persistent_search": "slower isolated searches"}
        out = [text for key, text in words.items() if getattr(self, key) != getattr(defaults, key)]
        if self.critic_searches != defaults.critic_searches:
            out.append(f"critic counter-searches {self.critic_searches}")
        if self.tool_budget != defaults.tool_budget:
            out.append(f"{self.tool_budget} tool calls")
        return out

    def cli_args(self, model: str | None) -> list[str]:
        args = ["--rerank"] if self.rerank else []
        if model is not None and not self.critic:
            # Palladion's measurement mode without the critic (arm B5). It is not a serving mode, and says so.
            args += ["--evaluator-arm", "B5", "--acknowledge-not-serving"]
        return args

    def overrides(self, supported: set[str]) -> dict[str, Any]:
        wanted = {"continuity_enabled": self.memory, "critic_search_max_calls": self.critic_searches,
                  "tool_max_calls": self.tool_budget,
                  "search_worker_mode": "persistent" if self.persistent_search else "per_request"}
        return {key: value for key, value in wanted.items() if key in supported}


# A flat YAML subset is all Palladion's settings file uses ------------------------------------------------------------

def _scalar(raw: str) -> Any:
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    if raw.lower() in ("true", "false"):
        return raw.lower() == "true"
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if re.fullmatch(r"-?\d+\.\d+", raw):
        return float(raw)
    return raw


def load_flat_yaml(path: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line or line[0] in " \t":
            continue
        key, _, raw = line.partition(":")
        out[key.strip()] = _scalar(raw.strip())
    return out


def dump_flat_yaml(values: dict[str, Any]) -> str:
    def render(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        return json.dumps(value) if isinstance(value, str) else repr(value)  # a JSON string is valid YAML

    header = "# Generated by palladion-ui from Palladion's own settings plus the chosen options. Do not edit.\n"
    return header + "".join(f"{key}: {render(value)}\n" for key, value in values.items())


def supported_settings(app_dir: Path) -> set[str]:
    """The settings keys this Palladion accepts, read from its own source (its model forbids unknown keys)."""
    try:
        source = (app_dir / "src/evidence_agent/settings.py").read_text(encoding="utf-8")
    except OSError:
        return set()
    return set(re.findall(r"^    ([a-z_0-9]+): ", source, re.MULTILINE))


def write_settings(ui: Settings, options: PowerOptions) -> Path:
    """Palladion's settings file with the chosen options applied; returns the file for serve.py --settings."""
    base = load_flat_yaml(ui.app_dir / "config" / "settings.yaml")
    base.update(options.overrides(supported_settings(ui.app_dir)))
    base["qdrant_url"], base["qdrant_collection"] = ui.qdrant_url, ui.collection
    target = ui.palladion_settings_file
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dump_flat_yaml(base), encoding="utf-8")
    return target


def read_pins(app_dir: Path) -> dict[str, Any]:
    """The pinned retrieval models, as Palladion's own source states them."""
    def constant(path: str, name: str) -> str | None:
        try:
            found = re.search(rf'^{name} = "?([^"\n]+)"?', (app_dir / path).read_text(encoding="utf-8"), re.MULTILINE)
        except OSError:
            return None
        return found.group(1) if found else None

    depth = constant("src/evidence_agent/retrieval/rerank.py", "DEFAULT_RERANK_CANDIDATES")
    return {"embedding": constant("src/evidence_agent/retrieval/embeddings.py", "MODEL_REPOSITORY"),
            "reranker": constant("src/evidence_agent/retrieval/rerank.py", "RERANKER_NAME"),
            "rerank_depth": int(depth) if depth and depth.isdigit() else None}


# The report the Settings screen shows ----------------------------------------------------------------------------------

def _item(item_id: str, label: str, state: str, detail: str, **extra: Any) -> dict[str, Any]:
    return {"id": item_id, "label": label, "state": state, "detail": detail, **extra}


def report(ui: Settings, options: PowerOptions, runtime: dict[str, Any], neo4j_up: bool) -> dict[str, Any]:
    base = load_flat_yaml(ui.app_dir / "config" / "settings.yaml")
    pins = read_pins(ui.app_dir)
    supported = supported_settings(ui.app_dir)
    model = runtime.get("model") if runtime.get("state") == "ready" else None
    labels = dict(ui.models)
    on = lambda flag: "on" if flag else "off"  # noqa: E731

    finding = [
        _item("hybrid", "Keyword and meaning search", "locked",
              f"Keyword matching (BM25, {base.get('bm25_profile', 'english')}) and meaning matching "
              f"({pins['embedding'] or 'embedding model'}) run together and are merged by reciprocal rank fusion."),
        _item("rerank", "Reranker", on(options.rerank),
              f"{pins['reranker'] or 'A cross-encoder'} re-reads up to {pins['rerank_depth'] or 20} passages together with the "
              "question and puts the best first. It runs after the safety checks and can only reorder what passed.",
              control="toggle", key="rerank", value=options.rerank,
              effect="Results stay in the order the merged search gives. Ranking is less precise; nothing is blocked."),
        _item("exact", "Exact-code lane", "locked",
              "Codes such as POL-001 or POL-001@v2 are looked up by identity, and an unknown code is never replaced by a similar one."),
        _item("eligibility", "Which documents can apply", "locked",
              "Only approved documents the person may read, valid at the case's time and not replaced, can be returned."),
        _item("workers", "Persistent search workers", "unavailable" if "search_worker_mode" not in supported else on(options.persistent_search),
              "Search processes that keep the models loaded between questions. A new process per search starts about 12 seconds slower.",
              control="toggle" if "search_worker_mode" in supported else None, key="persistent_search", value=options.persistent_search,
              effect="Every agent search starts a fresh, strictly isolated process. Same results, much slower."),
        _item("graph", "Graph navigation", "unavailable",
              "Follows source-proven links between passages. Needs Neo4j, which is not set up in this runtime, and the pilot "
              "found no extra recoveries, so Palladion keeps it off by default."
              + (" (A Neo4j is reachable here, but the runtime was not seeded for it.)" if neo4j_up else "")),
    ]
    thinking = [
        _item("model", "Agent model", "on" if model else "off",
              f"{labels.get(model, model)} decides which read tools to call and drafts the claims. It never has the last word."
              if model else "No model is running. Questions run a plain document search. Choose a model in the top bar to enable the agent."),
        _item("critic", "Independent critic", on(options.critic),
              f"A second model, in a separate conversation, challenges the draft and may search for a missing exception "
              f"(up to {base.get('critic_max_calls', 3)} calls).",
              control="toggle", key="critic", value=options.critic, experiment=True,
              effect="Palladion switches to its measurement mode, which it says is not a serving mode. The gate still runs, but it cannot see a "
                     "review, so it withholds policy-based and operational claims and adds \"mandatory critic review\" as a gap."),
        _item("critic_searches", "Critic counter-searches", "on" if options.critic_searches else "off",
              "How many extra searches the critic may run to look for evidence the draft missed.",
              control="number", key="critic_searches", value=options.critic_searches, min=0, max=2,
              effect="The critic can check fewer places for a missing exception."),
        _item("tool_budget", "Tool calls per question", "on", "The most reads (search, live data, policy, memory) the agent may make for one question.",
              control="number", key="tool_budget", value=options.tool_budget, min=1, max=8,
              effect="The agent may run out of reads before it has the evidence, and the answer says so."),
        _item("budgets", "Model call limits", "locked",
              f"At most {base.get('main_max_calls', 5)} agent calls (one is reserved for the final wording) and "
              f"{base.get('critic_max_calls', 3)} critic calls per question, within {base.get('request_timeout_seconds', 60)} seconds."),
    ]
    remembering = [
        _item("memory", "Memory and continuity", on(options.memory),
              "Earlier turns of the session, open gaps, rechecked evidence handles and the person's private preferences, as untrusted context.",
              control="toggle", key="memory", value=options.memory,
              effect="Every question starts fresh. The agent no longer reads earlier turns or preferences."),
    ]
    locked = [_item(i, label, "locked", detail) for i, label, detail in LOCKED]
    health = [
        _item("qdrant", "Vector search (Qdrant)", "on" if runtime.get("qdrant") else "off",
              "Holds the keyword and meaning indexes. Never the authority: every hit is re-checked against the original file."),
        _item("palladion", "Palladion", "on" if runtime.get("api") else "off", f"State: {runtime.get('state', 'unknown')}."),
        _item("neo4j", "Neo4j (graph)", "on" if neo4j_up else "off", "Only needed for graph navigation."),
    ]
    return {"options": asdict(options), "full": options.full, "reductions": options.reductions(), "model": model,
            "groups": [
                {"id": "finding", "title": "Finding evidence", "items": finding},
                {"id": "thinking", "title": "Thinking and checking", "items": thinking},
                {"id": "remembering", "title": "Remembering", "items": remembering},
                {"id": "locked", "title": "Always on: Palladion has no switch for these", "items": locked},
                {"id": "health", "title": "What is running", "items": health}]}
