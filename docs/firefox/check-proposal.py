#!/usr/bin/env python3
"""Exercise the proposal's actual topology helper with Linux UAPI and mocked OS calls.

This is not a complete Firefox compile or a broker/seccomp integration test.
"""
from pathlib import Path
import re
import subprocess
import tempfile

patch = Path(__file__).with_name('0001-rdd-v4l2-request-proposal.patch').read_text()
added = ''.join(line[1:] for line in patch.splitlines(True)
                if line.startswith('+') and not line.startswith('+++'))
helper = re.search(r'static void AddV4l2RequestMediaDevices\(.*?\n}\n', added, re.S)
if not helper:
    raise SystemExit('cannot extract proposed production helper')
preamble = r'''
#include <linux/media.h>
#include <dirent.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <algorithm>
#include <cassert>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <string>
#include <utility>
#include <vector>
static const int rdonly = 1, rdwr = 3;
struct nsPrintfCString {
  std::string text;
  nsPrintfCString(const char* fmt, ...) {
    char buf[512]; va_list ap; va_start(ap, fmt);
    vsnprintf(buf, sizeof(buf), fmt, ap); va_end(ap); text = buf;
  }
  const char* get() const { return text.c_str(); }
};
template<class T> struct nsTArray : std::vector<T> {
  bool IsEmpty() const { return this->empty(); }
  bool Contains(T value) const {
    return std::find(this->begin(), this->end(), value) != this->end();
  }
};
// Mozilla's deleter is default-constructible; provide the equivalent shim.
struct Free { void operator()(char* p) const { free(p); } };
template<class T> using UniqueFreePtr = std::unique_ptr<T, Free>;
template<class T> auto MakeUnique(size_t count) { return std::make_unique<T>(count); }
namespace SandboxBroker {
struct Policy {
  std::vector<std::pair<int, std::string>> paths;
  void AddPath(int perms, const char* path) { paths.emplace_back(perms, path); }
};
}
struct Fixture {
  std::string name = "media0";
  uint32_t firstCount = 1, secondCount = 1;
  uint64_t firstVersion = 4, secondVersion = 4;
  int ioctlFailure = 0, queries = 0, opens = 0, closes = 0;
  bool openFailure = false, statFailure = false, character = true, read = false;
  uint32_t interfaceType = MEDIA_INTF_T_V4L_VIDEO, deviceMajor = 81, deviceMinor = 0;
} f;
static DIR* TestOpenDir(const char*) { return reinterpret_cast<DIR*>(1); }
static dirent* TestReadDir(DIR*) {
  static dirent entry;
  if (f.read) return nullptr;
  f.read = true; memset(&entry, 0, sizeof(entry));
  strncpy(entry.d_name, f.name.c_str(), sizeof(entry.d_name) - 1);
  return &entry;
}
static int TestCloseDir(DIR*) { return 0; }
static int TestOpen(const char*, int flags) {
  ++f.opens;
  assert(flags & O_NOFOLLOW); assert(flags & O_CLOEXEC);
  return f.openFailure ? -1 : 7;
}
static int TestClose(int fd) { assert(fd == 7); ++f.closes; return 0; }
static int TestStat(int fd, struct stat* st) {
  assert(fd == 7); memset(st, 0, sizeof(*st));
  st->st_mode = f.character ? S_IFCHR : S_IFREG;
  return f.statFailure ? -1 : 0;
}
static int TestIoctl(int fd, unsigned long request, void* arg) {
  assert(fd == 7); assert(request == MEDIA_IOC_G_TOPOLOGY);
  ++f.queries;
  if (f.queries == f.ioctlFailure) return -1;
  auto* topology = static_cast<media_v2_topology*>(arg);
  if (f.queries == 1) {
    topology->num_interfaces = f.firstCount;
    topology->topology_version = f.firstVersion;
  } else {
    auto* interfaces = reinterpret_cast<media_v2_interface*>(topology->ptr_interfaces);
    for (uint32_t i = 0; i < std::min(topology->num_interfaces, f.secondCount); ++i) {
      interfaces[i] = {}; interfaces[i].intf_type = f.interfaceType;
      interfaces[i].devnode.major = f.deviceMajor;
      interfaces[i].devnode.minor = f.deviceMinor;
    }
    topology->num_interfaces = f.secondCount;
    topology->topology_version = f.secondVersion;
  }
  return 0;
}
static char* TestRealpath(const char*, char*) { return strdup("/canonical/video0/uevent"); }
#define opendir TestOpenDir
#define readdir TestReadDir
#define closedir TestCloseDir
#define open TestOpen
#define close TestClose
#define fstat TestStat
#define ioctl TestIoctl
#define realpath TestRealpath
'''
tests = r'''
static void Check(bool expected, bool admitted = true) {
  nsTArray<dev_t> devices;
  if (admitted) devices.push_back(makedev(81, 0));
  SandboxBroker::Policy policy;
  AddV4l2RequestMediaDevices(&policy, devices);
  if (!expected) { assert(policy.paths.empty()); return; }
  const std::vector<std::pair<int, std::string>> wanted = {
    {rdonly, "/sys/dev/char/81:0/uevent"},
    {rdonly, "/canonical/video0/uevent"}, {rdwr, "/dev/media0"}};
  assert(policy.paths == wanted); assert(f.closes == 1);
}
int main() {
  f = {}; Check(true);
  f = {}; Check(false, false); assert(f.opens == 0);
  f = {}; f.deviceMinor = 1; Check(false); // unrelated/camera controller
  f = {}; f.interfaceType = MEDIA_INTF_T_V4L_SUBDEV; Check(false);
  f = {}; f.firstCount = 0; Check(false);
  f = {}; f.firstCount = 257; Check(false);
  f = {}; f.secondVersion = 5; Check(false);
  f = {}; f.secondCount = 2; Check(false);
  f = {}; f.secondCount = 0; Check(false);
  f = {}; f.character = false; Check(false);
  f = {}; f.statFailure = true; Check(false);
  f = {}; f.openFailure = true; Check(false);
  f = {}; f.ioctlFailure = 1; Check(false);
  f = {}; f.ioctlFailure = 2; Check(false);
  f = {}; f.name = "media"; Check(false); assert(f.opens == 0);
  f = {}; f.name = "media0suffix"; Check(false); assert(f.opens == 0);
  puts("16 production topology-helper fixtures passed");
}
'''
with tempfile.TemporaryDirectory() as directory:
    source = Path(directory) / 'topology.cpp'
    binary = Path(directory) / 'topology-test'
    source.write_text(preamble + helper.group() + tests)
    subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                    str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
