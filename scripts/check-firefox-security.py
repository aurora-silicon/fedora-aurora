#!/usr/bin/env python3
"""Track Aurora's Firefox rebuild deadline for every Fedora Firefox security update.

The Aurora repository has priority over Fedora's, so Aurora systems get a
Fedora Firefox security fix only once Aurora's rebuild is served. For each
Fedora release this script reads Fedora's Firefox security updates from Bodhi
and the firefox and firefox-langpacks packages that each Aurora channel serves,
and keeps one GitHub issue per Fedora update while Aurora is behind it
(docs/firefox/security-updates.md):

- the clock starts when Fedora first pushes the update (updates-testing or
  updates); Aurora's testing channel is due 72 hours later and stable 7 days
  later; urgent/high updates escalate at 48 hours;
- Aurora is current only when its firefox, with the Aurora release suffix
  removed, is at least Fedora's version-release and firefox-langpacks is the
  same build. A higher `.auroraN` suffix alone never counts;
- the issue is labelled `firefox-security`, gains `overdue` and a comment when
  a deadline passes, and is closed once every channel is current.

This is security freshness only. Whether a snapshot carries Aurora's Firefox
at all is assemble-repository.py's REQUIRED_TOGETHER check.

    check-firefox-security.py [--release 44 --release 45] [--live]

Without --live it prints what it would do. It exits 1 while an obligation is
overdue. --bodhi and --served read saved responses instead of the network.
"""
import argparse
import dataclasses
import datetime
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('published_evr', ROOT / 'scripts' / 'check-published-evr.py')
evr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(evr)

BODHI = 'https://bodhi.fedoraproject.org'
SITE = 'https://aurorasilicon.org/fedora-aurora'
DOC = 'docs/firefox/security-updates.md'
# The channels the site serves per Fedora release (scripts/channel-site.py SLOTS).
CHANNELS = {44: ('testing', 'stable'), 45: ('testing',)}
DUE = {'testing': datetime.timedelta(hours=72), 'stable': datetime.timedelta(days=7)}
ESCALATE = datetime.timedelta(hours=48)
ESCALATING_SEVERITY = {'urgent', 'high'}
PACKAGES = ('firefox', 'firefox-langpacks')
WITHDRAWN = {'unpushed', 'revoked'}
LABEL = 'firefox-security'
OVERDUE = 'overdue'
LABELS = {LABEL: ('b60205', 'Aurora Firefox rebuild owed for a Fedora security update'),
          OVERDUE: ('d93f0b', 'Past its deadline')}
OWNERS = ('Accountable: the distro merge-train maintainers. '
          'Backup: the release coordinator.')


def marker(alias):
    return f'<!-- firefox-security-sla: {alias} -->'


def comment_marker(alias, event):
    return f'<!-- firefox-security-sla: {alias} {event} -->'


def utc(text):
    if not text:
        return None
    return datetime.datetime.fromisoformat(text.replace('Z', '')).replace(tzinfo=datetime.timezone.utc)


def stamp(when):
    return when.strftime('%Y-%m-%d %H:%M UTC')


@dataclasses.dataclass(frozen=True)
class Update:
    alias: str
    fedora: int
    version: str
    release: str
    epoch: str
    severity: str
    status: str
    pushed: datetime.datetime | None

    @property
    def nvr(self):
        return f'firefox-{self.version}-{self.release}'

    @property
    def url(self):
        return f'{BODHI}/updates/{self.alias}'

    def due(self, channel):
        return self.pushed + DUE[channel]

    @property
    def escalate_at(self):
        return self.pushed + ESCALATE if self.severity in ESCALATING_SEVERITY else None


def parse_update(data):
    """An Update from one Bodhi update object, or None if it has no firefox build."""
    builds = [b for b in data.get('builds', []) if b['nvr'].rsplit('-', 2)[0] == 'firefox']
    if not builds:
        return None
    _, version, release = builds[0]['nvr'].rsplit('-', 2)
    pushes = [t for t in (utc(data.get('date_testing')), utc(data.get('date_stable'))) if t]
    return Update(alias=data['alias'], fedora=int(data['release']['version']), version=version,
                  release=release, epoch=str(builds[0].get('epoch') or 0),
                  severity=data.get('severity') or 'unspecified', status=data['status'],
                  pushed=min(pushes) if pushes else None)


