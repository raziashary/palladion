"""Figures from the standard library, and the dominance rule (B08-T06.01)."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from benchmark.analysis.plots import PlotError, Point, bars_svg, mark_dominated, scatter_svg

SVG = "{http://www.w3.org/2000/svg}"


def flags(points: list[Point]) -> dict[str, bool]:
    return {p.label: p.dominated for p in mark_dominated(points)}


def test_a_system_beaten_on_both_axes_is_dominated_and_the_others_are_not() -> None:
    result = flags([Point("cheap", 1, 0.5), Point("worse", 2, 0.4), Point("best", 3, 0.9)])
    assert result == {"cheap": False, "worse": True, "best": False}


def test_beaten_on_one_axis_and_tied_on_the_other_is_still_dominated() -> None:
    assert flags([Point("a", 1, 0.5), Point("b", 2, 0.5)]) == {"a": False, "b": True}
    assert flags([Point("a", 1, 0.5), Point("b", 1, 0.4)]) == {"a": False, "b": True}


def test_identical_points_dominate_neither_and_a_lone_point_is_not_dominated() -> None:
    assert flags([Point("a", 1, 0.5), Point("b", 1, 0.5)]) == {"a": False, "b": False}
    assert flags([Point("only", 5, 0.1)]) == {"only": False}


def test_a_trade_off_leaves_both_systems_unmarked() -> None:
    assert flags([Point("fast", 1, 0.2), Point("good", 9, 0.8)]) == {"fast": False, "good": False}


def test_a_system_appears_once() -> None:
    with pytest.raises(PlotError, match="once"):
        mark_dominated([Point("a", 1, 1), Point("a", 2, 2)])


def parse(svg: str) -> ET.Element:
    return ET.fromstring(svg)


def test_a_scatter_is_valid_svg_with_every_system_labelled_and_the_dominated_one_hollow() -> None:
    svg = scatter_svg(
        "Cost and quality", "tokens", "coverage", mark_dominated([Point("R3", 1, 0.5), Point("R<1>", 2, 0.4)])
    )
    root = parse(svg)
    texts = [t.text for t in root.iter(f"{SVG}text")]
    assert "Cost and quality" in texts and "R3" in texts and "R<1> (dominated)" in texts
    circles = list(root.iter(f"{SVG}circle"))
    assert [c.get("fill") for c in circles] == ["#1f77b4", "none"]


def test_a_scatter_of_one_point_or_equal_coordinates_still_draws() -> None:
    root = parse(scatter_svg("t", "x", "y", [Point("a", 3, 3), Point("b", 3, 3)]))
    assert len(list(root.iter(f"{SVG}circle"))) == 2


def test_a_figure_with_nothing_to_draw_is_refused() -> None:
    with pytest.raises(PlotError, match="at least one point"):
        scatter_svg("t", "x", "y", [])
    with pytest.raises(PlotError, match="at least one bar"):
        bars_svg("t", "y", {})
    with pytest.raises(PlotError, match="at least one bar"):
        bars_svg("t", "y", {"Q1": {}})


def test_bars_have_a_whisker_only_where_an_interval_exists() -> None:
    groups: dict[str, dict[str, tuple[float, float | None, float | None]]] = {
        "Q1": {"R3": (0.4, 0.2, 0.6), "R7a": (0.1, None, None)},
        "Q2": {"R3": (0.0, 0.0, 0.0)},
    }
    root = parse(bars_svg("By stratum", "CompleteSet@10", groups))
    rects = [r for r in root.iter(f"{SVG}rect") if r.find(f"{SVG}title") is not None]
    assert [r.find(f"{SVG}title").text for r in rects] == ["R3 0.400", "R7a 0.100", "R3 0.000"]  # type: ignore[union-attr]
    assert len(list(root.iter(f"{SVG}line"))) == 2, "R3 in Q1 and R3 in Q2 have intervals, R7a in Q1 does not"
    labels = [t.text for t in root.iter(f"{SVG}text")]
    assert "Q1" in labels and "Q2" in labels and "R7a" in labels


def test_all_zero_bars_do_not_divide_by_zero() -> None:
    root = parse(bars_svg("t", "y", {"Q1": {"A": (0.0, None, None)}}))
    assert len(list(root.iter(f"{SVG}rect"))) >= 2
