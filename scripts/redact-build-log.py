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
    print('[build configuration value omitted]' if sensitive.search(line)
          else line.rstrip('\n'), flush=True)
