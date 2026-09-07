"""Tests for protocol-aware MCP endpoint checks."""

import io
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import URLError

from check_mcp_endpoints import (
    REQUEST_ID,
    Endpoint,
    check_endpoints,
    check_once,
    load_endpoints,
    render_report,
    write_lychee_excludes,
)


class Response(io.BytesIO):
    def __init__(self, body: bytes, content_type: str, status: int = 200):
        super().__init__(body)
        self.headers = {"Content-Type": content_type}
        self.status = status


def initialize_result() -> dict:
    return {
        "jsonrpc": "2.0",
        "id": REQUEST_ID,
        "result": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "serverInfo": {"name": "Test", "version": "1.0"},
        },
    }


class McpEndpointTests(unittest.TestCase):
    def test_loads_only_mcp_endpoints_in_filename_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "b.json").write_text(
                json.dumps({"name": "Beta", "mcp_endpoint": "https://b.example/mcp"})
            )
            (root / "a.json").write_text(json.dumps({"name": "Alpha"}))
            (root / "c.json").write_text(
                json.dumps({"name": "Charlie", "mcp_endpoint": "https://c.example/mcp"})
            )

            self.assertEqual(
                load_endpoints(root),
                [
                    Endpoint("Beta", "https://b.example/mcp"),
                    Endpoint("Charlie", "https://c.example/mcp"),
                ],
            )

    def test_writes_exact_lychee_exclusion_patterns(self):
        endpoints = [Endpoint("Example", "https://example.org/a.b/mcp/")]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "excludes.txt"
            write_lychee_excludes(output, endpoints)
            self.assertEqual(output.read_text(), "^https://example\\.org/a\\.b/mcp/?$\n")

    def test_accepts_json_initialize_response(self):
        body = json.dumps(initialize_result()).encode()
        requests = []

        def opener(request, timeout):
            requests.append((request, timeout))
            return Response(body, "application/json; charset=utf-8")

        check_once(Endpoint("Example", "https://example.org/mcp"), 3, opener)
        request, timeout = requests[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(timeout, 3)
        self.assertIn("application/json", request.headers["Accept"])
        self.assertEqual(json.loads(request.data)["method"], "initialize")

    def test_accepts_server_sent_initialize_response(self):
        body = b"event: message\r\ndata: " + json.dumps(initialize_result()).encode() + b"\r\n\r\n"
        opener = lambda request, timeout: Response(body, "text/event-stream")
        check_once(Endpoint("Example", "https://example.org/mcp"), 3, opener)

    def test_retries_and_reports_connection_failures(self):
        calls = []
        sleeps = []

        def opener(request, timeout):
            calls.append(request.full_url)
            raise URLError(TimeoutError())

        endpoint = Endpoint("Example", "https://example.org/mcp")
        failures = check_endpoints([endpoint], 3, 2, opener, sleeps.append)

        self.assertEqual(len(calls), 3)
        self.assertEqual(sleeps, [1, 2])
        self.assertEqual(failures[0].reason, "connection failed: TimeoutError")
        report = render_report(failures, 1)
        self.assertIn("Checked 1 Streamable HTTP MCP endpoints", report)
        self.assertIn("[Example](https://example.org/mcp)", report)

    def test_rejects_json_rpc_errors(self):
        payload = {"jsonrpc": "2.0", "id": REQUEST_ID, "error": {"code": -32600}}
        body = json.dumps(payload).encode()
        opener = lambda request, timeout: Response(body, "application/json")

        with self.assertRaisesRegex(ValueError, "JSON-RPC error -32600"):
            check_once(Endpoint("Example", "https://example.org/mcp"), 3, opener)


if __name__ == "__main__":
    unittest.main()
