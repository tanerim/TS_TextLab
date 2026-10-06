import csv
import tempfile
import unittest
from pathlib import Path

from app.export_service import timestamped_csv_path, write_tab_csv


class ExportServiceTests(unittest.TestCase):
    def test_timestamp_is_present_once_with_or_without_extension(self):
        stamp = "20261006-143025-123456"
        for name in ("analysis", "analysis.csv", "analysis.CSV", f"analysis-{stamp}.csv"):
            with self.subTest(name=name):
                self.assertEqual(timestamped_csv_path(name, stamp).name, f"analysis-{stamp}.csv")
        self.assertNotEqual(
            timestamped_csv_path("analysis.csv", stamp),
            timestamped_csv_path("analysis.csv", "20261006-143025-123457"),
        )

    def test_unicode_tabs_newlines_and_quotes_round_trip(self):
        headers = ["Token", "Tag"]
        rows = [("İstanbul", "Noun"), ("bir\tiki", 'a"b'), ("satır\nsonu", "")]
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "result.csv"
            write_tab_csv(target, headers, rows)
            with target.open(encoding="utf-8", newline="") as stream:
                actual = list(csv.reader(stream, delimiter="\t"))
            self.assertEqual(actual, [headers, *map(list, rows)])
            self.assertTrue(target.read_bytes().startswith(b"Token\tTag\n"))


if __name__ == "__main__":
    unittest.main()
