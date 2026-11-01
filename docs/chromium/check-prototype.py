#!/usr/bin/env python3
"""Compile the actual prototype helper with Linux UAPI and mocked OS calls.

This does not compile Chromium or validate its real brokers or seccomp policy.
"""
from pathlib import Path
import os
import subprocess
import tempfile

patch = Path(__file__).with_name(
    "0001-linux-stateless-decoder-broker-prototype.patch").read_text()
section = patch.split("+++ b/sandbox/policy/linux/v4l2_request_decoder_paths.h\n", 1)[1]
header = "".join(line[1:] for line in section.splitlines(True)
                 if line.startswith("+"))
test = r'''
#include <fcntl.h>
#include <linux/media.h>
#include <linux/videodev2.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <unistd.h>
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <utility>
#include <vector>

struct Fixture {
  bool video_open = true, media_open = true, character = true;
  bool stat_ok = true, querycap_ok = true, enum_ok = true;
  bool legacy_caps = false, stream = true, m2m = true, endless_formats = false;
  uint32_t format = V4L2_PIX_FMT_H264_SLICE;
  uint32_t first_count = 1, second_count = 1, minor = 0;
  uint32_t intf_type = MEDIA_INTF_T_V4L_VIDEO;
  uint64_t second_version = 4;
  int fail_topology = 0, topology_calls = 0;
  int video_probes = 0, media_probes = 0, formats = 0, live = 0;
} f;

static int MockOpen(const char* path, int flags) {
  assert(flags & O_NOFOLLOW); assert(flags & O_CLOEXEC);
  assert(flags & O_NONBLOCK); assert((flags & O_ACCMODE) == O_RDWR);
  if (strncmp(path, "/dev/video", 10) == 0) {
    ++f.video_probes;
    if (std::string(path) == "/dev/video0" && f.video_open) {
      ++f.live; return 10;
    }
  } else {
    assert(strncmp(path, "/dev/media", 10) == 0);
    ++f.media_probes;
    if (std::string(path) == "/dev/media0" && f.media_open) {
      ++f.live; return 20;
    }
  }
  return -1;
}
static int MockClose(int fd) {
  assert(fd == 10 || fd == 20); --f.live; return 0;
}
static int MockFstat(int fd, struct stat* st) {
  assert(fd == 10 || fd == 20);
  *st = {}; st->st_mode = f.character ? S_IFCHR : S_IFREG;
  st->st_rdev = makedev(81, 0); return f.stat_ok ? 0 : -1;
}
static int MockIoctl(int fd, unsigned long request, void* arg) {
  if (request == VIDIOC_QUERYCAP) {
    assert(fd == 10);
    auto* cap = static_cast<v4l2_capability*>(arg);
    uint32_t caps = (f.stream ? V4L2_CAP_STREAMING : 0) |
                   (f.m2m ? V4L2_CAP_VIDEO_M2M_MPLANE : V4L2_CAP_VIDEO_CAPTURE_MPLANE);
    cap->capabilities = f.legacy_caps ? caps : V4L2_CAP_DEVICE_CAPS;
    cap->device_caps = f.legacy_caps ? 0 : caps;
    return f.querycap_ok ? 0 : -1;
  }
  if (request == VIDIOC_ENUM_FMT) {
    assert(fd == 10);
    auto* fmt = static_cast<v4l2_fmtdesc*>(arg);
    assert(fmt->type == V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE);
    ++f.formats;
    if (!f.enum_ok || (fmt->index > 0 && !f.endless_formats)) return -1;
    fmt->pixelformat = f.format; return 0;
  }
  assert(fd == 20 && request == MEDIA_IOC_G_TOPOLOGY);
  auto* topology = static_cast<media_v2_topology*>(arg);
  ++f.topology_calls;
  if (f.topology_calls == f.fail_topology) return -1;
  if (f.topology_calls == 1) {
    topology->num_interfaces = f.first_count; topology->topology_version = 4;
  } else {
    auto* interfaces = reinterpret_cast<media_v2_interface*>(topology->ptr_interfaces);
    // Emulate the UAPI's bounded copy even if the returned count grows.
    for (uint32_t i = 0; i < std::min(topology->num_interfaces, f.second_count); ++i) {
      interfaces[i] = {}; interfaces[i].intf_type = f.intf_type;
      interfaces[i].devnode.major = 81; interfaces[i].devnode.minor = f.minor;
    }
    topology->num_interfaces = f.second_count;
    topology->topology_version = f.second_version;
  }
  return 0;
}
#define open MockOpen
#define close MockClose
#define fstat MockFstat
#define ioctl MockIoctl
#include "helper.h"
#undef open
#undef close
#undef fstat
#undef ioctl

static int cases = 0;
static void Check(bool allowed) {
  std::vector<std::string> paths;
  sandbox::policy::AddV4L2RequestDecoderPaths(
      [&](const std::string& path) { paths.push_back(path); });
  const std::vector<std::string> expected = {"/dev/video0", "/dev/media0"};
  assert(paths == (allowed ? expected : std::vector<std::string>{}));
  assert(f.live == 0); assert(f.video_probes == 256);
  assert(f.media_probes == 0 || f.media_probes == 10);
  ++cases;
}
int main() {
  f = {}; Check(true);
  f = {}; f.legacy_caps = true; Check(true);
  for (auto format : {V4L2_PIX_FMT_HEVC_SLICE, V4L2_PIX_FMT_VP9_FRAME,
                      V4L2_PIX_FMT_AV1_FRAME}) {
    f = {}; f.format = format; Check(true);
  }
  f = {}; f.video_open = false; Check(false);
  f = {}; f.media_open = false; Check(false);
  f = {}; f.character = false; Check(false);
  f = {}; f.stat_ok = false; Check(false);
  f = {}; f.querycap_ok = false; Check(false);
  f = {}; f.enum_ok = false; Check(false);
  f = {}; f.stream = false; Check(false);
  f = {}; f.m2m = false; Check(false); // capture-only camera
  f = {}; f.format = V4L2_PIX_FMT_H264; Check(false); // stateful, not this proposal
  f = {}; f.format = 0; f.endless_formats = true; Check(false); assert(f.formats == 128);
  f = {}; f.first_count = 0; Check(false);
  f = {}; f.first_count = 257; Check(false);
  f = {}; f.first_count = 256; f.second_count = 256; f.minor = 1; Check(false);
  f = {}; f.second_count = 2; Check(false);
  f = {}; f.second_count = 0; Check(false);
  f = {}; f.second_version = 5; Check(false);
  f = {}; f.fail_topology = 1; Check(false);
  f = {}; f.fail_topology = 2; Check(false);
  f = {}; f.minor = 1; Check(false); // unrelated camera media controller
  f = {}; f.intf_type = MEDIA_INTF_T_V4L_SUBDEV; Check(false);
  printf("%d prototype fixtures passed\n", cases);
}
'''
with tempfile.TemporaryDirectory(prefix="chromium-v4l2-prototype-") as directory:
    root = Path(directory)
    (root / "helper.h").write_text(header)
    (root / "check.cc").write_text(test)
    compiler = os.environ.get("CXX", "c++")
    for flags, name in [([], "check"),
                        (["-fsanitize=address,undefined", "-fno-omit-frame-pointer"],
                         "check-sanitized")]:
        subprocess.run([compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror",
                        *flags, str(root / "check.cc"), "-o", str(root / name)], check=True)
        subprocess.run([str(root / name)], check=True)
