Name: aurora-platform
Version: 44
Release: 2%{?dist}
Summary: Aurora Apple Silicon hardware stack
License: MIT
URL: https://github.com/aurora-silicon/fedora-aurora
BuildArch: noarch
Provides: asahi-platform-metapackage
Conflicts: asahi-platform-metapackage
Requires: aurora-firstboot
Requires: kernel-aurora aura uboot-aurora aurora-release aurora-logos aurora-firmware aurora-audio alsa-ucm-conf-aurora speakerguardd speakersafetyd aurora-bless aurora-neo-platform-config asahi-fwupdate dracut-asahi update-m1n1 tiny-dfr

Source100: README

%description
Aurora Apple Silicon hardware stack.

%prep

%build

%install
install -Dm644 %{_sourcedir}/README %{buildroot}%{_docdir}/aurora-platform/README

%files
%{_docdir}/aurora-platform/

%changelog
* Sun Oct 18 2026 Aurora Silicon <hey@djdev.me> - 1
- Initial Fedora Aurora package.
