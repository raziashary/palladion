"""The descriptive comparison report of Palladion beside the other systems (B08-T06.01, B08-T08.06, BADR-0043/0044).

The report is assembled from run directories and from nothing else: every figure traces to a scorecard, a book or a
manifest the runs wrote, and each run's matched-list digest and commit are listed in its provenance table. It states
whatit is (exploratory, not sealed, free tier, one run per question), puts run states beside scores, reports cost beside
quality, lists the negative and the favourable findings alike, marks a system another beats on every axis as dominated
from the data, and never reduces anything to one number or one winner.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from benchmark.analysis.plots import Point, bars_svg, mark_dominated, scatter_svg
from benchmark.analysis.tables import ALL_STRATA, Cell, Scorecard, answer_effects, build_scorecard, format_interval
from benchmark.config import load_evaluation_config
from benchmark.contracts import QUOTA_BLOCKED_CODE, ContractError
from benchmark.eval.cost_latency import latency_summary
from benchmark.eval.score_answers import AnswerRunScore, ArmAnswerSummary, score_answer_run, summarize_arm
from benchmark.eval.score_run import HARM_METRICS, RunScore, score_run
from benchmark.eval.statistics import Interval
from benchmark.fixtures.manifest import Layout, Namespace, read_identity
from benchmark.matched import load as matched_load
from benchmark.run_manifest import ManifestError, read_verified
from benchmark.track_a import WITHDRAWN, read_withdrawn

CONFIGS = Path(__file__).resolve().parents[2] / "configs"
PRIMARY_METRIC = "complete_set_at_k"
SHARED_INDEX_ARMS = frozenset({"R2", "R3"})
RECALL_METRIC = "valid_source_recall"
MRR_METRIC = "mrr"
TRACK_A_METRICS = (PRIMARY_METRIC, RECALL_METRIC, MRR_METRIC)
TRACK_C_NOTE = "NOT_RUN or NOT_OBSERVABLE cells are results of the run, never zeros."


class ReportError(ContractError):
    """The report cannot be assembled from what it was given."""


@dataclass(frozen=True)
class Provenance:
    """Where a table came from: the run directory, its run id, the commit of any system under test, the lists."""

    label: str
    run_dir: str
    run_id: str
    commit: str | None
    matched_list_sha256: str | None


@dataclass(frozen=True)
class ArmCost:
    """Query-time cost of one arm from the generator's own records; None is unknown, never zero."""

    calls: int
    prompt_tokens: int
    completion_tokens: int
    provider_latency_ms: float | None  # mean over answered calls, the provider's time without the harness's pace

    @property
    def tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True)
class TrackARun:
    condition: str
    provenance: Provenance
    score: RunScore
    card: Scorecard
    builds: Sequence[Mapping[str, Any]]
    reference: str
    primary: str


@dataclass(frozen=True)
class TrackBRun:
    provenance: Provenance
    score: AnswerRunScore
    summaries: Sequence[ArmAnswerSummary]
    effects: Sequence[Any]
    costs: Mapping[str, ArmCost]
    planned_pairs: int


@dataclass(frozen=True)
class TrackCRun:
    provenance: Provenance
    summary: Mapping[str, Any]
    arms: Sequence[str]
    turn_states: Mapping[str, Mapping[str, int]]  # system -> run state -> turns, from the ledger
    case_states: Mapping[str, Mapping[str, int]]  # system -> run state -> mutation cases


@dataclass(frozen=True)
class GraphRun:
    """A graph comparator's run, reported on its own corpus and never pooled with the full-corpus tables."""

    provenance: Provenance
    corpus: str
    summary: Mapping[str, Any]


@dataclass(frozen=True)
class ComparisonInputs:
    track_a: Sequence[TrackARun]
    track_b: TrackBRun | None
    track_c: Sequence[TrackCRun]
    graph: Sequence[GraphRun]
    matched_digests: Mapping[str, str]

    @property
    def provenances(self) -> list[Provenance]:
        runs: list[Provenance] = [r.provenance for r in self.track_a]
        if self.track_b is not None:
            runs.append(self.track_b.provenance)
        return [*runs, *(r.provenance for r in self.track_c), *(r.provenance for r in self.graph)]

    @property
    def commits(self) -> set[str]:
        return {p.commit for p in self.provenances if p.commit}


# --------------------------------------------------------------------------- reading the runs


