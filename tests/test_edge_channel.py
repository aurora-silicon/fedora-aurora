"""The Edge package feed, Edge snapshots and Edge images (aurora-distributions docs/edge-train.md)."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import edgelib  # noqa: E402
import fedoralib  # noqa: E402


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


signing = module('edge_repository_signing', 'scripts/sign-repository.py')
site = module('edge_channel_site', 'scripts/channel-site.py')
snapshot = module('edge_snapshot', 'scripts/edge-snapshot.py')
proof = module('edge_image_proof', 'scripts/edge-image-proof.py')
configure = module('edge_configure', 'images/configure.py')

LINUX = {'repository': 'aurora-silicon/linux', 'branch': 'aurora-edge', 'revision': '1' * 40, 'tree': '2' * 40}
MESA = {'repository': 'aurora-silicon/mesa', 'branch': 'aurora-edge', 'revision': '3' * 40, 'tree': '4' * 40}


class SnapshotTagTests(unittest.TestCase):
    def test_edge_tags_are_their_own_namespace(self):
        self.assertEqual(edgelib.snapshot('edge-20261121.1', 44), 'edge-20261121.1')
        self.assertNotIn('scripts/edgelib.py', fedoralib.SHARED)
        for tag, fedora in (('testing-20261121.1', 44), ('edge-20261121.1', 45), ('edge-latest', 44),
                            ('edge-20261121.1/../x', 44)):
            with self.subTest(tag=tag, fedora=fedora):
                with self.assertRaises(ValueError):
                    edgelib.snapshot(tag, fedora)
        with self.assertRaises(ValueError):
            fedoralib.snapshot('edge-20261121.1', 44)

    def test_edge_metadata_archive_lives_at_the_edge_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / '44/edge/aarch64'
            data = repo / 'repodata'
            data.mkdir(parents=True)
            (root / 'RPM-GPG-KEY-aurora').write_bytes(b'key')
            (repo / 'manifest.json').write_bytes(b'{"channel": "edge"}\n')
            content = b'primary'
            (data / 'primary.xml.gz').write_bytes(content)
            (data / 'repomd.xml').write_text(
                '<repomd xmlns="http://linux.duke.edu/metadata/repo"><data type="primary">'
                f'<checksum type="sha256">{hashlib.sha256(content).hexdigest()}</checksum>'
                f'<location href="repodata/primary.xml.gz"/><size>{len(content)}</size></data></repomd>')
            (data / 'repomd.xml.asc').write_bytes(b'signature')
            archive = signing.archive_metadata(root, 'edge-20261121.1', 44, channel='edge')
            import tarfile
            with tarfile.open(archive) as bundle:
                names = bundle.getnames()
            self.assertIn('44/edge/aarch64/repodata/repomd.xml', names)
            self.assertFalse(any(name.startswith('44/testing/') for name in names))


class ChannelSiteTests(unittest.TestCase):
    def record(self, tag='edge-20261121.1', pair=None):
        return {'schema_version': 1, 'release': 'alpha.4', 'pair': pair or {'linux': LINUX, 'mesa': MESA},
                'distributions': {'fedora': {'repository': 'aurora-silicon/fedora-aurora', 'snapshot': tag}}}

    def test_edge_is_a_fedora_44_slot(self):
        self.assertIn('edge', site.CHANNELS)
        self.assertEqual(site.SLOTS['edge'], (44, 'edge'))
        self.assertEqual(site.channel_key('edge', 44), 'edge')
        with self.assertRaises(ValueError):
            site.channel_key('edge', 45)

    def sources(self, mesa=None, signing_run=44700000001, rpms=('kernel-aurora-core-7.3.0-43.rpm',)):
        return {'schema': 1, 'channel': 'edge', 'signing_run': signing_run, 'edge_rpms': list(rpms),
                'packaged_sources': {'linux': LINUX, 'mesa': mesa or MESA}}

    def test_the_adopted_train_snapshot_moves_the_edge_feed(self):
        self.assertEqual(site.edge_gate(self.record(), 'edge-20261121.1', self.sources()), 'train')
        with self.assertRaisesRegex(ValueError, 'pair'):
            site.edge_gate(self.record(), 'edge-20261121.1', self.sources(mesa=dict(MESA, revision='5' * 40)))
        with self.assertRaisesRegex(ValueError, 'no adopted Edge train'):
            site.edge_gate(None, 'edge-20261121.1', self.sources())

    def test_a_refresh_keeps_the_exact_qualified_kernel_and_mesa_rpms(self):
        adopted = self.sources()
        self.assertEqual(site.edge_gate(self.record(), 'edge-20261128.1', self.sources(), adopted), 'refresh')
        for changed in (self.sources(signing_run=44800000000), self.sources(rpms=('kernel-aurora-core-7.3.0-44.rpm',)),
                        self.sources(mesa=dict(MESA, revision='5' * 40))):
            with self.subTest(changed=changed):
                with self.assertRaisesRegex(ValueError, 'adopted Edge train'):
                    site.edge_gate(self.record(), 'edge-20261128.1', changed, adopted)
        with self.assertRaisesRegex(ValueError, 'adopted Edge train'):
            site.edge_gate(self.record(), 'edge-20261128.1', self.sources(), None)

    def test_snapshot_metadata_path_follows_the_publication_lane(self):
        self.assertEqual(site.lane('edge'), 'edge')
        self.assertEqual(site.lane('stable'), 'testing')
        self.assertEqual(site.lane('testing'), 'testing')
        self.assertTrue(site.publisher('edge').endswith('/publish-edge.yml'))
        self.assertTrue(site.publisher('stable').endswith('/publish.yml'))


class EdgeSnapshotTests(unittest.TestCase):
    base = [('kernel-aurora-core.aarch64', 'kernel-aurora-core-7.3.0-41.fc44.aurora.aarch64.rpm'),
            ('mesa-aurora-vulkan-drivers.aarch64', 'mesa-aurora-vulkan-drivers-26.3.0-30.fc44.aurora.aarch64.rpm'),
            ('aura.aarch64', 'aura-1.0.0.b13.1-2.fc44.aarch64.rpm'),
            ('aurora-platform-core.noarch', 'aurora-platform-core-44-46.fc44.noarch.rpm')]
    edge = [('kernel-aurora-core.aarch64', 'kernel-aurora-core-7.3.0-43.fc44.aurora.aarch64.rpm'),
            ('kernel-aurora-modules-extra.aarch64', 'kernel-aurora-modules-extra-7.3.0-43.fc44.aurora.aarch64.rpm'),
            ('mesa-aurora-vulkan-drivers.aarch64', 'mesa-aurora-vulkan-drivers-26.3.0-35.fc44.aurora.aarch64.rpm'),
            ('aurora-flatpak-gl.aarch64', 'aurora-flatpak-gl-26.3.0-35.fc44.aurora.aarch64.rpm')]

    def test_edge_packages_replace_their_base_identities(self):
        keep, add = snapshot.plan(self.base, self.edge)
        self.assertEqual(keep, ['aura-1.0.0.b13.1-2.fc44.aarch64.rpm', 'aurora-platform-core-44-46.fc44.noarch.rpm'])
        self.assertEqual(add, sorted(name for _, name in self.edge))

    def test_only_kernel_and_mesa_packages_may_come_from_the_edge_build(self):
        with self.assertRaisesRegex(ValueError, 'not a kernel or Mesa'):
            snapshot.plan(self.base, self.edge + [('aura.aarch64', 'aura-1.0.0.b14-1.fc44.aarch64.rpm')])

    def test_each_package_family_has_one_version(self):
        mixed = self.edge + [('mesa-aurora-dri-drivers.aarch64',
                              'mesa-aurora-dri-drivers-26.3.0-34.fc44.aurora.aarch64.rpm')]
        with self.assertRaisesRegex(ValueError, 'one version'):
            snapshot.plan(self.base, mixed)

    def test_packaged_sources_are_the_aurora_edge_pair(self):
        sources = {'kernel-aurora': {'commit': LINUX['revision']}, 'mesa-aurora': {'commit': MESA['revision']},
                   'mesa-aurora-fex-guest': {'commit': MESA['revision']}}
        trees = {'linux': LINUX['tree'], 'mesa': MESA['tree']}
        self.assertEqual(snapshot.packaged_sources(sources, trees), {'linux': LINUX, 'mesa': MESA})
        sources['mesa-aurora-fex-guest']['commit'] = '6' * 40
        with self.assertRaisesRegex(ValueError, 'one Mesa'):
            snapshot.packaged_sources(sources, trees)


class ImageProofTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'root'
        krel = '7.3.0-43.fc44.aurora.aarch64'
        (self.root / f'usr/lib/modules/{krel}').mkdir(parents=True)
        (self.root / f'usr/lib/modules/{krel}/vmlinuz').write_bytes(b'kernel image')
        (self.root / 'usr/lib64').mkdir(parents=True)
        (self.root / 'usr/lib64/libvulkan_asahi.so').write_bytes(b'mesa dso')
        (self.root / 'etc/yum.repos.d').mkdir(parents=True)
        (self.root / 'etc/yum.repos.d/aurora.repo').write_text(
            '[aurora]\nbaseurl=https://aurorasilicon.org/fedora-aurora/$releasever/edge/aarch64\nenabled=1\n')
        self.sources = {'linux': LINUX, 'mesa': MESA}

    def test_proof_records_the_edge_build_the_image_carries(self):
        result = proof.proof(self.root, 'fedora-gnome', 'edge-20261121.1', self.sources)
        self.assertEqual(result['schema'], 2)
        self.assertEqual(result['channel'], 'edge')
        self.assertEqual(result['feed'], 'https://aurorasilicon.org/fedora-aurora/44/edge/aarch64')
        self.assertEqual(result['packaged_sources'], self.sources)
        self.assertEqual(result['files']['kernelImageSHA256'], 'sha256:' + hashlib.sha256(b'kernel image').hexdigest())
        self.assertEqual(result['files']['mesaDsoSHA256'], 'sha256:' + hashlib.sha256(b'mesa dso').hexdigest())

    def test_an_image_that_follows_another_feed_has_no_proof(self):
        for text in ('[aurora]\nbaseurl=https://aurorasilicon.org/fedora-aurora/$releasever/testing/aarch64\nenabled=1\n',
                     '[aurora]\nbaseurl=https://aurorasilicon.org/fedora-aurora/$releasever/edge/aarch64\nenabled=0\n'):
            with self.subTest(text=text):
                (self.root / 'etc/yum.repos.d/aurora.repo').write_text(text)
                with self.assertRaisesRegex(ValueError, 'Edge feed'):
                    proof.proof(self.root, 'fedora-gnome', 'edge-20261121.1', self.sources)

    def test_two_kernels_are_refused(self):
        (self.root / 'usr/lib/modules/7.3.0-41.fc44.aurora.aarch64').mkdir()
        (self.root / 'usr/lib/modules/7.3.0-41.fc44.aurora.aarch64/vmlinuz').write_bytes(b'old')
        with self.assertRaisesRegex(ValueError, 'one kernel'):
            proof.proof(self.root, 'fedora-kde', 'edge-20261121.1', self.sources)


class BuildRepositoryTests(unittest.TestCase):
    def test_edge_images_build_from_the_snapshot_and_follow_the_feed(self):
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / '44/edge/aarch64'
            (repository / 'repodata').mkdir(parents=True)
            (repository / 'repodata/repomd.xml').write_text('<repomd/>')
            (repository / 'repodata/repomd.xml.asc').write_text('signature')
            feed = 'https://aurorasilicon.org/fedora-aurora/$releasever/edge/aarch64'
            self.assertEqual(configure.build_source(feed, repository), repository.resolve().as_uri())
            self.assertEqual(configure.build_source(feed, None), feed)
            with self.assertRaisesRegex(ValueError, 'Edge feed'):
                configure.build_source('https://aurorasilicon.org/fedora-aurora/$releasever/testing/aarch64', repository)
            (repository / 'repodata/repomd.xml.asc').unlink()
            with self.assertRaisesRegex(ValueError, 'signed'):
                configure.build_source(feed, repository)


class WorkflowTests(unittest.TestCase):
    def test_edge_snapshots_are_signed_only_on_main_in_the_signing_environment(self):
        text = (ROOT / '.github/workflows/publish-edge.yml').read_text()
        sign = text.split('\n  sign:\n', 1)[1].split('\n  release:\n', 1)[0]
        self.assertIn('environment: testing-signing', sign)
        self.assertIn("github.ref == 'refs/heads/main'", text)
        self.assertIn('--network none', sign)
        self.assertIn('--channel edge', sign)
        collect = text.split('\n  sign:\n', 1)[0]
        self.assertNotIn('secrets.', collect)

    def test_edge_deploys_read_the_adopted_train(self):
        text = (ROOT / '.github/workflows/deploy-snapshot.yml').read_text()
        self.assertIn('options: [testing, stable, edge]', text)
        self.assertIn('site/installer/edge-train.json', text)
        self.assertIn('--edge-train', text)

    def test_edge_images_attest_their_proof(self):
        text = (ROOT / '.github/workflows/images.yml').read_text()
        self.assertIn('options: [testing, stable, edge]', text)
        self.assertIn('out/*-installer/edge-image-proof.json', text)
        self.assertIn('edge-snapshot', text)


if __name__ == '__main__':
    unittest.main()
