"""Reuse requires merged, byte-identical recipes and authenticated CI inventory."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_import', ROOT / 'scripts/import-rpm-build.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class BuildImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init', '-q')
        for name in module.SHARED:
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('build tooling\n')
        self.recipe = self.repo / 'packages/example/example.spec'
        self.recipe.parent.mkdir(parents=True)
        self.recipe.write_text('Name: example\n')
        (self.repo / 'sources.json').write_text(json.dumps({'example': {'commit': 'source-pin'}}))
        self.commit('native build')
        self.metadata = {'head_sha': self.git('rev-parse', 'HEAD'), 'conclusion': 'success',
                         'head_repository': {'full_name': 'aurora-silicon/fedora-aurora'},
                         'event': 'workflow_dispatch', 'path': '.github/workflows/rpms.yml'}
        self.artifacts = self.root / 'artifacts'
        out = self.artifacts / 'rpm-example/out'
        records = []
        for kind, name in [('rpms', 'example-1-1.aarch64.rpm'), ('srpms', 'example-1-1.src.rpm')]:
            path = out / kind / name
            path.parent.mkdir(parents=True)
            path.write_bytes(b'native fixture artifact')
            records.append({'filename': name, 'bytes': path.stat().st_size,
                            'sha256': module.digest(path)})
        receipt = out / 'manifests/example.json'
        receipt.parent.mkdir()
        receipt.write_text(json.dumps({'package': 'example', 'succeeded': True, 'architecture': 'aarch64',
                                      'recipe_inputs': {'example.spec': module.digest(self.recipe)}, 'artifacts': records}))

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True).strip()

    def commit(self, message):
        self.git('add', '.')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', message)

    def run_import(self):
        return module.import_build(self.repo, self.metadata, self.artifacts, self.root / 'output',
                                   'aurora-silicon/fedora-aurora')

    def test_ancestor_build_with_unchanged_recipe_is_reused(self):
        (self.repo / 'README').write_text('unrelated change\n')
        self.commit('merge follow-up')
        self.assertEqual(self.run_import(), 1)
        self.assertEqual(len(list((self.root / 'output').rglob('*.rpm'))), 2)

    def test_changed_recipe_is_not_reused(self):
        self.recipe.write_text('Name: example\nRelease: 2\n')
        self.commit('new recipe')
        with self.assertRaisesRegex(ValueError, 'recipe changed'):
            self.run_import()

    def test_changed_source_pin_is_not_reused(self):
        (self.repo / 'sources.json').write_text(json.dumps({'example': {'commit': 'new-pin'}}))
        self.commit('new source pin')
        with self.assertRaisesRegex(ValueError, 'inputs changed'):
            self.run_import()

    def test_corrupt_native_artifact_is_rejected(self):
        next(self.artifacts.rglob('*.aarch64.rpm')).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            self.run_import()

    def test_unmerged_commit_is_rejected(self):
        (self.repo / 'README').write_text('unmerged\n')
        self.commit('unmerged')
        self.metadata['head_sha'] = self.git('rev-parse', 'HEAD')
        self.git('checkout', '--detach', 'HEAD~1')
        with self.assertRaisesRegex(ValueError, 'not been merged'):
            self.run_import()
