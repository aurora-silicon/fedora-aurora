import concurrent.futures
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ProtonPreparation(unittest.TestCase):
    def setUp(self):
        self.temporary = self.enterContext(tempfile.TemporaryDirectory(prefix='aurora proton '))
        self.root = Path(self.temporary)
        self.home = self.root / 'home'
        self.home.mkdir()
        self.packaged = self.root / 'packaged'
        self.packaged.mkdir()
        self.current = self.packaged / 'current'
        self.source = self.revision('Aurora-Proton11-9-1.fc44')
        self.current.symlink_to(self.source)
        self.lib = self.root / 'lib'
        self.lib.mkdir()
        self.prepare = self.lib / 'prepare-proton'
        self.prepare.write_text((ROOT / 'packages/aurora-proton/prepare-proton').read_text()
                                .replace('@PROTON@', shlex.quote(str(self.current)))
                                .replace('#!/bin/bash\n', '#!' + shutil.which('bash') + '\n', 1))
        self.prepare.chmod(0o755)
        self.env = {**os.environ, 'HOME': str(self.home), 'XDG_DATA_HOME': str(self.home / 'data')}
        self.env.pop('STEAM_EXTRA_COMPAT_TOOLS_PATHS', None)
        self.env.pop('AURORA_STEAM_PROTON', None)

    def revision(self, name):
        path = self.packaged / name
        path.mkdir()
        (path / 'proton').write_text('#!/bin/sh\nexit 0\n')
        (path / 'proton').chmod(0o555)
        return path

    def run_prepare(self):
        return subprocess.run([str(self.prepare)], env=self.env, capture_output=True, text=True)

    def run_environment(self, **changes):
        env = {**self.env, **changes}
        script = 'lib=$1; source "$2"; printf "%s" "${STEAM_EXTRA_COMPAT_TOOLS_PATHS-absent}"'
        return subprocess.run(['bash', '-euc', script, 'fixture', str(self.lib),
                               str(ROOT / 'packages/aurora-steam-native/proton-env')],
                              env=env, capture_output=True, text=True)

    def test_copy_is_writable_and_preserves_personal_settings_on_repeat(self):
        result = self.run_prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        target = Path(result.stdout.strip())
        self.assertEqual(target.name, self.source.name)
        self.assertTrue((target / 'proton').stat().st_mode & 0o200)
        self.assertEqual((target / '.aurora-proton-source').read_text().strip(), str(self.source))
        settings = target / 'user_settings.py'
        settings.write_text('user_settings = {"PROTON_LOG": "1"}\n')
        self.assertEqual(self.run_prepare().returncode, 0)
        self.assertEqual(settings.read_text(), 'user_settings = {"PROTON_LOG": "1"}\n')
        self.assertFalse((self.source / 'user_settings.py').exists())

    def test_distro_revision_change_keeps_old_copy_and_uses_new_payload(self):
        old = Path(self.run_prepare().stdout.strip())
        (old / 'user_settings.py').write_text('personal settings')
        newer = self.revision('Aurora-Proton11-9-1.fc45')
        self.current.unlink()
        self.current.symlink_to(newer)
        result = self.run_prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        new = Path(result.stdout.strip())
        self.assertNotEqual(old, new)
        self.assertEqual(new.name, newer.name)
        self.assertEqual((old / 'user_settings.py').read_text(), 'personal settings')
        self.assertFalse((new / 'user_settings.py').exists())

    def test_unmanaged_existing_target_is_not_overwritten(self):
        target = self.home / 'data/aurora-proton' / self.source.name
        target.mkdir(parents=True)
        (target / 'personal').write_text('preserve')
        result = self.run_prepare()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(target.iterdir()), [target / 'personal'])
        self.assertEqual((target / 'personal').read_text(), 'preserve')

    def test_nonempty_custom_paths_and_optout_do_not_prepare_default(self):
        custom = '/home/owner/my tool:/home/owner/another tool'
        result = self.run_environment(STEAM_EXTRA_COMPAT_TOOLS_PATHS=custom)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, custom)
        result = self.run_environment(AURORA_STEAM_PROTON='0')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'absent')
        self.assertFalse((self.home / 'data').exists())

    def test_empty_custom_paths_prepare_the_default(self):
        result = self.run_environment(STEAM_EXTRA_COMPAT_TOOLS_PATHS='')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(result.stdout).name, self.source.name)
        self.assertTrue(Path(result.stdout).is_dir())

    def test_simultaneous_steam_and_play_preparation_is_safe(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self.run_prepare(), range(2)))
        for result in results:
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(results[0].stdout, results[1].stdout)
        self.assertEqual(list((self.home / 'data/aurora-proton').glob('.install.*')), [])
