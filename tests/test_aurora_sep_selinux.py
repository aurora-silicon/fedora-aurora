"""aurora-sep's SELinux module covers exactly the driver's state files, and
fingerprint sign-in is turned on once and never forced back on."""
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / 'packages/aurora-sep'

# Every file the apple_sep driver keeps in /var/lib (drivers/soc/apple:
# catacomb.rs, keybag.rs, refkey.rs, store.rs, xart_guard.rs).
STATE = [
    'apple-sep-catacomb-master.bin', 'apple-sep-catacomb-owner.bin',
    'apple-sep-catacomb-user.bin', 'aurora-sep-keybag.bin',
    'aurora-sep-refkey.bin', 'aurora-sep-refkey-v2.bin',
    'aurora-sep-host-state.bin', 'aurora-sep-xart-owned.bin',
    'aurora-sep-xart-allow-once.bin', 'aurora-sep-xart-policy-previous.bin',
    'aurora-sep-touchid-lockout.bin',
]


class SelinuxModuleTests(unittest.TestCase):
    def setUp(self):
        self.te = (PKG / 'aurora_sep.te').read_text()
        self.fc = (PKG / 'aurora_sep.fc').read_text()
        self.spec = (PKG / 'aurora-sep.spec').read_text()

    def contexts(self):
        rules = []
        for line in self.fc.splitlines():
            if line.strip() and not line.startswith('#'):
                regex, kind, context = line.split('\t')
                rules.append((re.compile(regex + r'\Z'), kind, context))
        return rules

    def test_every_state_file_maps_to_the_state_type(self):
        for name in STATE:
            hits = [c for r, k, c in self.contexts() if r.match('/var/lib/' + name)]
            self.assertEqual(len(hits), 1, name)
            self.assertIn(':aurora_sep_state_t,', hits[0], name)

    def test_nothing_else_in_var_lib_gets_the_state_type(self):
        for other in ['/var/lib/aurora-sep', '/var/lib/aurora-sep/x',
                      '/var/lib/fprint', '/var/lib/aurora-sep-keybag.bin.tmp',
                      '/var/lib/apple-sep-catacomb-other.bin']:
            self.assertFalse(any(r.match(other) for r, _, _ in self.contexts()), other)

    def test_the_kernel_creates_each_file_with_the_state_type(self):
        for name in STATE:
            self.assertIn(
                'type_transition kernel_t var_lib_t:file aurora_sep_state_t "%s";' % name,
                self.te)

    def test_no_access_to_generic_var_lib(self):
        self.assertNotRegex(self.te, r'allow\s+\S+\s+var_lib_t')

    def test_state_access_is_scoped(self):
        allowed = set(re.findall(r'allow\s+(\w+)\s+aurora_sep_state_t:', self.te))
        self.assertEqual(allowed, {'kernel_t', 'init_t', 'fprintd_t', 'kmod_t',
                                   'aurora_touchid_rearm_t'})
        self.assertRegex(self.te, r'allow init_t aurora_sep_state_t:file read_file_perms;')

    def test_the_loader_runs_in_its_own_domain(self):
        for path in ('/usr/libexec/aurora-sep-load', '/usr/local/sbin/aurora-sep-load'):
            hits = [c for r, k, c in self.contexts() if r.match(path)]
            self.assertEqual(hits, ['gen_context(system_u:object_r:aurora_sep_load_exec_t,s0)'], path)
        self.assertIn('init_daemon_domain(aurora_sep_load_t, aurora_sep_load_exec_t)', self.te)
        self.assertRegex(self.te, r"optional_policy\(`\n\tunconfined_domain\(aurora_sep_load_t\)\n'\)")

    def test_other_domains_only_stop_logging_the_view_of_probe_keys(self):
        # Hiding the probe keys from /proc/keys listings is intended; only the
        # log line goes. No domain gains any access to them.
        self.assertEqual(re.findall(r'^dontaudit .*$', self.te, re.M),
                         ['dontaudit domain aurora_sep_load_t:key view;'])
        self.assertNotRegex(self.te, r'allow\s+\S+\s+\S+:key')

    def test_upgrade_labels_an_installed_loader(self):
        post = self.spec[self.spec.index('%posttrans selinux'):self.spec.index('%files')]
        self.assertIn('restorecon %{_libexecdir}/aurora-sep-load', post)

    def test_no_apostrophe_breaks_an_m4_quoted_block(self):
        for block in re.findall(r"optional_policy\(`(.*?)\n'\)", self.te, re.S):
            self.assertNotIn("'", block.replace("')", ''))

    def test_upgrade_relabels_exactly_the_state_files_without_touching_them(self):
        post = self.spec[self.spec.index('%posttrans selinux'):self.spec.index('%files')]
        self.assertEqual(sorted(re.findall(r'/var/lib/([\w.-]+\.bin)', post)), sorted(STATE))
        self.assertIn('restorecon -F "$f"', post)
        for verb in ('rm ', 'mv ', 'cp ', 'truncate', '>"$f"'):
            self.assertNotIn(verb, post)


