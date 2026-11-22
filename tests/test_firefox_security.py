"""Firefox security-update SLA: Fedora update vs. the Aurora channels, and the tracking issue."""
import datetime
import importlib.util
import io
from pathlib import Path
import contextlib
import re
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests' / 'fixtures' / 'firefox-security'
_spec = importlib.util.spec_from_file_location('sla', ROOT / 'scripts/check-firefox-security.py')
sla = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sla)

UTC = datetime.timezone.utc


def at(text):
    return datetime.datetime.fromisoformat(text).replace(tzinfo=UTC)


def update(**kw):
    values = dict(alias='FEDORA-2026-0000000003', fedora=44, version='160.0.1', release='1.fc44',
                  epoch='0', severity='medium', status='stable', pushed=at('2026-11-18 03:00:00'))
    values.update(kw)
    return sla.Update(**values)


def served(firefox, langpacks=None):
    found = {'firefox': ('0',) + tuple(firefox.split('-'))}
    if langpacks is not False:
        found['firefox-langpacks'] = ('0',) + tuple((langpacks or firefox).split('-'))
    return found


BEHIND = {'testing': (False, 'serves 160.0-1.fc44.aurora2'), 'stable': (False, 'serves 160.0-1.fc44.aurora2')}


class BodhiTests(unittest.TestCase):
    def test_fixture_updates(self):
        updates = sla.bodhi_updates(44, FIXTURES / 'bodhi-f44.json')
        self.assertEqual([u.nvr for u in updates], ['firefox-160.0.1-1.fc44', 'firefox-160.0-1.fc44',
                                                    'firefox-160.0-1.fc44', 'firefox-159.0-1.fc44'])
        testing, unpushed, stable, direct = updates
        # The clock starts at the first push, to updates-testing or straight to updates.
        self.assertEqual(testing.pushed, at('2026-11-18 03:00:00'))
        self.assertEqual(stable.pushed, at('2026-11-11 02:44:52'))
        self.assertEqual(direct.pushed, at('2026-10-29 01:27:21'))
        self.assertIsNone(unpushed.pushed)
        self.assertEqual((testing.severity, testing.status, testing.fedora), ('high', 'testing', 44))
        self.assertEqual(testing.due('testing'), at('2026-11-21 03:00:00'))
        self.assertEqual(testing.due('stable'), at('2026-11-25 03:00:00'))
        self.assertEqual(testing.escalate_at, at('2026-11-20 03:00:00'))
        self.assertIsNone(update(severity='medium').escalate_at)
        self.assertEqual(update(severity='urgent').escalate_at, at('2026-11-20 03:00:00'))

    def test_other_release_and_packages_are_ignored(self):
        self.assertEqual(sla.bodhi_updates(45, FIXTURES / 'bodhi-f44.json'), [])
        self.assertIsNone(sla.parse_update({'alias': 'X', 'status': 'stable', 'release': {'version': '44'},
                                            'builds': [{'nvr': 'firefox-pkcs11-1.0-1.fc44'}]}))


class FreshnessTests(unittest.TestCase):
    def test_served_metadata_takes_the_newest_aarch64_build(self):
        found = sla.served_packages((FIXTURES / 'primary-44-testing.xml').read_bytes())
        self.assertEqual(found, {'firefox': ('0', '160.0', '1.fc44.aurora2'),
                                 'firefox-langpacks': ('0', '160.0', '1.fc44.aurora2')})
        self.assertEqual(sla.served(44, 'testing', FIXTURES / 'primary-44-testing.xml'), found)
        self.assertIsNone(sla.served(44, 'stable', FIXTURES / 'absent.xml'))

    def test_a_rebuild_of_the_same_fedora_build_is_current(self):
        self.assertEqual(sla.freshness(served('160.0.1-1.fc44.aurora2'), update())[0], True)
        self.assertEqual(sla.freshness(served('161.0-1.fc44.aurora1'), update())[0], True)

    def test_a_higher_aurora_suffix_alone_is_not_current(self):
        self.assertEqual(sla.freshness(served('160.0-1.fc44.aurora9'), update())[0], False)
        # Same upstream version, but Fedora's security update is a later release (new patches).
        self.assertEqual(sla.freshness(served('160.0.1-1.fc44.aurora9'), update(release='2.fc44'))[0], False)
        self.assertEqual(sla.base_evr(('0', '160.0', '1.fc44.aurora12')), ('0', '160.0', '1.fc44'))

    def test_langpacks_must_be_the_same_build(self):
        current, why = sla.freshness(served('160.0.1-1.fc44.aurora2', '160.0-1.fc44.aurora2'), update())
        self.assertEqual((current, why), (False, 'firefox 160.0.1-1.fc44.aurora2 but firefox-langpacks '
                                                 '160.0-1.fc44.aurora2'))
        self.assertFalse(sla.freshness(served('160.0.1-1.fc44.aurora2', False), update())[0])
        self.assertFalse(sla.freshness({}, update())[0])

    def test_an_unserved_channel_is_unknown(self):
        self.assertEqual(sla.freshness(None, update()), (None, 'channel not served'))

    def test_channels_match_the_site(self):
        _s = importlib.util.spec_from_file_location('channel_site', ROOT / 'scripts/channel-site.py')
        site = importlib.util.module_from_spec(_s)
        with mock.patch('sys.path', [str(ROOT / 'scripts')] + __import__('sys').path):
            _s.loader.exec_module(site)
        slots = {}
        for fedora, channel in site.SLOTS.values():
            slots.setdefault(fedora, []).append(channel)
        self.assertEqual({k: tuple(v) for k, v in slots.items()}, sla.CHANNELS)


