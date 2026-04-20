"""
Exporters — JSON, CSV, and Markdown report output for CI/CD pipelines and dashboards.
"""

from __future__ import annotations

import csv
import json
import io
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp_latency_profiler.core.profiler import MCPLatencyProfiler


def export_json(profiler: "MCPLatencyProfiler", indent: int = 2) -> str:
    """
    Export full profiling session as JSON.
    Safe for CI artefact storage and Grafana ingestion.
    """
    stats = profiler.get_stats()
    records = profiler.get_all_records()

    payload = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "session_duration_s": round(profiler.session_duration_s(), 3),
            "total_calls": profiler.total_calls(),
            "unique_tools": len(stats),
            "failed_calls": len(profiler.get_failed_calls()),
            "slow_calls": len(profiler.get_slow_calls()),
            "slow_threshold_ms": profiler.slow_threshold_ms,
        },
        "tool_stats": {
            name: {
                "call_count": s.call_count,
                "success_count": s.success_count,
                "failure_count": s.failure_count,
                "error_rate_pct": round(s.error_rate, 2),
                "latency_ms": {
                    "p50": round(s.p50, 2),
                    "p95": round(s.p95, 2),
                    "p99": round(s.p99, 2),
                    "mean": round(s.mean, 2),
                    "stddev": round(s.stddev, 2),
                    "min": round(s.min, 2),
                    "max": round(s.max, 2),
                },
            }
            for name, s in sorted(stats.items())
        },
        "records": [
            {
                "call_id": r.call_id,
                "tool_name": r.tool_name,
                "duration_ms": round(r.duration_ms, 3),
                "success": r.success,
                "error": r.error,
                "agent_loop": r.agent_loop,
                "input_size_bytes": r.input_size_bytes,
                "output_size_bytes": r.output_size_bytes,
            }
            for r in records
        ],
    }
    return json.dumps(payload, indent=indent)


def export_csv(profiler: "MCPLatencyProfiler") -> str:
    """
    Export per-call records as CSV.
    Compatible with pandas, DuckDB, and spreadsheet tools.
    """
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "call_id", "tool_name", "duration_ms", "success",
            "error", "agent_loop", "input_size_bytes", "output_size_bytes",
        ],
        extrasaction="ignore",
    )
    writer.writeheader()
    for r in profiler.get_all_records():
        writer.writerow({
            "call_id": r.call_id,
            "tool_name": r.tool_name,
            "duration_ms": round(r.duration_ms, 3),
            "success": r.success,
            "error": r.error or "",
            "agent_loop": r.agent_loop,
            "input_size_bytes": r.input_size_bytes,
            "output_size_bytes": r.output_size_bytes,
        })
    return output.getvalue()


def export_markdown(profiler: "MCPLatencyProfiler") -> str:
    """
    Export a Markdown summary report.
    Ideal for GitHub PR comments and wiki pages.
    """
    stats = profiler.get_stats()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# MCP Tool Call Latency Report",
        "",
        f"Generated: {now}  ",
        f"Session: {profiler.session_duration_s():.1f}s | "
        f"Calls: {profiler.total_calls()} | "
        f"Tools: {len(stats)} | "
        f"Failures: {len(profiler.get_failed_calls())}",
        "",
        "## Per-tool latency (ms)",
        "",
        "| Tool | Calls | p50 | p95 | p99 | Max | Err% |",
        "|------|------:|----:|----:|----:|----:|-----:|",
    ]

    for name, s in sorted(stats.items(), key=lambda x: x[1].p95, reverse=True):
        def flag(v: float) -> str:
            if v >= 500:
                return f"**{v:.1f}** 🔴"
            elif v >= 100:
                return f"{v:.1f} 🟡"
            return f"{v:.1f}"

        lines.append(
            f"| `{name}` | {s.call_count} | {flag(s.p50)} | {flag(s.p95)} "
            f"| {flag(s.p99)} | {flag(s.max)} | {s.error_rate:.1f}% |"
        )

    slow = profiler.get_slow_calls()
    if slow:
        lines += [
            "",
            f"## Slow calls (>{profiler.slow_threshold_ms:.0f}ms)",
            "",
            "| ID | Tool | Loop | Duration ms |",
            "|----|------|-----:|------------:|",
        ]
        for r in sorted(slow, key=lambda x: x.duration_ms, reverse=True)[:20]:
            lines.append(
                f"| `{r.call_id}` | `{r.tool_name}` | {r.agent_loop} | {r.duration_ms:.1f} |"
            )

    failed = profiler.get_failed_calls()
    if failed:
        lines += [
            "",
            "## Failed calls",
            "",
            "| ID | Tool | Error |",
            "|----|------|-------|",
        ]
        for r in failed[:20]:
            lines.append(f"| `{r.call_id}` | `{r.tool_name}` | {r.error or 'unknown'} |")

    lines += ["", "---", "_Generated by [perf-grimoire](https://github.com/perf-grimoire)_"]
    return "\n".join(lines)


def save_report(profiler: "MCPLatencyProfiler", path: str, fmt: str = "json") -> None:
    """
    Save a report to disk.
    fmt: 'json' | 'csv' | 'markdown'
    """
    exporters = {
        "json": export_json,
        "csv": export_csv,
        "markdown": export_markdown,
        "md": export_markdown,
    }
    fn = exporters.get(fmt)
    if fn is None:
        raise ValueError(f"Unknown format '{fmt}'. Choose from: {list(exporters)}")
    content = fn(profiler)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
