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
    def plan(self, changed_sources, shared_tooling=False, split=False, event_name="push"):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'scripts').mkdir()
            shutil.copyfile(ROOT / 'scripts/ci-plan.py', root / 'scripts/ci-plan.py')
            for name in ['avd-fw', 'kernel-aurora', 'mesa-aurora', 'upower-aurora']:
                recipe = root / 'packages' / name / (name + '.spec')
                recipe.parent.mkdir(parents=True)
                recipe.write_text('Name: ' + name + '\n')
            x86 = root / 'packages/mesa-aurora-fex-guest/mesa-aurora-fex-guest.spec'
            x86.parent.mkdir(parents=True)
            x86.write_text('# aurora-builder: x86_64\nName: mesa-aurora-fex-guest\n')
            sources = {'kernel-aurora': {'commit': 'old'}, 'mesa-aurora': {'commit': 'old'},
                       'mesa-aurora-fex-guest': {'commit': 'old'}}
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
                name = shared_tooling if isinstance(shared_tooling, str) else 'build-rpm'
                path = root / (name if '/' in name else 'scripts/' + name)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('changed shared builder\n')
            git('add', '.')
            git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'update')
            event = root / 'event.json'
            event.write_text(json.dumps({'before': before, 'pull_request': {'base': {'sha': before}}}))
            env = {**os.environ, 'GITHUB_EVENT_PATH': str(event), 'GITHUB_EVENT_NAME': event_name,
                   'GITHUB_SHA': git('rev-parse', 'HEAD')}
            output = subprocess.check_output(['python3', str(root / 'scripts/ci-plan.py')], env=env, text=True)
            plan = dict(line.split('=', 1) for line in output.splitlines())
            plan = {key: json.loads(value) for key, value in plan.items()}
            return plan if split else plan['packages'] + plan['x86_packages']

    def test_new_firmware_and_power_pins_leave_kernel_and_mesa_unbuilt(self):
        self.assertEqual(self.plan({'avd-fw': {'commit': 'new'}, 'upower-aurora': {'commit': 'new'}}),
                         ['avd-fw', 'upower-aurora'])

    def test_existing_source_pin_rebuilds_only_its_package(self):
        self.assertEqual(self.plan({'kernel-aurora': {'commit': 'new'}}), ['kernel-aurora'])

    def test_shared_builder_still_invalidates_every_package(self):
        self.assertEqual(self.plan({'avd-fw': {'commit': 'new'}}, shared_tooling=True),
                         ['avd-fw', 'kernel-aurora', 'mesa-aurora', 'upower-aurora', 'mesa-aurora-fex-guest'])

    def test_x86_payload_recipes_are_planned_for_the_x86_builder_only(self):
        self.assertEqual(self.plan({'mesa-aurora': {'commit': 'new'}, 'mesa-aurora-fex-guest': {'commit': 'new'}},
                                   split=True),
                         {'packages': ['mesa-aurora'], 'x86_packages': ['mesa-aurora-fex-guest']})

    def test_flatpak_repository_builder_invalidates_native_build_receipts(self):
        self.assertEqual(self.plan({'avd-fw': {'commit': 'new'}}, shared_tooling='build-flatpak-gl-repo'),
                         ['avd-fw', 'kernel-aurora', 'mesa-aurora', 'upower-aurora', 'mesa-aurora-fex-guest'])

    def test_pr_source_change_builds_affected_recipes_without_unrelated_kernel(self):
        self.assertEqual(self.plan({'mesa-aurora': {'commit': 'new'}}, event_name='pull_request'),
                         ['mesa-aurora'])

    def test_pr_shared_builder_change_still_invalidates_all_recipes(self):
        self.assertEqual(self.plan({'avd-fw': {'commit': 'new'}}, shared_tooling=True,
                                   event_name='pull_request'),
                         ['avd-fw', 'kernel-aurora', 'mesa-aurora', 'upower-aurora', 'mesa-aurora-fex-guest'])

    def test_pr_workflow_change_invalidates_every_build(self):
        self.assertEqual(self.plan({}, shared_tooling='.github/workflows/rpms.yml',
                                   event_name='pull_request'),
                         ['avd-fw', 'kernel-aurora', 'mesa-aurora', 'upower-aurora', 'mesa-aurora-fex-guest'])

    def test_pr_receipt_builder_change_invalidates_every_build(self):
        self.assertEqual(self.plan({}, shared_tooling='build-receipt.py',
                                   event_name='pull_request'),
                         ['avd-fw', 'kernel-aurora', 'mesa-aurora', 'upower-aurora', 'mesa-aurora-fex-guest'])
