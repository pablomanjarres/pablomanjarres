#!/usr/bin/env python3
"""Shared SVG components for desktop and phone contribution graphics."""

from __future__ import annotations

import math
from html import escape

from contribution_data import ACTIVITY_LABELS, ProfileData


def fmt(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


def text(x: float, y: float, label: str, *, size: int, color: str,
         weight: int = 400, anchor: str = "start", extra: str = "") -> str:
    return (f'<text x="{fmt(x)}" y="{fmt(y)}" fill="{color}" '
            f'font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" '
            f'{extra}>{escape(label)}</text>')


def polygon(points: list[tuple[float, float]], **attributes: str) -> str:
    point_list = " ".join(f"{fmt(x)},{fmt(y)}" for x, y in points)
    attrs = " ".join(f'{key.replace("_", "-")}="{value}"' for key, value in attributes.items())
    return f'<polygon points="{point_list}" {attrs}/>'


def render_bar(x: float, bottom: float, source_height: float) -> str:
    if source_height <= 2.6:
        height = 3.5
        top, front, side = "#F9FAFF", "#E8ECF8", "#D7DEF0"
    else:
        height = min(198, 5 + source_height * 1.08)
        if source_height >= 105:
            top, front, side = "#B0F5FF", "#43C8DF", "#2296BA"
        elif source_height >= 52:
            top, front, side = "#CFD6FF", "#7788DF", "#5869BD"
        elif source_height >= 19:
            top, front, side = "#E9ECFF", "#AAB5ED", "#8898D5"
        else:
            top, front, side = "#F8F9FF", "#CDD5F3", "#AEBBE3"
    y = bottom - height
    front_face = polygon([(x, y), (x + 8.5, y), (x + 8.5, bottom), (x, bottom)], fill=front)
    side_face = polygon([(x + 8.5, y), (x + 12.5, y - 4),
                         (x + 12.5, bottom - 4), (x + 8.5, bottom)], fill=side)
    top_face = polygon([(x, y), (x + 4, y - 4),
                        (x + 12.5, y - 4), (x + 8.5, y)], fill=top)
    return front_face + side_face + top_face


def radar(data: ProfileData) -> str:
    cx, cy, radius = 1041, 306, 78
    angles = [math.radians(-90 + index * 72) for index in range(5)]

    def points(scale: float) -> list[tuple[float, float]]:
        return [(cx + math.cos(angle) * radius * scale,
                 cy + math.sin(angle) * radius * scale) for angle in angles]

    parts = [text(869, 167, "Activity shape", size=21, color="#F5F6FF", weight=700)]
    for scale in (0.25, 0.5, 0.75, 1):
        parts.append(polygon(points(scale), fill="none", stroke="#4B536E", stroke_width="1"))
    for x, y in points(1):
        parts.append(f'<line x1="{cx}" y1="{cy}" x2="{fmt(x)}" y2="{fmt(y)}" stroke="#394158"/>')

    scales = [0.13 + 0.87 * math.log10(data.activity[label] + 1) / 4 for label in ACTIVITY_LABELS]
    shape = [(cx + math.cos(angle) * radius * scale,
              cy + math.sin(angle) * radius * scale) for angle, scale in zip(angles, scales)]
    parts.append(polygon(shape, fill="url(#radarFill)", fill_opacity="0.8",
                         stroke="#6CE3F1", stroke_width="3", stroke_linejoin="round"))
    for x, y in shape:
        parts.append(f'<circle cx="{fmt(x)}" cy="{fmt(y)}" r="3.5" fill="#B7FAFF"/>')

    labels = (
        ("Commits", 1041, 196, "middle"),
        ("Issues", 1152, 274, "start"),
        ("Pull requests", 1111, 396, "start"),
        ("Reviews", 971, 396, "end"),
        ("Repos", 930, 274, "end"),
    )
    for source_label, (label, x, y, anchor) in zip(ACTIVITY_LABELS, labels):
        parts.append(text(x, y, label, size=14, color="#F1F3FC", weight=600, anchor=anchor))
        parts.append(text(x, y + 18, f"{data.activity[source_label]:,}", size=13,
                          color="#98A5C3", anchor=anchor))
    return "".join(parts)


def calendar_art(data: ProfileData) -> str:
    parts = ['<path d="M72 526 L755 526 L786 578 L103 578 Z" fill="#E7EBF8" opacity="0.62"/>']
    for day in range(7):
        y = 526 + day * 8
        parts.append(f'<line x1="{fmt(75 + day * 4.7)}" y1="{y}" '
                     f'x2="{fmt(757 + day * 4.7)}" y2="{y}" stroke="#D3D9EC" stroke-width="0.8"/>')
    for day in range(7):
        for week in range(math.ceil(len(data.heights) / 7)):
            index = week * 7 + day
            if index < len(data.heights):
                parts.append(render_bar(77 + week * 12.9 + day * 4.7,
                                        526 + day * 8, data.heights[index]))
    parts.extend([
        text(76, 596, "Earlier", size=15, color="#7D86A5", weight=500),
        text(779, 596, "Now", size=15, color="#7D86A5", weight=500, anchor="end"),
    ])
    return "".join(parts)


def language_mix(data: ProfileData) -> str:
    leading_language = max(data.languages, key=data.languages.get)
    language_total = sum(data.languages.values())
    leading_share = round(data.languages[leading_language] * 100 / language_total)
    return "".join([
        text(869, 509, "Language mix", size=20, color="#222844", weight=700),
        text(1213, 507, f"{leading_share}%", size=28, color="#5559C9", weight=750, anchor="end"),
        '<rect x="869" y="530" width="344" height="13" rx="6.5" fill="#E0E3F2"/>',
        f'<rect x="869" y="530" width="{fmt(344 * data.languages[leading_language] / language_total)}" '
        'height="13" rx="6.5" fill="#666EE0"/>',
        '<circle cx="876" cy="577" r="5" fill="#666EE0"/>',
        text(890, 583, leading_language, size=16, color="#39405E", weight=600),
        '<circle cx="1091" cy="577" r="5" fill="#CED4EC"/>',
        text(1105, 583, "Other", size=16, color="#78819B", weight=500),
    ])


def svg_open(width: int, height: int, data: ProfileData) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc" '
        'font-family="Avenir Next, Helvetica Neue, Arial, sans-serif">',
        '<title id="title">A year in code: GitHub contributions</title>',
        f'<desc id="desc">{data.contributions:,} contributions from {data.start} to {data.end}. '
        f'{data.stars} stars and {data.forks} forks. An isometric daily contribution chart, '
        'activity radar, and language mix.</desc>',
        '<defs><linearGradient id="background" x2="1" y2="1"><stop stop-color="#F8F9FF"/>'
        '<stop offset="0.58" stop-color="#E8EAFE"/><stop offset="1" stop-color="#CFD5F2"/></linearGradient>'
        '<linearGradient id="radarFill" x1="0" y1="0" x2="1" y2="1">'
        '<stop stop-color="#38D4EC"/><stop offset="1" stop-color="#6A70F0"/></linearGradient>'
        '<filter id="shadow" x="-10%" y="-10%" width="120%" height="130%">'
        '<feDropShadow dx="0" dy="14" stdDeviation="18" flood-color="#6973AC" flood-opacity="0.14"/>'
        '</filter></defs>',
        f'<rect width="{width}" height="{height}" rx="24" fill="url(#background)"/>',
    ]


def social_count(data: ProfileData) -> str:
    return (f"{data.stars:,} {'star' if data.stars == 1 else 'stars'}    "
            f"{data.forks:,} {'fork' if data.forks == 1 else 'forks'}")
