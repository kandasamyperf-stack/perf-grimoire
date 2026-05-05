"""CLI entry point for MCP Load Forge — includes a built-in mock MCP server for demo."""

import argparse
import json
import random
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from .forger import LoadForger
from .models import ForgeConfig
from .reporter import ForgeReporter


# ---------------------------------------------------------------------------
# Built-in mock MCP server (for demo / CI without a real MCP server)
# ---------------------------------------------------------------------------

class MockMCPHandler(BaseHTTPRequestHandler):
    """Minimal MCP-compatible JSON-RPC handler."""

    # Configurable via class vars
    base_latency_ms: float = 30.0
    jitter_ms: float = 20.0
    error_rate: float = 0.02

    def do_POST(self) -> None:  # noqa: N802
        if random.random() < self.error_rate:
            self.send_response(503)
            self.end_headers()
            return

        latency = (self.base_latency_ms + random.uniform(0, self.jitter_ms)) / 1000
        time.sleep(latency)

        body = json.dumps(
            {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "pong"}]}}
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # suppress request logs
        pass


def _start_mock_server(port: int) -> HTTPServer:
    server = HTTPServer(("127.0.0.1", port), MockMCPHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="mcp-load-forge",
        description="Forge your MCP server under real load conditions.",
    )
    parser.add_argument("--url", default=None, help="MCP server URL (omit to use built-in mock)")
    parser.add_argument("--tool", default="echo", help="Tool name to call (default: echo)")
    parser.add_argument("--concurrency", type=int, default=10, help="Peak virtual users (default: 10)")
    parser.add_argument("--ramp-up", type=int, default=5, help="Ramp-up seconds (default: 5)")
    parser.add_argument("--sustained", type=int, default=10, help="Sustained seconds (default: 10)")
    parser.add_argument("--requests", type=int, default=100, help="Total requests (default: 100)")
    parser.add_argument("--spike", type=float, default=2.0, help="Spike multiplier (default: 2.0)")
    parser.add_argument("--p99-threshold", type=float, default=2000.0, help="p99 threshold ms (default: 2000)")
    parser.add_argument("--error-threshold", type=float, default=0.05, help="Error rate threshold (default: 0.05)")
    parser.add_argument("--mock-port", type=int, default=18080, help="Port for built-in mock server (default: 18080)")
    parser.add_argument("--mock-latency", type=float, default=30.0, help="Mock server base latency ms (default: 30)")
    parser.add_argument("--mock-error-rate", type=float, default=0.02, help="Mock server error rate (default: 0.02)")

    args = parser.parse_args()

    mock_server = None
    server_url = args.url

    if server_url is None:
        print(f"🔧 Starting built-in mock MCP server on port {args.mock_port}…")
        MockMCPHandler.base_latency_ms = args.mock_latency
        MockMCPHandler.error_rate = args.mock_error_rate
        mock_server = _start_mock_server(args.mock_port)
        server_url = f"http://127.0.0.1:{args.mock_port}"
        time.sleep(0.2)

    config = ForgeConfig(
        server_url=server_url,
        tool_name=args.tool,
        concurrency=args.concurrency,
        ramp_up_seconds=args.ramp_up,
        sustained_seconds=args.sustained,
        total_requests=args.requests,
        spike_multiplier=args.spike,
        p99_threshold_ms=args.p99_threshold,
        error_rate_threshold=args.error_threshold,
    )

    print(f"⚒️  MCP Load Forge starting against {server_url}")
    print(f"   Peak VUs: {config.concurrency}  |  Spike: {int(config.concurrency * config.spike_multiplier)} VUs")
    print()

    forger = LoadForger(config)
    result = forger.run(on_progress=lambda msg: print(f"  {msg}"))

    print()
    ForgeReporter().print_report(result)

    if mock_server:
        mock_server.shutdown()

    raise SystemExit(0 if result.passed else 1)


if __name__ == "__main__":
    main()
