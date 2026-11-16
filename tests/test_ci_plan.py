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
    def plan(self, changed_sources, shared_tooling=False, split=False, event_name="push", requires=None,
             requested='', heavy_change=False, cancelled_sources=None, last_build='base', called=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'scripts').mkdir()
            shutil.copyfile(ROOT / 'scripts/ci-plan.py', root / 'scripts/ci-plan.py')
            shutil.copyfile(ROOT / 'scripts/gh-retry', root / 'scripts/gh-retry')
            (root / 'scripts/gh-retry').chmod(0o755)
            for name in ['avd-fw', 'kernel-aurora', 'mesa-aurora', 'upower-aurora']:
                recipe = root / 'packages' / name / (name + '.spec')
                recipe.parent.mkdir(parents=True)
                recipe.write_text('Name: ' + name + '\n')
                if name == 'kernel-aurora':
                    recipe.write_text(recipe.read_text() + '%package devel\nSummary: headers\n')
                for user, needed in (requires or {}).items():
                    if user == name:
                        recipe.write_text(recipe.read_text() + 'BuildRequires: ' + needed + '\n')
            x86 = root / 'packages/mesa-aurora-fex-guest/mesa-aurora-fex-guest.spec'
            x86.parent.mkdir(parents=True)
            x86.write_text('# aurora-builder: x86_64\nName: mesa-aurora-fex-guest\n')
            heavy = root / 'packages/firefox/firefox.spec'
            heavy.parent.mkdir(parents=True)
            heavy.write_text('# aurora-builder: heavy\nName: firefox\n')
            sources = {'kernel-aurora': {'commit': 'old'}, 'mesa-aurora': {'commit': 'old'},
                       'mesa-aurora-fex-guest': {'commit': 'old'}}
            (root / 'sources.json').write_text(json.dumps(sources))
            def git(*args):
                return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()
            git('init', '-q')
            git('add', '.')
            git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'base')
            base = before = git('rev-parse', 'HEAD')
            if cancelled_sources:
                # A push whose own build was cancelled while it waited.
                sources.update(cancelled_sources)
                (root / 'sources.json').write_text(json.dumps(sources))
                git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qam', 'cancelled')
                before = git('rev-parse', 'HEAD')
            sources.update(changed_sources)
            (root / 'sources.json').write_text(json.dumps(sources))
            if heavy_change:
                heavy.write_text(heavy.read_text() + 'Release: 2\n')
            if shared_tooling:
                name = shared_tooling if isinstance(shared_tooling, str) else 'build-rpm'
                path = root / (name if '/' in name else 'scripts/' + name)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('changed shared builder\n')
            git('add', '.')
            git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'update')
            event = root / 'event.json'
            event.write_text(json.dumps({'before': before, 'pull_request': {'base': {'sha': before}},
                                         'inputs': {'packages': requested}}))
            # The successful main builds the plan finds, newest first, through a fake gh.
            heads = {'base': [base], 'none': [], 'foreign': ['f' * 40]}[last_build]
            runs = root / 'runs.json'
            runs.write_text(json.dumps({'workflow_runs': [
                {'id': 100 - i, 'head_sha': head, 'created_at': f'2026-11-12T0{9 - i}:00:00Z'}
                for i, head in enumerate(heads)]}))
            marker = root / 'gh-called'
            fake = root / 'fake-gh'
            fake.write_text(f'#!/bin/sh\ntouch {marker}\ncat {runs}\n')
            fake.chmod(0o755)
            env = {**os.environ, 'GITHUB_EVENT_PATH': str(event), 'GITHUB_EVENT_NAME': event_name,
                   'GITHUB_SHA': git('rev-parse', 'HEAD'), 'GITHUB_REPOSITORY': 'aurora-silicon/fedora-aurora',
                   'GH_RETRY_GH': str(fake)}
            output = subprocess.check_output(['python3', str(root / 'scripts/ci-plan.py')], env=env, text=True,
                                             stderr=subprocess.DEVNULL)
            if called is not None:
                called.append(marker.exists())
            plan = dict(line.split('=', 1) for line in output.splitlines())
            plan = {key: json.loads(value) for key, value in plan.items()}
            return plan if split else plan['packages'] + plan['x86_packages'] + plan['heavy_packages']

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
                         {'full': True, 'packages': ['mesa-aurora'], 'x86_packages': ['mesa-aurora-fex-guest'],
                          'heavy_packages': []})

    def test_flatpak_repository_builder_invalidates_native_build_receipts(self):
        self.assertEqual(self.plan({'avd-fw': {'commit': 'new'}}, shared_tooling='build-flatpak-gl-repo'),
                         ['avd-fw', 'kernel-aurora', 'mesa-aurora', 'upower-aurora', 'mesa-aurora-fex-guest'])

    def test_release_selection_helper_invalidates_every_build(self):
        self.assertEqual(self.plan({}, shared_tooling='fedoralib.py'),
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

    def test_pr_subset_is_not_a_full_run(self):
        self.assertFalse(self.plan({'mesa-aurora': {'commit': 'new'}}, split=True,
                                   event_name='pull_request')['full'])

    def test_push_is_a_full_run(self):
        self.assertTrue(self.plan({'mesa-aurora': {'commit': 'new'}}, split=True)['full'])

    def test_pr_change_rebuilds_recipes_that_build_require_it(self):
        self.assertEqual(self.plan({'kernel-aurora': {'commit': 'new'}}, event_name='pull_request',
                                   requires={'avd-fw': 'kernel-aurora-devel'}),
                         ['avd-fw', 'kernel-aurora'])

    def test_heavy_recipe_change_is_not_built_by_a_push_or_pull_request(self):
        for event in ('push', 'pull_request'):
            with self.subTest(event=event):
                self.assertEqual(self.plan({}, heavy_change=True, event_name=event), [])

    def test_shared_builder_change_leaves_the_heavy_recipe_out_of_the_full_set(self):
        plan = self.plan({}, shared_tooling=True, split=True)
        self.assertTrue(plan['full'])
        self.assertEqual(plan['heavy_packages'], [])

    def test_manual_run_builds_a_named_heavy_recipe_alone(self):
        plan = self.plan({}, split=True, event_name='workflow_dispatch', requested='firefox', heavy_change=True)
        self.assertEqual(plan, {'full': False, 'packages': [], 'x86_packages': [], 'heavy_packages': ['firefox']})

    def test_shared_lookaside_fetcher_invalidates_every_build(self):
        self.assertEqual(self.plan({}, shared_tooling='fetch-fedora-lookaside.py'),
                         ['avd-fw', 'kernel-aurora', 'mesa-aurora', 'upower-aurora', 'mesa-aurora-fex-guest'])

    def test_push_builds_what_a_cancelled_push_changed_too(self):
        self.assertEqual(self.plan({'mesa-aurora': {'commit': 'new'}},
                                   cancelled_sources={'kernel-aurora': {'commit': 'new'}}),
                         ['kernel-aurora', 'mesa-aurora'])

    def test_push_after_a_last_build_outside_its_history_builds_everything(self):
        self.assertEqual(self.plan({'mesa-aurora': {'commit': 'new'}}, last_build='foreign'),
                         ['avd-fw', 'kernel-aurora', 'mesa-aurora', 'upower-aurora', 'mesa-aurora-fex-guest'])

    def test_push_without_a_successful_main_build_builds_everything(self):
        self.assertEqual(self.plan({'mesa-aurora': {'commit': 'new'}}, last_build='none'),
                         ['avd-fw', 'kernel-aurora', 'mesa-aurora', 'upower-aurora', 'mesa-aurora-fex-guest'])

    def test_pull_request_plans_from_its_base_without_the_build_history(self):
        called = []
        self.assertEqual(self.plan({'mesa-aurora': {'commit': 'new'}}, event_name='pull_request',
                                   cancelled_sources={'kernel-aurora': {'commit': 'new'}}, last_build='none',
                                   called=called),
                         ['mesa-aurora'])
        self.assertEqual(called, [False])