def provenance_of(label: str, run_dir: Path) -> Provenance:
    """Read a run's identity from its verified manifest (``manifest-*.json`` or Track C's ``manifest.json``)."""
    paths = sorted(run_dir.glob("manifest-*.json")) or [run_dir / "manifest.json"]
    try:
        manifest = read_verified(paths[0])
    except (ManifestError, ContractError, OSError, ValueError) as exc:
        raise ReportError(f"{run_dir.name} has no manifest that verifies") from exc
    config = manifest.retrieval_config
    commit = next((m.system_under_test.commit for m in (read_verified(p) for p in paths) if m.system_under_test), None)
    return Provenance(label, run_dir.name, manifest.run_id, commit, config.get("matched_list_sha256"))


def arm_costs(records_path: Path) -> dict[str, ArmCost]:
    """Per arm: calls, tokens and the provider's mean latency, from the shared generator's records."""
    calls: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if records_path.exists():
        for line in records_path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            calls[str(row.get("arm_id"))].append(row)
    costs = {}
    for arm, rows in sorted(calls.items()):
        answered = [r["latency_ms"] for r in rows if r.get("status") == "OK" and r.get("latency_ms") is not None]
        costs[arm] = ArmCost(
            len(rows),
            sum(r.get("prompt_tokens") or 0 for r in rows),
            sum(r.get("completion_tokens") or 0 for r in rows),
            sum(answered) / len(answered) if answered else None,
        )
    return costs


def load_track_a(
    condition: str, run_dir: Path, root: Path, *, reference: str, primary: str, withdrawn: Mapping[str, str]
) -> TrackARun:
    """Score a Track A run directory the way ``scripts/score_track_a.py`` does and keep the scorecard."""
    config = json.loads((run_dir / "run_config.json").read_text(encoding="utf-8"))
    evaluation = load_evaluation_config(CONFIGS / "evaluation.yaml")
    published = Layout(root).path(Namespace.PUBLISHED)
    identity = read_identity(published)
    score = score_run(
        ledger_path=run_dir / "ledger.jsonl",
        manifests={arm: run_dir / f"manifest-{arm}.json" for arm in config["arms"]},
        gold_path=Layout(root).path(Namespace.DEV_ANNOTATIONS) / f"questions_{config['split']}.jsonl",
        published_dir=published,
        roles={p.principal_id: p.role_id for p in identity.principals},
        kinds=evaluation.slot_kinds,
        k=int(config["k"]),
        withdrawn=withdrawn,
    )
    card = build_scorecard(
        score, metrics=(*TRACK_A_METRICS, *sorted(HARM_METRICS)), stats=evaluation.statistics,
        reference=reference, primary=primary,
    )  # fmt: skip
    return TrackARun(
        condition,
        provenance_of(f"Track A {condition}", run_dir),
        score,
        card,
        config.get("builds", []),
        reference,
        primary,
    )


def load_track_b(run_dir: Path, root: Path, *, reference: str, primary: str, withdrawn: Mapping[str, str]) -> TrackBRun:
    """Score a Track B run directory the way ``scripts/score_track_b.py`` does."""
    evaluation = load_evaluation_config(CONFIGS / "evaluation.yaml")
    score = score_answer_run(run_dir=run_dir, root=root, withdrawn=withdrawn)
    summaries = [
        summarize_arm(score, arm, evaluation.loss_matrix, evaluation.statistics.confidence) for arm in score.arms
    ]
    effects = answer_effects(score, reference=reference, primary=primary, stats=evaluation.statistics)
    config = json.loads((run_dir / "run_config.json").read_text(encoding="utf-8"))
    planned = int(config["questions"]) * len(config["arms"])
    return TrackBRun(
        provenance_of("Track B C2", run_dir),
        score,
        summaries,
        effects,
        arm_costs(run_dir / "generation_records.jsonl"),
        planned,
    )


def _states_by_arm(ledger: Path, *, cases: bool) -> dict[str, dict[str, int]]:
    """System -> run state -> count over a Track C ledger's turns (or its mutation cases). A pair a daily limit or a
    cap stopped is its own state, QUOTA_BLOCKED, not a NOT_RUN of the system."""
    counts: dict[str, dict[str, int]] = {}
    if ledger.exists():
        for line in ledger.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            parts = str(row["arm"]).split("|")
            if (len(parts) > 1 and parts[1] == "mutation") != cases:
                continue
            state = QUOTA_BLOCKED_CODE if row.get("code") == QUOTA_BLOCKED_CODE else str(row["status"])
            arm = counts.setdefault(parts[0], {})
            arm[state] = arm.get(state, 0) + 1
    return counts