class PlanTests(unittest.TestCase):
    def kinds(self, actions):
        return [a[0] for a in actions]

    def test_behind_opens_one_issue_with_the_due_time(self):
        actions = sla.plan(update(), BEHIND, None, at('2026-11-18 06:00:00'))
        self.assertEqual(self.kinds(actions), ['create'])
        _, title, body, labels = actions[0]
        self.assertEqual(title, 'Firefox security: rebuild firefox-160.0.1-1.fc44 (F44), '
                                'testing due 2026-11-21 03:00 UTC')
        self.assertEqual(labels, ['firefox-security'])
        self.assertIn(sla.marker('FEDORA-2026-0000000003'), body)
        self.assertIn('| testing | 2026-11-21 03:00 UTC | behind', body)
        self.assertIn('| stable | 2026-11-25 03:00 UTC | behind', body)
        self.assertIn('distro merge-train maintainers', body)
        self.assertIn('release coordinator', body)
        self.assertIn('https://github.com/aurora-silicon/fedora-aurora/blob/main/docs/firefox/security-updates.md',
                      body)

    def test_an_unchanged_issue_is_left_alone(self):
        now = at('2026-11-18 06:00:00')
        _, title, body, _ = sla.plan(update(), BEHIND, None, now)[0]
        issue = sla.Issue(7, 'open', title, body, {'firefox-security'})
        self.assertEqual(sla.plan(update(), BEHIND, issue, now), [])
        self.assertEqual(sla.alias_of(issue), 'FEDORA-2026-0000000003')

    def test_status_change_edits_the_body(self):
        now = at('2026-11-18 06:00:00')
        _, title, body, _ = sla.plan(update(), BEHIND, None, now)[0]
        issue = sla.Issue(7, 'open', title, body, {'firefox-security'})
        status = dict(BEHIND, testing=(True, 'serves 160.0.1-1.fc44.aurora2'))
        self.assertEqual(self.kinds(sla.plan(update(), status, issue, now)), ['edit'])

    def test_high_severity_escalates_at_48_hours_once(self):
        u = update(severity='high')
        issue = sla.Issue(7, 'open', sla.title(u),
                          sla.body(u, BEHIND, '@org/team', 'aurora-silicon/fedora-aurora'), {'firefox-security'})
        self.assertEqual(sla.plan(u, BEHIND, issue, at('2026-11-20 02:59:00'), '@org/team'), [])
        actions = sla.plan(u, BEHIND, issue, at('2026-11-20 03:00:00'), '@org/team')
        self.assertEqual(self.kinds(actions), ['comment'])
        self.assertIn('@org/team Escalation', actions[0][1])
        issue.comments.append(actions[0][1])
        self.assertEqual(sla.plan(u, BEHIND, issue, at('2026-11-20 04:00:00'), '@org/team'), [])
        # Medium severity waits for the deadline.
        m = update()
        self.assertEqual(sla.plan(m, BEHIND, sla.Issue(8, 'open', sla.title(m),
                         sla.body(m, BEHIND, '', 'aurora-silicon/fedora-aurora'), {'firefox-security'}),
                         at('2026-11-20 03:00:00')), [])

    def test_past_due_labels_overdue_and_comments_once_per_channel(self):
        u = update()
        issue = sla.Issue(7, 'open', sla.title(u), sla.body(u, BEHIND, '', 'aurora-silicon/fedora-aurora'),
                          {'firefox-security'})
        actions = sla.plan(u, BEHIND, issue, at('2026-11-21 03:00:00'))
        self.assertEqual(self.kinds(actions), ['label', 'comment'])
        self.assertEqual(actions[0], ('label', 'overdue'))
        self.assertIn('overdue-testing', actions[1][1])
        issue.labels.add('overdue')
        issue.comments.append(actions[1][1])
        self.assertEqual(sla.plan(u, BEHIND, issue, at('2026-11-22 00:00:00')), [])
        later = sla.plan(u, BEHIND, issue, at('2026-11-25 03:00:00'))
        self.assertEqual(self.kinds(later), ['comment'])
        self.assertIn('overdue-stable', later[0][1])
        # A new issue past its deadline is created already labelled.
        self.assertEqual(sla.plan(u, BEHIND, None, at('2026-11-21 03:00:00'))[0][3],
                         ['firefox-security', 'overdue'])

    def test_current_everywhere_closes_and_never_opens(self):
        status = {'testing': (True, 'serves 160.0.1-1.fc44.aurora2'), 'stable': (None, 'channel not served')}
        self.assertEqual(sla.plan(update(), status, None, at('2026-11-30 00:00:00')), [])
        issue = sla.Issue(7, 'open', 't', sla.marker('FEDORA-2026-0000000003'), {'firefox-security'})
        self.assertEqual(self.kinds(sla.plan(update(), status, issue, at('2026-11-19 00:00:00'))),
                         ['comment', 'close'])
        issue.state = 'closed'
        self.assertEqual(sla.plan(update(), status, issue, at('2026-11-19 00:00:00')), [])

    def test_stable_behind_keeps_the_issue_open(self):
        status = {'testing': (True, 'serves 160.0.1-1.fc44.aurora2'), 'stable': (False, 'serves 160.0-1.fc44.aurora2')}
        self.assertEqual(self.kinds(sla.plan(update(), status, None, at('2026-11-19 00:00:00'))), ['create'])

    def test_a_closed_issue_reopens_while_behind(self):
        u = update()
        issue = sla.Issue(7, 'closed', sla.title(u), sla.body(u, BEHIND, '', 'aurora-silicon/fedora-aurora'),
                          {'firefox-security'})
        self.assertEqual(self.kinds(sla.plan(u, BEHIND, issue, at('2026-11-19 00:00:00'))), ['reopen', 'comment'])

    def test_withdrawn_update_closes_its_issue(self):
        u = update(status='unpushed', pushed=None)
        self.assertEqual(self.kinds(sla.plan_withdrawn(u, sla.Issue(7, 'open', 't', 'b', set()))),
                         ['comment', 'close'])
        self.assertEqual(sla.plan_withdrawn(u, sla.Issue(7, 'closed', 't', 'b', set())), [])


