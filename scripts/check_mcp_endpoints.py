#!/usr/bin/env python3
"""Check remote Streamable HTTP endpoints with an MCP initialize request."""

from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
SERVERS_DIR = ROOT / "servers"
PROTOCOL_VERSION = "2025-06-18"
REQUEST_ID = "france-mcp-servers-health-check"
MAX_RESPONSE_BYTES = 1024 * 1024
USER_AGENT = "france-mcp-servers-link-check/1.0"


@dataclass(frozen=True)
class Endpoint:
    name: str
    url: str


@dataclass(frozen=True)
class Failure:
    endpoint: Endpoint
    reason: str


def load_endpoints(directory: Path = SERVERS_DIR) -> list[Endpoint]:
    endpoints = []
    for path in sorted(directory.glob("*.json")):
        server = json.loads(path.read_text(encoding="utf-8"))
        url = server.get("mcp_endpoint")
        if isinstance(url, str):
            endpoints.append(Endpoint(name=server.get("name", path.stem), url=url))
    return endpoints


def write_lychee_excludes(path: Path, endpoints: list[Endpoint]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    patterns = [f"^{re.escape(endpoint.url.rstrip('/'))}/?$" for endpoint in endpoints]
    path.write_text("\n".join(patterns) + "\n", encoding="utf-8")


def initialize_request(endpoint: Endpoint) -> Request:
    payload = {
        "jsonrpc": "2.0",
        "id": REQUEST_ID,
        "method": "initialize",
        "params": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "france-mcp-servers-link-check", "version": "1.0"},
        },
    }
    return Request(
        endpoint.url,
        data=json.dumps(payload).encode(),
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )


def read_json_response(response: BinaryIO, content_type: str) -> object:
    if content_type.lower().split(";", 1)[0].strip() == "text/event-stream":
        data_lines: list[bytes] = []
        size = 0
        while size <= MAX_RESPONSE_BYTES:
            line = response.readline(MAX_RESPONSE_BYTES + 1)
            if not line:
                break
            size += len(line)
            if line in (b"\n", b"\r\n") and data_lines:
                break
            if line.startswith(b"data:"):
                data_lines.append(line[5:].lstrip().rstrip(b"\r\n"))
        raw = b"\n".join(data_lines)
    else:
        raw = response.read(MAX_RESPONSE_BYTES + 1)

    if not raw or len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("empty or oversized response")
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("response did not contain valid JSON") from exc


def validate_initialize_response(payload: object) -> None:
    if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0":
        raise ValueError("response was not JSON-RPC 2.0")
    if payload.get("id") != REQUEST_ID:
        raise ValueError("response used an unexpected request id")
    if "error" in payload:
        error = payload["error"]
        code = error.get("code") if isinstance(error, dict) else "unknown"
        raise ValueError(f"initialize returned JSON-RPC error {code}")
    result = payload.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("protocolVersion"), str):
        raise ValueError("initialize result omitted the protocol version")


def open_url(request: Request, timeout: float):
    context = ssl.create_default_context()
    if ssl.get_default_verify_paths().cafile is None:
        system_bundle = Path("/etc/ssl/cert.pem")
        if system_bundle.is_file():
            context.load_verify_locations(system_bundle)
    return urlopen(request, timeout=timeout, context=context)


def check_once(
    endpoint: Endpoint,
    timeout: float,
    opener: Callable = open_url,
) -> None:
    try:
        with opener(initialize_request(endpoint), timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if not 200 <= status < 300:
                raise ValueError(f"HTTP {status}")
            content_type = response.headers.get("Content-Type", "")
            payload = read_json_response(response, content_type)
    except HTTPError as exc:
        raise ValueError(f"HTTP {exc.code}") from exc
    except URLError as exc:
        raise ValueError(f"connection failed: {type(exc.reason).__name__}") from exc
    validate_initialize_response(payload)


def check_endpoints(
    endpoints: list[Endpoint],
    timeout: float,
    retries: int,
    opener: Callable = open_url,
    sleep: Callable[[float], None] = time.sleep,
) -> list[Failure]:
    failures = []
    for endpoint in endpoints:
        reason = "unknown error"
        for attempt in range(retries + 1):
            try:
                check_once(endpoint, timeout, opener)
                break
            except (OSError, ValueError) as exc:
                reason = str(exc)
                if attempt < retries:
                    sleep(2**attempt)
        else:
            failures.append(Failure(endpoint, reason))
    return failures


def render_report(failures: list[Failure], total: int) -> str:
    lines = [
        "# MCP endpoint check",
        "",
        f"Checked {total} Streamable HTTP MCP endpoints with a JSON-RPC `initialize` request.",
        "",
        "## Errors",
        "",
    ]
    lines.extend(
        f"* [{failure.endpoint.name}]({failure.endpoint.url}) — {failure.reason}"
        for failure in failures
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    exclusions = subparsers.add_parser("exclusions", help="write Lychee exclusion patterns")
    exclusions.add_argument("output", type=Path)

    check = subparsers.add_parser("check", help="check every catalog MCP endpoint")
    check.add_argument("--report", type=Path)
    check.add_argument("--timeout", type=float, default=15)
    check.add_argument("--retries", type=int, default=2)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    endpoints = load_endpoints()
    if args.command == "exclusions":
        write_lychee_excludes(args.output, endpoints)
        print(f"Wrote {len(endpoints)} MCP endpoint exclusions to {args.output}.")
        return 0

    failures = check_endpoints(endpoints, args.timeout, args.retries)
    if not failures:
        print(f"{len(endpoints)} MCP endpoints responded to initialize.")
        return 0

    report = render_report(failures, len(endpoints))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report, encoding="utf-8")
    print(report, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