def load_track_c(run_dir: Path) -> TrackCRun:
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    arms = sorted(summary.get("spend", {}))
    return TrackCRun(
        provenance_of("Track C", run_dir),
        summary,
        arms,
        _states_by_arm(run_dir / "ledger.jsonl", cases=False),
        _states_by_arm(run_dir / "ledger.jsonl", cases=True),
    )


def main(argv: Sequence[str] | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Assemble the descriptive comparison report from run directories.")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--track-a", action="append", default=[], metavar="CONDITION=DIR")
    parser.add_argument("--track-b", type=Path, default=None)
    parser.add_argument("--track-c", type=Path, action="append", default=[])
    parser.add_argument("--reference", default="R3")
    parser.add_argument("--primary", default="R7a")
    parser.add_argument("--matched", action="append", default=[], metavar="NAME=FILE")
    parser.add_argument("--withdrawn", type=Path, default=WITHDRAWN)
    options = parser.parse_args(argv)
    try:
        withdrawn = read_withdrawn(options.withdrawn)
        track_a = []
        for item in options.track_a:
            condition, _, directory = item.partition("=")
            track_a.append(
                load_track_a(
                    condition,
                    Path(directory),
                    options.root,
                    reference=options.reference,
                    primary=options.primary,
                    withdrawn=withdrawn,
                )
            )
        track_b = (
            load_track_b(
                options.track_b, options.root, reference=options.reference, primary=options.primary, withdrawn=withdrawn
            )
            if options.track_b
            else None
        )
        track_c = [load_track_c(d) for d in options.track_c]
        digests = {
            name: matched_load(Path(file)).digest for name, _, file in (m.partition("=") for m in options.matched)
        }
        inputs = ComparisonInputs(track_a, track_b, track_c, [], digests)
        path = write_report(options.out, inputs)
    except (ContractError, OSError, ValueError, KeyError) as exc:
        print(f"refused: {str(exc)[:300]}", file=sys.stderr)
        return 2
    print(f"PASS: report written to {path}")
    return 0


# --------------------------------------------------------------------------- tables


def _states(summary: ArmAnswerSummary) -> str:
    return ", ".join(f"{k}={v}" for k, v in summary.states.items()) or "none"


def _cell_of(card: Scorecard, stratum: str, arm: str, metric: str) -> Cell:
    try:
        return card.cell(stratum, arm, metric)
    except StopIteration:
        raise ReportError(f"the scorecard has no {metric} for {arm} in {stratum}") from None


def _interval(card: Scorecard, stratum: str, arm: str, metric: str) -> str:
    cell = _cell_of(card, stratum, arm, metric)
    return format_interval(cell.itt if metric not in HARM_METRICS else cell.conditional)


def _bounds(card: Scorecard, arm: str, metric: str) -> str:
    cell = _cell_of(card, ALL_STRATA, arm, metric)
    if cell.harm_bounds is None:
        return "n/a"
    lower, upper = cell.harm_bounds
    return f"{lower:.3f} to {upper:.3f}" if lower != upper else f"{lower:.3f}"


def _latency(run: TrackARun, arm: str) -> str:
    records = [r for r in run.score.ledger_records if r.arm == arm]
    summary = latency_summary(records, deadline_ms=None)
    if not summary.completed:
        return "NOT_OBSERVABLE"
    return f"p50 {summary.percentiles['p50']:.0f} ms, p95 {summary.percentiles['p95']:.0f} ms"


def _build_cost(run: TrackARun, arm: str) -> str:
    record = next((b for b in run.builds if b.get("arm") == arm), None)
    if record is None or record.get("status") != "BUILT":
        return "NOT_RUN"
    if arm == "R7a":
        loaded = record.get("load_seconds")
        return (
            "NOT_OBSERVABLE (the load happens inside Palladion; no time was recorded)"
            if loaded is None
            else f"{loaded:.0f} s (corpus load and indexing inside Palladion)"
        )
    if arm in SHARED_INDEX_ARMS:
        return "none of its own (uses the R0 and R1 indices)"
    return f"{record.get('seconds', 0.0):.1f} s"


