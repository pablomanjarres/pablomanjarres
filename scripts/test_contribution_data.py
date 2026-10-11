"""Check the SVG data contract used by the scheduled profile refresh."""

import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from contribution_data import (EMPTY_DAY_HEIGHT, MAX_DAY_HEIGHT, ProfileData,
                               descendants, parse_snapshot, parse_source, tag_name)
from fetch_contribution_data import fetch_snapshot, write_snapshot


SOURCE = Path(__file__).resolve().parents[1] / "profile-3d-contrib/profile-night-view.svg"


class ContributionDataTests(unittest.TestCase):
    def parse_modified(self, root: ET.Element) -> ProfileData:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "generated.svg"
            ET.ElementTree(root).write(source, encoding="utf-8")
            return parse_source(source)

    def test_abbreviated_social_labels_keep_exact_counts(self) -> None:
        root = ET.parse(SOURCE).getroot()
        footer = next(group for group in root if tag_name(group) == "g" and any(
            (label.text or "").strip() == "contributions"
            for label in descendants(group, "text")
        ))
        labels = descendants(footer, "text")
        for label, abbreviated, exact in (
            (labels[2], "12K", "12345"),
            (labels[3], "1M+", "1000001"),
        ):
            label.text = abbreviated
            title = next(child for child in label if tag_name(child) == "title")
            title.text = exact

        data = self.parse_modified(root)

        self.assertEqual(data.stars, 12345)
        self.assertEqual(data.forks, 1000001)

    def test_activity_properties_use_height_threshold_and_calendar_order(self) -> None:
        data = replace(parse_source(SOURCE), heights=[2.6, 2.61, 9, 2.6, 3, 4, 5])
        self.assertEqual(data.active_days, 5)
        self.assertEqual(data.longest_streak, 3)
        with self.assertRaises(AttributeError):
            data.active_days = 10
        with self.assertRaises(AttributeError):
            data.longest_streak = 10

    def test_calendar_without_active_days_has_no_streak(self) -> None:
        data = replace(parse_source(SOURCE), heights=[2.6] * 365)
        self.assertEqual(data.active_days, 0)
        self.assertEqual(data.longest_streak, 0)

    def test_invalid_heights_are_rejected(self) -> None:
        for invalid in ("nan", "inf", "-inf", "2.59"):
            with self.subTest(height=invalid):
                root = ET.parse(SOURCE).getroot()
                calendar = next(group for group in root
                                if tag_name(group) == "g" and 350 <= len(group) <= 372)
                faces = [child for child in calendar[0] if tag_name(child) == "rect"]
                faces[1].set("height", invalid)
                with self.assertRaisesRegex(ValueError, "invalid daily contribution height"):
                    self.parse_modified(root)

    def test_date_range_must_match_calendar_length(self) -> None:
        data = parse_source(SOURCE)
        for end in (data.end + timedelta(days=1), data.start - timedelta(days=1)):
            with self.subTest(end=end):
                root = ET.parse(SOURCE).getroot()
                footer = next(group for group in root if tag_name(group) == "g" and any(
                    (label.text or "").strip() == "contributions"
                    for label in descendants(group, "text")
                ))
                descendants(footer, "text")[-1].text = f"{data.start} / {end}"
                with self.assertRaisesRegex(ValueError, "date range does not match"):
                    self.parse_modified(root)



if __name__ == "__main__":
    unittest.main()
