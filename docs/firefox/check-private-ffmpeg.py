#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compile the actual patched library selector from a Firefox source tree.

Checks selection only, not dlopen, FFmpeg ABI linkage or the RDD sandbox.
"""
import argparse
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("source", type=Path, help="unpatched Firefox 159.0 source root")
args = parser.parse_args()
relative = Path("dom/media/platforms/ffmpeg/FFmpegRuntimeLinker.cpp")
patch = Path(__file__).with_name("0002-opt-in-private-ffmpeg.patch").resolve()
with tempfile.TemporaryDirectory(prefix="firefox-avd-library-") as directory:
    root = Path(directory)
    source = root / relative
    source.parent.mkdir(parents=True)
    source.write_bytes((args.source / relative).read_bytes())
    subprocess.run(["git", "-C", str(root), "apply", str(patch)], check=True)
    text = source.read_text()
    start = text.index("#if defined(MOZ_WIDGET_GTK) && defined(__aarch64__)")
    end = text.index("\n/* static */", start)
    declarations = text[start:end]
    start = text.index('  const char* avdFFmpeg = PR_GetEnv("MOZ_AVD_FFMPEG");')
    start = text.rfind("#if", 0, start)
    end = text.index("    PRLibSpec lspec;", start)
    selector = text[start:end]
    program = r'''
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>
#ifdef __aarch64__
#undef __aarch64__
#endif
#if TEST_AARCH64
#define __aarch64__ 1
#endif
#define MOZ_WIDGET_GTK 1
#define FFMPEG_MAX_MAJOR_VERSION 63
#define FFMPEG_MAX_MAJOR_VERSION_STR_INNER(x) #x
#define FFMPEG_MAX_MAJOR_VERSION_STR(x) FFMPEG_MAX_MAJOR_VERSION_STR_INNER(x)
static const char* env_value;
[[maybe_unused]] static const char* PR_GetEnv(const char* key) {
  assert(std::string(key) == "MOZ_AVD_FFMPEG"); return env_value;
}
''' + declarations + '''
static std::vector<std::string> Candidates(const char* value) {
  env_value = value;
  std::vector<std::string> selected;
''' + selector + '''
    selected.emplace_back(lib);
  }
  return selected;
}
int main() {
  const std::string private_library = "/usr/lib64/aurora-avd/libavcodec.so.62";
  const auto normal = Candidates(nullptr);
  assert(!normal.empty() && normal.front() == "libavcodec.so.63");
  for (const auto& library : normal) assert(library != private_library);
  for (const char* value : {"", "0", "yes", "true", "11", "1extra"}) {
    assert(Candidates(value) == normal);
  }
#if TEST_AARCH64
  const std::vector<std::string> only_private = {private_library};
  assert(Candidates("1") == only_private);
#else
  assert(Candidates("1") == normal);
#endif
  puts("8 actual library-selector cases passed");
}
'''
    (root / "selector.cc").write_text(program)
    for arch in (0, 1):
        binary = root / f"selector-{arch}"
        subprocess.run(["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                        f"-DTEST_AARCH64={arch}", str(root / "selector.cc"),
                        "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
