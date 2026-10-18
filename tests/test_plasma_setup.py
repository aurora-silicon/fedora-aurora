from pathlib import Path
import contextlib
import io
import runpy
import tempfile
import unittest

HELPER = runpy.run_path(str(Path(__file__).resolve().parents[1] / "packages/aurora-remix-scripts/complete-plasma-setup"))


class PlasmaSetupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.completion = self.root / "complete"
        self.configuration = self.root / "99-plasma-setup.conf"
        self.generated = b"[Autologin]\nUser=plasma-setup\nSession=plasma\n"

    def tearDown(self):
        self.temporary.cleanup()

    def run_helper(self):
        with contextlib.redirect_stdout(io.StringIO()):
            HELPER["retire_setup_login"](self.completion, [self.configuration])

    def test_setup_login_remains_before_linux_owner_completion(self):
        self.configuration.write_bytes(self.generated)
        self.run_helper()
        self.assertEqual(self.configuration.read_bytes(), self.generated)

    def test_generated_setup_login_is_retired_after_owner_completion(self):
        self.completion.touch()
        self.configuration.write_bytes(self.generated)
        self.run_helper()
        self.assertFalse(self.configuration.exists())
        self.run_helper()

    def test_administrator_login_or_edits_are_preserved(self):
        self.completion.touch()
        for content in [b"[Autologin]\nUser=alice\nSession=plasma\n", self.generated + b"# administrator edit\n"]:
            with self.subTest(content=content):
                self.configuration.write_bytes(content)
                self.run_helper()
                self.assertEqual(self.configuration.read_bytes(), content)

    def test_symlink_is_preserved(self):
        self.completion.touch()
        target = self.root / "administrator-file"
        target.write_bytes(self.generated)
        self.configuration.symlink_to(target)
        self.run_helper()
        self.assertTrue(self.configuration.is_symlink())
        self.assertEqual(target.read_bytes(), self.generated)

    def test_completion_symlink_does_not_retire_setup_login(self):
        target = self.root / "other"
        target.touch()
        self.completion.symlink_to(target)
        self.configuration.write_bytes(self.generated)
        self.run_helper()
        self.assertEqual(self.configuration.read_bytes(), self.generated)
