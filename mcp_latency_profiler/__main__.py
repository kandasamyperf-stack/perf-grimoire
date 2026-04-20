"""
perf-grimoire · MCP Tool Call Latency Profiler
CLI entry point — demo mode, file-replay mode, and live-agent mode.

Usage:
    python -m mcp_latency_profiler demo          # simulate agent loop with fake tools
    python -m mcp_latency_profiler replay FILE   # replay a recorded JSON session
    python -m mcp_latency_profiler report FILE   # print report from JSON file
"""

import asyncio
import argparse
import json
import random
import sys
import time
from pathlib import Path


async def _simulate_tool_call(name: str, base_ms: float, jitter: float, fail_rate: float):
    """Simulate a realistic MCP tool call with configurable latency and failure rate."""
    delay = (base_ms + random.gauss(0, jitter)) / 1000
    delay = max(0.001, delay)
    await asyncio.sleep(delay)
    if random.random() < fail_rate:
        raise RuntimeError(f"Simulated transient failure in {name}")


async def run_demo(loops: int = 5, calls_per_loop: int = 6) -> None:
    """
    Simulate a multi-loop agentic session with realistic MCP tool latency profiles.
    Demonstrates all profiler features with zero external dependencies.
    """
    from mcp_latency_profiler.core.profiler import MCPLatencyProfiler
    from mcp_latency_profiler.core.dashboard import print_full_report, console, RICH_AVAILABLE
    from mcp_latency_profiler.exporters.reporters import export_markdown

    TOOLS = [
        # (name, base_ms, jitter_ms, fail_rate)
        ("filesystem_read",   18,  5,  0.02),
        ("web_search",       320, 80,  0.05),
        ("code_executor",    210, 60,  0.03),
        ("memory_store",      12,  3,  0.01),
        ("memory_retrieve",   15,  4,  0.01),
        ("llm_summarise",    480, 120, 0.04),
        ("vector_search",     95, 25,  0.02),
        ("api_call_github",  280, 90,  0.06),
    ]

    profiler = MCPLatencyProfiler(slow_threshold_ms=300)

    if RICH_AVAILABLE:
        from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn
        from rich import print as rprint
        console.print("\n[bold cyan]perf-grimoire[/bold cyan] · MCP Latency Profiler demo\n")

        with Progress(
            SpinnerColumn(),
            "[progress.description]{task.description}",
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Simulating agent loops...", total=loops * calls_per_loop)
            for loop_idx in range(loops):
                profiler.next_loop()
                sampled = random.choices(TOOLS, k=calls_per_loop)
                for tool_cfg in sampled:
                    name, base_ms, jitter, fail_rate = tool_cfg
                    async with profiler.measure(name):
                        try:
                            await _simulate_tool_call(name, base_ms, jitter, fail_rate)
                        except Exception:
                            pass
                    progress.advance(task)
                await asyncio.sleep(0.05)
    else:
        print("perf-grimoire · MCP Latency Profiler demo")
        for loop_idx in range(loops):
            profiler.next_loop()
            sampled = random.choices(TOOLS, k=calls_per_loop)
            for tool_cfg in sampled:
                name, base_ms, jitter, fail_rate = tool_cfg
                async with profiler.measure(name):
                    try:
                        await _simulate_tool_call(name, base_ms, jitter, fail_rate)
                    except Exception:
                        pass
            print(f"  Loop {loop_idx + 1}/{loops} complete")

    print_full_report(profiler)

    md = export_markdown(profiler)
    out_path = Path("latency_report.md")
    out_path.write_text(md, encoding="utf-8")
    if RICH_AVAILABLE:
        console.print(f"[dim]Markdown report saved → {out_path}[/dim]\n")
    else:
        print(f"Markdown report saved → {out_path}")


async def run_replay(json_path: str) -> None:
    """Replay a saved JSON session and print its report."""
    from mcp_latency_profiler.core.profiler import MCPLatencyProfiler, ToolCallRecord
    from mcp_latency_profiler.core.dashboard import print_full_report

    data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    profiler = MCPLatencyProfiler()

    for rec in data.get("records", []):
        record = ToolCallRecord(
            call_id=rec["call_id"],
            tool_name=rec["tool_name"],
            start_time=0.0,
            end_time=rec["duration_ms"] / 1000,
            duration_ms=rec["duration_ms"],
            success=rec["success"],
            error=rec.get("error"),
            agent_loop=rec.get("agent_loop", 0),
            input_size_bytes=rec.get("input_size_bytes", 0),
            output_size_bytes=rec.get("output_size_bytes", 0),
        )
        profiler._records.append(record)

    print_full_report(profiler)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="mcp-latency-profiler",
        description="perf-grimoire · MCP Tool Call Latency Profiler",
    )
    sub = parser.add_subparsers(dest="command")

    demo_p = sub.add_parser("demo", help="Simulate an agentic session and print report")
    demo_p.add_argument("--loops", type=int, default=5, help="Number of agent loops (default: 5)")
    demo_p.add_argument("--calls", type=int, default=6, help="Tool calls per loop (default: 6)")

    replay_p = sub.add_parser("replay", help="Replay a saved JSON session")
    replay_p.add_argument("file", help="Path to saved JSON session")

    args = parser.parse_args()

    if args.command == "demo":
        asyncio.run(run_demo(loops=args.loops, calls=args.calls))
    elif args.command == "replay":
        asyncio.run(run_replay(args.file))
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
