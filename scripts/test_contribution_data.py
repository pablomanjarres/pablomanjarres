"""Check the SVG data contract used by the scheduled profile refresh."""

import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from contribution_data import descendants, parse_source, tag_name


SOURCE = Path("profile-3d-contrib/profile-night-view.svg")


class ContributionDataTests(unittest.TestCase):
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

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "generated.svg"
            ET.ElementTree(root).write(source, encoding="utf-8")
            data = parse_source(source)

        self.assertEqual(data.stars, 12345)
        self.assertEqual(data.forks, 1000001)


if __name__ == "__main__":
    unittest.main()