def served_packages(primary):
    """{name: (epoch, version, release)} of the newest firefox and langpacks in primary.xml bytes."""
    newest = {}
    for pkg in ET.fromstring(primary).findall('c:package', evr.NS):
        name = pkg.findtext('c:name', namespaces=evr.NS)
        if name not in PACKAGES or pkg.findtext('c:arch', namespaces=evr.NS) != 'aarch64':
            continue
        v = pkg.find('c:version', evr.NS)
        found = (v.get('epoch') or '0', v.get('ver'), v.get('rel'))
        if name not in newest or evr.vercmp_evr(found, newest[name]) > 0:
            newest[name] = found
    return newest


def base_evr(found):
    """Aurora's EVR without the Aurora release suffix: what Fedora build it rebuilds."""
    return found[0], found[1], re.sub(r'\.aurora\d*$', '', found[2])


def freshness(served, update):
    """(current, why) for one channel; current is None when the channel is not served."""
    if served is None:
        return None, 'channel not served'
    firefox = served.get('firefox')
    if firefox is None:
        return False, 'no firefox'
    show = f'{firefox[1]}-{firefox[2]}'
    langpacks = served.get('firefox-langpacks')
    if langpacks != firefox:
        return False, (f'firefox {show} but firefox-langpacks '
                       f'{"missing" if langpacks is None else langpacks[1] + "-" + langpacks[2]}')
    if evr.vercmp_evr(base_evr(firefox), (update.epoch, update.version, update.release)) < 0:
        return False, f'serves {show}'
    return True, f'serves {show}'


@dataclasses.dataclass
class Issue:
    number: int
    state: str
    title: str
    body: str
    labels: set
    comments: list = dataclasses.field(default_factory=list)


def alias_of(issue):
    m = re.search(r'<!-- firefox-security-sla: (\S+) -->', issue.body or '')
    return m[1] if m else None


def title(update):
    return (f'Firefox security: rebuild {update.nvr} (F{update.fedora}), '
            f'testing due {stamp(update.due("testing"))}')


def body(update, status, mention, repository):
    rows = []
    for channel, (current, why) in status.items():
        state = {True: 'current', False: 'behind', None: 'not served'}[current]
        rows.append(f'| {channel} | {stamp(update.due(channel))} | {state} ({why}) |')
    escalate = update.escalate_at
    lines = [
        marker(update.alias),
        f'Fedora pushed [{update.alias}]({update.url}) ({update.nvr}, severity {update.severity}) '
        f'on {stamp(update.pushed)}. Aurora must serve a rebuild of it, with matching '
        f'firefox-langpacks, by these deadlines:',
        '',
        '| Aurora channel | Due | Now |',
        '|---|---|---|',
        *rows,
        '',
        (f'Severity {update.severity}: escalates at {stamp(escalate)}.' if escalate else
         f'Severity {update.severity}: escalates when a deadline passes.'),
        '',
        OWNERS + (f' ({mention})' if mention else ''),
        '',
        f'Process, and the stock Fedora Firefox fallback for users if the rebuild cannot ship '
        f'in time: [{DOC}](https://github.com/{repository}/blob/main/{DOC}).',
        '',
        'Maintained by `.github/workflows/track-firefox.yml`; it closes this issue once every '
        'channel serves the rebuild. A higher Aurora release suffix alone does not count.',
    ]
    return '\n'.join(lines) + '\n'


def plan(update, status, issue, now, mention='', repository='aurora-silicon/fedora-aurora'):
    """Actions that bring the issue for UPDATE in line with STATUS at NOW.

    Each action is a tuple: ('create', title, body, labels), ('edit', title, body),
    ('label', name), ('comment', text), ('close',), ('reopen',).
    """
    actions = []
    met = all(current is not False for current, _ in status.values())
    said = '\n'.join(issue.comments) if issue else ''
    if met:
        if issue and issue.state == 'open':
            served = '; '.join(f'{c}: {why}' for c, (_, why) in status.items())
            actions += [('comment', f'{comment_marker(update.alias, "met")}\nAurora is current '
                         f'with {update.nvr} ({served}). Closing.'), ('close',)]
        return actions
    want_title, want_body = title(update), body(update, status, mention, repository)
    overdue = [c for c, (current, _) in status.items() if current is False and now >= update.due(c)]
    if issue is None:
        actions.append(('create', want_title, want_body, [LABEL] + ([OVERDUE] if overdue else [])))
    else:
        if issue.state != 'open':
            actions += [('reopen',), ('comment', f'Reopened: Aurora is behind {update.nvr} again.')]
        if (issue.title, issue.body) != (want_title, want_body):
            actions.append(('edit', want_title, want_body))
        if LABEL not in issue.labels:
            actions.append(('label', LABEL))
        if overdue and OVERDUE not in issue.labels:
            actions.append(('label', OVERDUE))
    who = f'{mention} ' if mention else ''
    escalate = update.escalate_at
    if (escalate and now >= escalate and status['testing'][0] is False
            and comment_marker(update.alias, 'escalated') not in said):
        actions.append(('comment', f'{comment_marker(update.alias, "escalated")}\n{who}Escalation: '
                        f'{update.nvr} is a {update.severity} security update and Aurora testing is '
                        f'still behind 48 hours after Fedora pushed it. Testing is due '
                        f'{stamp(update.due("testing"))}. If the rebuild cannot make it, publish '
                        f'the fallback in {DOC}.'))
    for channel in overdue:
        event = f'overdue-{channel}'
        if comment_marker(update.alias, event) not in said:
            actions.append(('comment', f'{comment_marker(update.alias, event)}\n{who}Overdue: Aurora '
                            f'{channel} was due to serve the rebuild of {update.nvr} by '
                            f'{stamp(update.due(channel))} ({status[channel][1]}). Label `{OVERDUE}`; '
                            f'point users at the fallback in {DOC} until it ships.'))
    return actions


