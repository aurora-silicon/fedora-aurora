"""Source-only package updates must not schedule unrelated expensive builds."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PlanTests(unittest.TestCase):
    def plan(self, changed_sources, shared_tooling=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'scripts').mkdir()
            shutil.copyfile(ROOT / 'scripts/ci-plan.py', root / 'scripts/ci-plan.py')
            for name in ['avd-fw', 'kernel-aurora', 'mesa-aurora', 'upower-aurora']:
                recipe = root / 'packages' / name / (name + '.spec')
                recipe.parent.mkdir(parents=True)
                recipe.write_text('Name: ' + name + '\n')
            sources = {'kernel-aurora': {'commit': 'old'}, 'mesa-aurora': {'commit': 'old'}}
            (root / 'sources.json').write_text(json.dumps(sources))
            def git(*args):
                return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()
            git('init', '-q')
            git('add', '.')
            git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'base')
            before = git('rev-parse', 'HEAD')
            sources.update(changed_sources)
            (root / 'sources.json').write_text(json.dumps(sources))
            if shared_tooling:
                (root / 'scripts/build-rpm').write_text('changed shared builder\n')
            git('add', '.')
            git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'update')
            event = root / 'event.json'
            event.write_text(json.dumps({'before': before}))
            env = {**os.environ, 'GITHUB_EVENT_PATH': str(event), 'GITHUB_EVENT_NAME': 'push',
                   'GITHUB_SHA': git('rev-parse', 'HEAD')}
            output = subprocess.check_output(['python3', str(root / 'scripts/ci-plan.py')], env=env, text=True)
            return json.loads(output.removeprefix('packages='))

    def test_new_firmware_and_power_pins_leave_kernel_and_mesa_unbuilt(self):
        self.assertEqual(self.plan({'avd-fw': {'commit': 'new'}, 'upower-aurora': {'commit': 'new'}}),
                         ['avd-fw', 'upower-aurora'])

    def test_existing_source_pin_rebuilds_only_its_package(self):
        self.assertEqual(self.plan({'kernel-aurora': {'commit': 'new'}}), ['kernel-aurora'])

    def test_shared_builder_still_invalidates_every_package(self):
        self.assertEqual(self.plan({'avd-fw': {'commit': 'new'}}, shared_tooling=True),
                         ['avd-fw', 'kernel-aurora', 'mesa-aurora', 'upower-aurora'])
