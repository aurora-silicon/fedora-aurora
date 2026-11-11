"""Firefox: Fedora's recipe with the RDD V4L2 Request patch, rebuilt per update."""
import importlib.util
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'packages' / 'firefox'
_spec = importlib.util.spec_from_file_location('importer', ROOT / 'scripts/import-fedora-firefox.py')
importer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(importer)

FEDORA_SPEC = """\
# Don't create debuginfo rpm packages.
%global create_debuginfo  1
%if !%{release_build}
  %bcond wasi_sdk 0
%else
%ifarch s390x
  %bcond wasi_sdk 0
%else
  %bcond wasi_sdk 1
%endif
%endif
Version:        161.0
Release:        2%{?dist}
Source24:       mozilla-api-key
Patch44:        build-arm-libopus.patch
Patch604:       last.patch

%description
Mozilla Firefox
%prep
%patch -P604 -p1
rm -f .mozconfig
%changelog
* Fri Nov 06 2026 Fedora Packager <p@example.invalid> - 161.0-2
- Update
"""


class FirefoxRecipeTests(unittest.TestCase):
    def test_spec_edit_adds_the_patch_and_an_aurora_release(self):
        text = importer.edit_spec(FEDORA_SPEC, '0' * 40, 'Wed Nov 11 2026')
        self.assertTrue(text.startswith('# aurora-builder: heavy\n'))
        self.assertIn('Release:        2%{?dist}.aurora2\n', text)
        self.assertIn('Patch604:       last.patch\n\n# Aurora: V4L2 stateless decoders in RDD', text)
        self.assertIn('Patch900:       rdd-v4l2-request.patch\n', text)
        self.assertIn('%patch -P900 -p1 -b .rdd-v4l2-request\n\nrm -f .mozconfig\n', text)
        self.assertIn('%global create_debuginfo  0\n', text)
        self.assertIn('%else\n  %bcond wasi_sdk 0\n%endif\n%endif', text)
        self.assertIn('%changelog\n* Wed Nov 11 2026 Aurora Silicon <hey@djdev.me> - 161.0-2.aurora2\n'
                      "- Rebuild of Fedora's firefox-161.0-2.\n", text)
        self.assertIn('* Fri Nov 06 2026 Fedora Packager', text)

    def test_spec_edit_refuses_a_recipe_it_does_not_recognise(self):
        for old, new in [('rm -f .mozconfig\n', ''), ('  %bcond wasi_sdk 1\n', ''),
                         ('Release:        2%{?dist}', 'Release:        2')]:
            with self.subTest(removed=old), self.assertRaises(SystemExit):
                importer.edit_spec(FEDORA_SPEC.replace(old, new), '0' * 40, 'Wed Nov 11 2026')

    def test_imported_recipe_carries_the_patch_and_is_marked_heavy(self):
        spec = (PACKAGE / 'firefox.spec').read_text()
        self.assertTrue(spec.startswith('# aurora-builder: heavy\n'))
        self.assertRegex(spec, r'(?m)^Release:\s+\d+%\{\?dist\}\.aurora\d+$')
        self.assertRegex(spec, r'(?m)^Patch900:\s+rdd-v4l2-request\.patch$')
        self.assertRegex(spec, r'(?m)^%patch -P900 -p1 ')
        self.assertTrue((PACKAGE / 'rdd-v4l2-request.patch').is_file())

    def test_fedora_keys_are_fetched_not_committed(self):
        for directory in (PACKAGE, PACKAGE / 'f45'):
            pin = json.loads((directory / 'distgit.json').read_text())
            with self.subTest(directory=directory.name):
                self.assertRegex(pin['commit'], r'^[0-9a-f]{40}$')
                self.assertEqual(sorted(pin['fetch']), sorted(importer.FETCHED))
        for name in importer.FETCHED:
            self.assertFalse((PACKAGE / name).exists(), name)
            self.assertFalse((PACKAGE / 'f45' / name).exists(), name)

    def test_helper_scripts_keep_their_executable_bit(self):
        # The spec copies node-stdout-nonblocking-wrapper into the build and runs it.
        import os
        self.assertTrue(os.access(PACKAGE / 'node-stdout-nonblocking-wrapper', os.X_OK))
        self.assertFalse(os.access(PACKAGE / 'firefox.spec', os.X_OK))

    def test_lookaside_list_is_fedora_format(self):
        for line in (PACKAGE / 'sources').read_text().splitlines():
            self.assertRegex(line, r'^SHA512 \([A-Za-z0-9._+-]+\) = [0-9a-f]{128}$')

    def test_seccomp_admits_exactly_four_media_ioctls(self):
        patch = (PACKAGE / 'rdd-v4l2-request.patch').read_text()
        added = ''.join(line[1:] for line in patch.splitlines(True)
                        if line.startswith('+') and not line.startswith('+++'))
        rule = re.search(r'\.ElseIf\(AnyOf\((.*?)\),\s*Allow\(\)\)', added, re.S)
        self.assertEqual(re.findall(r'request == (\w+)', rule[1]),
                         ['MEDIA_IOC_G_TOPOLOGY', 'MEDIA_IOC_REQUEST_ALLOC',
                          'MEDIA_REQUEST_IOC_QUEUE', 'MEDIA_REQUEST_IOC_REINIT'])
        self.assertNotIn("'|'", added)

    def test_rdd_allows_sysinfo_for_mesa(self):
        patch = (PACKAGE / 'rdd-v4l2-request.patch').read_text()
        self.assertEqual(patch.count('\nFrom '), 1)
        self.assertIn('+      case __NR_sysinfo:\n+        return Allow();\n', patch)

    def test_broker_admits_media_nodes_only_through_an_allowed_video_node(self):
        patch = (PACKAGE / 'rdd-v4l2-request.patch').read_text()
        self.assertIn('aM2mDevices.Contains(', patch)
        self.assertIn('policy->AddPath(rdwr, path.get());', patch)
        self.assertNotRegex(patch, r'Add(?:Tree|Prefix|FilePrefix|Dir)\([^\n]*(?:media|/sys/dev)')

    def test_tracker_follows_both_fedora_branches(self):
        workflow = (ROOT / '.github/workflows/track-firefox.yml').read_text()
        self.assertIn('scripts/import-fedora-firefox.py', workflow)
        self.assertIn('-f packages=firefox', workflow)
        self.assertIn('git merge -q --no-ff', workflow)
        self.assertEqual(importer.RELEASES, {44: 'f44', 45: 'f45'})


if __name__ == '__main__':
    unittest.main()
