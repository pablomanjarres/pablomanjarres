#!/usr/bin/env python3
"""Render the profile dashboard from the generated 3D SVG."""

from __future__ import annotations

import argparse
from pathlib import Path

from contribution_data import ProfileData, parse_source
from contribution_shapes import calendar_art, language_mix, radar, social_count, svg_open, text

SOURCE = Path("profile-3d-contrib/profile-night-view.svg")
OUTPUT = Path("profile-3d-contrib/contribution-showcase.svg")
MOBILE_OUTPUT = Path("profile-3d-contrib/contribution-showcase-mobile.svg")


def render(data: ProfileData) -> str:
    date_label = f"{data.start:%d %b %Y}  —  {data.end:%d %b %Y}"
    parts = svg_open(1280, 660, data) + [
        '<circle cx="1230" cy="32" r="210" fill="#D9DAFA" opacity="0.45"/>',
        text(42, 77, "A year in code", size=39, color="#202542", weight=750),
        text(1238, 73, date_label, size=17, color="#5D6584", weight=500, anchor="end"),
        '<rect x="38" y="112" width="780" height="500" rx="25" fill="#FFFFFF" fill-opacity="0.83" filter="url(#shadow)"/>',
        '<rect x="838" y="112" width="404" height="340" rx="25" fill="#171C30" filter="url(#shadow)"/>',
        '<rect x="838" y="470" width="404" height="142" rx="25" fill="#FFFFFF" fill-opacity="0.86" filter="url(#shadow)"/>',
        text(75, 170, "Contributions", size=19, color="#626A86", weight=600),
        text(70, 255, f"{data.contributions:,}", size=75, color="#222844", weight=750,
             extra='letter-spacing="-4"'),
        text(77, 284, "in the last year", size=17, color="#8189A6"),
        calendar_art(data),
        radar(data),
        language_mix(data),
        text(42, 643, social_count(data), size=15, color="#5E6786", weight=500),
        text(1238, 643, "Updated from GitHub activity", size=15,
             color="#7E87A3", anchor="end"),
        '</svg>',
    ]
    return "\n".join(parts) + "\n"


def render_mobile(data: ProfileData) -> str:
    date_label = f"{data.start:%d %b %Y}  —  {data.end:%d %b %Y}"
    parts = svg_open(640, 1236, data) + [
        '<circle cx="608" cy="41" r="180" fill="#D9DAFA" opacity="0.45"/>',
        text(29, 79, "A year in code", size=44, color="#202542", weight=750),
        text(31, 112, date_label, size=21, color="#5D6584", weight=500),
        '<rect x="24" y="132" width="592" height="492" rx="25" fill="#FFFFFF" fill-opacity="0.83" filter="url(#shadow)"/>',
        '<rect x="24" y="641" width="592" height="381" rx="25" fill="#171C30" filter="url(#shadow)"/>',
        '<rect x="24" y="1038" width="592" height="142" rx="25" fill="#FFFFFF" fill-opacity="0.86" filter="url(#shadow)"/>',
        text(51, 186, "Contributions", size=22, color="#626A86", weight=600),
        text(46, 269, f"{data.contributions:,}", size=84, color="#222844", weight=750,
             extra='letter-spacing="-4"'),
        text(52, 301, "in the last year", size=20, color="#8189A6"),
        '<g transform="translate(-18 138) scale(0.79)">', calendar_art(data), '</g>',
        '<g transform="translate(-1012 455) scale(1.28)">', radar(data), '</g>',
        '<g transform="translate(-1154 356) scale(1.4)">', language_mix(data), '</g>',
        text(30, 1217, social_count(data), size=19, color="#5E6786", weight=500),
        '</svg>',
    ]
    return "\n".join(parts) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--mobile-output", type=Path, default=MOBILE_OUTPUT)
    args = parser.parse_args()
    data = parse_source(args.source)
    args.output.write_text(render(data), encoding="utf-8")
    args.mobile_output.write_text(render_mobile(data), encoding="utf-8")
    print(f"Rendered {args.output} and {args.mobile_output}")


if __name__ == "__main__":
    main()
