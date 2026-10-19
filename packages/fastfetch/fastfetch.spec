%global commit 1c1136ebd1e943d6d2ba7c204a11deee3e948dd8
Name:           fastfetch
Version:        2.68.1
Release:        2%{?dist}.aurora
Summary:        Fast neofetch-like system information tool

License:        MIT
URL:            https://github.com/fastfetch-cli/fastfetch
Source0:        fastfetch-%{commit}.tar.gz
Patch0:         0001-recognize-a18-pro.patch

BuildRequires:  cmake
BuildRequires:  python3
BuildRequires:  gcc
BuildRequires:  hwdata-devel
BuildRequires:  wayland-devel
BuildRequires:  libXrandr-devel
BuildRequires:  dconf-devel
BuildRequires:  dbus-devel
BuildRequires:  sqlite-devel
BuildRequires:  ImageMagick-devel
BuildRequires:  zlib-devel
BuildRequires:  libglvnd-devel
BuildRequires:  mesa-libGL-devel
BuildRequires:  glib2-devel
BuildRequires:  ocl-icd-devel
BuildRequires:  rpm-devel
BuildRequires:  libdrm-devel
BuildRequires:  pulseaudio-libs-devel
BuildRequires:  elfutils-libelf-devel
# not available on s390x
%if "%{_arch}" != "s390x"
BuildRequires:  libddcutil-devel
%endif
# vulkan-loader not available in el8 on some arches
%if 0%{?rhel} == 8
  %if "%{_arch}" != "s390x" && "%{_arch}" != "ppc64le"
BuildRequires:  vulkan-loader-devel
  %endif
%else
BuildRequires:  vulkan-loader-devel
%endif
BuildRequires:  chafa-devel
BuildRequires:  yyjson-devel
%if 0%{?fedora} || 0%{?rhel} < 10
BuildRequires:  efl-devel
%endif
BuildRequires:  libva-devel
BuildRequires:  libvdpau-devel
BuildRequires:  lua-devel

Recommends:     hwdata
Suggests:       libXrandr
Suggests:       dconf
Suggests:       sqlite-libs
Suggests:       zlib
Suggests:       libglvnd-glx
Suggests:       ImageMagick-libs
Suggests:       glib2
Suggests:       ocl-icd
Suggests:       chafa-libs
Suggests:       libddcutil
Suggests:       libdrm
Suggests:       pulseaudio-libs
Suggests:       elfutils-libelf

# The shell completion files were previously provided as separate subpackages
# which depended on their respective shell.  That was necessary to avoid the
# parent directories of the completion files from being unowned.  However, the
# filesystem package now owns those directories, so the separate subpackages
# are no longer necessary.
Provides:       fastfetch-bash-completion = %{version}%{release}
Provides:       fastfetch-zsh-completion = %{version}%{release}
Provides:       fastfetch-fish-completion = %{version}%{release}
Obsoletes:      fastfetch-bash-completion < 2.31.0-2
Obsoletes:      fastfetch-zsh-completion < 2.31.0-2
Obsoletes:      fastfetch-fish-completion < 2.31.0-2

ExcludeArch:    %{ix86}

%description
fastfetch is a neofetch-like tool for fetching system information and
displaying them in a pretty way. It is written in c to achieve much better
performance, in return only Linux and Android are supported. It also uses
mechanisms like multithreading and caching to finish as fast as possible.


%prep
%autosetup -n fastfetch-%{commit} -p1


%build
%cmake -DBUILD_TESTS=ON -DENABLE_SYSTEM_YYJSON=ON -DBUILD_FLASHFETCH=OFF
%cmake_build


%check
%ctest


%install
%cmake_install


%files
%license LICENSE
%doc README.md
%{_bindir}/%{name}
%{_datadir}/%{name}/
%{_mandir}/man1/fastfetch.1*
%{_datadir}/bash-completion/completions/%{name}
%{_datadir}/fish/vendor_completions.d/%{name}.fish
%{_datadir}/zsh/site-functions/_%{name}


%changelog
* Mon Oct 19 2026 Aurora Silicon <hey@djdev.me> - 2.68.1-2.aurora
- Backport A18 Pro chip naming for CPU and Asahi GPU detection
