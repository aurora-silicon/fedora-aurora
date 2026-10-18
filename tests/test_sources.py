import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("fetch", ROOT / "scripts/fetch-sources.py")
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


class SourceTests(unittest.TestCase):
    def test_source_pins_are_immutable_and_all_have_recipes(self):
        for name, item in json.loads((ROOT / "sources.json").read_text()).items():
            with self.subTest(package=name):
                self.assertRegex(item["commit"], r"^[0-9a-f]{40}$")
                self.assertRegex(item["sha256"], r"^[0-9a-f]{64}$")
                self.assertTrue(item["source_url"].endswith(item["commit"]))
                self.assertTrue((ROOT / f"packages/{name}/{name}.spec").is_file())

    def test_corrupt_cache_is_rejected_before_it_can_be_used(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item = {"commit": "a" * 40, "sha256": hashlib.sha256(b"expected").hexdigest()}
            (root / "sources.json").write_text(json.dumps({"fixture": item}))
            destination = root / "files"
            destination.mkdir()
            (destination / ("fixture-" + "a" * 40 + ".tar.gz")).write_bytes(b"wrong")
            with patch.object(fetch, "ROOT", root), self.assertRaisesRegex(ValueError, "checksum mismatch"):
                fetch.fetch("fixture", destination)


if __name__ == "__main__":
    unittest.main()
