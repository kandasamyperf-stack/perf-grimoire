"""Terminal reporter for MCP Load Forge results."""

from .models import ForgeResult, ForgePhase


class ForgeReporter:
    """Renders a ForgeResult as a readable terminal report."""

    PHASE_LABELS = {
        ForgePhase.COLD_START: "Cold Start",
        ForgePhase.RAMP_UP:    "Ramp Up",
        ForgePhase.SUSTAINED:  "Sustained",
        ForgePhase.SPIKE:      "Spike",
    }

    def print_report(self, result: ForgeResult) -> None:
        """Print a full forge report to stdout."""
        lines = self._build(result)
        print("\n".join(lines))

    def as_text(self, result: ForgeResult) -> str:
        """Return the report as a string."""
        return "\n".join(self._build(result))

    # ------------------------------------------------------------------

    def _build(self, result: ForgeResult) -> list[str]:
        lines: list[str] = []
        w = 62

        lines.append("=" * w)
        lines.append("  MCP LOAD FORGE — Results")
        lines.append("=" * w)

        # Config summary
        cfg = result.config
        lines.append(f"  Server  : {cfg.server_url}")
        lines.append(f"  Tool    : {cfg.tool_name}")
        lines.append(f"  Peak VUs: {cfg.concurrency}")
        lines.append(f"  Spike   : {int(cfg.concurrency * cfg.spike_multiplier)} VUs")
        lines.append("-" * w)

        # Cold start
        if result.cold_start_latencies_ms:
            med = result.cold_start_median_ms
            mx  = max(result.cold_start_latencies_ms)
            flag = "  ⚠️ SLOW" if med > cfg.cold_start_threshold_ms else ""
            lines.append(f"  Cold Start   median={med:.1f}ms  max={mx:.1f}ms{flag}")
        lines.append("-" * w)

        # Per-phase stats
        header = f"  {'Phase':<12} {'p50':>7} {'p95':>7} {'p99':>7} {'err%':>6} {'calls':>6}"
        lines.append(header)
        lines.append("  " + "-" * (w - 2))

        phase_order = [ForgePhase.RAMP_UP, ForgePhase.SUSTAINED, ForgePhase.SPIKE]
        for phase in phase_order:
            stats = result.phase_stats.get(phase)
            if not stats:
                continue
            label = self.PHASE_LABELS.get(phase, phase.value)
            err_pct = f"{stats.error_rate:.1%}"
            lines.append(
                f"  {label:<12} "
                f"{stats.p50_ms:>6.1f}ms "
                f"{stats.p95_ms:>6.1f}ms "
                f"{stats.p99_ms:>6.1f}ms "
                f"{err_pct:>6} "
                f"{stats.total_calls:>6}"
            )

        lines.append("-" * w)

        # Overall
        lines.append(
            f"  Overall  p99={result.overall_p99_ms:.1f}ms  "
            f"err={result.overall_error_rate:.1%}  "
            f"throughput~{result.throughput_rps:.1f} rps"
        )
        lines.append("-" * w)

        # Thresholds
        lines.append(f"  Thresholds:")
        lines.append(f"    p99 < {cfg.p99_threshold_ms:.0f}ms         "
                     f"{'✅ PASS' if result.overall_p99_ms <= cfg.p99_threshold_ms else '❌ FAIL'}")
        lines.append(f"    error rate < {cfg.error_rate_threshold:.0%}     "
                     f"{'✅ PASS' if result.overall_error_rate <= cfg.error_rate_threshold else '❌ FAIL'}")
        lines.append(f"    cold start < {cfg.cold_start_threshold_ms:.0f}ms     "
                     f"{'✅ PASS' if result.cold_start_median_ms <= cfg.cold_start_threshold_ms else '❌ FAIL'}")
        lines.append("-" * w)

        # Verdict
        if result.passed:
            lines.append("  ✅  FORGE PASSED — server held up under load")
        else:
            lines.append("  ❌  FORGE FAILED")
            for reason in result.failure_reasons:
                lines.append(f"       • {reason}")

        lines.append("=" * w)
        return lines
