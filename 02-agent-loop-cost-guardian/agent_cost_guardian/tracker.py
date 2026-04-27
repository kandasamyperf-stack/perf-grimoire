"""LoopTracker — real-time Rich CLI dashboard for agent loop monitoring."""

from typing import Optional

from .models import BudgetConfig, LoopStats


class LoopTracker:
    """
    Renders a live Rich dashboard showing token spend, cost, and iteration
    progress for a CostGuardian session.

    Usage
    -----
    tracker = LoopTracker(config, stats)
    tracker.render()   # prints current state as a Rich table
    """

    def __init__(self, config: BudgetConfig, stats: LoopStats):
        self.config = config
        self.stats = stats

    def render(self) -> None:
        """Print a Rich summary table to stdout."""
        try:
            from rich.table import Table
            from rich.console import Console
            from rich.progress import Progress, BarColumn, TextColumn
            from rich import box
        except ImportError:
            print(self._plain_render())
            return

        console = Console()
        cfg = self.config
        s = self.stats

        table = Table(
            title=f"[bold cyan]Agent Loop Cost Guardian[/] — session [yellow]{s.session_id}[/]",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Metric", style="cyan", no_wrap=True)
        table.add_column("Used", justify="right")
        table.add_column("Budget", justify="right")
        table.add_column("% Used", justify="right")

        def pct_style(used, total) -> str:
            p = used / total if total else 0
            if p >= 1.0:
                return f"[bold red]{p:.0%}[/]"
            if p >= 0.8:
                return f"[yellow]{p:.0%}[/]"
            return f"[green]{p:.0%}[/]"

        table.add_row(
            "Tokens",
            f"{s.total_tokens:,}",
            f"{cfg.max_tokens:,}",
            pct_style(s.total_tokens, cfg.max_tokens),
        )
        table.add_row(
            "Cost (USD)",
            f"${s.total_cost_usd:.4f}",
            f"${cfg.max_cost_usd:.2f}",
            pct_style(s.total_cost_usd, cfg.max_cost_usd),
        )
        table.add_row(
            "Iterations",
            str(s.total_iterations),
            str(cfg.max_iterations),
            pct_style(s.total_iterations, cfg.max_iterations),
        )
        table.add_row(
            "Retries",
            str(s.total_retries),
            str(cfg.max_retries),
            pct_style(s.total_retries, cfg.max_retries),
        )
        table.add_row("Tool Calls", str(s.total_tool_calls), "—", "—")

        console.print(table)

        if s.warnings:
            console.print(f"\n[yellow]⚠️  Warnings:[/]")
            for w in s.warnings:
                console.print(f"  • {w}")

        if s.killed:
            console.print(f"\n[bold red]🛑 Loop killed: {s.kill_reason}[/]")

    def _plain_render(self) -> str:
        """Fallback plain-text render when Rich is not installed."""
        return self.stats.summary()
