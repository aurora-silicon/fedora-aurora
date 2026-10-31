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
                if "archive_file" in item:
                    self.assertEqual(Path(item["archive_file"]).name, item["archive_file"])
                    self.assertTrue(item["source_url"].endswith('/' + item["archive_file"]))
                else:
                    self.assertTrue(item["source_url"].endswith(item["commit"]))
                self.assertTrue((ROOT / f"packages/{name}/{name}.spec").is_file())

    def test_release_archive_keeps_its_pinned_name_and_verified_cached_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            content = b"pinned release archive"
            item = {"commit": "a" * 40, "sha256": hashlib.sha256(content).hexdigest(), "archive_file": "fixture-1.tar.xz"}
            (root / "sources.json").write_text(json.dumps({"fixture": item}))
            cache = root / 'cache/sources'; cache.mkdir(parents=True)
            (cache / item['archive_file']).write_bytes(content)
            with patch.object(fetch, "ROOT", root):
                result = fetch.fetch('fixture', root / 'build')
            self.assertEqual(result.name, item['archive_file'])
            self.assertEqual(result.read_bytes(), content)

    def test_archive_filename_cannot_escape_the_source_directory(self):
        for name in ['../outside', '/absolute', '..', '.', '', 'dir\\outside']:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                item = {"commit": "a" * 40, "sha256": "b" * 64, "archive_file": name}
                (root / 'sources.json').write_text(json.dumps({'fixture': item}))
                with patch.object(fetch, 'ROOT', root), self.assertRaisesRegex(ValueError, 'unsafe source archive filename'):
                    fetch.fetch('fixture', root / 'build')

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

class ExtraSourceTests(unittest.TestCase):
    def test_extra_sources_are_verified_before_the_main_archive_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / 'files'
            destination.mkdir()
            extra = {'commit': 'b' * 40, 'sha256': hashlib.sha256(b'extra').hexdigest()}
            main = {'commit': 'a' * 40, 'sha256': hashlib.sha256(b'main').hexdigest(),
                    'extra_sources': {'dependency': extra}}
            (root / 'sources.json').write_text(json.dumps({'fixture': main}))
            (destination / ('fixture-' + 'a' * 40 + '.tar.gz')).write_bytes(b'main')
            dependency = destination / ('dependency-' + 'b' * 40 + '.tar.gz')
            dependency.write_bytes(b'wrong')
            with patch.object(fetch, 'ROOT', root), self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                fetch.fetch('fixture', destination)
            dependency.write_bytes(b'extra')
            with patch.object(fetch, 'ROOT', root):
                self.assertEqual(fetch.fetch('fixture', destination).read_bytes(), b'main')


if __name__ == "__main__":
    unittest.main()