def track_a_section(run: TrackARun) -> list[str]:
    card, arms = run.card, run.score.arms
    lines = [f"### Track A, condition {run.condition} ({run.provenance.run_dir})", ""]
    lines += ["Retrieval only: no model, no model tokens. Intention to treat; intervals are cluster bootstraps by "]
    lines += ["scenario family and are descriptive.", ""]
    lines += ["| arm | pairs | CompleteSet@10 | ValidSourceRecall@10 | MRR | query latency | build time |"]
    lines += ["|---|---|---|---|---|---|---|"]
    for arm in arms:
        n = _cell_of(card, ALL_STRATA, arm, PRIMARY_METRIC).eligible
        cells = " | ".join(_interval(card, ALL_STRATA, arm, m) for m in TRACK_A_METRICS)
        lines.append(f"| {arm} | {n} | {cells} | {_latency(run, arm)} | {_build_cost(run, arm)} |")
    lines += [
        "",
        "Harm over every eligible pair (share of pairs with the harm; none-of-the-unfinished to all-of-them):",
        "",
    ]
    lines += ["| arm | forbidden source | authority confusion | wrong vintage |", "|---|---|---|---|"]
    for arm in arms:
        lines.append(
            f"| {arm} | " + " | ".join(_bounds(card, arm, m) for m in sorted(HARM_METRICS, key=_harm_order)) + " |"
        )
    states = {s.arm: s for s in card.states if s.stratum == ALL_STRATA}
    lines += ["", "Run states: " + "; ".join(f"{a} {dict(states[a].states) or 'all OK'}" for a in arms) + ".", ""]
    lines += [f"Paired with {run.reference} (primary pairing {run.primary} against {run.reference}):", ""]
    lines += ["| arm | metric | difference | only arm / only ref | exact p | Holm p |", "|---|---|---|---|---|---|"]
    for e in (e for e in card.effects if e.stratum == ALL_STRATA and e.metric in TRACK_A_METRICS):
        split = "n/a" if e.only_arm is None else f"{e.only_arm} / {e.only_reference}"
        holm = "primary" if e.primary else ("n/a" if e.adjusted_p is None else f"{e.adjusted_p:.4f}")
        p = "n/a" if e.p_value is None else f"{e.p_value:.4f}"
        lines.append(f"| {e.arm} | {e.metric} | {format_interval(e.difference)} | {split} | {p} | {holm} |")
    lines += [
        "",
        "CompleteSet@10 by stratum (n = pairs owing the metric; strata with too few families show no interval):",
        "",
    ]
    strata = sorted({c.stratum for c in card.cells if c.stratum != ALL_STRATA})
    lines += ["| stratum | " + " | ".join(arms) + " |", "|---|" + "---|" * len(arms)]
    for stratum in strata:
        row = [
            f"{_interval(card, stratum, a, PRIMARY_METRIC)} (n={_cell_of(card, stratum, a, PRIMARY_METRIC).eligible})"
            for a in arms
        ]
        lines.append(f"| {stratum} | " + " | ".join(row) + " |")
    return [*lines, ""]


def _harm_order(metric: str) -> int:
    return ("forbidden_source_exposure", "authority_confusion", "wrong_vintage_intrusion").index(metric)


