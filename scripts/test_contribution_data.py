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


class ContributionSnapshotTests(unittest.TestCase):
    def snapshot(self) -> dict:
        return {
            "schema_version": 1,
            "start": "2026-01-01", "end": "2026-01-05",
            "contributions": 12, "restricted_contributions": 7,
            "stars": 3, "forks": 2,
            "activity": {"Commit": 4, "Issue": 1, "PullReq": 0, "Review": 0, "Repo": 0},
            "languages": {"Python": 4},
            "daily_contributions": [{"date": f"2026-01-0{i + 1}", "count": count}
                                    for i, count in enumerate((0, 3, 4, 0, 5))],
        }

    def test_snapshot_preserves_exact_dates_counts_and_restricted_activity(self) -> None:
        data = parse_snapshot(self.snapshot())
        self.assertEqual(data.daily_counts, [0, 3, 4, 0, 5])
        self.assertEqual((str(data.start), str(data.end)), ("2026-01-01", "2026-01-05"))
        self.assertEqual(data.contributions, 12)
        self.assertEqual(data.restricted_contributions, 7)
        self.assertEqual(data.activity["Commit"], 4)
        self.assertFalse(data.breakdown_complete)
        self.assertEqual((data.active_days, data.longest_streak), (3, 2))
        self.assertEqual(data.heights[0], EMPTY_DAY_HEIGHT)
        self.assertEqual(max(data.heights), MAX_DAY_HEIGHT)

    def test_breakdown_completeness_requires_exact_unrestricted_aggregate(self) -> None:
        self.assertFalse(parse_source(SOURCE).breakdown_complete)
        snapshot = self.snapshot()
        snapshot["restricted_contributions"] = 0
        self.assertTrue(parse_snapshot(snapshot).breakdown_complete)
        snapshot["languages"]["Python"] -= 1
        self.assertFalse(parse_snapshot(snapshot).breakdown_complete)

    def test_log_intensity_keeps_small_active_days_visible_beside_a_peak(self) -> None:
        snapshot = self.snapshot()
        for day, count in zip(snapshot["daily_contributions"], (0, 1, 10, 100, 2089)):
            day["count"] = count
        snapshot["contributions"] = 2200
        data = parse_snapshot(snapshot)
        self.assertEqual(data.daily_counts, [0, 1, 10, 100, 2089])
        self.assertEqual(data.heights[0], EMPTY_DAY_HEIGHT)
        self.assertGreater(data.heights[1], 10)
        self.assertEqual(data.heights[-1], MAX_DAY_HEIGHT)
        self.assertEqual(data.heights, sorted(data.heights))

    def test_zero_calendar_retains_baseline_without_division(self) -> None:
        snapshot = self.snapshot()
        for day in snapshot["daily_contributions"]:
            day["count"] = 0
        snapshot.update(contributions=0, restricted_contributions=0)
        snapshot["activity"] = dict.fromkeys(snapshot["activity"], 0)
        snapshot["languages"] = {}
        data = parse_snapshot(snapshot)
        self.assertEqual(data.heights, [EMPTY_DAY_HEIGHT] * 5)
        self.assertEqual((data.active_days, data.longest_streak), (0, 0))

    def test_snapshot_rejects_gaps_duplicate_dates_and_wrong_range(self) -> None:
        for replacement in ("2026-01-02", "2026-01-04"):
            with self.subTest(date=replacement):
                snapshot = self.snapshot()
                snapshot["daily_contributions"][2]["date"] = replacement
                with self.assertRaisesRegex(ValueError, "consecutive and ordered"):
                    parse_snapshot(snapshot)
        snapshot = self.snapshot()
        snapshot["end"] = "2026-01-06"
        with self.assertRaisesRegex(ValueError, "date range does not match"):
            parse_snapshot(snapshot)

    def test_snapshot_rejects_inexact_counts_and_mismatched_total(self) -> None:
        for count in (-1, True, 1.5):
            with self.subTest(count=count):
                snapshot = self.snapshot()
                snapshot["daily_contributions"][0]["count"] = count
                with self.assertRaisesRegex(ValueError, "invalid daily count"):
                    parse_snapshot(snapshot)
        snapshot = self.snapshot()
        snapshot["contributions"] += 1
        with self.assertRaisesRegex(ValueError, "total does not match"):
            parse_snapshot(snapshot)

    def test_completeness_guard_preserves_previous_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "snapshot.json"
            output.write_text("previous complete snapshot")
            with self.assertRaisesRegex(ValueError, "restricted contributions have no verified type"):
                write_snapshot(self.snapshot(), output, require_complete_breakdown=True)
            self.assertEqual(output.read_text(), "previous complete snapshot")
            write_snapshot(self.snapshot(), output)
            self.assertEqual(parse_source(output).restricted_contributions, 7)
            self.assertEqual(json.loads(output.read_text())["daily_contributions"],
                             self.snapshot()["daily_contributions"])

    def test_complete_snapshot_can_replace_previous_file(self) -> None:
        snapshot = self.snapshot()
        snapshot["restricted_contributions"] = 0
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "snapshot.json"
            write_snapshot(snapshot, output, require_complete_breakdown=True)
            self.assertEqual(parse_source(output).daily_counts, [0, 3, 4, 0, 5])

    def test_fetch_discards_repository_identity_and_paginates_public_aggregates(self) -> None:
        fixture = self.snapshot()
        collection = {
            "startedAt": "2026-01-01T00:00:00Z", "endedAt": "2026-01-05T23:59:59Z",
            "restrictedContributionsCount": 7,
            "totalCommitContributions": 4, "totalIssueContributions": 1,
            "totalPullRequestContributions": 0, "totalPullRequestReviewContributions": 0,
            "totalRepositoryContributions": 0,
            "contributionCalendar": {
                "totalContributions": 12,
                "weeks": [{"contributionDays": [{"date": day["date"], "contributionCount": day["count"]}
                                                 for day in fixture["daily_contributions"]]}],
            },
            "commitContributionsByRepository": [{
                "repository": {"primaryLanguage": {"name": "Python"}, "nameWithOwner": "sensitive/identity"},
                "contributions": {"totalCount": 4},
            }],
        }
        responses = [
            {"profile": {"login": "public-profile", "contributionsCollection": collection}},
            {"profile": {"repositories": {"nodes": [{"stargazerCount": 2, "forkCount": 2}],
                                           "pageInfo": {"hasNextPage": True, "endCursor": "next"}}}},
            {"profile": {"repositories": {"nodes": [{"stargazerCount": 1, "forkCount": 0}],
                                           "pageInfo": {"hasNextPage": False, "endCursor": "end"}}}},
        ]
        with patch("fetch_contribution_data.graphql", side_effect=responses) as api:
            snapshot = fetch_snapshot()
        serialized = json.dumps(snapshot)
        self.assertNotIn("sensitive/identity", serialized)
        self.assertNotIn("nameWithOwner", serialized)
        self.assertEqual((snapshot["stars"], snapshot["forks"]), (3, 2))
        self.assertEqual(snapshot["restricted_contributions"], 7)
        self.assertEqual(snapshot["activity"]["Commit"], 4)
        self.assertEqual(api.call_args_list[2].args[1], {"after": "next"})
        self.assertTrue(all("privacy: PUBLIC" in call.args[0] for call in api.call_args_list[1:]))

    def test_explicit_window_requires_both_timezone_aware_endpoints(self) -> None:
        with self.assertRaisesRegex(ValueError, "Provide both"):
            fetch_snapshot(from_time="2026-01-01T00:00:00Z")
        with self.assertRaisesRegex(ValueError, "ordered timestamps with a timezone"):
            fetch_snapshot(from_time="2026-01-01T00:00:00", to_time="2026-01-05T00:00:00")


if __name__ == "__main__":
    unittest.main()
