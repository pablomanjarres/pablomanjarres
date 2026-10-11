"""Data-driven charts shared by the desktop and mobile profile layouts."""

from __future__ import annotations

import math
from datetime import timedelta

from contribution_data import ACTIVITY_LABELS, EMPTY_DAY_HEIGHT, ProfileData
from contribution_shapes import (ColorTheme, DEFAULT_THEME, circle, fmt, line,
                                 polygon, smooth_path, text)


def _tint(color: str, target: str, amount: float) -> str:
    channels = [round(int(color[i:i + 2], 16) * (1 - amount)
                      + int(target[i:i + 2], 16) * amount) for i in (1, 3, 5)]
    return "#" + "".join(f"{channel:02X}" for channel in channels)


def _contribution_bar(x: float, bottom: float, height: float, width: float,
                      depth_x: float, depth_y: float, intensity: float,
                      theme: ColorTheme) -> str:
    front = theme.line if intensity == 0 else _tint(theme.accent, "#FFFFFF", .75 - .55 * intensity)
    side = _tint(front, theme.ink, .09)
    top = _tint(front, "#FFFFFF", .36)
    y = bottom - height
    return "".join([
        polygon([(x, y), (x + width, y), (x + width, bottom), (x, bottom)], fill=front),
        polygon([(x + width, y), (x + width + depth_x, y - depth_y),
                 (x + width + depth_x, bottom - depth_y), (x + width, bottom)], fill=side),
        polygon([(x, y), (x + depth_x, y - depth_y),
                 (x + width + depth_x, y - depth_y), (x + width, y)], fill=top),
    ])


def contribution_landscape(data: ProfileData, x: float, y: float,
                           width: float, height: float,
                           theme: ColorTheme = DEFAULT_THEME) -> str:
    """Fit a complete yearly isometric calendar inside the supplied rectangle."""
    if width <= 0 or height <= 0:
        raise ValueError("Contribution landscape requires positive dimensions")
    offset = (data.start.weekday() + 1) % 7
    columns = math.ceil((len(data.heights) + offset) / 7)
    margin_x, margin_y = min(8, width * .05), min(10, height * .05)
    plot_width, plot_height = width - 2 * margin_x, height - 2 * margin_y
    step = plot_width / (columns - 1 + 6 * .36 + .66 + .30)
    week_drop = min(step * .16, plot_height * .18 / max(1, columns - 1))
    row_drop = min(step * .66, plot_height * .22 / 6)
    depth_x, depth_y = step * .30, min(step * .30, plot_height * .04)
    magnitude = max(max(data.heights) - EMPTY_DAY_HEIGHT, 1)
    intensities = [max(0, value - EMPTY_DAY_HEIGHT) / magnitude for value in data.heights]
    projections = [(i + offset) // 7 * week_drop + (i + offset) % 7 * row_drop
                   for i in range(len(data.heights))]
    floor_depth = max(projections)
    base_height = min(4, plot_height * .05)
    tallest = base_height + min(
        ((plot_height - floor_depth - depth_y + position - base_height) / intensity
         for position, intensity in zip(projections, intensities) if intensity > 0),
        default=plot_height * .6)
    bar_heights = [min(2.2, plot_height * .025) if intensity == 0
                   else base_height + intensity * (tallest - base_height)
                   for intensity in intensities]
    baseline = y + margin_y + plot_height - floor_depth
    parts = []
    for index, (intensity, bar_height) in enumerate(zip(intensities, bar_heights)):
        week, day = divmod(index + offset, 7)
        date = data.start + timedelta(days=index)
        if data.daily_counts is not None:
            count = data.daily_counts[index]
            status = f"{count:,} {'contribution' if count == 1 else 'contributions'}"
        else:
            status = "active" if intensity > 0 else "no contributions"
        parts.append(f'<g data-date="{date}"><title>{date:%d %b %Y}: {status}</title>')
        parts.append(_contribution_bar(x + margin_x + week * step + day * step * .36,
                                      baseline + week * week_drop + day * row_drop,
                                      bar_height, step * .66, depth_x, depth_y, intensity, theme))
        parts.append("</g>")
    return "".join(parts)


