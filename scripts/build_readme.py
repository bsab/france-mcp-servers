#!/usr/bin/env python3
"""Regenerate the dynamic README sections from the files in servers/.

Usage:
    python3 scripts/build_readme.py            # rewrite the README
    python3 scripts/build_readme.py --check    # exit with 1 if the README is outdated
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import NamedTuple

from quality import readiness_label, readiness_score

ROOT = Path(__file__).resolve().parent.parent
SERVERS_DIR = ROOT / "servers"
README = ROOT / "README.md"


class Category(NamedTuple):
    slug: str
    emoji: str
    label: str
    description: str

    @property
    def heading(self) -> str:
        return f"{self.emoji} {self.label}"


# Keep emoji separate from labels so catalog.json consumers receive plain labels.
CATEGORIES = [
    Category("data-statistics", "📊", "Data and Statistics", "INSEE, Eurostat, open data"),
    Category("geospatial", "🗺️", "Geospatial and Territory", "Geography, addresses, cadastre, urban planning"),
    Category("legal-tech", "⚖️", "Legal Tech and Law", "Legislation, case law, privacy"),
    Category("government-public-finance", "🏛️", "Government and Public Finance", "Government, parliament, tax, procurement"),
    Category("public-services", "🧭", "Public Services", "Administrative procedures and public services"),
    Category("employment", "💼", "Employment and Labor", "Jobs, occupations, recruitment, labor data"),
    Category("transport", "🚆", "Transport and Mobility", "Rail, public transport, routes, disruptions"),
    Category("invoicing", "🧾", "Electronic Invoicing", "Electronic invoices and business billing"),
    Category("cybersecurity-compliance", "🛡️", "Cybersecurity and Compliance", "Cybersecurity rules and regulatory compliance"),
    Category("design-other", "🎨", "Design and Other Services", "Design systems, weather, other services"),
]

# Abbreviations used in the catalog's "Lang" column.
LANGUAGE_ABBR = {"TypeScript": "TS", "JavaScript": "JS"}

BLOCK_RE_TEMPLATE = r"(<!-- BEGIN:{name} -->\n)(?:.*?)(\n<!-- END:{name} -->)"


def load_servers() -> list[dict]:
    servers = []
    for path in sorted(SERVERS_DIR.glob("*.json")):
        with path.open(encoding="utf-8") as fh:
            try:
                data = json.load(fh)
            except json.JSONDecodeError as exc:
                sys.exit(f"{path}: Invalid JSON: {exc}")
        data["_path"] = path
        servers.append(data)
    if not servers:
        sys.exit(f"{SERVERS_DIR}: no servers found")
    return servers


def primary_url(server: dict) -> str:
    for key in ("repository_url", "site_url", "mcp_endpoint"):
        url = server.get(key)
        if url:
            return url
    sys.exit(f"{server['_path']}: missing a URL (repository_url, site_url or mcp_endpoint)")


def sort_key(server: dict):
    score = readiness_score(server)
    return (score is None, -score if score is not None else 0, server["name"].casefold())


def render_row(server: dict) -> str:
    name = html.escape(server["name"])
    label = f"<strong>{name}</strong>" if server.get("featured") else name
    url = html.escape(primary_url(server), quote=True)
    description = html.escape(server.get("short_description") or server["description"])
    endpoint = server.get("mcp_endpoint")
    language = server.get("language", "—")
    quality = readiness_label(server)
    if server.get("quality"):
        assessment_path = html.escape(f"servers/{server['_path'].name}", quote=True)
        reviewed_at = html.escape(server["quality"]["reviewed_at"], quote=True)
        quality = (
            f'<a href="{assessment_path}" '
            f'title="Documentation review: {reviewed_at}; criteria and sources">{quality}</a>'
        )
    connect = "—"
    if endpoint:
        escaped_endpoint = html.escape(endpoint, quote=True)
        connect = (
            f'<a href="{escaped_endpoint}" target="_blank" rel="noopener noreferrer" '
            f'title="Open MCP endpoint: {name}"><kbd>Connect</kbd></a>'
        )

    return (
        "  <tr>\n"
        f'    <td><a href="{url}">{label}</a></td>\n'
        f'    <td align="right">{quality}</td>\n'
        f'    <td align="right">{server.get("stars", 0)}</td>\n'
        f"    <td>{html.escape(LANGUAGE_ABBR.get(language, language))}</td>\n"
        f"    <td>{description}</td>\n"
        f"    <td align=\"center\">{connect}</td>\n"
        "  </tr>"
    )


def render_catalog(servers: list[dict]) -> str:
    known = {category.slug for category in CATEGORIES}
    for server in servers:
        if server.get("category") not in known:
            sys.exit(f"{server['_path']}: unknown category {server.get('category')!r}")

    sections = []
    for category in CATEGORIES:
        rows = sorted((s for s in servers if s["category"] == category.slug), key=sort_key)
        if not rows:
            continue
        body = "\n".join(render_row(server) for server in rows)
        sections.append(
            f"### {category.heading}\n\n"
            '<table width="100%">\n'
            "  <thead>\n"
            "    <tr>\n"
            '      <th width="23%">Project</th>\n'
            '      <th width="13%" align="right">🎯 Ready score /100</th>\n'
            '      <th width="6%" align="right">⭐</th>\n'
            '      <th width="8%">Lang</th>\n'
            '      <th width="40%">Description</th>\n'
            '      <th width="10%">Link</th>\n'
            "    </tr>\n"
            "  </thead>\n"
            "  <tbody>\n"
            f"{body}\n"
            "  </tbody>\n"
            "</table>"
        )
    return "\n\n".join(sections)


def render_badges(servers: list[dict]) -> str:
    categories = len({s["category"] for s in servers})
    return (
        '  <a href="https://github.com/bsab/france-mcp-servers/actions/workflows/ci.yml">'
        '<img src="https://github.com/bsab/france-mcp-servers/actions/workflows/ci.yml/badge.svg" '
        'alt="CI"/></a>\n'
        '  <a href="https://github.com/bsab/france-mcp-servers/actions/workflows/link-check.yml">'
        '<img src="https://github.com/bsab/france-mcp-servers/actions/workflows/link-check.yml/badge.svg" '
        'alt="Link check"/></a>\n'
        '  <a href="https://github.com/bsab/france-mcp-servers/actions/workflows/pages.yml">'
        '<img src="https://github.com/bsab/france-mcp-servers/actions/workflows/pages.yml/badge.svg" '
        'alt="GitHub Pages"/></a>\n'
        '  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" '
        'alt="MIT License"/></a>\n'
        f'  <img src="https://img.shields.io/badge/MCP%20servers-{len(servers)}-blue.svg" '
        f'alt="{len(servers)} servers"/>\n'
        f'  <img src="https://img.shields.io/badge/categories-{categories}-orange.svg" '
        f'alt="{categories} categories"/>'
    )


def replace_block(content: str, name: str, body: str) -> str:
    pattern = re.compile(BLOCK_RE_TEMPLATE.format(name=re.escape(name)), re.S)
    if not pattern.search(content):
        sys.exit(f"README.md: marker <!-- BEGIN:{name} --> / <!-- END:{name} --> not found")
    # Insert via a lambda so backreferences in the body are not interpreted.
    return pattern.sub(lambda m: m.group(1) + body + m.group(2), content)


def build(content: str, servers: list[dict]) -> str:
    content = replace_block(content, "badges", render_badges(servers))
    content = replace_block(content, "catalog", render_catalog(servers))
    return content


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="check that the README matches servers/ without rewriting it",
    )
    args = parser.parse_args()

    servers = load_servers()
    current = README.read_text(encoding="utf-8")
    updated = build(current, servers)

    if args.check:
        if current != updated:
            print(
                "README.md is outdated. Run: python3 scripts/build_readme.py",
                file=sys.stderr,
            )
            return 1
        print(f"README.md is in sync ({len(servers)} servers).")
        return 0

    if current == updated:
        print(f"README.md is already up to date ({len(servers)} servers).")
        return 0

    README.write_text(updated, encoding="utf-8")
    print(f"README.md regenerated ({len(servers)} servers).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
