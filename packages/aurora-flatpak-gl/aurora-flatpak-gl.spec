# Aurora's Mesa for Flatpak apps.
#
# Flatpak apps load OpenGL and Vulkan from the runtime's GL extension, not from
# the system, so without this they run Flathub's GL.default Mesa. This package
# carries org.freedesktop.Platform.GL.aurora (built by build-extension.sh
# from the same Mesa commit as mesa-aurora) as a local OSTree repository,
# installs it into the system Flatpak installation and enables it ahead of
# GL.default. Removing the package removes the extension and the settings, and
# apps go back to GL.default.
#
# The repository is not built here: build it with build-extension.sh (next to
# this file) for each runtime branch, tar it as Source10 and build with --with repo.
# Without it the package carries only the settings, which change nothing until
# GL.aurora is installed.
%bcond repo 0
%global mesa_commit 473e325b4f50d01d9716fe276bfdce57d0a76ca7
%global mesa_short 473e325b4f50
%global debug_package %{nil}
%global __requires_exclude_from ^%{_datadir}/aurora-flatpak-gl/
%global __provides_exclude_from ^%{_datadir}/aurora-flatpak-gl/
Name: aurora-flatpak-gl
Version: 26.3.0
Release: 0.1.%{mesa_short}%{?dist}
Summary: Aurora Mesa for Flatpak apps
License: MIT
URL: https://github.com/aurora-silicon/fedora-aurora
Source0: aurora-flatpak-gl
Source1: 60-aurora-flatpak-gl.conf
Source2: aurora-flatpak-gl.sh
%if %{with repo}
Source10: aurora-flatpak-gl-repo-%{mesa_short}.tar
%endif
ExclusiveArch: aarch64
Requires: flatpak

%description
Installs org.freedesktop.Platform.GL.aurora, Aurora's Mesa built for the
Freedesktop Flatpak runtimes, and enables it for every Flatpak app ahead of
Flathub's GL.default. Apps then get the same Asahi Gallium and Honeykrisp
drivers as the rest of the system. Runtime branches without a GL.aurora build
keep using GL.default.

%prep

%build

%install
install -Dm755 %{SOURCE0} %{buildroot}%{_libexecdir}/aurora-flatpak-gl/aurora-flatpak-gl
install -Dm644 %{SOURCE1} %{buildroot}%{_prefix}/lib/environment.d/60-aurora-flatpak-gl.conf
install -Dm644 %{SOURCE2} %{buildroot}%{_sysconfdir}/profile.d/aurora-flatpak-gl.sh
install -d %{buildroot}%{_datadir}/aurora-flatpak-gl
%if %{with repo}
tar -xf %{SOURCE10} -C %{buildroot}%{_datadir}/aurora-flatpak-gl
test -d %{buildroot}%{_datadir}/aurora-flatpak-gl/repo/objects
%endif

%posttrans
%{_libexecdir}/aurora-flatpak-gl/aurora-flatpak-gl enable >/dev/null || :

%preun
if [ $1 -eq 0 ]; then
    %{_libexecdir}/aurora-flatpak-gl/aurora-flatpak-gl disable >/dev/null || :
fi

%files
%{_libexecdir}/aurora-flatpak-gl/
%{_prefix}/lib/environment.d/60-aurora-flatpak-gl.conf
%config(noreplace) %{_sysconfdir}/profile.d/aurora-flatpak-gl.sh
%{_datadir}/aurora-flatpak-gl/

%changelog
* Thu Oct 29 2026 Aurora Silicon <hey@djdev.me> - 26.3.0-0.1.473e325b4f50
- Initial package: GL.aurora for the 25.08 and 26.08 runtimes from Mesa
  473e325b4f50.
