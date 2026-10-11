"""Shared visual tokens and SVG components for the contribution graphic."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

from contribution_data import ProfileData


@dataclass(frozen=True)
class ColorTheme:
    ink: str
    muted: str
    accent: str
    line: str
    surface: str
    border: str
    glow: str
    palette: tuple[str, ...]


THEMES = {
    "violet": ColorTheme(
        ink="#242330", muted="#736F7D", accent="#7955DF", line="#ECEAF2",
        surface="#FCFBFE", border="#ECE8F3", glow="#BAA4F0",
        palette=("#7955DF", "#B59BEF", "#F3A581", "#EBC56F", "#70B5A5", "#BCC0CE"),
    ),
    "blue": ColorTheme(
        ink="#202D42", muted="#687387", accent="#2F6BD1", line="#E4EAF5",
        surface="#FBFCFF", border="#E4EAF5", glow="#9ABBEF",
        palette=("#2F6BD1", "#9278C5", "#C57946", "#9D8736", "#3F8C7C", "#8791A1"),
    ),
    "teal": ColorTheme(
        ink="#203731", muted="#65756F", accent="#117D76", line="#E1ECE7",
        surface="#FAFDFC", border="#E1ECE7", glow="#8DCDBD",
        palette=("#117D76", "#6589C3", "#C87860", "#9D8736", "#9174B8", "#8791A1"),
    ),
    "orange": ColorTheme(
        ink="#3B2C24", muted="#796C62", accent="#B6572C", line="#EEE6DE",
        surface="#FEFCF9", border="#EEE6DE", glow="#E9BC91",
        palette=("#B6572C", "#B38A36", "#698BCC", "#398E85", "#9774BD", "#8791A1"),
    ),
}
DEFAULT_THEME_NAME = "blue"
DEFAULT_THEME = THEMES[DEFAULT_THEME_NAME]


def fmt(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def text(x: float, y: float, label: str, size: int = 16, color: str = DEFAULT_THEME.ink,
         weight: int = 400, anchor: str = "start", extra: str = "") -> str:
    return (f'<text x="{fmt(x)}" y="{fmt(y)}" font-size="{size}" fill="{color}" '
            f'font-weight="{weight}" text-anchor="{anchor}" {extra}>{escape(label)}</text>')


def rect(x: float, y: float, width: float, height: float, color: str,
         radius: float = 0, extra: str = "") -> str:
    return (f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(width)}" '
            f'height="{fmt(height)}" rx="{fmt(radius)}" fill="{color}" {extra}/>')


def line(x1: float, y1: float, x2: float, y2: float, color: str = DEFAULT_THEME.line) -> str:
    return (f'<path d="M{fmt(x1)} {fmt(y1)} L{fmt(x2)} {fmt(y2)}" '
            f'fill="none" stroke="{color}"/>')


def circle(x: float, y: float, radius: float, color: str, extra: str = "") -> str:
    return f'<circle cx="{fmt(x)}" cy="{fmt(y)}" r="{fmt(radius)}" fill="{color}" {extra}/>'


def icon(name: str, x: float, y: float, size: int = 24, color: str = DEFAULT_THEME.accent) -> str:
    paths = {
        "star": '<path d="m12 3 2.8 5.7 6.3.9-4.6 4.4 1.1 6.3-5.6-3-5.6 3 1.1-6.3L3 9.6l6.2-.9Z"/>',
        "fork": '<path d="M6 7v4a4 4 0 0 0 4 4h2m6-8v4a4 4 0 0 1-4 4h-2v3"/><circle cx="6" cy="5" r="2"/><circle cx="18" cy="5" r="2"/><circle cx="12" cy="20" r="2"/>',
    }
    return (f'<g transform="translate({fmt(x)} {fmt(y)}) scale({fmt(size / 24)})" '
            f'fill="none" stroke="{color}" stroke-width="1.7" '
            f'stroke-linecap="round" stroke-linejoin="round">{paths[name]}</g>')


def polygon(points: list[tuple[float, float]], **attrs: str) -> str:
    coords = " ".join(f"{fmt(x)},{fmt(y)}" for x, y in points)
    attributes = " ".join(f'{key.replace("_", "-")}="{value}"' for key, value in attrs.items())
    return f'<polygon points="{coords}" {attributes}/>'


def smooth_path(points: list[tuple[float, float]], closed: bool = False) -> str:
    """A restrained Catmull-Rom contour through the supplied data points."""
    path = f"M{fmt(points[0][0])} {fmt(points[0][1])}"
    for i in range(len(points) if closed else len(points) - 1):
        p0 = points[(i - 1) % len(points)] if closed or i else points[0]
        p1, p2 = points[i], points[(i + 1) % len(points)]
        p3 = points[(i + 2) % len(points)] if closed else points[min(i + 2, len(points) - 1)]
        c1 = tuple(p1[j] + (p2[j] - p0[j]) / 8 for j in (0, 1))
        c2 = tuple(p2[j] - (p3[j] - p1[j]) / 8 for j in (0, 1))
        path += f" C{fmt(c1[0])} {fmt(c1[1])},{fmt(c2[0])} {fmt(c2[1])},{fmt(p2[0])} {fmt(p2[1])}"
    return path + (" Z" if closed else "")


def svg_open(width: int, height: int, data: ProfileData,
             theme: ColorTheme = DEFAULT_THEME) -> list[str]:
    activity_scope = "Activity" if data.breakdown_complete else "Visible activity"
    language_scope = "Commits" if data.breakdown_complete else "Visible commits"
    private = (f"{data.restricted_contributions:,} private contributions without an accessible type breakdown. "
               if data.restricted_contributions else "")
    description = (f"{data.contributions:,} contributions from {data.start} to {data.end}. "
                   f"{data.active_days} active days. Longest streak: {data.longest_streak} days. "
                   f"{data.stars} stars and {data.forks} forks. "
                   f"Daily contribution calendar. {activity_scope} on a logarithmic scale: "
                   + ", ".join(f"{label} {count:,}" for label, count in data.activity.items())
                   + ". " + private
                   + f"{language_scope} by language: "
                   + ", ".join(f"{label} {count:,}" for label, count in data.languages.items()) + ".")
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title description" '
        'font-family="Arial, Helvetica, sans-serif">',
        '<title id="title">Contribution activity</title>',
        f'<desc id="description">{escape(description)}</desc>',
        f'<defs><radialGradient id="radarGlow"><stop stop-color="{theme.glow}" stop-opacity=".36"/>'
        f'<stop offset="1" stop-color="{theme.glow}" stop-opacity="0"/></radialGradient></defs>',
        rect(0.5, 0.5, width - 1, height - 1, theme.surface, 24, f'stroke="{theme.border}"'),
    ]
