"""
MCP Tool Call Latency Profiler — Core Engine
Instruments MCP tool invocations and captures timing telemetry.
"""

import asyncio
import time
import uuid
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from contextlib import asynccontextmanager


@dataclass
class ToolCallRecord:
    """Immutable record of a single MCP tool call."""
    call_id: str
    tool_name: str
    start_time: float
    end_time: float
    duration_ms: float
    success: bool
    error: Optional[str] = None
    input_size_bytes: int = 0
    output_size_bytes: int = 0
    agent_loop: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_slow(self) -> bool:
        return self.duration_ms > 500

    @property
    def is_failed(self) -> bool:
        return not self.success


@dataclass
class ToolStats:
    """Aggregated statistics for a single tool."""
    tool_name: str
    call_count: int
    success_count: int
    failure_count: int
    durations_ms: List[float]

    @property
    def p50(self) -> float:
        return statistics.median(self.durations_ms) if self.durations_ms else 0.0

    @property
    def p95(self) -> float:
        return self._percentile(95)

    @property
    def p99(self) -> float:
        return self._percentile(99)

    @property
    def mean(self) -> float:
        return statistics.mean(self.durations_ms) if self.durations_ms else 0.0

    @property
    def stddev(self) -> float:
        return statistics.stdev(self.durations_ms) if len(self.durations_ms) > 1 else 0.0

    @property
    def min(self) -> float:
        return min(self.durations_ms) if self.durations_ms else 0.0

    @property
    def max(self) -> float:
        return max(self.durations_ms) if self.durations_ms else 0.0

    @property
    def error_rate(self) -> float:
        return (self.failure_count / self.call_count * 100) if self.call_count else 0.0

    def _percentile(self, pct: float) -> float:
        if not self.durations_ms:
            return 0.0
        sorted_d = sorted(self.durations_ms)
        idx = int(len(sorted_d) * pct / 100)
        return sorted_d[min(idx, len(sorted_d) - 1)]


class MCPLatencyProfiler:
    """
    Async profiler that wraps MCP tool calls and collects latency telemetry.

    Usage:
        profiler = MCPLatencyProfiler()

        # Wrap an existing tool function
        wrapped = profiler.wrap_tool("search_web", original_search_fn)

        # Or use as a context manager for manual timing
        async with profiler.measure("my_tool") as ctx:
            result = await some_tool_call()

        # Get statistics
        stats = profiler.get_stats()
    """

    def __init__(self, slow_threshold_ms: float = 500.0, max_records: int = 10_000):
        self._records: List[ToolCallRecord] = []
        self._lock = asyncio.Lock()
        self.slow_threshold_ms = slow_threshold_ms
        self.max_records = max_records
        self._current_loop = 0
        self._session_start = time.monotonic()

    def next_loop(self) -> None:
        """Advance the agent loop counter."""
        self._current_loop += 1

    @asynccontextmanager
    async def measure(self, tool_name: str, metadata: Optional[Dict] = None):
        """Context manager for manual timing of any async block."""
        call_id = str(uuid.uuid4())[:8]
        start = time.monotonic()
        error_msg = None
        success = True
        try:
            yield call_id
        except Exception as e:
            success = False
            error_msg = type(e).__name__ + ": " + str(e)
            raise
        finally:
            end = time.monotonic()
            record = ToolCallRecord(
                call_id=call_id,
                tool_name=tool_name,
                start_time=start,
                end_time=end,
                duration_ms=(end - start) * 1000,
                success=success,
                error=error_msg,
                agent_loop=self._current_loop,
                metadata=metadata or {},
            )
            async with self._lock:
                if len(self._records) < self.max_records:
                    self._records.append(record)

    def wrap_tool(self, tool_name: str, fn: Callable) -> Callable:
        """
        Wrap an async MCP tool function with latency instrumentation.
        Returns a new async function that records timing on each call.
        """
        profiler = self

        async def instrumented(*args, **kwargs):
            async with profiler.measure(tool_name) as call_id:
                result = await fn(*args, **kwargs)
                # Best-effort size estimation
                try:
                    import json
                    out_size = len(json.dumps(result, default=str).encode())
                    in_size = len(json.dumps({"args": args, "kwargs": kwargs}, default=str).encode())
                    # Patch the last record with sizes
                    async with profiler._lock:
                        for r in reversed(profiler._records):
                            if r.call_id == call_id:
                                object.__setattr__(r, "output_size_bytes", out_size)
                                object.__setattr__(r, "input_size_bytes", in_size)
                                break
                except Exception:
                    pass
            return result

        instrumented.__name__ = f"profiled_{tool_name}"
        return instrumented

    def get_all_records(self) -> List[ToolCallRecord]:
        return list(self._records)

    def get_stats(self) -> Dict[str, ToolStats]:
        """Compute per-tool aggregated statistics."""
        by_tool: Dict[str, List[ToolCallRecord]] = defaultdict(list)
        for r in self._records:
            by_tool[r.tool_name].append(r)

        stats = {}
        for tool_name, records in by_tool.items():
            durations = [r.duration_ms for r in records]
            successes = [r for r in records if r.success]
            failures = [r for r in records if not r.success]
            stats[tool_name] = ToolStats(
                tool_name=tool_name,
                call_count=len(records),
                success_count=len(successes),
                failure_count=len(failures),
                durations_ms=durations,
            )
        return stats

    def get_slow_calls(self, threshold_ms: Optional[float] = None) -> List[ToolCallRecord]:
        threshold = threshold_ms or self.slow_threshold_ms
        return [r for r in self._records if r.duration_ms > threshold]

    def get_failed_calls(self) -> List[ToolCallRecord]:
        return [r for r in self._records if not r.success]

    def session_duration_s(self) -> float:
        return time.monotonic() - self._session_start

    def total_calls(self) -> int:
        return len(self._records)

    def reset(self) -> None:
        self._records.clear()
        self._current_loop = 0
        self._session_start = time.monotonic()