class TouchIdRearmPolicyTests(unittest.TestCase):
    def setUp(self):
        self.te = (PKG / 'aurora_sep.te').read_text()
        self.fc = (PKG / 'aurora_sep.fc').read_text()

    def test_only_the_rearm_domain_opens_the_rearm_device(self):
        users = set(re.findall(r'allow\s+(\w+)\s+aurora_sep_rearm_device_t:', self.te))
        self.assertEqual(users, {'aurora_touchid_rearm_t'})
        self.assertIn('/dev/sep-bio-rearm\t-c\tgen_context(system_u:object_r:aurora_sep_rearm_device_t,s0)', self.fc)

    def test_confined_users_and_their_agents_reach_the_key_node(self):
        # ssh-keygen and ssh-add run in the login user's own domain and the
        # agent in that role's agent domain (staff_ssh_agent_t), so the
        # policy names the attributes, not only ssh_t/ssh_agent_t.
        for client in ('ssh_t', 'ssh_agent_t', 'ssh_keygen_t'):
            self.assertIn(f'aurora_sep_key_client({client})', self.te)
        for attr in ('userdomain', 'ssh_agent_type'):
            self.assertIn(f'aurora_sep_key_client_attr({attr})', self.te)
        self.assertIn('/dev/sep-key\t-c\tgen_context(system_u:object_r:aurora_sep_key_device_t,s0)', self.fc)

    def test_a_confined_agent_may_make_its_socket_directory(self):
        self.assertIn('allow ssh_agent_type ssh_home_t:dir { create_dir_perms rw_dir_perms rmdir };', self.te)
        self.assertIn('allow ssh_agent_type ssh_home_t:sock_file { create unlink getattr setattr };', self.te)

    def test_the_rearm_service_runs_in_its_own_domain(self):
        self.assertIn('init_daemon_domain(aurora_touchid_rearm_t, aurora_touchid_rearm_exec_t)', self.te)
        self.assertIn('/usr/libexec/aurora-touchid-rearm\t--\tgen_context(system_u:object_r:aurora_touchid_rearm_exec_t,s0)', self.fc)
        self.assertNotIn('unconfined_domain(aurora_touchid_rearm_t)', self.te)

    def test_the_rearm_service_keeps_no_new_privileges(self):
        # aurora-touchid-rearm@.service sets NoNewPrivileges=yes. Under it,
        # SELinux allows a domain transition only when it is bounded or
        # allowed by process2 nnp_transition: systemd's into the helper's
        # domain, and the helper's pam_unix into unix_chkpwd's.
        self.assertIn('init_nnp_daemon_domain(aurora_touchid_rearm_t)', self.te)
        self.assertIn('auth_nnp_domtrans_chkpwd(aurora_touchid_rearm_t)', self.te)
        self.assertIn('auth_use_pam(aurora_touchid_rearm_t)', self.te)
        # No blanket nnp rule for any other domain.
        self.assertEqual(re.findall(r'nnp_(?:daemon_domain|domtrans_\w+)\((\w+)\)', self.te),
                         ['aurora_touchid_rearm_t', 'aurora_touchid_rearm_t'])
        self.assertNotRegex(self.te, r'process2')


def hint_harness():
    script = (PKG / 'aurora-sep-ready').read_text()
    start = script.index('pam_hint() {')
    body = script[start:script.index('\n}\n', start) + 3]
    return 'log() { echo "LOG: $*"; }\n' + body + 'pam_hint\n'


class FingerprintSignInTests(unittest.TestCase):
    def run_hint(self, features, enable_ok=True, marker=False):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            state = tmp / 'state'
            state.mkdir()
            if marker:
                (state / 'fingerprint-sign-in-offered').touch()
            calls = tmp / 'calls'
            fake = tmp / 'bin'
            fake.mkdir()
            (fake / 'authselect').write_text(
                '#!/bin/sh\necho "$*" >>"%s"\n'
                'case "$1" in current) %s ;; enable-feature) exit %d ;; esac\n'
                % (calls, 'echo "%s"' % features if features is not None else 'exit 2',
                   0 if enable_ok else 1))
            (fake / 'authselect').chmod(0o755)
            env = dict(os.environ, PATH='%s:/usr/bin:/bin' % fake, AURORA_SEP_STATE_DIR=str(state))
            out = subprocess.run(['sh', '-c', hint_harness()], env=env, text=True,
                                 capture_output=True, check=True).stdout
            made = (state / 'fingerprint-sign-in-offered').exists()
            return out, calls.read_text() if calls.exists() else '', made

    def test_turned_on_once_when_off(self):
        out, calls, made = self.run_hint('local with-silent-lastlog')
        self.assertIn('enable-feature with-fingerprint', calls)
        self.assertTrue(made)
        self.assertIn('available', out)

    def test_a_later_opt_out_is_kept(self):
        out, calls, made = self.run_hint('local', marker=True)
        self.assertNotIn('enable-feature', calls)
        self.assertIn('turned off', out)

    def test_already_on_only_records_the_marker(self):
        _, calls, made = self.run_hint('local with-fingerprint')
        self.assertNotIn('enable-feature', calls)
        self.assertTrue(made)

    def test_no_authselect_profile_is_left_alone(self):
        _, calls, made = self.run_hint(None)
        self.assertNotIn('enable-feature', calls)
        self.assertFalse(made)

    def test_a_failed_enable_leaves_no_marker(self):
        out, _, made = self.run_hint('local', enable_ok=False)
        self.assertFalse(made)
        self.assertIn('could not', out)


if __name__ == '__main__':
    unittest.main()
