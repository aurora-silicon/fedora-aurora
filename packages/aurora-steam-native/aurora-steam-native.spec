# Aurora's Steam: the aurora-steam-native launcher for Valve's native ARM64
# Linux client, plus `steam` so that `dnf install steam` installs it. Valve's
# client is downloaded per user on the first start; nothing from Valve ships.
%global commit c06f610e3604c3f2b1b8466dff60d6878d0cd0da
%global lib %{_libexecdir}/aurora-steam-native
Name: aurora-steam-native
Version: 0
Release: 1.gitc06f610%{?dist}
Summary: Valve's native ARM64 Steam client in a 4 KiB page process tree
License: MIT
URL: https://github.com/aurora-silicon/aurora-steam-native
Source0: aurora-steam-native-%{commit}.tar.gz
Source1: steam
Source2: steam.desktop
BuildArch: noarch
BuildRequires: python3 desktop-file-utils
Requires: aurora-userpages
Requires: python3
# Steam's UI modules link against GTK 2.
Requires: gtk2
# x86 Linux titles run through FEX; their GPU driver is the guest Mesa.
Requires: fex-emu
Recommends: fex-emu-thunks
Recommends: mesa-aurora-fex-guest
Recommends: mesa-vulkan-drivers
# Aurora Play
Recommends: python3-gobject gtk4 libadwaita
Recommends: libnotify

%description
Starts Valve's native ARM64 Linux Steam client through `userpages 4k`, so
Steam, its runtime, Proton, FEX and the games it starts get the 4 KiB pages
they assume on Aurora's 16 KiB page kernels. Includes Aurora Play, a small
launcher for the installed games.

%package -n steam
Summary: Steam for Aurora (native ARM64 client)
Requires: %{name} = %{version}-%{release}

%description -n steam
`steam` for Aurora on Apple Silicon. The first start installs Valve's native
ARM64 Linux client for the current user from Valve's CDN, checked against
Valve's manifest, then starts it in a 4 KiB page process tree. The kernel
must be booted with user4k=on (the default on Aurora images).

%prep
%autosetup -n aurora-steam-native-%{commit}
find . -name __pycache__ -prune -exec rm -rf {} +
sed -e 's,@LIBDIR@,%{lib},' -e 's,@USERPAGES@,%{_bindir}/userpages,' %{SOURCE1} > steam

%build

%install
install -Dm755 install-steam-arm64.py %{buildroot}%{lib}/install-steam-arm64.py
install -Dm755 bin/steam-native4k %{buildroot}%{lib}/bin/steam-native4k
install -Dm755 bin/aurora-play %{buildroot}%{lib}/bin/aurora-play
install -Dm755 libexec/steam-native4k-launch-loop.sh %{buildroot}%{lib}/libexec/steam-native4k-launch-loop.sh
# The installer copies these next to itself when it sets up a user.
install -Dm644 share/applications/steam-native-arm64.desktop %{buildroot}%{lib}/share/applications/steam-native-arm64.desktop
install -Dm644 share/applications/org.aurorasilicon.Play.desktop %{buildroot}%{lib}/share/applications/org.aurorasilicon.Play.desktop
install -Dm644 share/icons/hicolor/scalable/apps/org.aurorasilicon.Play.svg %{buildroot}%{lib}/share/icons/hicolor/scalable/apps/org.aurorasilicon.Play.svg
install -Dm755 steam %{buildroot}%{_bindir}/steam
mkdir -p %{buildroot}%{_bindir}
ln -s ../libexec/aurora-steam-native/bin/aurora-play %{buildroot}%{_bindir}/aurora-play
install -Dm644 %{SOURCE2} %{buildroot}%{_datadir}/applications/steam.desktop
install -Dm644 share/applications/org.aurorasilicon.Play.desktop %{buildroot}%{_datadir}/applications/org.aurorasilicon.Play.desktop
install -Dm644 share/icons/hicolor/scalable/apps/org.aurorasilicon.Play.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/org.aurorasilicon.Play.svg

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/steam.desktop
desktop-file-validate %{buildroot}%{_datadir}/applications/org.aurorasilicon.Play.desktop
bash -n %{buildroot}%{_bindir}/steam
grep -q '^userpages=${AURORA_USERPAGES_LAUNCHER:-%{_bindir}/userpages}$' %{buildroot}%{_bindir}/steam
grep -q '^lib=%{lib}$' %{buildroot}%{_bindir}/steam
for t in tests/test-steam-native4k-launch-env.py tests/test-offline-installer.py tests/test-aurora-play-settings.py; do
  python3 -I "$t"
done

%files
%license LICENSES/MIT.txt
%doc README.md
%{lib}/
%{_bindir}/aurora-play
%{_datadir}/applications/org.aurorasilicon.Play.desktop
%{_datadir}/icons/hicolor/scalable/apps/org.aurorasilicon.Play.svg

%files -n steam
%{_bindir}/steam
%{_datadir}/applications/steam.desktop

%changelog
* Tue Nov 03 2026 Ryan Murray <ryan@aurorasilicon.org> - 0-1.gitc06f610
- Package aurora-steam-native at c06f610 and ship `steam`, which installs
  Valve's native ARM64 client per user and starts it in a 4 KiB page tree.
