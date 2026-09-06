#!/usr/bin/env python3
"""Validate files in servers/ against schema/server.schema.json.

Also check catalog-wide constraints (filenames and unique names and URLs)
that cannot be expressed in the schema for a single entry.

Usage:
    python3 scripts/validate_servers.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:
    sys.exit(
        "Missing dependency: jsonschema. Install it with:\n"
        "    python3 -m pip install -r scripts/requirements.txt"
    )

ROOT = Path(__file__).resolve().parent.parent
SERVERS_DIR = ROOT / "servers"
SCHEMA_PATH = ROOT / "schema" / "server.schema.json"

FILENAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
URL_FIELDS = ("repository_url", "site_url", "mcp_endpoint")


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def describe(error) -> str:
    location = "".join(f"[{part!r}]" for part in error.absolute_path)
    # The top-level anyOf only requires a URL; avoid dumping the entire object.
    if error.validator == "anyOf" and not error.absolute_path:
        return "at least one of repository_url, site_url or mcp_endpoint is required"
    return f"{location or '<root>'}: {error.message}"


def main() -> int:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    paths = sorted(SERVERS_DIR.glob("*.json"))
    if not paths:
        print(f"{relative(SERVERS_DIR)}: no servers found", file=sys.stderr)
        return 1

    errors: list[str] = []
    names: defaultdict[str, list[Path]] = defaultdict(list)
    urls: defaultdict[str, list[Path]] = defaultdict(list)

    for path in paths:
        if not FILENAME_RE.match(path.stem):
            errors.append(f"{relative(path)}: filename must be in kebab-case")

        try:
            server = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{relative(path)}: Invalid JSON: {exc}")
            continue

        if not isinstance(server, dict):
            errors.append(f"{relative(path)}: file must contain a JSON object")
            continue

        for error in sorted(validator.iter_errors(server), key=lambda e: list(e.absolute_path)):
            errors.append(f"{relative(path)}: {describe(error)}")

        if isinstance(server.get("name"), str):
            names[server["name"].casefold()].append(path)
        for field in URL_FIELDS:
            url = server.get(field)
            if isinstance(url, str):
                urls[url.rstrip("/")].append(path)

    for name, duplicates in sorted(names.items()):
        if len(duplicates) > 1:
            files = ", ".join(relative(p) for p in duplicates)
            errors.append(f"duplicate name {name!r}: {files}")

    for url, duplicates in sorted(urls.items()):
        # One entry may repeat a URL across fields (e.g. site_url == mcp_endpoint).
        distinct = sorted({p for p in duplicates})
        if len(distinct) > 1:
            files = ", ".join(relative(p) for p in distinct)
            errors.append(f"duplicate URL {url}: {files}")

    if errors:
        prefix = "::error::" if os.environ.get("GITHUB_ACTIONS") else ""
        for error in errors:
            print(f"{prefix}{error}")
        print(f"\n{len(errors)} errors in {len(paths)} files.", file=sys.stderr)
        return 1

    print(f"{len(paths)} valid servers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
