"""Core load forging engine for MCP servers."""

import asyncio
import time
import urllib.request
import urllib.error
import json
import threading
from typing import Callable, Optional

from .models import (
    ForgeConfig,
    ForgeResult,
    ForgePhase,
    PhaseStats,
    ToolCallResult,
)


class LoadForger:
    """
    Forge an MCP server under configurable load conditions.

    Runs four phases:
      1. Cold Start  — measures first-connection latency
      2. Ramp Up     — gradually increases concurrency
      3. Sustained   — holds peak concurrency
      4. Spike       — bursts beyond peak to find breaking point
    """

    def __init__(self, config: Optional[ForgeConfig] = None):
        self.config = config or ForgeConfig()
        self._lock = threading.Lock()
        self._results: list[ToolCallResult] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, on_progress: Optional[Callable[[str], None]] = None) -> ForgeResult:
        """Run all forge phases synchronously. Returns a ForgeResult."""
        return asyncio.run(self._run_async(on_progress))

    async def run_async(
        self, on_progress: Optional[Callable[[str], None]] = None
    ) -> ForgeResult:
        """Run all forge phases asynchronously."""
        return await self._run_async(on_progress)

    # ------------------------------------------------------------------
    # Internal orchestration
    # ------------------------------------------------------------------

    async def _run_async(
        self, on_progress: Optional[Callable[[str], None]] = None
    ) -> ForgeResult:
        cfg = self.config
        result = ForgeResult(config=cfg)

        def _log(msg: str) -> None:
            if on_progress:
                on_progress(msg)

        # Phase 1: Cold Start
        _log(f"[cold_start] sampling {cfg.cold_start_runs} cold connections…")
        cold_latencies = await self._phase_cold_start(cfg.cold_start_runs)
        result.cold_start_latencies_ms = cold_latencies

        # Phase 2: Ramp Up
        _log(f"[ramp_up] ramping to {cfg.concurrency} VUs over {cfg.ramp_up_seconds}s…")
        ramp_results = await self._phase_ramp_up()
        result.phase_stats[ForgePhase.RAMP_UP] = self._aggregate(
            ForgePhase.RAMP_UP, ramp_results
        )
        result.all_results.extend(ramp_results)

        # Phase 3: Sustained
        _log(
            f"[sustained] holding {cfg.concurrency} VUs for {cfg.sustained_seconds}s…"
        )
        sustained_results = await self._phase_sustained()
        result.phase_stats[ForgePhase.SUSTAINED] = self._aggregate(
            ForgePhase.SUSTAINED, sustained_results
        )
        result.all_results.extend(sustained_results)

        # Phase 4: Spike
        spike_concurrency = int(cfg.concurrency * cfg.spike_multiplier)
        _log(f"[spike] firing spike at {spike_concurrency} VUs for 5s…")
        spike_results = await self._phase_spike()
        result.phase_stats[ForgePhase.SPIKE] = self._aggregate(
            ForgePhase.SPIKE, spike_results
        )
        result.all_results.extend(spike_results)

        # Evaluate thresholds
        self._evaluate(result)
        return result

    # ------------------------------------------------------------------
    # Phases
    # ------------------------------------------------------------------

    async def _phase_cold_start(self, runs: int) -> list[float]:
        latencies: list[float] = []
        for _ in range(runs):
            await asyncio.sleep(0.05)  # small gap simulates cold reconnect
            latency = await self._single_call_async()
            if latency is not None:
                latencies.append(latency)
        return latencies

    async def _phase_ramp_up(self) -> list[ToolCallResult]:
        cfg = self.config
        results: list[ToolCallResult] = []
        steps = max(cfg.ramp_up_seconds, 1)
        for step in range(1, steps + 1):
            concurrency = max(1, int(cfg.concurrency * step / steps))
            batch = await self._concurrent_batch(
                concurrency, ForgePhase.RAMP_UP, concurrency
            )
            results.extend(batch)
            await asyncio.sleep(1)
        return results

    async def _phase_sustained(self) -> list[ToolCallResult]:
        cfg = self.config
        results: list[ToolCallResult] = []
        requests_per_second = max(
            1, cfg.total_requests // max(cfg.sustained_seconds, 1)
        )
        for _ in range(cfg.sustained_seconds):
            batch = await self._concurrent_batch(
                min(cfg.concurrency, requests_per_second),
                ForgePhase.SUSTAINED,
                cfg.concurrency,
            )
            results.extend(batch)
            await asyncio.sleep(1)
        return results

    async def _phase_spike(self) -> list[ToolCallResult]:
        cfg = self.config
        spike_concurrency = int(cfg.concurrency * cfg.spike_multiplier)
        results = await self._concurrent_batch(
            spike_concurrency, ForgePhase.SPIKE, spike_concurrency
        )
        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _concurrent_batch(
        self,
        n: int,
        phase: ForgePhase,
        concurrency_level: int,
    ) -> list[ToolCallResult]:
        tasks = [
            self._call_and_record(phase, concurrency_level) for _ in range(n)
        ]
        return list(await asyncio.gather(*tasks))

    async def _call_and_record(
        self, phase: ForgePhase, concurrency_level: int
    ) -> ToolCallResult:
        start = time.perf_counter()
        try:
            status, error = await asyncio.get_event_loop().run_in_executor(
                None, self._http_tool_call
            )
            latency_ms = (time.perf_counter() - start) * 1000
            return ToolCallResult(
                phase=phase,
                latency_ms=latency_ms,
                success=(error is None),
                status_code=status,
                error=error,
                concurrency_at_call=concurrency_level,
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            return ToolCallResult(
                phase=phase,
                latency_ms=latency_ms,
                success=False,
                error=str(exc),
                concurrency_at_call=concurrency_level,
            )

    async def _single_call_async(self) -> Optional[float]:
        start = time.perf_counter()
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, self._http_tool_call
            )
            return (time.perf_counter() - start) * 1000
        except Exception:
            return None

    def _http_tool_call(self) -> tuple[Optional[int], Optional[str]]:
        """Make a single MCP-style JSON-RPC tool call over HTTP."""
        cfg = self.config
        payload = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": cfg.tool_name,
                    "arguments": cfg.tool_args,
                },
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            cfg.server_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(  # nosec B310 - URL is user-supplied MCP server endpoint, http/https only
                req, timeout=cfg.request_timeout_seconds
            ) as resp:
                return resp.status, None
        except urllib.error.HTTPError as exc:
            return exc.code, f"HTTP {exc.code}: {exc.reason}"
        except urllib.error.URLError as exc:
            return None, f"URLError: {exc.reason}"
        except TimeoutError:
            return None, "Request timed out"

    def _aggregate(
        self, phase: ForgePhase, results: list[ToolCallResult]
    ) -> PhaseStats:
        stats = PhaseStats(phase=phase)
        for r in results:
            stats.total_calls += 1
            if r.success:
                stats.success_count += 1
                stats.latencies_ms.append(r.latency_ms)
            else:
                stats.error_count += 1
        return stats

    def _evaluate(self, result: ForgeResult) -> None:
        cfg = self.config

        if result.overall_p99_ms > cfg.p99_threshold_ms:
            result.passed = False
            result.failure_reasons.append(
                f"p99 latency {result.overall_p99_ms:.1f}ms "
                f"exceeds threshold {cfg.p99_threshold_ms:.1f}ms"
            )

        if result.overall_error_rate > cfg.error_rate_threshold:
            result.passed = False
            result.failure_reasons.append(
                f"error rate {result.overall_error_rate:.1%} "
                f"exceeds threshold {cfg.error_rate_threshold:.1%}"
            )

        if result.cold_start_median_ms > cfg.cold_start_threshold_ms:
            result.passed = False
            result.failure_reasons.append(
                f"cold start median {result.cold_start_median_ms:.1f}ms "
                f"exceeds threshold {cfg.cold_start_threshold_ms:.1f}ms"
            )
