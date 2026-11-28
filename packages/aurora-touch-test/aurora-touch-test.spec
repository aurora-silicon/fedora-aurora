Name: aurora-touch-test
Version: 0.1.0
Release: 1%{?dist}
Summary: Guided full-screen touchscreen diagnostics
License: GPL-2.0-only
URL: https://github.com/aurora-silicon/fedora-aurora
Source0: aurora-touch-test.py
Source1: scoring.py
Source2: index.html
Source3: test_scoring.py
Source4: k114s-evdev.txt
Source5: README.md
Source6: COPYING
BuildArch: noarch
BuildRequires: python3
Requires: python3-evdev
Requires: firefox

%description
An opt-in, guided touchscreen test with evdev scoring for timed holds and
three-finger swipes. Saves a local JSON report with a verdict per step.

%prep
%setup -c -T
cp %{SOURCE0} %{SOURCE1} %{SOURCE2} %{SOURCE3} %{SOURCE4} %{SOURCE5} %{SOURCE6} .

%build

%check
python3 -B -m unittest -v test_scoring

%install
install -Dm755 aurora-touch-test.py %{buildroot}%{_libexecdir}/aurora-touch-test/aurora-touch-test.py
install -Dm644 scoring.py %{buildroot}%{_libexecdir}/aurora-touch-test/scoring.py
install -Dm644 index.html %{buildroot}%{_libexecdir}/aurora-touch-test/index.html
install -d %{buildroot}%{_bindir}
ln -sr %{buildroot}%{_libexecdir}/aurora-touch-test/aurora-touch-test.py %{buildroot}%{_bindir}/aurora-touch-test

%files
%license COPYING
%doc README.md
%{_bindir}/aurora-touch-test
%{_libexecdir}/aurora-touch-test

%changelog
* Sat Nov 28 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.1.0-1
- Package the guided touchscreen test.