def plan_withdrawn(update, issue):
    if issue.state != 'open':
        return []
    return [('comment', f'{comment_marker(update.alias, "withdrawn")}\nFedora {update.status} '
             f'{update.alias}; it is no longer a shipped update. Closing.'), ('close',)]


class GitHub:
    """The issue operations, through the gh CLI."""

    def __init__(self, repository, live):
        self.repository, self.live = repository, live

    def api(self, *args, data=None):
        out = subprocess.run(['gh', 'api', *args], input=None if data is None else json.dumps(data),
                             capture_output=True, text=True, check=True).stdout
        return json.loads(out) if out.strip() else None

    def issues(self):
        pages = subprocess.run(['gh', 'api', '--paginate', '--slurp',
                                f'repos/{self.repository}/issues?labels={LABEL}&state=all&per_page=100'],
                               capture_output=True, text=True, check=True).stdout
        found = []
        for item in (i for page in json.loads(pages) for i in page):
            if 'pull_request' in item:
                continue
            found.append(Issue(item['number'], item['state'], item['title'], item['body'] or '',
                               {label['name'] for label in item['labels']}))
        return found

    def load_comments(self, issue):
        pages = subprocess.run(['gh', 'api', '--paginate', '--slurp',
                                f'repos/{self.repository}/issues/{issue.number}/comments?per_page=100'],
                               capture_output=True, text=True, check=True).stdout
        issue.comments = [c['body'] or '' for page in json.loads(pages) for c in page]

    def ensure_labels(self):
        if not self.live:
            return
        for name, (color, description) in LABELS.items():
            subprocess.run(['gh', 'label', 'create', name, '--repo', self.repository, '--color', color,
                            '--description', description], capture_output=True)

    def apply(self, issue, actions):
        for action in actions:
            detail = next((line for line in (action[1].splitlines() if len(action) > 1 else [])
                           if not line.startswith('<!--')), '')
            print(f'  {"" if self.live else "dry run: "}#{issue.number if issue else "new"} '
                  f'{action[0]} {detail[:160]}'.rstrip())
            if not self.live:
                continue
            path = f'repos/{self.repository}/issues'
            kind = action[0]
            if kind == 'create':
                issue = Issue(self.api(path, '--input', '-', data={
                    'title': action[1], 'body': action[2], 'labels': action[3]})['number'],
                    'open', action[1], action[2], set(action[3]))
            elif kind == 'edit':
                self.api(f'{path}/{issue.number}', '-X', 'PATCH', '--input', '-',
                         data={'title': action[1], 'body': action[2]})
            elif kind == 'label':
                self.api(f'{path}/{issue.number}/labels', '--input', '-', data={'labels': [action[1]]})
            elif kind == 'comment':
                self.api(f'{path}/{issue.number}/comments', '--input', '-', data={'body': action[1]})
            elif kind in ('close', 'reopen'):
                self.api(f'{path}/{issue.number}', '-X', 'PATCH', '--input', '-',
                         data={'state': 'closed' if kind == 'close' else 'open'})


def fetch_json(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'Accept': 'application/json'}),
                                timeout=60) as r:
        return json.load(r)


def bodhi_updates(fedora, saved=None):
    """Fedora's newest Firefox security updates for one release, any status."""
    if saved:
        data = json.loads(Path(saved).read_text())
    else:
        query = urllib.parse.urlencode({'packages': 'firefox', 'releases': f'F{fedora}',
                                        'type': 'security', 'rows_per_page': 20})
        data = fetch_json(f'{BODHI}/updates/?{query}')
    return [u for u in map(parse_update, data['updates']) if u and u.fedora == fedora]


