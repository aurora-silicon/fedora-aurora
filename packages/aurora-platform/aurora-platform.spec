Name: aurora-platform
Version: 44
Release: 6%{?dist}
Summary: Aurora Apple Silicon hardware stack
License: MIT
URL: https://github.com/aurora-silicon/fedora-aurora
BuildArch: noarch
Provides: asahi-platform-metapackage
Conflicts: asahi-platform-metapackage
Requires: fastfetch >= 2.68.1-2
Requires: linux-firmware amd-gpu-firmware intel-gpu-firmware nvidia-gpu-firmware
Requires: iwlwifi-dvm-firmware iwlwifi-mvm-firmware realtek-firmware
Requires: aurora-sep libfprint(aurora-sep) = 4
Requires: aurora-firstboot avd-fw upower >= 1.91.4
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
