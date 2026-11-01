#!/usr/bin/env python3
"""Compile ABRT's actual startup scanner with report-I/O stubs.

Exercise directory traversal and the publication boundary without a system
daemon, a real crash, root privileges, or access to any host crash reports.
"""
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

source = Path(sys.argv[1]).read_text()
start = source.index("static void mark_unprocessed_dump_dirs_not_reportable(")
body = source.index("{", start)
depth = 1
end = body + 1
while depth:
    depth += (source[end] == "{") - (source[end] == "}")
    end += 1
scanner = source[start:end]
prefix = r'''
#include <assert.h>
#include <dirent.h>
#include <glib.h>
#include <limits.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#define FILENAME_COUNT "count"
#define FILENAME_NOT_REPORTABLE "not-reportable"
#define _(s) (s)
static int opened, marked, unfinished, errors;
#define log_notice(...) do { if (strstr(#__VA_ARGS__, "Preserving")) unfinished++; } while (0)
#define log_warning(...) ((void)0)
#define perror_msg(...) do { errors++; } while (0)
static bool libreport_dot_or_dotdot(const char *s) { return !strcmp(s, ".") || !strcmp(s, ".."); }
struct dump_dir { char path[PATH_MAX]; };
static struct dump_dir *dd_opendir(const char *path, int flags) {
    (void)flags;
    static struct dump_dir dd;
    opened++;
    snprintf(dd.path, sizeof(dd.path), "%s", path);
    char *time = g_build_filename(path, "time", NULL);
    bool exists = access(time, F_OK) == 0;
    g_free(time);
    if (!exists) { errors++; return NULL; }
    return &dd;
}
static bool dd_exist(struct dump_dir *dd, const char *item) {
    char *path = g_build_filename(dd->path, item, NULL);
    bool exists = access(path, F_OK) == 0;
    g_free(path);
    return exists;
}
static bool problem_dump_dir_is_complete(struct dump_dir *dd) { return dd_exist(dd, FILENAME_COUNT); }
static void dd_save_text(struct dump_dir *dd, const char *item, const char *text) {
    char *path = g_build_filename(dd->path, item, NULL);
    assert(g_file_set_contents(path, text, -1, NULL));
    marked++;
    g_free(path);
}
static void dd_close(struct dump_dir *dd) { (void)dd; }
'''
suffix = r'''
int main(int argc, char **argv) {
    assert(argc == 2);
    mark_unprocessed_dump_dirs_not_reportable(argv[1]);
    assert(opened == 3); /* complete, incomplete, previously marked */
    assert(marked == 1); /* only the published incomplete report */
    assert(unfinished == 3); /* active, interrupted and vanished producers */
    assert(errors == 0);

    char *staging = g_build_filename(argv[1], "live.new", NULL);
    char *published = g_build_filename(argv[1], "published", NULL);
    assert(rename(staging, published) == 0);
    g_free(staging); g_free(published);
    opened = marked = unfinished = errors = 0;
    mark_unprocessed_dump_dirs_not_reportable(argv[1]);
    assert(opened == 4 && marked == 1 && unfinished == 2 && errors == 0);

    /* An invalid published directory must still be diagnosed. */
    char *invalid = g_build_filename(argv[1], "invalid", NULL);
    assert(mkdir(invalid, 0700) == 0);
    g_free(invalid);
    opened = marked = unfinished = errors = 0;
    mark_unprocessed_dump_dirs_not_reportable(argv[1]);
    assert(opened == 5 && marked == 0 && unfinished == 2 && errors == 1);
    puts("ABRT staging scan: PASS (preservation, publication, complete/incomplete and invalid reports)");
    return 0;
}
'''
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    spool = root / "spool"
    spool.mkdir()
    fixtures = {
        "complete": {"time": b"1", "count": b"1"},
        "incomplete": {"time": b"2"},
        "marked": {"time": b"3", "not-reportable": b"existing reason"},
        "live.new": {"time": b"4", "partial": b"preserve live bytes"},
        "orphan.new": {"partial": b"preserve interrupted bytes"},
    }
    for name, items in fixtures.items():
        (spool / name).mkdir(mode=0o700)
        for item, data in items.items():
            (spool / name / item).write_bytes(data)
    (spool / "auxiliary-file").write_text("not a report")
    # A vanished producer must not make the scanner stat an unpublished name.
    (spool / "vanished.new").symlink_to("missing-staging-directory")
    harness = root / "scan.c"
    harness.write_text(prefix + scanner + suffix)
    flags = shlex.split(subprocess.check_output(
        ["pkg-config", "--cflags", "--libs", "glib-2.0"], text=True))
    subprocess.run([os.environ.get("CC", "cc"), "-Wall", "-Wextra", "-Werror",
                    str(harness), "-o", str(root / "scan"), *flags], check=True)
    subprocess.run([str(root / "scan"), str(spool)], check=True)
    for name in ("live.new", "orphan.new"):
        actual = spool / ("published" if name == "live.new" else name)
        expected = dict(fixtures[name])
        if name == "live.new":
            expected["not-reportable"] = (actual / "not-reportable").read_bytes()
        assert {p.name: p.read_bytes() for p in actual.iterdir()} == expected
        assert actual.stat().st_mode & 0o777 == 0o700
    assert (spool / "marked/not-reportable").read_bytes() == b"existing reason"
    assert (spool / "vanished.new").is_symlink()
