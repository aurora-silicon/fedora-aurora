import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('resolve_build_runs', ROOT / 'scripts/resolve-build-runs.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
REPOSITORY = 'aurora-silicon/fedora-aurora'


class ResolveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for path in module.importer.SHARED:
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('builder\n')
        for name in ('aura', 'kernel-aurora', 'mesa-aurora'):
            recipe = self.root / 'packages' / name / f'{name}.spec'
            recipe.parent.mkdir(parents=True)
            recipe.write_text('Release: 1\n')
        (self.root / 'sources.json').write_text(json.dumps({'aura': {'commit': '1'}}))
        self.git('init', '-q')
        self.first = self.commit()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], text=True).strip()

    def commit(self):
        self.git('add', '.')
        self.git('-c', 'user.name=t', '-c', 'user.email=t@example.org', 'commit', '-qm', 'step')
        return self.git('rev-parse', 'HEAD')

    def run_record(self, run_id, sha, created='2026-10-22T00:00:00Z', **extra):
        return {'id': run_id, 'head_sha': sha, 'conclusion': 'success', 'event': 'push', 'created_at': created,
                'path': '.github/workflows/rpms.yml', 'head_repository': {'full_name': REPOSITORY}, **extra}

    def artifacts(self, mapping):
        return lambda run_id: {f'rpm-{name}': {'id': run_id * 10 + i, 'digest': 'sha256:x', 'size_in_bytes': 1}
                               for i, name in enumerate(mapping.get(run_id, []))}

    def test_newest_build_per_package_and_publish_only_unpublished_runs(self):
        (self.root / 'packages/aura/aura.spec').write_text('Release: 2\n')
        second = self.commit()
        runs = [self.run_record(2, second, '2026-10-22T02:00:00Z'), self.run_record(1, self.first)]
        artifacts = self.artifacts({1: ['aura', 'kernel-aurora', 'mesa-aurora'], 2: ['aura']})
        plan = module.resolve(self.root, REPOSITORY, runs, artifacts, {1}, 'testing-1')
        self.assertEqual(plan['action'], 'publish')
        self.assertEqual(plan['packages']['aura']['run'], 2)
        self.assertEqual(plan['packages']['kernel-aurora']['run'], 1)
        self.assertEqual(plan['runs'], [{'run': 1, 'packages': ['kernel-aurora', 'mesa-aurora']},
                                        {'run': 2, 'packages': ['aura']}])
        published = module.resolve(self.root, REPOSITORY, runs, artifacts, {1, 2}, 'testing-2')
        self.assertEqual(published['action'], 'up-to-date')

    def test_unmerged_failed_or_retooled_builds_do_not_qualify(self):
        self.git('checkout', '-q', '-b', 'side')
        (self.root / 'README').write_text('unmerged\n')
        side = self.commit()
        self.git('checkout', '-q', '-')
        self.assertEqual(module.eligible_packages(self.root, self.run_record(1, side), REPOSITORY), set())
        self.assertEqual(module.eligible_packages(
            self.root, self.run_record(1, self.first, conclusion='failure'), REPOSITORY), set())
        (self.root / module.importer.SHARED[0]).write_text('new builder\n')
        self.commit()
        self.assertEqual(module.eligible_packages(self.root, self.run_record(1, self.first), REPOSITORY), set())

    def test_published_snapshots_are_separate_for_each_fedora_release(self):
        from unittest.mock import patch
        releases = [{'tag_name': tag, 'created_at': stamp, 'draft': False, 'assets': []}
                    for tag, stamp in [('testing-20261102.2', '2026-11-02T01:00:00Z'),
                                       ('testing-f45-20261102.9', '2026-11-02T02:00:00Z')]]
        with patch.object(module.lib, 'gh_api', return_value=releases):
            self.assertEqual(module.published_runs(REPOSITORY), (set(), 'testing-20261102.2'))
            self.assertEqual(module.published_runs(REPOSITORY, fedora=45), (set(), 'testing-f45-20261102.9'))
        with self.assertRaisesRegex(ValueError, 'Fedora 45 snapshot'):
            module.resolve(self.root, REPOSITORY, [], self.artifacts({}), set(), 'testing-f45-20261102.9')
        with self.assertRaisesRegex(ValueError, 'this Fedora release'):
            module.resolve(self.root, REPOSITORY, [], self.artifacts({}), set(), 'testing-20261102.2', fedora=45)

    def test_f45_release_volume_cannot_hide_the_f44_base_snapshot(self):
        from unittest.mock import patch
        new = [{'tag_name': f'testing-f45-20261102.{n}', 'created_at': '2026-11-02T02:00:00Z',
                'draft': False, 'assets': []} for n in range(100)]
        old = {'tag_name': 'testing-20261102.7', 'created_at': '2026-11-02T01:00:00Z',
               'draft': False, 'assets': []}
        def api(endpoint):
            return new if endpoint.endswith('&page=1') else [old]
        with patch.object(module.lib, 'gh_api', side_effect=api) as read:
            self.assertEqual(module.published_runs(REPOSITORY), (set(), old['tag_name']))
            self.assertEqual(read.call_count, 2)

    def test_no_snapshot_and_no_builds_means_every_package_needs_a_build(self):
        plan = module.resolve(self.root, REPOSITORY, [], self.artifacts({}), set(), None)
        self.assertEqual(plan['action'], 'missing')
        self.assertEqual(plan['rebuild'], ['aura', 'kernel-aurora', 'mesa-aurora'])


if __name__ == '__main__':
    unittest.main()
