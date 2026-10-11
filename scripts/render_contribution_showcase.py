#!/usr/bin/env python3
"""Compose one contribution graphic for desktop and mobile README layouts."""

from __future__ import annotations

import argparse
from pathlib import Path

from contribution_charts import contribution_landscape, languages, radar
from contribution_data import ProfileData, parse_source
from contribution_shapes import (ColorTheme, DEFAULT_THEME, DEFAULT_THEME_NAME,
                                 THEMES, icon, svg_open, text)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'profile-3d-contrib/contribution-data.json'
OUTPUT = ROOT / 'profile-3d-contrib/contribution-showcase.svg'
MOBILE_OUTPUT = ROOT / 'profile-3d-contrib/contribution-showcase-mobile.svg'


def header(data: ProfileData, mobile: bool, theme: ColorTheme) -> str:
    left = 32 if mobile else 40
    period = f'{data.start:%d %b %Y} – {data.end:%d %b %Y}'
    parts = [text(left, 52, 'A year in code', 27, theme.ink, 600)]
    parts.append(text(left if mobile else 1240, 80 if mobile else 51, period,
                      14, theme.muted, anchor='start' if mobile else 'end'))
    return ''.join(parts)


def contribution_summary(data: ProfileData, mobile: bool, theme: ColorTheme) -> str:
    left = 32 if mobile else 40
    baseline = 156 if mobile else 142
    parts = [text(left - 2, baseline, f'{data.contributions:,}', 64, theme.ink, 700,
                  extra='letter-spacing="-2.5"'),
             text(left if mobile else 281, baseline + (29 if mobile else -3),
                  'contributions', 18, theme.muted),
             text(left, baseline + (59 if mobile else 29),
                  'Public and private contributions', 14, theme.muted)]
    for i, (name, value, label) in enumerate((('star', data.stars, 'stars'), ('fork', data.forks, 'forks'))):
        x = (390 if mobile else 618) + i * (102 if mobile else 120)
        parts.extend([icon(name, x, baseline - 19, 20, theme.accent),
                      text(x + 29, baseline - 2, f'{value:,}', 20, theme.ink, 600),
                      text(x + 28, baseline + 19, label, 12, theme.muted)])
    return ''.join(parts)


def activity_chart(data: ProfileData, mobile: bool, theme: ColorTheme) -> str:
    x, y, width = (140, 532, 360) if mobile else (884, 140, 300)
    return ''.join([
        text(32 if mobile else 940, 571 if mobile else 153, 'Activity breakdown', 18, theme.ink, 600),
        radar(data, x, y, width, theme),
        text(x + width / 2, y + (309 if mobile else 286), 'Logarithmic scale', 11, theme.muted, anchor='middle'),
    ])


def language_chart(data: ProfileData, mobile: bool, theme: ColorTheme) -> str:
    x, y, width = (32, 892, 576) if mobile else (40, 230, 726)
    heading_y = 877 if mobile else 217
    scope = 'All commits' if data.breakdown_complete else 'Visible commits'
    return ''.join([text(x, heading_y, 'Languages', 18, theme.ink, 600),
                    text(x + 114, heading_y, scope, 13, theme.muted),
                    languages(data, x, y, width, theme)])


def footer(data: ProfileData, mobile: bool, height: int, theme: ColorTheme) -> str:
    x = 32 if mobile else 40
    baseline = height - 24
    private = (f'{data.restricted_contributions:,} private contributions'
               if data.restricted_contributions else
               'Private contributions included' if data.breakdown_complete else
               'GitHub contribution calendar')
    stats_y = baseline - (23 if mobile else 0)
    return ''.join([text(x, stats_y, f'{data.active_days} active days', 14, theme.muted),
                    text(x + 180, stats_y, f'{data.longest_streak}-day best streak', 14, theme.muted),
                    text(x if mobile else 1240, baseline, private, 13, theme.muted,
                         anchor='start' if mobile else 'end')])


def render(data: ProfileData, mobile: bool = False,
           theme: ColorTheme = DEFAULT_THEME) -> str:
    width, height = (640, 1112) if mobile else (1280, 704)
    plot = (24, 320, 592, 228) if mobile else (32, 432, 1216, 220)
    parts = svg_open(width, height, data, theme)
    parts.extend([header(data, mobile, theme), contribution_summary(data, mobile, theme),
                  text(32 if mobile else 40, 296 if mobile else 420, 'Daily activity', 13, theme.muted),
                  contribution_landscape(data, *plot, theme=theme), activity_chart(data, mobile, theme),
                  language_chart(data, mobile, theme), footer(data, mobile, height, theme), '</svg>'])
    return '\n'.join(parts) + '\n'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--theme', choices=THEMES, default=DEFAULT_THEME_NAME, help='Coordinated chart color palette')
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--mobile-output', type=Path, default=MOBILE_OUTPUT)
    args = parser.parse_args()
    data = parse_source(args.source)
    for output, mobile in ((args.output, False), (args.mobile_output, True)):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(render(data, mobile, THEMES[args.theme]), encoding='utf-8')
    print(f'Rendered {args.output.name} and {args.mobile_output.name}')


if __name__ == '__main__':
    main()
