from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'packages/aurora-sep/authselect-vendor-local'
FPRINTD = 'auth        sufficient                                   pam_fprintd.so                                         {include if "with-fingerprint"}\n'
GUARD = ('auth        [success=1 default=ignore]                   pam_succeed_if.so service notin '
         'sudo:sudo-i:polkit-1 quiet {include if "with-fingerprint"}\n')
UNIX = 'auth        sufficient                                   pam_unix.so {if not "without-nullok":nullok}\n'
REARM = ('auth        [success=ok new_authtok_reqd=ok default=2]   pam_unix.so {if not "without-nullok":nullok}\n'
         '-auth       optional                                     pam_aurora_touchid.so {include if "with-fingerprint"}\n'
         'auth        sufficient                                   pam_permit.so\n')
SYSTEM_AUTH = ('auth        required                                     pam_env.so\n' + FPRINTD + UNIX +
               'auth        required                                     pam_deny.so\n')
PASSWORD_AUTH = ('auth        required                                     pam_env.so\n' + UNIX +
                 'auth        required                                     pam_faillock.so authfail\n'
                 'auth        required                                     pam_deny.so\n')


class AuthselectVendorLocalTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        share = Path(self.temporary.name) / 'share/authselect'
        self.default, self.vendor = share / 'default/local', share / 'vendor/local'
        self.default.mkdir(parents=True)
        (self.default / 'system-auth').write_text(SYSTEM_AUTH)
        (self.default / 'password-auth').write_text(PASSWORD_AUTH)
        for name in ('README', 'fingerprint-auth', 'postlogin', 'dconf-db'):
            (self.default / name).write_text(f'{name}\n')

    def tearDown(self):
        self.temporary.cleanup()

    def run_script(self, *arguments):
        env = dict(os.environ, AURORA_AUTHSELECT_DEFAULT=str(self.default),
                   AURORA_AUTHSELECT_VENDOR=str(self.vendor), AURORA_AUTHSELECT_NO_APPLY='1')
        return subprocess.run(['sh', str(SCRIPT), *arguments], env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True)

    def test_system_auth_offers_fingerprint_only_to_sudo_and_polkit(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual((self.vendor / 'system-auth').read_text(),
                         SYSTEM_AUTH.replace(FPRINTD, GUARD + FPRINTD).replace(UNIX, REARM))
        # pam_fprintd stays sufficient, ahead of the password.
        self.assertIn(FPRINTD, (self.vendor / 'system-auth').read_text())

    def test_every_other_file_is_the_default_profile_s(self):
        self.run_script()
        for name in ('README', 'fingerprint-auth', 'postlogin', 'dconf-db'):
            self.assertEqual(os.readlink(self.vendor / name), str(self.default / name))
        self.assertTrue((self.vendor / '.aurora-sep').is_file())

    def test_rebuilding_follows_the_installed_default_profile(self):
        self.run_script()
        (self.default / 'smartcard-auth').write_text('new\n')
        (self.default / 'system-auth').write_text('auth required pam_faillock.so preauth\n' + SYSTEM_AUTH)
        self.assertEqual(self.run_script().returncode, 0)
        self.assertTrue((self.vendor / 'smartcard-auth').is_symlink())
        self.assertTrue((self.vendor / 'system-auth').read_text().startswith('auth required pam_faillock.so'))
        self.assertEqual((self.vendor / 'system-auth').read_text().count('pam_succeed_if.so'), 1)
        self.assertFalse(self.vendor.with_name('local.new').exists())

    def test_unexpected_default_profile_falls_back_to_authselect_s_own(self):
        self.run_script()
        (self.default / 'system-auth').write_text(SYSTEM_AUTH.replace('sufficient  ', 'required    '))
        result = self.run_script()
        self.assertEqual(result.returncode, 0)
        self.assertIn('expected pam_fprintd line', result.stdout)
        self.assertFalse(self.vendor.exists())

    def test_an_empty_directory_is_filled_and_another_profile_is_left_alone(self):
        self.vendor.mkdir(parents=True)
        self.run_script()
        self.assertTrue((self.vendor / 'system-auth').is_file())
        (self.vendor / '.aurora-sep').unlink()
        (self.vendor / 'system-auth').write_text('theirs\n')
        result = self.run_script()
        self.assertIn('not Aurora', result.stdout)
        self.assertEqual((self.vendor / 'system-auth').read_text(), 'theirs\n')

    def test_a_password_re_arms_touch_id_after_pam_unix(self):
        self.assertEqual(self.run_script().returncode, 0)
        self.assertEqual((self.vendor / 'password-auth').read_text(), PASSWORD_AUTH.replace(UNIX, REARM))
        system = (self.vendor / 'system-auth').read_text()
        # pam_fprintd stays ahead of the password, and the module only behind it.
        self.assertLess(system.index('pam_fprintd.so'), system.index('pam_unix.so'))
        self.assertLess(system.index('pam_unix.so'), system.index('pam_aurora_touchid.so'))
        self.assertEqual(system.count('pam_aurora_touchid.so'), 1)

    def test_a_profile_without_the_pam_unix_line_keeps_the_fingerprint_change(self):
        (self.default / 'system-auth').write_text(SYSTEM_AUTH.replace(UNIX, 'auth required pam_unix.so\n'))
        (self.default / 'password-auth').write_text('auth required pam_unix.so\n')
        result = self.run_script()
        self.assertEqual(result.returncode, 0)
        self.assertIn('expected pam_unix line', result.stdout)
        self.assertNotIn('pam_aurora_touchid', (self.vendor / 'system-auth').read_text())
        self.assertIn(GUARD, (self.vendor / 'system-auth').read_text())
        self.assertEqual(os.readlink(self.vendor / 'password-auth'), str(self.default / 'password-auth'))

    def test_remove(self):
        self.run_script()
        self.assertEqual(self.run_script('--remove').returncode, 0)
        self.assertFalse(self.vendor.exists())


if __name__ == '__main__':
    unittest.main()
