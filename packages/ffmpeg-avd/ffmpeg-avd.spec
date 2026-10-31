# Bound compile/link jobs in the controller slot.
%global _lto_cflags %{nil}
%global request_commit b57fbbe50c9b2656fad86a1a7eeabfd2b2a50935
%global mpv_commit 41f6a645068483470267271e1d09966ca3b9f413
%global private_libdir %{_libdir}/aurora-avd
# Private ABI: do not satisfy another application's FFmpeg dependencies.
%global __provides_exclude_from ^%{private_libdir}/.*$
%global __requires_exclude ^lib(avcodec|avdevice|avfilter|avformat|avutil|swresample|swscale)\\.so.*$

Name: ffmpeg-avd
Version: 8.1
Release: 1%{?dist}
Summary: Isolated FFmpeg with the public V4L2 Request API hwaccels
License: LGPL-2.1-or-later AND GPL-2.0-or-later
URL: https://github.com/Kwiboo/FFmpeg
Source0: https://ffmpeg.org/releases/ffmpeg-%{version}.tar.xz
Source1: https://github.com/mpv-player/mpv/archive/%{mpv_commit}.tar.gz#/mpv-%{mpv_commit}.tar.gz
Patch0: 0001-v4l2request-n8.1.patch
Patch1: 0002-mpv-request-drm-import.patch
ExclusiveArch: aarch64
BuildRequires: gcc gcc-c++ make meson ninja-build pkgconf-pkg-config
BuildRequires: kernel-headers >= 6.5
BuildRequires: pkgconfig(libdrm) pkgconfig(libudev) pkgconfig(libva)
BuildRequires: pkgconfig(libplacebo) pkgconfig(egl) pkgconfig(gl)
BuildRequires: pkgconfig(wayland-client) pkgconfig(wayland-cursor) pkgconfig(wayland-egl)
BuildRequires: wayland-protocols-devel pkgconfig(xkbcommon)
BuildRequires: pkgconfig(lcms2) pkgconfig(libass) pkgconfig(luajit)
BuildRequires: pkgconfig(zlib) pkgconfig(gnutls) pkgconfig(dav1d)
BuildRequires: pkgconfig(libpulse) pkgconfig(alsa)
BuildRequires: python3

%description
FFmpeg 8.1 with Jonas Karlman's 13-commit V4L2 Request API series,
including H.264, HEVC, VP9 and AV1. The ffmpeg-avd command and private
libraries coexist with system FFmpeg. No system library or configuration
is replaced. This is a qualification build, not a hardware support claim.

%package -n mpv-avd
Summary: Separate mpv linked to the private Request API FFmpeg
Requires: ffmpeg-avd%{?_isa} = %{version}-%{release}

%description -n mpv-avd
mpv with the normal --hwdec=v4l2request and v4l2request-copy options,
linked to the matching private FFmpeg. The system mpv remains available.

%prep
%autosetup -n ffmpeg-%{version} -N
%patch -P 0 -p1
# Source1 is pinned separately because mpv must see the patched hwdevice API.
tar -xf %{SOURCE1}
pushd mpv-%{mpv_commit}
%patch -P 1 -p1
popd

%build
%set_build_flags
./configure --prefix=%{_prefix} --bindir=%{_bindir} \
  --libdir=%{private_libdir} --incdir=%{_includedir}/aurora-avd \
  --disable-static --enable-shared --enable-pic --disable-stripping \
  --disable-debug --disable-doc --disable-ffplay --disable-autodetect \
  --enable-v4l2-request --enable-libdrm --enable-libudev --enable-vaapi \
  --enable-gnutls --enable-libdav1d --enable-zlib \
  --extra-cflags="$CFLAGS" --extra-ldflags="$LDFLAGS -Wl,-rpath,%{private_libdir}"
%make_build
# Stage headers and link libraries for mpv only; no development ABI is shipped.
make DESTDIR="$PWD/stage" install
stage=$PWD/stage
for pc in "$stage%{private_libdir}/pkgconfig/"*.pc; do
  sed -i "s|^prefix=.*|prefix=$stage%{_prefix}|; s|^libdir=.*|libdir=$stage%{private_libdir}|; s|^includedir=.*|includedir=$stage%{_includedir}/aurora-avd|" "$pc"
done
export PKG_CONFIG_PATH="$stage%{private_libdir}/pkgconfig"
meson setup mpv-build mpv-%{mpv_commit} --prefix=%{_prefix} --libdir=%{_libdir} \
  --buildtype=plain --wrap-mode=nodownload -Dlibmpv=false \
  -Dmanpage-build=disabled -Dvaapi=enabled -Ddrm=enabled \
  -Dwayland=enabled -Dgl=enabled -Degl=enabled \
  -Dc_link_args="$LDFLAGS -Wl,-rpath,%{private_libdir}"
meson compile -C mpv-build %{?_smp_mflags}

%install
mkdir -p %{buildroot}%{private_libdir} %{buildroot}%{_bindir}
cp -a stage%{private_libdir}/lib*.so* %{buildroot}%{private_libdir}/
install -m755 ffmpeg %{buildroot}%{_bindir}/ffmpeg-avd
install -m755 ffprobe %{buildroot}%{_bindir}/ffprobe-avd
# Meson installation removes its temporary build-library RUNPATH entries.
meson install -C mpv-build --destdir "$PWD/mpv-stage"
install -m755 mpv-stage%{_bindir}/mpv %{buildroot}%{_bindir}/mpv-avd
# Unversioned links are needed only when compiling mpv.
find %{buildroot}%{private_libdir} -name '*.so' -type l -delete

%check
export LD_LIBRARY_PATH="$PWD/stage%{private_libdir}"
./ffmpeg -hide_banner -hwaccels > hwaccels.txt
cat hwaccels.txt
grep -qx v4l2request hwaccels.txt
for codec in H264 HEVC VP9 AV1; do
  grep -q "#define CONFIG_${codec}_V4L2REQUEST_HWACCEL 1" config_components.h
done
mpv-build/mpv --no-config --hwdec=help > mpv-hwdec.txt
cat mpv-hwdec.txt
grep -q v4l2request mpv-hwdec.txt

%files
%license COPYING.LGPLv2.1
%{_bindir}/ffmpeg-avd
%{_bindir}/ffprobe-avd
%dir %{private_libdir}
%{private_libdir}/lib*.so.*

%files -n mpv-avd
%license mpv-%{mpv_commit}/Copyright mpv-%{mpv_commit}/LICENSE.GPL
%{_bindir}/mpv-avd

%changelog
* Sat Oct 31 2026 Aurora contributors <noreply@aurora-silicon.org> - 8.1-1
- Isolate the public request hwaccels and matching mpv from system FFmpeg