class WorkflowTests(unittest.TestCase):
    def test_tracker_runs_the_sla_check_with_issue_access(self):
        workflow = (ROOT / '.github/workflows/track-firefox.yml').read_text()
        job = workflow.split('\n  security-sla:\n', 1)[1]
        self.assertIn('issues: write', job)
        self.assertIn('python3 scripts/check-firefox-security.py --repository "$REPOSITORY"', job)
        self.assertIn("vars.FIREFOX_SECURITY_SLA != 'false'", job)
        self.assertTrue((ROOT / sla.DOC).is_file())


class EndToEndTests(unittest.TestCase):
    """main() with saved responses and a fake GitHub: dry run prints, nothing is changed."""

    def run_main(self, now, issues=()):
        argv = ['check-firefox-security.py', '--release', '44', '--now', now,
                '--bodhi', f'44={FIXTURES / "bodhi-f44.json"}',
                '--served', f'44/testing={FIXTURES / "primary-44-testing.xml"}',
                '--served', f'44/stable={FIXTURES / "absent.xml"}',
                '--served', f'44/edge={FIXTURES / "absent.xml"}']
        out = io.StringIO()
        with mock.patch('sys.argv', argv), \
                mock.patch.object(sla.GitHub, 'issues', return_value=list(issues)), \
                mock.patch.object(sla.GitHub, 'load_comments'), \
                mock.patch.object(sla, 'bodhi_update', side_effect=AssertionError('network')), \
                mock.patch('subprocess.run', side_effect=AssertionError('no gh writes in a dry run')), \
                contextlib.redirect_stdout(out):
            code = sla.main()
        return code, out.getvalue()

    def test_dry_run_plans_one_issue_for_the_newer_update(self):
        code, out = self.run_main('2026-11-19T00:00:00')
        self.assertEqual(code, 0)
        self.assertEqual(len(re.findall(r'dry run: #new create', out)), 1, out)
        self.assertIn('firefox-160.0.1-1.fc44 (F44)', out)
        self.assertIn('stable not served', out)

    def test_overdue_fails(self):
        code, out = self.run_main('2026-11-21T04:00:00')
        self.assertEqual(code, 1)
        self.assertIn('::error::Firefox security rebuild overdue: FEDORA-2026-0000000003 testing', out)


if __name__ == '__main__':
    unittest.main()
