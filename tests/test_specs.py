import json
from pathlib import Path
import re
import unittest
ROOT = Path(__file__).resolve().parents[1]
class SpecTests(unittest.TestCase):
    def test_declared_local_sources_and_patches_are_present(self):
        for spec in (ROOT / 'packages').glob('*/*.spec'):
            with self.subTest(spec=spec.name):
                for kind, value in re.findall(r'^(Source\d*|Patch\d*):\s+(\S+)', spec.read_text(), re.M):
                    if '%{' not in value and not value.startswith('http'):
                        self.assertTrue((spec.parent / value).is_file(), value)
    def test_noarch_recipes_do_not_claim_machine_specific_binaries(self):
        for name in ['aurora-audio', 'alsa-ucm-conf-aurora', 'aurora-release', 'aurora-logos', 'speakersafetyd-aurora-profiles']:
            text = (ROOT / 'packages' / name / (name + '.spec')).read_text()
            self.assertIn('BuildArch: noarch', text)
    def test_fex_guest_mesa_moves_in_lockstep_with_the_host_mesa(self):
        def fields(name):
            text = (ROOT / 'packages' / name / (name + '.spec')).read_text()
            commit = re.search(r'^%(?:\{!\?commit:)?%?global commit ([0-9a-f]{40})', text, re.M).group(1)
            version = re.search(r'^Version:\s+(\S+)', text, re.M).group(1)
            release = re.search(r'^Release:\s+(\S+)', text, re.M).group(1)
            macros = dict(re.findall(r'^%\{!\?(\w+):%global \1 (\S+)\}', text, re.M))
            expand = lambda value: re.sub(r'%\{(\w+)\}', lambda m: macros.get(m.group(1), m.group(0)), value)
            return commit, expand(version), expand(release), text
        host, guest = fields('mesa-aurora'), fields('mesa-aurora-fex-guest')
        self.assertEqual(host[:3], guest[:3])
        sources = json.loads((ROOT / 'sources.json').read_text())
        self.assertEqual(sources['mesa-aurora-fex-guest'], sources['mesa-aurora'])
        self.assertEqual(sources['mesa-aurora']['commit'], host[0])
        self.assertIn('BuildArch: noarch', guest[3])
        self.assertIn('# aurora-builder: x86_64', guest[3].splitlines())
        self.assertIn('Requires: mesa-dri-drivers = %{version}-%{release}', guest[3])
        self.assertIn('Requires: mesa-vulkan-drivers = %{version}-%{release}', guest[3])
    def test_spec_commit_matches_its_source_pin(self):
        sources = json.loads((ROOT / 'sources.json').read_text())
        for spec in (ROOT / 'packages').glob('*/*.spec'):
            name = spec.parent.name
            match = re.search(r'^%(?:\{!\?commit:)?%?global commit ([0-9a-f]{40})', spec.read_text(), re.M)
            if name not in sources or not match:
                continue
            with self.subTest(package=name):
                self.assertEqual(sources[name]['commit'], match.group(1))
if __name__ == '__main__': unittest.main()