def radar(data: ProfileData, x: float, y: float, width: float,
          theme: ColorTheme = DEFAULT_THEME) -> str:
    cx, cy, radius = x + width / 2, y + 140, min(104, width * .265)
    angles = [math.radians(-90 + i * 72) for i in range(5)]

    def points(scale: float):
        return [(cx + math.cos(a) * radius * scale, cy + math.sin(a) * radius * scale) for a in angles]

    parts = [circle(cx, cy + 26, radius + 42, "url(#radarGlow)")]
    for scale in (.25, .5, .75, 1):
        parts.append(polygon(points(scale), fill="none", stroke=theme.line, stroke_width="1.1"))
    parts.extend(line(cx, cy, px, py, theme.line) for px, py in points(1))
    ceiling = max(1, math.ceil(math.log10(max(data.activity.values()) + 1)))
    values = [math.log10(data.activity[key] + 1) / ceiling for key in ACTIVITY_LABELS]
    contour = [(cx + math.cos(a) * radius * value, cy + math.sin(a) * radius * value)
               for a, value in zip(angles, values)]
    parts.append(f'<path d="{smooth_path(contour, True)}" fill="{theme.accent}" fill-opacity=".12" '
                 f'stroke="{theme.accent}" stroke-width="2.7" stroke-linejoin="round"/>')
    parts.extend(circle(px, py, 3, theme.surface, f'stroke="{theme.accent}" stroke-width="1.6"') for px, py in contour)
    commit_label = "Commits" if data.breakdown_complete else "Visible commits"
    labels = (commit_label, "Issues", "Pull requests", "Reviews", "Repositories")
    positions = ((cx, cy - radius - 26, "middle"),
                 (cx + radius + 5, cy - 32, "middle"),
                 (cx + radius * .76, cy + radius + 26, "middle"),
                 (cx - radius * .76, cy + radius + 26, "middle"),
                 (cx - radius - 5, cy - 32, "middle"))
    for key, label, (px, py, anchor) in zip(ACTIVITY_LABELS, labels, positions):
        parts.extend([text(px, py, label, 13, theme.muted, anchor=anchor),
                      text(px, py + 22, f"{data.activity[key]:,}", 17, theme.ink, 600, anchor)])
    return "".join(parts)


def languages(data: ProfileData, x: float, y: float, width: float,
              theme: ColorTheme = DEFAULT_THEME) -> str:
    ranked = sorted(((name, count) for name, count in data.languages.items()
                     if name != "other" and count > 0),
                    key=lambda item: -item[1])
    items = ranked[:5]
    other = data.languages.get("other", 0) + sum(count for _, count in ranked[5:])
    if other:
        items.append(("other", other))
    total = sum(data.languages.values())
    cx, cy, radius = x + 80, y + 86, 64
    circumference = 2 * math.pi * radius
    offset = 0
    parts = [circle(cx, cy, radius, "none", f'stroke="{theme.line}" stroke-width="16"')]
    if total == 0:
        parts.extend([text(cx, cy + 8, "—", 25, theme.muted, anchor="middle"),
                      text(x + 196, cy + 6, "No language data", 15, theme.muted)])
        return "".join(parts)
    colors = {name: theme.palette[min(i, len(theme.palette) - 1)] for i, (name, _) in enumerate(items)}
    for name, count in items:
        length = circumference * count / total
        parts.append(circle(cx, cy, radius, "none", f'stroke="{colors[name]}" stroke-width="16" '
                            f'stroke-dasharray="{fmt(length)} {fmt(circumference - length)}" '
                            f'stroke-dashoffset="{fmt(-offset)}" transform="rotate(-90 {fmt(cx)} {fmt(cy)})"'))
        offset += length
    parts.extend([text(cx, cy + 1, f"{items[0][1] / total:.1%}", 25, theme.ink, 700, "middle"),
                  text(cx, cy + 24, items[0][0], 12, theme.muted, anchor="middle")])
    legend_x = x + 196
    column_width = (width - 196) / 2
    for i, (name, count) in enumerate(items):
        column, row = divmod(i, 3)
        lx, ly = legend_x + column * column_width, y + 34 + row * 49
        parts.extend([circle(lx + 4, ly - 5, 4.5, colors[name]),
                      text(lx + 18, ly, "Other" if name == "other" else name, 15, theme.ink, 500),
                      text(lx + 18, ly + 19, f"{count / total:.1%}", 13, theme.muted)])
    return "".join(parts)
