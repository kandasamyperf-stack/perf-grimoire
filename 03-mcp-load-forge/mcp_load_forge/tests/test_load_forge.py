"""Tests for MCP Load Forge."""

import asyncio
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

import pytest

from mcp_load_forge.forger import LoadForger
from mcp_load_forge.models import ForgeConfig, ForgePhase, PhaseStats, ForgeResult
from mcp_load_forge.reporter import ForgeReporter


# ---------------------------------------------------------------------------
# Shared mock server fixture
# ---------------------------------------------------------------------------

class _FastHandler(BaseHTTPRequestHandler):
    latency_ms: float = 10.0
    error_rate: float = 0.0
    _call_count = 0

    def do_POST(self):  # noqa: N802
        _FastHandler._call_count += 1
        import random
        if random.random() < self.error_rate:
            self.send_response(503)
            self.end_headers()
            return
        time.sleep(self.latency_ms / 1000)
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"content": []}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def mock_server():
    server = HTTPServer(("127.0.0.1", 19090), _FastHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield "http://127.0.0.1:19090"
    server.shutdown()


# ---------------------------------------------------------------------------
# ForgeConfig tests
# ---------------------------------------------------------------------------

class TestForgeConfig:
    def test_defaults(self):
        cfg = ForgeConfig()
        assert cfg.concurrency == 10
        assert cfg.ramp_up_seconds == 5
        assert cfg.sustained_seconds == 20
        assert cfg.p99_threshold_ms == 2000.0
        assert cfg.error_rate_threshold == 0.05

    def test_custom_values(self):
        cfg = ForgeConfig(concurrency=50, sustained_seconds=60, p99_threshold_ms=500.0)
        assert cfg.concurrency == 50
        assert cfg.sustained_seconds == 60
        assert cfg.p99_threshold_ms == 500.0

    def test_spike_multiplier(self):
        cfg = ForgeConfig(concurrency=10, spike_multiplier=3.0)
        assert cfg.spike_multiplier == 3.0


# ---------------------------------------------------------------------------
# PhaseStats tests
# ---------------------------------------------------------------------------

class TestPhaseStats:
    def test_empty_stats(self):
        stats = PhaseStats(phase=ForgePhase.SUSTAINED)
        assert stats.error_rate == 0.0
        assert stats.p50_ms == 0.0
        assert stats.p99_ms == 0.0
        assert stats.mean_ms == 0.0

    def test_percentiles(self):
        stats = PhaseStats(phase=ForgePhase.SUSTAINED)
        stats.latencies_ms = list(range(1, 101))  # 1..100ms
        stats.total_calls = 100
        stats.success_count = 100
        assert 49 <= stats.p50_ms <= 51
        assert 94 <= stats.p95_ms <= 96
        assert 98 <= stats.p99_ms <= 100

    def test_error_rate(self):
        stats = PhaseStats(phase=ForgePhase.SPIKE)
        stats.total_calls = 100
        stats.error_count = 10
        stats.success_count = 90
        assert stats.error_rate == pytest.approx(0.10)

    def test_mean(self):
        stats = PhaseStats(phase=ForgePhase.RAMP_UP)
        stats.latencies_ms = [10.0, 20.0, 30.0]
        assert stats.mean_ms == pytest.approx(20.0)

    def test_min_max(self):
        stats = PhaseStats(phase=ForgePhase.RAMP_UP)
        stats.latencies_ms = [5.0, 50.0, 200.0]
        assert stats.min_ms == 5.0
        assert stats.max_ms == 200.0


# ---------------------------------------------------------------------------
# ForgeResult tests
# ---------------------------------------------------------------------------

class TestForgeResult:
    def _make_result(self, latencies, errors=0):
        from mcp_load_forge.models import ToolCallResult
        cfg = ForgeConfig()
        result = ForgeResult(config=cfg)
        for i, lat in enumerate(latencies):
            success = i >= errors
            result.all_results.append(
                ToolCallResult(
                    phase=ForgePhase.SUSTAINED,
                    latency_ms=lat,
                    success=success,
                )
            )
        return result

    def test_overall_error_rate(self):
        result = self._make_result([10] * 100, errors=5)
        assert result.overall_error_rate == pytest.approx(0.05)

    def test_overall_p99(self):
        result = self._make_result(list(range(1, 101)))
        assert result.overall_p99_ms >= 98

    def test_cold_start_median(self):
        cfg = ForgeConfig()
        result = ForgeResult(config=cfg)
        result.cold_start_latencies_ms = [100.0, 200.0, 300.0]
        assert result.cold_start_median_ms == 200.0

    def test_throughput_rps(self):
        cfg = ForgeConfig(sustained_seconds=10)
        result = ForgeResult(config=cfg)
        stats = PhaseStats(phase=ForgePhase.SUSTAINED)
        stats.total_calls = 100
        result.phase_stats[ForgePhase.SUSTAINED] = stats
        assert result.throughput_rps == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# LoadForger integration tests (uses mock server)
# ---------------------------------------------------------------------------

class TestLoadForger:
    def _fast_config(self, url):
        return ForgeConfig(
            server_url=url,
            concurrency=3,
            ramp_up_seconds=2,
            sustained_seconds=3,
            total_requests=20,
            cold_start_runs=3,
            spike_multiplier=1.5,
            p99_threshold_ms=5000.0,
            error_rate_threshold=0.10,
            cold_start_threshold_ms=2000.0,
        )

    def test_run_returns_forge_result(self, mock_server):
        cfg = self._fast_config(mock_server)
        forger = LoadForger(cfg)
        result = forger.run()
        assert isinstance(result, ForgeResult)

    def test_cold_start_samples_collected(self, mock_server):
        cfg = self._fast_config(mock_server)
        forger = LoadForger(cfg)
        result = forger.run()
        assert len(result.cold_start_latencies_ms) > 0

    def test_all_phases_present(self, mock_server):
        cfg = self._fast_config(mock_server)
        forger = LoadForger(cfg)
        result = forger.run()
        assert ForgePhase.RAMP_UP in result.phase_stats
        assert ForgePhase.SUSTAINED in result.phase_stats
        assert ForgePhase.SPIKE in result.phase_stats

    def test_passes_against_fast_server(self, mock_server):
        cfg = self._fast_config(mock_server)
        forger = LoadForger(cfg)
        result = forger.run()
        assert result.passed is True
        assert result.failure_reasons == []

    def test_fails_on_tight_p99_threshold(self, mock_server):
        cfg = self._fast_config(mock_server)
        cfg.p99_threshold_ms = 0.001  # impossibly tight
        forger = LoadForger(cfg)
        result = forger.run()
        assert result.passed is False
        assert any("p99" in r for r in result.failure_reasons)

    def test_all_results_populated(self, mock_server):
        cfg = self._fast_config(mock_server)
        forger = LoadForger(cfg)
        result = forger.run()
        assert len(result.all_results) > 0

    def test_progress_callback_called(self, mock_server):
        cfg = self._fast_config(mock_server)
        forger = LoadForger(cfg)
        messages = []
        result = forger.run(on_progress=messages.append)
        assert len(messages) >= 4  # one per phase

    def test_async_run(self, mock_server):
        cfg = self._fast_config(mock_server)
        forger = LoadForger(cfg)
        result = asyncio.run(forger.run_async())
        assert isinstance(result, ForgeResult)


# ---------------------------------------------------------------------------
# Reporter tests
# ---------------------------------------------------------------------------

class TestForgeReporter:
    def _sample_result(self):
        cfg = ForgeConfig(server_url="http://localhost:8000", concurrency=10)
        result = ForgeResult(config=cfg, passed=True)
        result.cold_start_latencies_ms = [45.0, 50.0, 55.0]
        for phase in [ForgePhase.RAMP_UP, ForgePhase.SUSTAINED, ForgePhase.SPIKE]:
            stats = PhaseStats(phase=phase)
            stats.total_calls = 50
            stats.success_count = 49
            stats.error_count = 1
            stats.latencies_ms = [30.0 + i for i in range(49)]
            result.phase_stats[phase] = stats
        return result

    def test_as_text_contains_server(self):
        result = self._sample_result()
        text = ForgeReporter().as_text(result)
        assert "http://localhost:8000" in text

    def test_as_text_contains_phases(self):
        result = self._sample_result()
        text = ForgeReporter().as_text(result)
        assert "Ramp Up" in text
        assert "Sustained" in text
        assert "Spike" in text

    def test_pass_verdict(self):
        result = self._sample_result()
        text = ForgeReporter().as_text(result)
        assert "FORGE PASSED" in text

    def test_fail_verdict(self):
        result = self._sample_result()
        result.passed = False
        result.failure_reasons = ["p99 latency 3000.0ms exceeds threshold 2000.0ms"]
        text = ForgeReporter().as_text(result)
        assert "FORGE FAILED" in text
        assert "p99" in text

    def test_cold_start_shown(self):
        result = self._sample_result()
        text = ForgeReporter().as_text(result)
        assert "Cold Start" in text
