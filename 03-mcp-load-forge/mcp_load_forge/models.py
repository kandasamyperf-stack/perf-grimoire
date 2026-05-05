"""Data models for MCP Load Forge."""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class ForgePhase(str, Enum):
    COLD_START = "cold_start"
    RAMP_UP = "ramp_up"
    SUSTAINED = "sustained"
    SPIKE = "spike"


@dataclass
class ForgeConfig:
    """Configuration for a load forge run."""

    # Target MCP server
    server_url: str = "http://localhost:8000"
    tool_name: str = "echo"
    tool_args: dict = field(default_factory=lambda: {"message": "forge-test"})

    # Load profile
    concurrency: int = 10
    """Number of concurrent virtual users."""

    ramp_up_seconds: int = 5
    """Time to ramp from 1 to full concurrency."""

    sustained_seconds: int = 20
    """How long to hold peak load."""

    spike_multiplier: float = 2.0
    """Spike load = concurrency * spike_multiplier for 5 seconds."""

    total_requests: int = 200
    """Total requests to fire across all phases."""

    request_timeout_seconds: float = 10.0
    """Per-request timeout before marking as failed."""

    cold_start_runs: int = 5
    """How many cold-start samples to take."""

    # Thresholds (fail forge if breached)
    p99_threshold_ms: float = 2000.0
    """Fail if p99 latency exceeds this."""

    error_rate_threshold: float = 0.05
    """Fail if error rate exceeds 5%."""

    cold_start_threshold_ms: float = 500.0
    """Fail if cold start median exceeds this."""


@dataclass
class ToolCallResult:
    """Result of a single MCP tool call."""

    phase: ForgePhase
    latency_ms: float
    success: bool
    status_code: Optional[int] = None
    error: Optional[str] = None
    concurrency_at_call: int = 1


@dataclass
class PhaseStats:
    """Aggregated stats for one forge phase."""

    phase: ForgePhase
    total_calls: int = 0
    success_count: int = 0
    error_count: int = 0
    latencies_ms: list = field(default_factory=list)

    @property
    def error_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.error_count / self.total_calls

    @property
    def p50_ms(self) -> float:
        return self._percentile(50)

    @property
    def p95_ms(self) -> float:
        return self._percentile(95)

    @property
    def p99_ms(self) -> float:
        return self._percentile(99)

    @property
    def mean_ms(self) -> float:
        if not self.latencies_ms:
            return 0.0
        return sum(self.latencies_ms) / len(self.latencies_ms)

    @property
    def max_ms(self) -> float:
        return max(self.latencies_ms) if self.latencies_ms else 0.0

    @property
    def min_ms(self) -> float:
        return min(self.latencies_ms) if self.latencies_ms else 0.0

    def _percentile(self, pct: int) -> float:
        if not self.latencies_ms:
            return 0.0
        sorted_l = sorted(self.latencies_ms)
        idx = int(len(sorted_l) * pct / 100)
        idx = min(idx, len(sorted_l) - 1)
        return sorted_l[idx]


@dataclass
class ForgeResult:
    """Full result of a load forge run."""

    config: ForgeConfig
    phase_stats: dict = field(default_factory=dict)  # ForgePhase -> PhaseStats
    cold_start_latencies_ms: list = field(default_factory=list)
    all_results: list = field(default_factory=list)  # list[ToolCallResult]
    passed: bool = True
    failure_reasons: list = field(default_factory=list)

    @property
    def overall_error_rate(self) -> float:
        total = len(self.all_results)
        if total == 0:
            return 0.0
        errors = sum(1 for r in self.all_results if not r.success)
        return errors / total

    @property
    def overall_p99_ms(self) -> float:
        latencies = [r.latency_ms for r in self.all_results if r.success]
        if not latencies:
            return 0.0
        sorted_l = sorted(latencies)
        idx = min(int(len(sorted_l) * 0.99), len(sorted_l) - 1)
        return sorted_l[idx]

    @property
    def cold_start_median_ms(self) -> float:
        if not self.cold_start_latencies_ms:
            return 0.0
        sorted_l = sorted(self.cold_start_latencies_ms)
        return sorted_l[len(sorted_l) // 2]

    @property
    def throughput_rps(self) -> float:
        """Approximate requests per second across sustained phase."""
        stats = self.phase_stats.get(ForgePhase.SUSTAINED)
        if not stats or stats.total_calls == 0:
            return 0.0
        return stats.total_calls / max(self.config.sustained_seconds, 1)
