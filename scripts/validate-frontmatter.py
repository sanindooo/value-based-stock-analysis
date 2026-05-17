#!/usr/bin/env python3
"""Validate YAML frontmatter in docs/solutions/ markdown files.

Catches silent-corruption parser-safety issues:
- Malformed --- delimiter lines
- Unquoted ' #' in scalar values (silent comment truncation)
- Unquoted ': ' in scalar values (silent mapping confusion)

Uses Python 3 stdlib only (no PyYAML or other deps).
Exit 0 = parser-safe. Exit 1 = issues found (details on stderr).
"""

import re
import sys


def extract_frontmatter(text: str) -> tuple[list[str], bool]:
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return [], False

    end = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = i
            break

    if end is None:
        return [], False

    return lines[1:end], True


def check_line(line: str, line_num: int, errors: list[str]) -> None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or stripped.startswith("-"):
        if stripped.startswith("- "):
            value = stripped[2:]
            if not (value.startswith('"') and value.endswith('"')):
                if " #" in value:
                    errors.append(f"Line {line_num}: unquoted ' #' in array item may cause silent comment truncation: {stripped}")
                if ": " in value and not value.startswith("["):
                    errors.append(f"Line {line_num}: unquoted ': ' in array item may cause silent mapping confusion: {stripped}")
        return

    if ":" not in stripped:
        return

    key, _, raw_value = line.partition(":")
    value = raw_value.strip()

    if not value or value.startswith("[") or value.startswith('"') or value.startswith("'"):
        return

    if " #" in value:
        errors.append(f"Line {line_num}: unquoted ' #' in scalar value for '{key.strip()}' may cause silent comment truncation")

    parts = value.split(": ", 1)
    if len(parts) > 1 and not value.startswith('"'):
        errors.append(f"Line {line_num}: unquoted ': ' in scalar value for '{key.strip()}' may cause silent mapping confusion")


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: validate-frontmatter.py <path>", file=sys.stderr)
        return 1

    path = sys.argv[1]
    try:
        with open(path) as f:
            text = f.read()
    except FileNotFoundError:
        print(f"File not found: {path}", file=sys.stderr)
        return 1

    lines_raw = text.split("\n")
    if not lines_raw or lines_raw[0].strip() != "---":
        print(f"Malformed frontmatter: first line is not '---'", file=sys.stderr)
        return 1

    fm_lines, ok = extract_frontmatter(text)
    if not ok:
        print(f"Malformed frontmatter: no closing '---' delimiter found", file=sys.stderr)
        return 1

    errors: list[str] = []
    for i, line in enumerate(fm_lines, start=2):
        check_line(line, i, errors)

    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