def track_b_section(run: TrackBRun) -> list[str]:
    lines = [f"### Track B, condition C2 ({run.provenance.run_dir})", ""]
    lines += [
        "Every retriever feeds the same generator with the same prompt and budget; each question ran on one model "
    ]
    lines += ["for all arms (the model mix is in the limits). Intention to treat beside conditional.", ""]
    lines += ["| arm | pairs | states | coverage (ITT) | directive rate (conditional) | directive rate (worst case) |"]
    lines += ["|---|---|---|---|---|---|"]
    for s in run.summaries:
        e = s.endpoints
        itt = "n/a" if e.coverage_itt is None else f"{e.coverage_itt:.3f} ({e.correct_answers}/{e.answerable})"
        cond = (
            "n/a"
            if e.directive_rate_conditional is None
            else f"{e.directive_rate_conditional:.3f} ({e.unsupported_directives}/{e.completed})"
        )
        worst = "n/a" if e.directive_rate_worst_case is None else f"{e.directive_rate_worst_case:.3f}"
        lines.append(f"| {s.arm} | {s.pairs} | {_states(s)} | {itt} | {cond} | {worst} |")
    lines += [
        "",
        "Query-time cost from the generator's records (retrieval and embedding are local and not priced in tokens):",
        "",
    ]
    lines += ["| arm | calls | prompt tokens | completion tokens | mean provider latency |", "|---|---|---|---|---|"]
    for arm in run.score.arms:
        c = run.costs.get(arm)
        lines.append(
            f"| {arm} | NOT_OBSERVABLE | NOT_OBSERVABLE | NOT_OBSERVABLE | NOT_OBSERVABLE |"
            if c is None
            else f"| {arm} | {c.calls} | {c.prompt_tokens} | {c.completion_tokens} | "
            + ("NOT_OBSERVABLE" if c.provider_latency_ms is None else f"{c.provider_latency_ms:.0f} ms")
            + " |"
        )
    if run.effects:
        lines += ["", "Co-primary endpoints paired with the reference on the same questions:", ""]
        lines += [
            "| arm | endpoint | questions | difference | only arm / only ref | exact p | Holm p |",
            "|---|---|---|---|---|---|---|",
        ]
        for e in run.effects:
            holm = "primary" if e.primary else ("n/a" if e.adjusted_p is None else f"{e.adjusted_p:.4f}")
            lines.append(
                f"| {e.arm} | {e.metric} | {e.pairs} | {format_interval(e.difference)} |"
                f" {e.only_arm} / {e.only_reference} |"
                f" {e.p_value:.4f} | {holm} |"
            )
    return [*lines, ""]


def _count_text(counts: Mapping[str, int] | None, planned: str = "NOT_RUN") -> str:
    return ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) if counts else planned


def track_c_section(runs: Sequence[TrackCRun]) -> list[str]:
    lines = ["### Track C: native end-to-end systems", ""]
    if not runs:
        return [*lines, "No Track C run is part of this report.", ""]
    lines += [
        "| run | system | turns by state | mutation cases by state | model calls | prompt tokens | completion tokens |",
        "|---|---|---|---|---|---|---|",
    ]
    for run in runs:
        spend = run.summary.get("spend", {})
        for arm in run.arms:
            used = spend.get(arm, {})
            lines.append(
                f"| {run.provenance.run_dir} | {arm} | {_count_text(run.turn_states.get(arm))} |"
                f" {_count_text(run.case_states.get(arm))} | {used.get('calls', 'NOT_OBSERVABLE')} |"
                f" {used.get('prompt_tokens', 'NOT_OBSERVABLE')} | {used.get('completion_tokens', 'NOT_OBSERVABLE')} |"
            )
    lines += ["", TRACK_C_NOTE, ""]
    for run in runs:
        memory = run.summary.get("memory", {})
        if not memory:
            continue
        names = sorted({name for values in memory.values() for name in values})
        silent = [
            n
            for n in names
            if all(str(v.get(n, "")).startswith(("NOT_OBSERVABLE", "no eligible")) for v in memory.values())
        ]
        shown = [n for n in names if n not in silent]
        lines += [f"Memory measures, {run.provenance.run_dir} (condition = system, memory baseline, heat):", ""]
        lines += ["| condition | " + " | ".join(shown) + " |", "|---|" + "---|" * len(shown)]
        lines += [
            f"| {cond} | " + " | ".join(str(values.get(n, "n/a")) for n in shown) + " |"
            for cond, values in sorted(memory.items())
        ]
        if silent:
            lines += [
                "",
                "Not observed in any condition of this run (NOT_OBSERVABLE, or no eligible observation): "
                + ", ".join(silent)
                + ".",
                "",
            ]
    return lines


def graph_section(runs: Sequence[GraphRun]) -> list[str]:
    lines = ["### Graph comparators (R4 to R6), on their own corpus", ""]
    if not runs:
        return [*lines, "No graph comparator produced a measured retrieval result in this report.", ""]
    for run in runs:
        lines.append(
            f"- {run.provenance.label} on {run.corpus} ({run.provenance.run_dir}): "
            f"{json.dumps(run.summary, sort_keys=True)[:400]}"
        )
    return [*lines, ""]


# --------------------------------------------------------------------------- figures and findings


