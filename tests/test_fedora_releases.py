"""Release isolation and frozen Fedora 44 publication output contracts."""
import contextlib
import datetime
import hashlib
import importlib.util
import io
import json
import os
import re
import tarfile
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import fedoralib
import updatelib


def module(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT / f'scripts/{name}.py')
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def plan_fixture(resolver, fedora=44):
    names = ['aurora-repos', 'mesa-aurora']
    artifacts = {fedoralib.artifact(n, f): {'id': i, 'digest': 'sha256:fixture', 'size_in_bytes': 10}
                 for f in (44, 45) for i, n in enumerate(names, start=f)}
    with patch.object(resolver, 'packages', return_value=names), \
         patch.object(resolver, 'eligible_packages', return_value=set(names)), \
         patch.object(resolver.lib, 'git', return_value='1' * 40):
        args = {} if fedora == 44 else {'fedora': fedora}
        plan = resolver.resolve(ROOT, 'aurora-silicon/fedora-aurora', [{'id': 123, 'head_sha': '2' * 40}],
                                lambda run: artifacts, set(), fedoralib.prefix(fedora) + '20261101.1', **args)
    return json.dumps(plan, indent=2) + '\n'


def manifest_fixture(signer, fedora=44):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        rpms = root / 'rpms'
        rpms.mkdir()
        (rpms / f'fixture-1-1.fc{fedora}.noarch.rpm').write_bytes(b'fixture RPM bytes')
        fingerprint = (ROOT / 'keys/fingerprint.txt').read_text().strip()

        def check_output(command, **kwargs):
            if command[0] == 'rpm':
                return f'1.fc{fedora}'
            return 'fpr:::::::::' + fingerprint + ':\n'

        def run(*command, **kwargs):
            if command[0] == 'createrepo_c':
                data = root / f'site/{fedora}/testing/aarch64/repodata'
                data.mkdir()
                (data / 'repomd.xml').write_text('metadata fixture')

        argv = ['sign-repository.py', '--rpms', str(rpms), '--output', str(root / 'site'),
                '--asset-base', 'https://example.invalid/releases/testing-fixture.1']
        if fedora != 44:
            argv += ['--fedora-release', str(fedora)]
        with patch.object(sys, 'argv', argv), patch.object(signer, 'run', side_effect=run), \
             patch.object(signer.subprocess, 'check_output', side_effect=check_output), \
             patch.dict(os.environ, FEDORA_RPM_SIGNING_KEY='fixture', FEDORA_RPM_SIGNING_PASSPHRASE='fixture'), \
             contextlib.redirect_stdout(io.StringIO()):
            signer.main()
        return (root / f'site/{fedora}/testing/aarch64/manifest.json').read_text()


def pages_fixture(site):
    class FixedDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 2, tzinfo=datetime.timezone.utc)

    state = updatelib.empty_channels('aurora-silicon/fedora-aurora')
    for channel in ('testing', 'stable'):
        state = updatelib.record_channel(state, channel, {'tag': 'testing-old.1'})
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        args = SimpleNamespace(repository=state['repository'], fedora_release=44, channel='testing',
                               tag='testing-new.1', min_soak_hours=0, site=str(root / 'site'),
                               work=str(root / 'work'), state_out=str(root / 'state.json'),
                               site_url='https://example.invalid', allow_downgrade=False)

        def fetch(repository, tag, channel, destination, work, home, fingerprint, release=44):
            target = destination / f'{release}/{channel}/aarch64'
            target.mkdir(parents=True)
            (target / 'repomd.fixture').write_text(tag)
            return 'verified'

        output = io.StringIO()
        with patch.object(site.lib, 'load_channels', return_value=state), \
             patch.object(site, 'keyring', return_value=(root, 'fingerprint')), \
             patch.object(site, 'fetch_snapshot', side_effect=fetch), \
             patch.object(site, 'live_repository', return_value=None), \
             patch.object(site.lib, 'gh_api', return_value={'target_commitish': 'main', 'created_at': 'fixture'}), \
             patch.object(site.datetime, 'datetime', FixedDateTime), \
             patch.dict(os.environ, GITHUB_RUN_ID='123', GITHUB_ACTOR='fixture'), \
             contextlib.redirect_stdout(output):
            site.assemble(args)
        return {**{name: (root / 'site' / name).read_text() for name in ('index.html', 'channels.json')},
                'state.json': (root / 'state.json').read_text(), 'summary': output.getvalue()}


