"""Publication refuses a set in which a package's Requires cannot be satisfied.

dnf skips such a package on upgrade without an error: a kernel needing an
avd-fw the set does not carry leaves the fleet on the old kernel. The fleet
upgrade test excludes the boot chain, so scripts/check-repository-closure
checks every package of the set being published with dnf5 repoclosure,
excludes switched off. Here dnf5 is a stub; scripts/test-repository-closure
(checks.yml) runs the real one on probe packages for Fedora 44 and 45.
"""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / 'scripts/check-repository-closure'

# dnf5 repoclosure's report for the kernel of fedora-aurora#467 published
# beside the Fedora 45 avd-fw that predates ea8ae7c8.
UNRESOLVED = '''package: kernel-aurora-core-7.3.0-41.fc45.aurora.aarch64 from aurora-candidate
  unresolved deps (1):
    avd-fw >= 0.1-5
Error: Repoclosure ended with unresolved dependencies (1) across 1 packages.
'''

DNF5 = '''printf '%s\\n' "$@" > "$STUB_LOG/dnf5.args"
cat "$STUB_LOG/dnf5.out"
exit "$(cat "$STUB_LOG/dnf5.status")"
'''

CREATEREPO = '''printf '%s\\n' "$@" > "$STUB_LOG/createrepo_c.args"
while [ "$#" -gt 1 ]; do
  [ "$1" = --outputdir ] && mkdir -p "$2/repodata"
  shift
done
exit 0
'''


class ClosureCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        tmp = Path(self.tmp.name)
        self.bin = tmp / 'bin'
        self.log = tmp / 'log'
        self.rpms = tmp / 'complete-rpms'
        for directory in (self.bin, self.log, self.rpms):
            directory.mkdir()
        self.stub('dnf', 'exit 0')
        self.stub('rpm', 'echo 45')
        self.stub('createrepo_c', CREATEREPO)
        self.stub('dnf5', DNF5)
        self.env = dict(os.environ, PATH=f'{self.bin}:{os.environ["PATH"]}', STUB_LOG=str(self.log),
                        TMPDIR=str(tmp))

    def stub(self, name, body):
        path = self.bin / name
        path.write_text(f'#!/bin/sh\n{body}\n')
        path.chmod(0o755)

    def rpm(self, filename):
        (self.rpms / filename).write_bytes(b'rpm')

    def closure(self, output='', status=0):
        (self.log / 'dnf5.out').write_text(output)
        (self.log / 'dnf5.status').write_text(f'{status}\n')
        return subprocess.run(['bash', str(CHECK), str(self.rpms)], env=self.env,
                              capture_output=True, text=True)

    def test_refuses_a_kernel_whose_avd_fw_floor_the_set_does_not_meet(self):
        self.rpm('kernel-aurora-core-7.3.0-41.fc45.aurora.aarch64.rpm')
        self.rpm('avd-fw-0.1-4.fc45.aurora.aarch64.rpm')
        result = self.closure(UNRESOLVED, status=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('    avd-fw >= 0.1-5\n', result.stdout)
        self.assertNotIn('Every Requires', result.stdout)

    def test_a_reported_unresolved_dependency_fails_whatever_dnf5_returns(self):
        self.rpm('kernel-aurora-core-7.3.0-41.fc45.aurora.aarch64.rpm')
        result = self.closure(UNRESOLVED, status=0)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('unexpected match', result.stderr)

    def test_a_failed_repoclosure_fails_without_a_report(self):
        self.rpm('kernel-aurora-core-7.3.0-41.fc45.aurora.aarch64.rpm')
        result = self.closure('Error: Failed to download metadata\n', status=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('dnf5 repoclosure failed with status 1', result.stderr)

    def test_passes_a_closed_set_and_leaves_it_as_it_is(self):
        names = ['kernel-aurora-core-7.3.0-41.fc45.aurora.aarch64.rpm', 'avd-fw-0.1-5.fc45.aurora.aarch64.rpm']
        for name in names:
            self.rpm(name)
        result = self.closure()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Every Requires of the 2 RPMs resolves from the set and Fedora 45', result.stdout)
        self.assertEqual(sorted(p.name for p in self.rpms.iterdir()), sorted(names))

    def test_checks_the_set_against_fedora_with_every_exclude_off(self):
        self.rpm('kernel-aurora-core-7.3.0-41.fc45.aurora.aarch64.rpm')
        self.assertEqual(self.closure().returncode, 0)
        indexed = (self.log / 'createrepo_c.args').read_text().splitlines()
        self.assertEqual(indexed[-1], str(self.rpms))
        index = indexed[indexed.index('--outputdir') + 1]
        self.assertNotEqual(Path(index), self.rpms)
        args = (self.log / 'dnf5.args').read_text().splitlines()
        self.assertIn('--setopt=disable_excludes=*', args)
        self.assertIn(f'--repofrompath=aurora-candidate,{index}', args)
        self.assertEqual(args[args.index('repoclosure'):], ['repoclosure', '--check=aurora-candidate'])
        # Fedora's own repositories stay enabled to resolve the rest.
        self.assertFalse([a for a in args if a.startswith(('--repo=', '--disablerepo', '--setopt=excludepkgs'))], args)

    def test_an_empty_set_is_refused(self):
        result = self.closure()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('No RPMs in', result.stderr)
        self.assertFalse((self.log / 'dnf5.args').exists())


def job(workflow, name):
    """The body of one job of a workflow."""
    body = workflow.split(f'\n  {name}:\n', 1)[1]
    return re.split(r'\n  [A-Za-z0-9_-]+:\n', body, maxsplit=1)[0]


class WiringTests(unittest.TestCase):
    def test_every_publication_checks_the_assembled_set_before_it_is_signed(self):
        collect = job((ROOT / '.github/workflows/publish.yml').read_text(), 'collect')
        steps = collect.split('\n      - ')
        names = [s.split('\n', 1)[0] for s in steps]
        closure = next(i for i, s in enumerate(steps) if 'scripts/check-repository-closure' in s)
        assemble = next(i for i, n in enumerate(names) if n.startswith('id: assemble'))
        bundle = next(i for i, n in enumerate(names) if n.startswith('id: bundle'))
        self.assertLess(assemble, closure)
        self.assertLess(closure, bundle)
        step = steps[closure]
        self.assertIn("if: steps.assemble.outputs.status == 'complete'\n", step)
        self.assertIn('"$FEDORA_IMAGE"', step)
        self.assertIn('bash scripts/check-repository-closure complete-rpms', step)
        self.assertNotIn('continue-on-error', step)
        # The assembled set is what the sign jobs receive.
        self.assertIn('mv complete-rpms candidate/', steps[bundle])

    def test_fedora_45_publication_runs_the_same_collect_job(self):
        follow = (ROOT / '.github/workflows/publish-fedora45.yml').read_text()
        self.assertIn('gh workflow run publish.yml --repo "$GITHUB_REPOSITORY" --ref main -f fedora-release=45', follow)
        publish = (ROOT / '.github/workflows/publish.yml').read_text()
        self.assertIn("options: ['44', '45']", publish)

    def test_source_checks_run_the_real_check_for_both_releases(self):
        closure = job((ROOT / '.github/workflows/checks.yml').read_text(), 'repository-closure')
        self.assertIn("release: ['44', '45']", closure)
        self.assertIn('registry.fedoraproject.org/fedora:${{ matrix.release }}', closure)
        self.assertIn('bash /src/scripts/test-repository-closure', closure)
        # The probe test configures the fleet's exclude, taken from the upgrade test.
        self.assertRegex((ROOT / 'scripts/test-fedora-repository').read_text(),
                         r'(?m)^excludepkgs=kernel-aurora\*,')


if __name__ == '__main__':
    unittest.main()
