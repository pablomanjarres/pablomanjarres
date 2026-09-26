#!/usr/bin/env python3
"""Read current contribution data from the pinned 3D SVG action output."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ACTIVITY_LABELS = ("Commit", "Issue", "PullReq", "Review", "Repo")


@dataclass(frozen=True)
class ProfileData:
    heights: list[float]
    start: date
    end: date
    contributions: int
    stars: int
    forks: int
    activity: dict[str, int]
    languages: dict[str, int]


def tag_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def descendants(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in element.iter() if tag_name(child) == name]


def parse_source(path: Path) -> ProfileData:
    root = ET.parse(path).getroot()
    groups = [child for child in root if tag_name(child) == "g"]
    calendar = next((group for group in groups if 350 <= len(group) <= 372), None)
    if calendar is None:
        raise ValueError("Generated SVG has no recognizable daily contribution grid")

    heights = []
    for day in calendar:
        faces = [child for child in day if tag_name(child) == "rect"]
        if len(faces) != 3:
            raise ValueError("Generated SVG changed its daily bar format")
        heights.append(float(faces[1].attrib["height"]))

    footer = next((group for group in groups if any(
        (text.text or "").strip() == "contributions" for text in descendants(group, "text")
    )), None)
    if footer is None:
        raise ValueError("Generated SVG has no contribution summary")
    footer_labels = descendants(footer, "text")
    footer_text = [(label.text or "").strip() for label in footer_labels]
    if len(footer_text) < 5 or footer_text[1] != "contributions":
        raise ValueError("Generated SVG changed its contribution summary format")
    period = re.fullmatch(r"(\d{4}-\d{2}-\d{2})\s*/\s*(\d{4}-\d{2}-\d{2})", footer_text[-1])
    if period is None:
        raise ValueError("Generated SVG has no recognizable date range")

    social_counts = []
    for label in footer_labels[2:4]:
        title = next((child for child in label if tag_name(child) == "title"), None)
        social_counts.append(int((title.text if title is not None else label.text) or ""))

    activity = {}
    for group in groups:
        for label in descendants(group, "text"):
            title = next((child for child in label if tag_name(child) == "title"), None)
            if label.text in ACTIVITY_LABELS and title is not None:
                activity[label.text] = int(title.text or "0")
    if set(activity) != set(ACTIVITY_LABELS):
        raise ValueError("Generated SVG changed its activity summary format")

    languages = {}
    for path_element in descendants(root, "path"):
        title = next((child for child in path_element if tag_name(child) == "title"), None)
        match = re.fullmatch(r"(.+)\s+(\d+)", (title.text or "") if title is not None else "")
        if match:
            languages[match.group(1)] = int(match.group(2))
    if not languages:
        raise ValueError("Generated SVG has no language mix")

    return ProfileData(
        heights=heights,
        start=date.fromisoformat(period.group(1)),
        end=date.fromisoformat(period.group(2)),
        contributions=int(re.sub(r"\D", "", footer_text[0])),
        stars=social_counts[0],
        forks=social_counts[1],
        activity=activity,
        languages=languages,
    )
