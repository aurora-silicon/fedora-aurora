#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Filter configuration values before retaining or displaying build logs."""
import re
import sys

sensitive = re.compile(
    r'api[-_ ]?key|password|secret|authorization\s*[:=]|[A-Z_]*TOKEN\s*='
    r'|CARGO_PKG_AUTHORS=|https?://[^/\s:@]+:[^/\s@]+@', re.IGNORECASE
)
for line in sys.stdin:
    if sensitive.search(line):
        # Cargo appends the cause after a command containing author/env values.
        # Retain only a narrowly parsed signal or numeric exit code.
        cause = re.search(r"\((?:signal: \d+, SIG[A-Z]+: [a-z ]+|exit status: \d+)\)", line)
        suffix = ' ' + cause.group(0) if cause else ''
        print('[build configuration value omitted]' + suffix, flush=True)
    else:
        print(line.rstrip('\n'), flush=True)
