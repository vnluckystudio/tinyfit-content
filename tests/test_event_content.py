import copy
import json
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import event_content


ROOT = Path(__file__).resolve().parents[1]


class EventContentTests(unittest.TestCase):
    def test_sample_event_is_valid(self):
        report = event_content.validate(ROOT)
        self.assertGreaterEqual(len(report), 1)
        self.assertTrue(all("puzzle(s)" in entry for entry in report))

    def test_rejects_timezone_less_schedule(self):
        with self.assertRaisesRegex(ValueError, "timezone is required"):
            event_content.parse_instant("2027-04-01T00:00:00", "startsAt")

    def test_rejects_malformed_minimum_app_version(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path in ROOT.rglob("*"):
                if path.is_file():
                    target = root / path.relative_to(ROOT)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(path.read_bytes())
            catalog_path = root / "events.json"
            catalog = json.loads(catalog_path.read_text())
            catalog["events"][0]["minAppVersion"] = "1.beta"
            catalog_path.write_text(json.dumps(catalog))
            with self.assertRaisesRegex(ValueError, "minAppVersion"):
                event_content.validate(root)

    def test_rejects_duplicate_event_id(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path in ROOT.rglob("*"):
                if path.is_file():
                    target = root / path.relative_to(ROOT)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(path.read_bytes())
            catalog_path = root / "events.json"
            catalog = json.loads(catalog_path.read_text())
            catalog["events"].append(copy.deepcopy(catalog["events"][0]))
            catalog_path.write_text(json.dumps(catalog))
            with self.assertRaisesRegex(ValueError, "duplicate event id"):
                event_content.validate(root)

    def test_init_event_scaffolds_catalog_and_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "templates").mkdir()
            (root / "templates/cover.webp").write_bytes((ROOT / "templates/cover.webp").read_bytes())
            (root / "events.json").write_text(json.dumps({"schemaVersion": 1, "contentVersion": "1", "events": []}))
            event_root = event_content.create_scaffold(
                "test-event", "Test Event", "Sample description", "2027-05-01T00:00:00Z", "2027-05-02T00:00:00Z", root
            )
            self.assertTrue((event_root / "event.json").is_file())
            self.assertTrue((event_root / "cover.webp").is_file())
            self.assertEqual(json.loads((root / "events.json").read_text())["events"][0]["id"], "test-event")


if __name__ == "__main__":
    unittest.main()