def figures(inputs: ComparisonInputs) -> dict[str, str]:
    """The SVG figures this report can draw from its inputs, by file name."""
    drawn: dict[str, str] = {}
    for run in inputs.track_a:
        points = [Point(arm, _p50(run, arm), _itt_estimate(run, arm)) for arm in run.score.arms]
        drawn[f"track_a_{run.condition}_quality_latency.svg"] = scatter_svg(
            f"Track A {run.condition}: CompleteSet@10 against median query latency",
            "median query latency (ms, lower is better)",
            "CompleteSet@10 (higher is better)",
            mark_dominated(points),
        )
        groups = {
            stratum: {
                arm: (
                    cell.itt.estimate,
                    cell.itt.low,
                    cell.itt.high,
                )
                for arm in run.score.arms
                if (cell := _cell_of(run.card, stratum, arm, PRIMARY_METRIC)).itt is not None
            }
            for stratum in sorted({c.stratum for c in run.card.cells if c.stratum != ALL_STRATA})
        }
        groups = {k: v for k, v in groups.items() if v}
        if groups:
            drawn[f"track_a_{run.condition}_by_stratum.svg"] = bars_svg(
                f"Track A {run.condition}: CompleteSet@10 by stratum", "CompleteSet@10", groups
            )
    if inputs.track_b is not None:
        b = inputs.track_b
        cost_points = [
            Point(s.arm, b.costs[s.arm].tokens / max(s.pairs, 1), s.endpoints.coverage_itt or 0.0)
            for s in b.summaries
            if s.arm in b.costs
        ]
        if cost_points:
            drawn["track_b_coverage_cost.svg"] = scatter_svg(
                "Track B: correct-answer coverage against tokens per pair",
                "model tokens per pair (lower is better)",
                "coverage, intention to treat (higher is better)",
                mark_dominated(cost_points),
            )
        risk = [
            Point(s.arm, s.abstention.selective_risk, s.abstention.selective_coverage)
            for s in b.summaries
            if s.abstention.selective_risk is not None and s.abstention.selective_coverage is not None
        ]
        if risk:
            drawn["track_b_risk_coverage.svg"] = scatter_svg(
                "Track B: selective coverage against selective risk",
                "selective risk (lower is better)",
                "selective coverage (higher is better)",
                mark_dominated(risk),
            )
    return drawn


def _itt_estimate(run: TrackARun, arm: str) -> float:
    interval = _cell_of(run.card, ALL_STRATA, arm, PRIMARY_METRIC).itt
    return interval.estimate if interval is not None else 0.0


def _p50(run: TrackARun, arm: str) -> float:
    summary = latency_summary([r for r in run.score.ledger_records if r.arm == arm], deadline_ms=None)
    return summary.percentiles["p50"] if summary.completed else 0.0


def findings(inputs: ComparisonInputs) -> list[str]:
    """Adverse, favourable and inconclusive primary comparisons, each from an interval, none hidden."""
    adverse: list[str] = []
    favourable: list[str] = []
    inconclusive: list[str] = []
    for run in inputs.track_a:
        for e in run.card.effects:
            if e.stratum != ALL_STRATA or not e.primary or e.metric not in TRACK_A_METRICS:
                continue
            text = (
                f"Track A {run.condition}: {e.arm} against {e.reference} on {e.metric}: {format_interval(e.difference)}"
            )
            _sort(text, e.difference, adverse, favourable, inconclusive)
    if inputs.track_b is not None:
        for e in inputs.track_b.effects:
            if e.primary:
                text = f"Track B: {e.arm} against {e.reference} on {e.metric}: {format_interval(e.difference)}"
                harmful = e.metric == "unsupported_directive"  # a lower rate is better
                _sort(text, e.difference, adverse, favourable, inconclusive, lower_is_better=harmful)
    lines = ["Primary pairings (intervals are descriptive, one run, not sealed):", ""]
    for title, items in (
        ("Adverse to the system under test", adverse),
        ("Favourable to it", favourable),
        ("Inconclusive (the interval includes zero)", inconclusive),
    ):
        lines.append(f"- {title}: none" if not items else f"- {title}:")
        lines += [f"  - {item}" for item in items]
    return [*lines, ""]


def _sort(
    text: str,
    difference: Interval,
    adverse: list[str],
    favourable: list[str],
    inconclusive: list[str],
    *,
    lower_is_better: bool = False,
) -> None:
    if difference.low is None or difference.high is None:
        inconclusive.append(text + " (descriptive: too few families for an interval)")
    elif difference.high < 0:
        (favourable if lower_is_better else adverse).append(text)
    elif difference.low > 0:
        (adverse if lower_is_better else favourable).append(text)
    else:
        inconclusive.append(text)


