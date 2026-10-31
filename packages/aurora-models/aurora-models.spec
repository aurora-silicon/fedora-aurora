Name: aurora-models
Version: 0.1.0
Release: 2%{?dist}
Summary: Explicit first-run fetcher for audited Aurora demo weights
License: MIT
URL: https://github.com/aurora-silicon/fedora-aurora
Source0: aurora-model-fetch
Source1: models.json
Source2: export_rnnoise.py
Source3: LICENSE
Source4: capture-ns-LICENSE
Source5: aurora-model-fetch.1
Source6: models-README
BuildArch: noarch
BuildRequires: python3
Requires: python3

%description
Downloads open RNNoise, DeepFilterNet3 and Whisper weights to a per-user cache
only when requested. Downloads and converted weights are SHA-256 checked
before use. No weights, service or system configuration are installed.

%prep
%build
%install
install -Dm755 %{SOURCE0} %{buildroot}%{_bindir}/aurora-model-fetch
sed -i 's|@DATA@|%{_datadir}/aurora-models|g' %{buildroot}%{_bindir}/aurora-model-fetch
install -Dm644 %{SOURCE1} %{buildroot}%{_datadir}/aurora-models/models.json
install -Dm644 %{SOURCE2} %{buildroot}%{_datadir}/aurora-models/export_rnnoise.py
sed -i '1{/^#!/d;}' %{buildroot}%{_datadir}/aurora-models/export_rnnoise.py
install -Dm644 %{SOURCE5} %{buildroot}%{_mandir}/man1/aurora-model-fetch.1
install -Dm644 %{SOURCE6} %{buildroot}%{_docdir}/%{name}/README
install -Dm644 %{SOURCE3} %{buildroot}%{_licensedir}/%{name}/LICENSE
install -Dm644 %{SOURCE4} %{buildroot}%{_licensedir}/%{name}/capture-ns-LICENSE
%check
python3 -m py_compile %{SOURCE0} %{SOURCE2}
%files
%doc %{_docdir}/%{name}/README
%{_mandir}/man1/aurora-model-fetch.1*
%license %{_licensedir}/%{name}/
%{_bindir}/aurora-model-fetch
%{_datadir}/aurora-models/
%changelog
* Sun Nov 01 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.1.0-2
- Install the serializer as data and document first-run fetching.
* Sat Oct 31 2026 Ryan Murray <ryan@aurorasilicon.org> - 0.1.0-1
- Add first-run downloads with immutable URLs and SHA-256 verification.
