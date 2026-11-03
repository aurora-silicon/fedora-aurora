import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'packages' / 'aurora-flatpak-gl' / 'aurora-flatpak-gl'
ID = 'org.freedesktop.Platform.GL.aurora'

# A flatpak stand-in that keeps the system installation in files: installed
# refs, remotes and the global override's environment lines.
FAKE_FLATPAK = r'''#!/bin/bash
s=$FAKE_FLATPAK_STATE
touch "$s/installed" "$s/remotes"
cmd=$1; shift
args=()
for a in "$@"; do case $a in -*) ;; *) args+=("$a") ;; esac; done
case $cmd in
  remotes) cat "$s/remotes" ;;
  remote-add) echo "${args[-2]}" >> "$s/remotes" ;;
  remote-modify) ;;
  remote-delete) grep -vxF "${args[0]}" "$s/remotes" > "$s/r.tmp"; mv "$s/r.tmp" "$s/remotes" ;;
  list) cat "$s/installed" ;;
  install) ref=${args[1]#runtime/}; grep -qxF "$ref" "$s/installed" || echo "$ref" >> "$s/installed" ;;
  uninstall) grep -vxF "${args[0]#runtime/}" "$s/installed" > "$s/i.tmp"; mv "$s/i.tmp" "$s/installed" ;;
  pin) ;;
  override)
    grep -qx '\[Environment\]' "$OVERRIDES" 2>/dev/null || echo '[Environment]' >> "$OVERRIDES"
    for a in "$@"; do case $a in --env=*) grep -qxF "${a#--env=}" "$OVERRIDES" || echo "${a#--env=}" >> "$OVERRIDES" ;; esac; done ;;
esac
'''


class FlatpakGlHelperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.state = self.tmp / 'state'
        self.state.mkdir()
        bindir = self.tmp / 'bin'
        bindir.mkdir()
        fake = bindir / 'flatpak'
        fake.write_text(FAKE_FLATPAK)
        fake.chmod(0o755)
        self.repo = self.tmp / 'repo'
        self.overrides = self.tmp / 'global'
        self.env = dict(os.environ, PATH=f'{bindir}:{os.environ["PATH"]}', FAKE_FLATPAK_STATE=str(self.state),
                        OVERRIDES=str(self.overrides), AURORA_FLATPAK_GL_REPO=str(self.repo),
                        AURORA_FLATPAK_GL_OVERRIDES=str(self.overrides))

    def package_repo(self, *branches):
        shutil.rmtree(self.repo, ignore_errors=True)
        (self.repo / 'objects').mkdir(parents=True)
        heads = self.repo / 'refs/heads/runtime' / ID / 'aarch64'
        heads.mkdir(parents=True)
        for branch in branches:
            (heads / branch).write_text('0' * 64 + '\n')

    def run_helper(self, action):
        return subprocess.run(['bash', str(HELPER), action], env=self.env, capture_output=True, text=True)

    def installed(self):
        path = self.state / 'installed'
        return path.read_text().split() if path.exists() else []

    def test_enable_installs_every_packaged_branch(self):
        self.package_repo('25.08', '26.08')
        self.assertEqual(self.run_helper('enable').returncode, 0)
        self.assertEqual(self.installed(), [f'{ID}/aarch64/25.08', f'{ID}/aarch64/26.08'])
        self.assertIn('LIBGL_DRIVERS_PATH=', self.overrides.read_text())

    def test_enable_drops_a_branch_the_repository_no_longer_carries(self):
        self.package_repo('25.08', '26.08')
        self.run_helper('enable')
        self.package_repo('26.08')
        self.assertEqual(self.run_helper('enable').returncode, 0)
        self.assertEqual(self.installed(), [f'{ID}/aarch64/26.08'])

    def test_a_package_without_the_repository_restores_gl_default(self):
        # An upgrade to a build without --with repo removes the older package's
        # repository; its GL.aurora (an older Mesa) must not stay active.
        self.package_repo('25.08')
        self.run_helper('enable')
        self.overrides.write_text(self.overrides.read_text() + 'MY_SETTING=1\n')
        shutil.rmtree(self.repo)
        self.assertEqual(self.run_helper('enable').returncode, 0)
        self.assertEqual(self.installed(), [])
        self.assertNotIn('aurora-gl', (self.state / 'remotes').read_text().split())
        self.assertEqual(self.overrides.read_text(), '[Environment]\nMY_SETTING=1\n')


if __name__ == '__main__':
    unittest.main()