LIMITS = (
    "Exploratory and descriptive: the confirmatory run was not sealed (no M tier, no tuning, no seal), the label "
    "audit was delegated and accepted by default, and the free tier set the sizes (BADR-0043, BADR-0044).",
    "One fixture (the S tier, 1,200 fictional documents), one split of 100 questions of which 97 are scored; strata "
    "are too small for most intervals.",
    "Every generative result is a single run at temperature 0 on three different models whose mix is stated; protocol "
    "14.4 asks for three repetitions.",
    "R0 to R3 index every published document and ignore approval state, validity windows and authority; Palladion "
    "applies them natively. The harm columns therefore compare different capabilities.",
    "Under C2 Palladion enforces its own per-document access lists (one reader per principal) and the other arms the "
    "neutral filter; any disagreement is counted as exposure, not masked.",
    "Palladion answers at most 12 results per search (HTTP 400 above), E3 is Palladion's own critic-off control and a "
    "distinct treatment, E2 was NOT_RUN (no access), R7b FEATURE_NOT_SUPPORTED (no graph store, no link-selection "
    "rule).",
    "E0 and E1 have no mutation interface and no live-status tool: their mutation cases are NOT_RUN and live-status "
    "turns are a capability difference, not a zero.",
    "Local arms report no model tokens (retrieval and embedding are local) and Palladion's corpus load time was not "
    "recorded: shown as NOT_OBSERVABLE.",
    "A pair a provider's daily limit stopped is counted apart (QUOTA_BLOCKED), in no rate and never as a zero.",
)


def render(inputs: ComparisonInputs) -> str:
    """The whole report as Markdown. Raises ``ReportError`` when the inputs may not share a report."""
    pins = inputs.commits
    if len(pins) > 1:
        raise ReportError(f"the runs name {len(pins)} different Palladion commits and may not share a report")
    lines = ["# Palladion beside the other systems: a descriptive comparison", ""]
    lines += [
        "**Status: exploratory. Not sealed. No composite score, no ranking and no claim that any system is better.**",
        "",
    ]
    lines += [
        f"Palladion commit: `{next(iter(pins), 'n/a')}`. Frozen matched lists: "
        + ", ".join(f"{k} `{v[:12]}`" for k, v in sorted(inputs.matched_digests.items()))
        + ".",
        "",
    ]
    lines += ["All data is fictional (Meridian Switchworks). Run states are results; none is folded into a score.", ""]
    lines += [
        "## Provenance",
        "",
        "| table | run directory | run id | commit | matched list |",
        "|---|---|---|---|---|",
    ]
    everything = inputs.provenances
    lines += [
        f"| {p.label} | {p.run_dir} | {p.run_id} | {(p.commit or 'n/a')[:12]} |"
        f" {(p.matched_list_sha256 or 'n/a')[:12]} |"
        for p in everything
    ]
    lines += ["", "## Results", ""]
    for run in inputs.track_a:
        lines += track_a_section(run)
    if inputs.track_b is not None:
        lines += track_b_section(inputs.track_b)
    lines += track_c_section(inputs.track_c)
    lines += graph_section(inputs.graph)
    lines += ["## Findings", "", *findings(inputs)]
    lines += ["## Negative findings and fairness deviations", ""] + [f"- {item}" for item in LIMITS] + [""]
    drawn = figures(inputs)
    if drawn:
        lines += ["## Figures", ""] + [f"![{name}](figures/{name})" for name in sorted(drawn)] + [""]
    return "\n".join(lines)


def write_report(out: Path, inputs: ComparisonInputs) -> Path:
    """Write ``report.md`` and its figures under ``out``; nothing is written if the report cannot be assembled."""
    text = render(inputs)
    drawn = figures(inputs)
    (out / "figures").mkdir(parents=True, exist_ok=True)
    for name, svg in drawn.items():
        (out / "figures" / name).write_text(svg, encoding="utf-8")
    path = out / "report.md"
    path.write_text(text, encoding="utf-8")
    return path


__all__ = [
    "ArmCost",
    "ComparisonInputs",
    "GraphRun",
    "Provenance",
    "ReportError",
    "TrackARun",
    "TrackBRun",
    "TrackCRun",
    "arm_costs",
    "figures",
    "findings",
    "load_track_a",
    "load_track_b",
    "load_track_c",
    "main",
    "provenance_of",
    "render",
    "write_report",
]


if __name__ == "__main__":
    raise SystemExit(main())
