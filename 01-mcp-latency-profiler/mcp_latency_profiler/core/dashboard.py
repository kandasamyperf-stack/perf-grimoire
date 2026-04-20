"""
Terminal Dashboard — Rich-powered live display of MCP latency metrics.
Renders p50/p95/p99 tables, flame-style bar charts, and error summaries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from mcp_latency_profiler.core.profiler import MCPLatencyProfiler, ToolStats

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.columns import Columns
    from rich.text import Text
    from rich.live import Live
    from rich.layout import Layout
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

console = Console()

FLAME_CHARS = "▏▎▍▌▋▊▉█"
BAR_WIDTH = 28


def _flame_bar(value: float, max_value: float, width: int = BAR_WIDTH) -> str:
    """Render a unicode flame-style bar proportional to value/max_value."""
    if max_value == 0:
        return " " * width
    ratio = min(value / max_value, 1.0)
    filled = ratio * width
    full_blocks = int(filled)
    remainder = filled - full_blocks
    bar = "█" * full_blocks
    if remainder > 0 and full_blocks < width:
        idx = int(remainder * len(FLAME_CHARS))
        bar += FLAME_CHARS[min(idx, len(FLAME_CHARS) - 1)]
    bar = bar.ljust(width)
    # Colour: green < 100ms, yellow 100–500ms, red > 500ms
    if value < 100:
        return f"[green]{bar}[/green]"
    elif value < 500:
        return f"[yellow]{bar}[/yellow]"
    else:
        return f"[red]{bar}[/red]"


def _latency_colour(ms: float) -> str:
    if ms < 100:
        return "green"
    elif ms < 500:
        return "yellow"
    return "red"


def render_stats_table(stats: dict) -> "Table":
    """Render the main p50/p95/p99 latency table."""
    table = Table(
        title="MCP Tool Latency — per-tool breakdown",
        box=box.SIMPLE_HEAD,
        show_footer=False,
        header_style="bold",
        expand=True,
    )
    table.add_column("Tool", style="cyan", no_wrap=True)
    table.add_column("Calls", justify="right", style="dim")
    table.add_column("p50 ms", justify="right")
    table.add_column("p95 ms", justify="right")
    table.add_column("p99 ms", justify="right")
    table.add_column("Max ms", justify="right")
    table.add_column("Err%", justify="right")
    table.add_column(f"Flame (p95, {BAR_WIDTH} cols)", no_wrap=True)

    if not stats:
        table.add_row("[dim]no calls recorded yet[/dim]", *["—"] * 7)
        return table

    max_p95 = max((s.p95 for s in stats.values()), default=1)

    for tool_name, s in sorted(stats.items(), key=lambda x: x[1].p95, reverse=True):
        err_style = "red" if s.error_rate > 0 else "dim"
        table.add_row(
            tool_name,
            str(s.call_count),
            f"[{_latency_colour(s.p50)}]{s.p50:.1f}[/]",
            f"[{_latency_colour(s.p95)}]{s.p95:.1f}[/]",
            f"[{_latency_colour(s.p99)}]{s.p99:.1f}[/]",
            f"[{_latency_colour(s.max)}]{s.max:.1f}[/]",
            f"[{err_style}]{s.error_rate:.1f}%[/]",
            _flame_bar(s.p95, max_p95),
        )
    return table


def render_summary_panel(profiler: "MCPLatencyProfiler") -> "Panel":
    """Render the top-level session summary."""
    stats = profiler.get_stats()
    total = profiler.total_calls()
    failed = len(profiler.get_failed_calls())
    slow = len(profiler.get_slow_calls())
    duration = profiler.session_duration_s()
    rate = total / duration if duration > 0 else 0

    all_durations = [r.duration_ms for r in profiler.get_all_records()]
    import statistics as st
    overall_p99 = (
        sorted(all_durations)[int(len(all_durations) * 0.99)]
        if all_durations else 0
    )

    cols = [
        Panel(f"[bold]{total}[/bold]\n[dim]total calls[/dim]", expand=True),
        Panel(f"[bold]{len(stats)}[/bold]\n[dim]unique tools[/dim]", expand=True),
        Panel(f"[bold green]{rate:.1f}/s[/bold green]\n[dim]call rate[/dim]", expand=True),
        Panel(
            f"[bold {'red' if failed else 'green'}]{failed}[/bold]\n[dim]failures[/dim]",
            expand=True,
        ),
        Panel(
            f"[bold {'yellow' if slow else 'green'}]{slow}[/bold]\n[dim]slow (>{profiler.slow_threshold_ms:.0f}ms)[/dim]",
            expand=True,
        ),
        Panel(
            f"[bold {_latency_colour(overall_p99)}]{overall_p99:.1f}ms[/bold]\n[dim]overall p99[/dim]",
            expand=True,
        ),
    ]
    return Panel(Columns(cols), title="[bold]Session summary[/bold]", border_style="dim")


def render_slow_calls_table(profiler: "MCPLatencyProfiler", limit: int = 10) -> "Table":
    """Render the top N slowest individual calls."""
    slow = sorted(profiler.get_all_records(), key=lambda r: r.duration_ms, reverse=True)[:limit]
    table = Table(
        title=f"Slowest {limit} individual calls",
        box=box.SIMPLE_HEAD,
        header_style="bold",
        expand=True,
    )
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Tool", style="cyan")
    table.add_column("Loop", justify="right", style="dim")
    table.add_column("Duration ms", justify="right")
    table.add_column("Status")

    for r in slow:
        status = "[green]ok[/green]" if r.success else f"[red]{r.error or 'error'}[/red]"
        table.add_row(
            r.call_id,
            r.tool_name,
            str(r.agent_loop),
            f"[{_latency_colour(r.duration_ms)}]{r.duration_ms:.1f}[/]",
            status,
        )
    return table


def render_loop_heatmap(profiler: "MCPLatencyProfiler") -> "Table":
    """Per-agent-loop call count and avg latency heatmap."""
    from collections import defaultdict
    by_loop: dict = defaultdict(list)
    for r in profiler.get_all_records():
        by_loop[r.agent_loop].append(r.duration_ms)

    table = Table(
        title="Agent loop heatmap",
        box=box.SIMPLE_HEAD,
        header_style="bold",
        expand=True,
    )
    table.add_column("Loop", justify="right", style="dim")
    table.add_column("Calls", justify="right")
    table.add_column("Avg ms", justify="right")
    table.add_column("Heat", no_wrap=True)

    if not by_loop:
        table.add_row("—", "—", "—", "—")
        return table

    max_avg = max(
        (sum(v) / len(v) for v in by_loop.values()), default=1
    )
    for loop_num in sorted(by_loop.keys()):
        durations = by_loop[loop_num]
        avg = sum(durations) / len(durations)
        table.add_row(
            str(loop_num),
            str(len(durations)),
            f"[{_latency_colour(avg)}]{avg:.1f}[/]",
            _flame_bar(avg, max_avg, width=20),
        )
    return table


def print_full_report(profiler: "MCPLatencyProfiler") -> None:
    """Print a complete static report to the terminal."""
    if not RICH_AVAILABLE:
        _fallback_print(profiler)
        return

    console.print()
    console.print(render_summary_panel(profiler))
    console.print()
    console.print(render_stats_table(profiler.get_stats()))
    console.print()

    cols = Columns(
        [render_slow_calls_table(profiler), render_loop_heatmap(profiler)],
        expand=True,
        equal=True,
    )
    console.print(cols)
    console.print()


def _fallback_print(profiler: "MCPLatencyProfiler") -> None:
    """Plain-text fallback when rich is not installed."""
    stats = profiler.get_stats()
    print("\n=== MCP Latency Profiler Report ===")
    print(f"Total calls: {profiler.total_calls()}")
    print(f"Session: {profiler.session_duration_s():.1f}s\n")
    header = f"{'Tool':<30} {'Calls':>6} {'p50':>8} {'p95':>8} {'p99':>8} {'Err%':>6}"
    print(header)
    print("-" * len(header))
    for tool, s in sorted(stats.items(), key=lambda x: x[1].p95, reverse=True):
        print(
            f"{tool:<30} {s.call_count:>6} {s.p50:>7.1f}ms {s.p95:>7.1f}ms"
            f" {s.p99:>7.1f}ms {s.error_rate:>5.1f}%"
        )
    print()
