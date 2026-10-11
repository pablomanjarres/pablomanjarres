#!/usr/bin/env python3
"""Read sanitized contribution snapshots or the legacy 3D SVG action output."""

from __future__ import annotations

import json
import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

ACTIVITY_LABELS = ("Commit", "Issue", "PullReq", "Review", "Repo")
EMPTY_DAY_HEIGHT = 2.6
MAX_DAY_HEIGHT = 120.0


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
    restricted_contributions: int = 0
    daily_counts: list[int] | None = None

    @property
    def breakdown_complete(self) -> bool:
        return (self.daily_counts is not None and self.restricted_contributions == 0
                and sum(self.languages.values()) == self.activity["Commit"])

    @property
    def active_days(self) -> int:
        """Count bars above the pinned generator's rounded zero-day height."""
        return sum(height > EMPTY_DAY_HEIGHT for height in self.heights)

    @property
    def longest_streak(self) -> int:
        """Count the longest consecutive run of active days in calendar order."""
        longest = current = 0
        for height in self.heights:
            current = current + 1 if height > EMPTY_DAY_HEIGHT else 0
            longest = max(longest, current)
        return longest


def tag_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def descendants(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in element.iter() if tag_name(child) == name]


def parse_source(path: Path) -> ProfileData:
    if path.suffix.lower() == ".json":
        return parse_snapshot(json.loads(path.read_text(encoding="utf-8")))
    return parse_legacy_svg(path)


def nonnegative_integer(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"Contribution snapshot has an invalid {label}")
    return value


def parse_snapshot(snapshot: dict) -> ProfileData:
    """Preserve exact counts; normalized heights are only a visual intensity."""
    if not isinstance(snapshot, dict) or snapshot.get("schema_version") != 1:
        raise ValueError("Contribution snapshot has an unsupported schema")
    days = snapshot.get("daily_contributions")
    if not isinstance(days, list) or not days:
        raise ValueError("Contribution snapshot has no daily contribution calendar")
    dates, counts = [], []
    for item in days:
        if not isinstance(item, dict) or not isinstance(item.get("date"), str):
            raise ValueError("Contribution snapshot has an invalid daily date")
        day = date.fromisoformat(item["date"])
        if day.isoformat() != item["date"] or dates and day != dates[-1] + timedelta(days=1):
            raise ValueError("Contribution snapshot daily dates must be consecutive and ordered")
        dates.append(day)
        counts.append(nonnegative_integer(item.get("count"), "daily count"))
    if snapshot.get("start") != dates[0].isoformat() or snapshot.get("end") != dates[-1].isoformat():
        raise ValueError("Contribution snapshot date range does not match its daily calendar")
    contributions = nonnegative_integer(snapshot.get("contributions"), "contribution total")
    if contributions != sum(counts):
        raise ValueError("Contribution snapshot total does not match its daily counts")
    restricted = nonnegative_integer(snapshot.get("restricted_contributions", 0), "restricted count")
    if restricted > contributions:
        raise ValueError("Contribution snapshot restricted count exceeds its total")
    activity = snapshot.get("activity")
    if not isinstance(activity, dict) or set(activity) != set(ACTIVITY_LABELS):
        raise ValueError("Contribution snapshot has an invalid activity breakdown")
    activity = {label: nonnegative_integer(count, "activity count") for label, count in activity.items()}
    languages = snapshot.get("languages")
    if not isinstance(languages, dict) or any(not isinstance(label, str) or not label for label in languages):
        raise ValueError("Contribution snapshot has an invalid language aggregate")
    languages = {label: nonnegative_integer(count, "language count") for label, count in languages.items()}
    peak = max(counts)
    scale = math.log1p(peak) or 1
    heights = [EMPTY_DAY_HEIGHT + (MAX_DAY_HEIGHT - EMPTY_DAY_HEIGHT) * (math.log1p(count) / scale)
               for count in counts]
    return ProfileData(
        heights=heights, start=dates[0], end=dates[-1], contributions=contributions,
        stars=nonnegative_integer(snapshot.get("stars"), "star count"),
        forks=nonnegative_integer(snapshot.get("forks"), "fork count"),
        activity=activity, languages=languages,
        restricted_contributions=restricted, daily_counts=counts,
    )


def require_complete(data: ProfileData) -> None:
    """Reject untyped private activity instead of treating it as commits."""
    if data.restricted_contributions:
        raise ValueError(
            f"Contribution breakdown is incomplete: {data.restricted_contributions:,} "
            "restricted contributions have no verified type; snapshot was not replaced"
        )
    if not data.breakdown_complete:
        raise ValueError("Contribution breakdown lacks exact daily counts or complete language totals; snapshot was not replaced")


def parse_legacy_svg(path: Path) -> ProfileData:
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
        height = float(faces[1].attrib["height"])
        if not math.isfinite(height) or height < EMPTY_DAY_HEIGHT:
            raise ValueError("Generated SVG has an invalid daily contribution height")
        heights.append(height)

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
    start = date.fromisoformat(period.group(1))
    end = date.fromisoformat(period.group(2))
    if (end - start).days + 1 != len(heights):
        raise ValueError("Generated SVG date range does not match its daily contribution grid")

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
        start=start,
        end=end,
        contributions=int(re.sub(r"\D", "", footer_text[0])),
        stars=social_counts[0],
        forks=social_counts[1],
        activity=activity,
        languages=languages,
    )
