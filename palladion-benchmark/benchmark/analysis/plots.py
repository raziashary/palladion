"""Figures as plain SVG, from the standard library, and the rule that marks a dominated system (B08-T06.01, BADR-0044).

No plotting package is added (BADR-0005): a figure here is a few hundred bytes of SVG that a browser or a Markdown
viewer shows. A figure draws only what it is given, in the order it is given; it never ranks, never draws a
composite, and labels a system that another system beats on every axis as dominated, from the data and nowhere else.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from xml.sax.saxutils import escape

WIDTH, HEIGHT = 640, 400
MARGIN_LEFT, MARGIN_RIGHT, MARGIN_TOP, MARGIN_BOTTOM = 70, 30, 40, 60


class PlotError(ValueError):
    """A figure cannot be drawn from what it was given."""


@dataclass(frozen=True)
class Point:
    """One system on a quality-against-cost figure. ``x`` is cost (lower is better), ``y`` is quality (higher)."""

    label: str
    x: float
    y: float
    dominated: bool = False


def mark_dominated(points: Sequence[Point]) -> list[Point]:
    """Flag every point that another point matches or beats on both axes and strictly beats on at least one.

    Two points with identical coordinates dominate neither. A point with no rival is left unmarked; the rule never
    says which point is best, only which ones are beaten.
    """
    if len({p.label for p in points}) != len(points):
        raise PlotError("each system appears once in a figure")
    marked = []
    for point in points:
        beaten = any(
            other.x <= point.x and other.y >= point.y and (other.x < point.x or other.y > point.y)
            for other in points
            if other is not point
        )
        marked.append(Point(point.label, point.x, point.y, beaten))
    return marked


def _scale(value: float, low: float, high: float, start: float, end: float) -> float:
    if high == low:
        return (start + end) / 2
    return start + (value - low) / (high - low) * (end - start)


def _frame(title: str, xlabel: str, ylabel: str) -> list[str]:
    plot_w, plot_h = WIDTH - MARGIN_LEFT - MARGIN_RIGHT, HEIGHT - MARGIN_TOP - MARGIN_BOTTOM
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="{WIDTH}" height="{HEIGHT}" '
        'font-family="sans-serif" font-size="12">',
        f"<title>{escape(title)}</title>",
        f'<text x="{WIDTH / 2}" y="22" text-anchor="middle" font-size="14">{escape(title)}</text>',
        f'<rect x="{MARGIN_LEFT}" y="{MARGIN_TOP}" width="{plot_w}" height="{plot_h}" fill="none" stroke="#888"/>',
        f'<text x="{MARGIN_LEFT + plot_w / 2}" y="{HEIGHT - 12}" text-anchor="middle">{escape(xlabel)}</text>',
        f'<text x="16" y="{MARGIN_TOP + plot_h / 2}" text-anchor="middle" '
        f'transform="rotate(-90 16 {MARGIN_TOP + plot_h / 2})">{escape(ylabel)}</text>',
    ]


def scatter_svg(title: str, xlabel: str, ylabel: str, points: Sequence[Point]) -> str:
    """A quality-cost figure: a filled mark for a system nothing beats, a hollow one with 'dominated' for the rest."""
    if not points:
        raise PlotError("a figure needs at least one point")
    xs, ys = [p.x for p in points], [p.y for p in points]
    x_low, x_high, y_low, y_high = min(xs), max(xs), min(ys), max(ys)
    left, right = MARGIN_LEFT + 10, WIDTH - MARGIN_RIGHT - 10
    top, bottom = MARGIN_TOP + 10, HEIGHT - MARGIN_BOTTOM - 10
    parts = _frame(title, xlabel, ylabel)
    parts += [
        f'<text x="{MARGIN_LEFT}" y="{HEIGHT - MARGIN_BOTTOM + 16}" font-size="10">{x_low:g}</text>',
        f'<text x="{WIDTH - MARGIN_RIGHT}" y="{HEIGHT - MARGIN_BOTTOM + 16}" text-anchor="end" '
        f'font-size="10">{x_high:g}</text>',
        f'<text x="{MARGIN_LEFT - 4}" y="{HEIGHT - MARGIN_BOTTOM}" text-anchor="end" font-size="10">{y_low:g}</text>',
        f'<text x="{MARGIN_LEFT - 4}" y="{MARGIN_TOP + 10}" text-anchor="end" font-size="10">{y_high:g}</text>',
    ]
    for point in points:
        cx = _scale(point.x, x_low, x_high, left, right)
        cy = _scale(point.y, y_low, y_high, bottom, top)
        fill = "none" if point.dominated else "#1f77b4"
        suffix = " (dominated)" if point.dominated else ""
        parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="6" fill="{fill}" stroke="#1f77b4" stroke-width="2"/>')
        parts.append(f'<text x="{cx + 9:.1f}" y="{cy + 4:.1f}">{escape(point.label + suffix)}</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def bars_svg(
    title: str, ylabel: str, groups: Mapping[str, Mapping[str, tuple[float, float | None, float | None]]]
) -> str:
    """Grouped bars with interval whiskers: ``groups[group][series] = (estimate, low, high)``.

    A series with no interval (a stratum with too few families) is drawn without a whisker, never with a made-up one.
    """
    if not groups or not any(groups.values()):
        raise PlotError("a figure needs at least one bar")
    series = sorted({name for values in groups.values() for name in values})
    top_value = max(
        max(est, high if high is not None else est) for values in groups.values() for est, _, high in values.values()
    )
    top_value = top_value if top_value > 0 else 1.0
    slot = (WIDTH - MARGIN_LEFT - MARGIN_RIGHT) / len(groups)
    bar = slot * 0.8 / len(series)
    parts = _frame(title, "", ylabel)
    parts.append(
        f'<text x="{MARGIN_LEFT - 4}" y="{MARGIN_TOP + 10}" text-anchor="end" font-size="10">{top_value:g}</text>'
    )
    parts.append(f'<text x="{MARGIN_LEFT - 4}" y="{HEIGHT - MARGIN_BOTTOM}" text-anchor="end" font-size="10">0</text>')
    for g, (group, values) in enumerate(groups.items()):
        x0 = MARGIN_LEFT + g * slot + slot * 0.1
        parts.append(
            f'<text x="{MARGIN_LEFT + g * slot + slot / 2:.1f}" y="{HEIGHT - MARGIN_BOTTOM + 16}" text-anchor="middle" '
            f'font-size="10">{escape(group)}</text>'
        )
        for s, name in enumerate(series):
            if name not in values:
                continue
            estimate, low, high = values[name]
            x = x0 + s * bar
            y = _scale(estimate, 0, top_value, HEIGHT - MARGIN_BOTTOM, MARGIN_TOP)
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar:.1f}" height="{HEIGHT - MARGIN_BOTTOM - y:.1f}" '
                f'fill="hsl({(s * 67) % 360},60%,55%)"><title>{escape(name)} {estimate:.3f}</title></rect>'
            )
            if low is not None and high is not None:
                mid = x + bar / 2
                y_low, y_high = (_scale(v, 0, top_value, HEIGHT - MARGIN_BOTTOM, MARGIN_TOP) for v in (low, high))
                parts.append(f'<line x1="{mid:.1f}" x2="{mid:.1f}" y1="{y_low:.1f}" y2="{y_high:.1f}" stroke="#000"/>')
    for s, name in enumerate(series):
        parts.append(
            f'<rect x="{MARGIN_LEFT + s * 90}" y="{HEIGHT - 28}" width="10" height="10" '
            f'fill="hsl({(s * 67) % 360},60%,55%)"/>'
            f'<text x="{MARGIN_LEFT + s * 90 + 14}" y="{HEIGHT - 19}" font-size="10">{escape(name)}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"
