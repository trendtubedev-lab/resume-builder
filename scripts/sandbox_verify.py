#!/usr/bin/env python3
"""Sandbox mount integrity check + null-strip stager.

WHY THIS EXISTS
---------------
In the Cowork sandbox, the project mount frequently serves a CORRUPTED view of
a file right after the host Edit/Write tools touch it: null bytes get inserted,
or the file is truncated at a byte offset. Importing or `py_compile`-ing such a
file in the sandbox fails ("source code string cannot contain null bytes" or a
SyntaxError mid-line) even though the real (host) file is perfectly fine. The
host-side Read/Write/Edit tools are authoritative; the sandbox bash view is not.

WHAT THIS DOES
--------------
For every app/*.py (or paths you pass), it:
  1. reads the mount copy, reports null-byte count + line count,
  2. writes a null-STRIPPED copy into a clean staging package (default
     /tmp/proj/app) so behavioral tests can import code that won't choke on
     mount nulls,
  3. compiles the stripped copy and reports OK / CORRUPTED (with the break line).

Then run your tests against the staged copy, e.g.:
    PYTHONPATH=/tmp/proj python3 -c "import app.agents; ..."

If a file is reported CORRUPTED (truncated, not just null-padded), splice the
authoritative tail from a host `Read` of that file:
    head -<break_line-1> /tmp/proj/app/<f> > /tmp/clean.py
    cat >> /tmp/clean.py <<'EOF'
    ...paste host Read lines from break_line to EOF...
    EOF
    mv /tmp/clean.py /tmp/proj/app/<f>

Usage:
    python3 scripts/sandbox_verify.py                # checks app/*.py
    python3 scripts/sandbox_verify.py app/x.py b/y.py
"""
from __future__ import annotations

import glob
import os
import py_compile
import shutil
import sys
import tempfile

STAGE = os.environ.get("SANDBOX_STAGE", "/tmp/proj")


def _stage_dir(rel_path: str) -> str:
    dst = os.path.join(STAGE, os.path.dirname(rel_path))
    os.makedirs(dst, exist_ok=True)
    return dst


def main(argv: list[str]) -> int:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(here)

    paths = argv[1:] or sorted(glob.glob("app/*.py"))
    # Make the staged tree an importable package mirror.
    os.makedirs(os.path.join(STAGE, "app"), exist_ok=True)
    open(os.path.join(STAGE, "app", "__init__.py"), "a").close()

    any_corrupt = False
    print(f"{'file':32} {'nulls':>6} {'lines':>6}  status")
    print("-" * 64)
    for rel in paths:
        try:
            raw = open(rel, "rb").read()
        except FileNotFoundError:
            print(f"{rel:32} {'-':>6} {'-':>6}  MISSING")
            any_corrupt = True
            continue
        nulls = raw.count(b"\x00")
        stripped = raw.replace(b"\x00", b"")
        lines = stripped.count(b"\n") + 1
        dst = os.path.join(STAGE, rel)
        _stage_dir(rel)
        with open(dst, "wb") as fh:
            fh.write(stripped)
        try:
            py_compile.compile(dst, doraise=True)
            status = "OK" if nulls == 0 else "OK (null-stripped)"
        except py_compile.PyCompileError as e:
            any_corrupt = True
            # surface the break line from the SyntaxError if present
            brk = getattr(getattr(e, "exc_value", None), "lineno", "?")
            status = f"CORRUPTED — splice from host Read at line {brk}"
        print(f"{rel:32} {nulls:>6} {lines:>6}  {status}")

    print("-" * 64)
    print(f"staged importable copy: {STAGE}  (use PYTHONPATH={STAGE})")
    if any_corrupt:
        print("Some files are mount-corrupted. The HOST files are still fine — verify\n"
              "them with the Read tool, and splice tails into the staged copy before testing.")
    return 1 if any_corrupt else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
