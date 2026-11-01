# Based on docker/docker-ce-packaging rpm/SPECS/docker-ce.spec (Apache-2.0).
# Build the upstream engine with its vendored dependencies, without fetching
# an untracked tini binary during the build. Fedora supplies tini-static.
# The upstream release build strips DWARF; match Docker CE's RPM recipe.
%global debug_package %{nil}

Name: docker-ce
Epoch: 3
Version: 29.9.2
Release: 1%{?dist}.aurora1
Summary: Docker engine with idempotent permanent firewalld policy setup
License: Apache-2.0 AND BSD-2-Clause AND BSD-3-Clause AND ISC AND MIT AND MPL-2.0 AND (Apache-2.0 OR GPL-2.0-or-later)
URL: https://github.com/moby/moby
Source0: https://github.com/moby/moby/archive/refs/tags/docker-v29.9.2.tar.gz
Patch100: docker-query-forwarding-policy.patch
BuildRequires: gcc gcc-c++ make golang >= 1.26.8 git-core pkgconfig(systemd) nftables-devel go-md2man
BuildRequires: pkgconfig(libsystemd)
BuildRequires: systemd-rpm-macros
Requires: (docker-ce-cli >= 29 or docker-cli >= 29)
Requires: (containerd.io >= 2.1.5 or containerd >= 2.1.5)
Requires: /usr/bin/tini-static
Requires: container-selinux systemd iptables nftables tar xz
Conflicts: moby-engine docker-io docker-ee

%description
The Docker engine and proxy with a permanent-policy existence check before
creating docker-forwarding. Existing policies retain their settings. Docker
and firewalld keep their normal diagnostics and firewall integration.

%prep
%autosetup -n moby-docker-v%{version} -p1

%build
export GOMAXPROCS=8
export GOFLAGS='-mod=vendor -buildvcs=false -p=8'
export DOCKER_GITCOMMIT=0367cbeb49b9d98cb0b4f51e95f7b54b4803e76c
export VERSION=%{version}
export DOCKER_BUILDTAGS='journald'
bash hack/make.sh dynbinary
%make_build -C man GO_MD2MAN=go-md2man

%check
go test -mod=vendor -buildvcs=false -p=8 ./daemon/libnetwork/iptables -run '^TestSetupDockerForwardingPolicy$' -count=1 -v
bundles/dynbinary-daemon/dockerd --version | grep -F 'Docker version %{version}, build 0367cbeb49b9d98cb0b4f51e95f7b54b4803e76c'

%install
install -Dm755 bundles/dynbinary-daemon/dockerd %{buildroot}%{_bindir}/dockerd
install -Dm755 bundles/dynbinary-daemon/docker-proxy %{buildroot}%{_bindir}/docker-proxy
mkdir -p %{buildroot}%{_libexecdir}/docker
ln -s %{_bindir}/tini-static %{buildroot}%{_libexecdir}/docker/docker-init
install -Dm644 contrib/init/systemd/docker.service %{buildroot}%{_unitdir}/docker.service
install -Dm644 contrib/init/systemd/docker.socket %{buildroot}%{_unitdir}/docker.socket
%make_install -C man mandir=%{_mandir} GO_MD2MAN=go-md2man
mkdir -p %{buildroot}%{_datadir}/docker-ce/selinux
install -m644 contrib/selinux/*.cil %{buildroot}%{_datadir}/docker-ce/selinux/
mkdir -p %{buildroot}%{_sysusersdir}
echo 'g docker -' > %{buildroot}%{_sysusersdir}/docker.conf
mkdir -p %{buildroot}%{_sysconfdir}/docker
mkdir -p %{buildroot}%{_licensedir}/%{name}
find vendor -type f \( -iname 'license*' -o -iname 'copying*' -o -iname 'notice*' \) \
    -exec cp --parents -t %{buildroot}%{_licensedir}/%{name} {} +

%post
%systemd_post docker.service docker.socket
if command -v semodule >/dev/null 2>&1 && selinuxenabled 2>/dev/null; then
    for policy in %{_datadir}/docker-ce/selinux/*.cil; do
        semodule -i "$policy" || echo "Unable to install Docker SELinux policy $policy" >&2
    done
fi

%preun
%systemd_preun docker.service docker.socket

%postun
%systemd_postun_with_restart docker.service
if [ "$1" -eq 0 ] && command -v semodule >/dev/null 2>&1 && selinuxenabled 2>/dev/null; then
    semodule -r docker-af-alg-deny docker-af-vsock-deny || :
fi

%files
%license LICENSE NOTICE
%{_licensedir}/%{name}/vendor/
%{_bindir}/dockerd
%{_bindir}/docker-proxy
%{_libexecdir}/docker/docker-init
%{_unitdir}/docker.service
%{_unitdir}/docker.socket
%{_sysusersdir}/docker.conf
%{_mandir}/man*/*
%{_datadir}/docker-ce/selinux/
%dir %{_sysconfdir}/docker

%changelog
* Sat Oct 31 2026 Aurora Silicon <ryan@aurorasilicon.org> - 3:29.9.2-1.aurora1
- Query permanent firewalld policies before creating docker-forwarding.