def bodhi_update(alias):
    return parse_update(fetch_json(f'{BODHI}/updates/{urllib.parse.quote(alias)}')['update'])


def served(fedora, channel, saved=None):
    """The channel's firefox packages, or None when the site does not serve the channel."""
    if saved:
        path = Path(saved)
        return served_packages(path.read_bytes()) if path.exists() else None
    base = f'{SITE}/{fedora}/{channel}/aarch64'
    try:
        repomd = ET.fromstring(evr.fetch(base + '/repodata/repomd.xml'))
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise
    href = next(d.find('r:location', evr.NS).get('href')
                for d in repomd.findall('r:data', evr.NS) if d.get('type') == 'primary')
    return served_packages(evr.decompress(evr.fetch(base + '/' + href), href))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--release', type=int, action='append', choices=sorted(CHANNELS))
    parser.add_argument('--repository', default=os.environ.get('GITHUB_REPOSITORY', 'aurora-silicon/fedora-aurora'))
    parser.add_argument('--live', action='store_true', help='change issues (default: print the plan)')
    parser.add_argument('--mention', default=os.environ.get('FIREFOX_SLA_MENTION', ''),
                        help='team or users to mention when escalating, e.g. @org/team')
    parser.add_argument('--now', type=utc, help='evaluate at this UTC time (default: now)')
    parser.add_argument('--bodhi', action='append', default=[], metavar='44=FILE',
                        help='saved Bodhi /updates/ response for a release')
    parser.add_argument('--served', action='append', default=[], metavar='44/testing=FILE',
                        help="saved primary.xml for a channel (a missing file: channel not served)")
    args = parser.parse_args()
    now = args.now or datetime.datetime.now(datetime.timezone.utc)
    saved_bodhi = dict(s.split('=', 1) for s in args.bodhi)
    saved_served = dict(s.split('=', 1) for s in args.served)
    github = GitHub(args.repository, args.live)
    issues = github.issues()
    by_alias = {alias_of(i): i for i in issues if alias_of(i)}
    overdue = []
    seen = set()
    for fedora in args.release or sorted(CHANNELS):
        repos = {c: served(fedora, c, saved_served.get(f'{fedora}/{c}')) for c in CHANNELS[fedora]}
        for channel, packages in repos.items():
            shown = ', '.join(f'{n} {v[1]}-{v[2]}' for n, v in sorted(packages.items())) if packages is not None else 'not served'
            print(f'Aurora {fedora}/{channel}: {shown or "no firefox"}')
        for update in bodhi_updates(fedora, saved_bodhi.get(str(fedora))):
            seen.add(update.alias)
            issue = by_alias.get(update.alias)
            if update.status in WITHDRAWN or update.pushed is None:
                if issue:
                    github.apply(issue, plan_withdrawn(update, issue))
                continue
            status = {c: freshness(repos[c], update) for c in CHANNELS[fedora]}
            print(f'F{fedora} {update.alias} {update.nvr} ({update.status}, {update.severity}, '
                  f'pushed {stamp(update.pushed)}): ' +
                  ', '.join(f'{c} {"current" if s[0] else "behind" if s[0] is False else "not served"}'
                            for c, s in status.items()))
            overdue += [f'{update.alias} {c}' for c, (current, _) in status.items()
                        if current is False and now >= update.due(c)]
            if issue:
                github.load_comments(issue)
            actions = plan(update, status, issue, now, args.mention, args.repository)
            if actions and any(a[0] in ('create', 'label') for a in actions):
                github.ensure_labels()
            github.apply(issue, actions)
    # An open issue whose update dropped out of the newest results: look it up directly.
    for alias, issue in by_alias.items():
        if alias in seen or issue.state != 'open':
            continue
        update = bodhi_update(alias)
        if update is None or update.fedora not in CHANNELS or (args.release and update.fedora not in args.release):
            continue
        if update.status in WITHDRAWN or update.pushed is None:
            github.apply(issue, plan_withdrawn(update, issue))
            continue
        repos = {c: served(update.fedora, c, saved_served.get(f'{update.fedora}/{c}')) for c in CHANNELS[update.fedora]}
        status = {c: freshness(repos[c], update) for c in CHANNELS[update.fedora]}
        overdue += [f'{update.alias} {c}' for c, (current, _) in status.items()
                    if current is False and now >= update.due(c)]
        github.load_comments(issue)
        github.apply(issue, plan(update, status, issue, now, args.mention, args.repository))
    for item in overdue:
        print(f'::error::Firefox security rebuild overdue: {item}')
    return 1 if overdue else 0


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    sys.exit(main())