class ReleaseTests(unittest.TestCase):
    def test_fedora44_plan_and_manifest_are_byte_identical_to_pre_change_main(self):
        fixture = json.loads((ROOT / 'tests/fixtures/fedora44-publish.json').read_text())
        self.assertEqual(plan_fixture(module('resolve-build-runs')), fixture['plan'])
        self.assertEqual(manifest_fixture(module('sign-repository')), fixture['manifest'])
        self.assertEqual(pages_fixture(module('channel-site')), fixture['pages'])

    def test_fedora45_plan_selects_only_namespaced_artifacts_and_manifest(self):
        plan = json.loads(plan_fixture(module('resolve-build-runs'), 45))
        self.assertEqual(plan['fedora'], 45)
        self.assertEqual(plan['packages']['aurora-repos']['artifact'], 45)
        manifest = json.loads(manifest_fixture(module('sign-repository'), 45))
        self.assertEqual(manifest['fedora'], 45)
        self.assertTrue(all('.fc45.' in p['filename'] for p in manifest['packages']))

    def test_snapshot_tags_and_sequences_cannot_cross_releases(self):
        for fedora, wrong in [(44, 'testing-f45-20261102.1'), (45, 'testing-20261102.1')]:
            with self.subTest(fedora=fedora), self.assertRaises(ValueError):
                fedoralib.snapshot(wrong, fedora)
        tags = ['testing-20261102.7', 'testing-f45-20261102.99']
        self.assertEqual(updatelib.next_snapshot_tag(tags, fedoralib.prefix(44), '20261102'), 'testing-20261102.8')
        self.assertEqual(updatelib.next_snapshot_tag(tags, fedoralib.prefix(45), '20261102'), 'testing-f45-20261102.100')

    def test_fedora45_uses_existing_graphics_and_mutter_sources_without_changing_44(self):
        old, new = fedoralib.sources(ROOT, 44), fedoralib.sources(ROOT, 45)
        self.assertEqual(old, json.loads((ROOT / 'sources.json').read_text()))
        self.assertEqual(new['mesa-aurora']['commit'], '9fe179df8bf1cec359d9e452fc9dfa8680285698')
        self.assertEqual(new['mesa-aurora'], new['mesa-aurora-fex-guest'])
        self.assertEqual(new['mutter']['version'], '51.1')
        for name in fedoralib.package_names(ROOT):
            spec = fedoralib.recipe_files(ROOT, name, 45)[name + '.spec']
            fetched = {record.get('archive_file', f"{key}-{record['commit']}.tar.gz")
                       for key, record in new.get(name, {}).get('extra_sources', {}).items()}
            for filename in re.findall(r'^(?:Patch\d*|Source\d*):\s+([^%\s]+)$', spec.read_text(), re.M):
                if not filename.startswith(('http:', 'https:')) and filename not in fetched:
                    self.assertIn(filename, fedoralib.recipe_files(ROOT, name, 45), (name, filename))

    def test_release_identity_stays_fedora45(self):
        files = fedoralib.recipe_files(ROOT, 'aurora-release', 45)
        self.assertIn('VERSION_ID=45\n', files['os-release'].read_text())
        self.assertIn('Requires: fedora-repos(45)', files['aurora-release.spec'].read_text())
        self.assertIn('%fedora              45\n', files['macros.dist'].read_text())

    def test_f45_uboot_uses_the_engine_capable_compatibility_development_packages(self):
        old = fedoralib.recipe_files(ROOT, 'uboot-aurora', 44)['uboot-aurora.spec'].read_text()
        new = fedoralib.recipe_files(ROOT, 'uboot-aurora', 45)['uboot-aurora.spec'].read_text()
        self.assertIn('openssl-devel openssl-devel-engine', old)
        self.assertIn('openssl3-devel openssl3-devel-engine', new)
        self.assertEqual(old.split('%build', 1)[1].split('%changelog', 1)[0],
                         new.split('%build', 1)[1].split('%changelog', 1)[0])

    def test_pages_preserve_all_three_channels_when_either_testing_channel_changes(self):
        site = module('channel-site')
        state = updatelib.empty_channels('aurora-silicon/fedora-aurora')
        for key, tag in [('testing', 'testing-old.1'), ('stable', 'testing-old.1'), ('45/testing', 'testing-f45-old.1')]:
            state = updatelib.record_channel(state, key, {'tag': tag})
        for fedora in (44, 45):
            with self.subTest(fedora=fedora), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                args = SimpleNamespace(repository=state['repository'], fedora_release=fedora, channel='testing',
                                       tag=fedoralib.prefix(fedora) + 'new.1', min_soak_hours=0,
                                       site=str(root / 'site'), work=str(root / 'work'), state_out=str(root / 'state'),
                                       site_url='https://example.invalid', allow_downgrade=False)

                def fetch(repository, tag, channel, destination, work, home, fingerprint, release=44):
                    target = destination / f'{release}/{channel}/aarch64'
                    target.mkdir(parents=True)
                    (target / 'repomd.fixture').write_text(tag)
                    return 'verified'

                with patch.object(site.lib, 'load_channels', return_value=state), \
                     patch.object(site, 'keyring', return_value=(root, 'fingerprint')), \
                     patch.object(site, 'fetch_snapshot', side_effect=fetch), \
                     patch.object(site, 'live_repository', return_value=None), \
                     patch.object(site.lib, 'gh_api', return_value={'target_commitish': 'main', 'created_at': 'fixture'}), \
                     contextlib.redirect_stdout(io.StringIO()):
                    site.assemble(args)
                for key, (release, channel) in site.SLOTS.items():
                    tag = args.tag if key == site.channel_key('testing', fedora) else state['channels'][key]['tag']
                    self.assertEqual((root / f'site/{release}/{channel}/aarch64/repomd.fixture').read_text(), tag)
                self.assertFalse((root / 'site/45/stable').exists())
                result = json.loads((root / 'state').read_text())
                self.assertEqual(result['channels']['stable'], state['channels']['stable'])
        with self.assertRaises(ValueError):
            site.channel_key('stable', 45)

    def test_f45_history_does_not_evict_the_f44_promotion_history(self):
        state = updatelib.empty_channels('aurora-silicon/fedora-aurora')
        old = {'tag': 'testing-old.1', 'deployed_at': '2026-10-01T00:00:00Z'}
        state = updatelib.record_channel(state, 'testing', old, keep=1)
        for tag in ('testing-f45-first.1', 'testing-f45-second.1'):
            state = updatelib.record_channel(state, '45/testing', {'tag': tag}, keep=1)
        self.assertEqual(updatelib.served_on(state, 'testing', 'tag', old['tag']), [{'channel': 'testing', **old}])
        self.assertEqual(len(state['history']), 2)

    def test_f45_metadata_archive_is_isolated_from_44(self):
        signer = module('sign-repository')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / '45/testing/aarch64'
            data = repo / 'repodata'
            data.mkdir(parents=True)
            (root / 'RPM-GPG-KEY-aurora').write_bytes(b'key')
            (repo / 'manifest.json').write_bytes(b'{}')
            (data / 'primary.xml.gz').write_bytes(b'primary')
            digest = hashlib.sha256(b'primary').hexdigest()
            (data / 'repomd.xml').write_text('<repomd xmlns="http://linux.duke.edu/metadata/repo"><data>'
                f'<checksum type="sha256">{digest}</checksum><size>7</size>'
                '<location href="repodata/primary.xml.gz"/></data></repomd>')
            (data / 'repomd.xml.asc').write_bytes(b'signature')
            archive = signer.archive_metadata(root, 'testing-f45-fixture.1', 45)
            with tarfile.open(archive) as bundle:
                self.assertTrue(all(n == 'RPM-GPG-KEY-aurora' or n.startswith('45/testing/') for n in bundle.getnames()))
            with self.assertRaises(ValueError):
                signer.archive_metadata(root, 'testing-f45-fixture.2')
