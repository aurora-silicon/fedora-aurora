import importlib.machinery
import importlib.util
from pathlib import Path
import stat
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader(
    "aurora_ppd_config", str(ROOT / "packages/aurora-platform/aurora-ppd-config"))
spec = importlib.util.spec_from_loader(loader.name, loader)
ppd = importlib.util.module_from_spec(spec)
loader.exec_module(ppd)
STOCK = b"[main]\ndefault=balanced\n[profiles]\npower-saver=powersave\nbalanced=balanced\nperformance=throughput-performance\n[battery]\nbalanced=balanced-battery\n"


class PPDConfigTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.conf = Path(self.scratch.name) / "ppd.conf"

    def test_stock_mapping_preserves_every_other_byte_and_metadata(self):
        original = b"# local notes\n" + STOCK.replace(b"default=balanced", b"default=power-saver")
        self.conf.write_bytes(original)
        self.conf.chmod(0o640)
        self.assertTrue(ppd.migrate(self.conf))
        self.assertEqual(self.conf.read_bytes(), original.replace(
            b"performance=throughput-performance", b"performance=aurora-performance"))
        self.assertEqual(stat.S_IMODE(self.conf.stat().st_mode), 0o640)
        self.assertEqual(self.conf.with_suffix(".conf.aurora-original").read_bytes(), original)
        self.assertFalse(ppd.migrate(self.conf))
        self.assertEqual(list(self.conf.parent.glob(".aurora-ppd-*")), [])

    def test_custom_mapping_invalid_config_and_missing_file_are_untouched(self):
        self.assertFalse(ppd.migrate(self.conf))
        for original in (
            STOCK.replace(b"performance=throughput-performance", b"performance=my-profile"),
            b"[profiles]\nperformance=throughput-performance\nperformance=custom\n",
            b"not an ini file\nperformance=throughput-performance\n",
            b"[profiles]\nfoo=bar\n performance=throughput-performance\n",
        ):
            with self.subTest(original=original):
                self.conf.write_bytes(original)
                self.assertFalse(ppd.migrate(self.conf))
                self.assertEqual(self.conf.read_bytes(), original)
                self.assertFalse(self.conf.with_suffix(".conf.aurora-original").exists())

    def test_only_profiles_section_changes(self):
        original = STOCK + b"performance=throughput-performance\n[local]\nperformance=throughput-performance\n"
        self.conf.write_bytes(original)
        self.assertTrue(ppd.migrate(self.conf))
        self.assertEqual(self.conf.read_bytes(), original.replace(
            b"performance=throughput-performance", b"performance=aurora-performance", 1))

    def test_crlf_and_no_final_newline(self):
        for original in (STOCK.replace(b"\n", b"\r\n"), STOCK.split(b"[battery]")[0].rstrip(b"\n")):
            self.conf.write_bytes(original)
            self.assertTrue(ppd.migrate(self.conf))
            self.assertEqual(self.conf.read_bytes(), original.replace(
                b"performance=throughput-performance", b"performance=aurora-performance"))

    def test_reinstalled_stock_config_is_migrated_without_losing_original_backup(self):
        self.conf.write_bytes(STOCK)
        ppd.migrate(self.conf)
        # A later tuned-ppd transaction supplies its stock config again.
        self.conf.write_bytes(STOCK + b"# new upstream setting\n")
        self.assertTrue(ppd.migrate(self.conf))
        self.assertEqual(self.conf.with_suffix(".conf.aurora-original").read_bytes(), STOCK)
        self.assertTrue(self.conf.read_bytes().endswith(b"# new upstream setting\n"))

    def test_administrator_symlink_is_untouched(self):
        target = self.conf.with_name("managed.conf")
        target.write_bytes(STOCK)
        self.conf.symlink_to(target)
        self.assertFalse(ppd.migrate(self.conf))
        self.assertTrue(self.conf.is_symlink())
        self.assertEqual(target.read_bytes(), STOCK)
