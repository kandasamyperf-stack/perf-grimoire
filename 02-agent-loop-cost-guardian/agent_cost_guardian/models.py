"""Data models for Cost Guardian."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BudgetConfig:
    """Budget limits for an agent loop session."""

    max_tokens: int = 50_000
    """Hard token limit across all LLM calls in the loop."""

    max_iterations: int = 20
    """Maximum number of agent loop iterations before forced stop."""

    max_cost_usd: float = 1.00
    """Maximum spend in USD before the guardian kills the loop."""

    max_retries: int = 5
    """Maximum retries allowed per iteration before aborting."""

    warn_at_pct: float = 0.80
    """Fraction of any budget at which a warning is emitted (default 80%)."""

    # Per-model token costs (USD per 1M tokens)
    input_cost_per_1m: float = 3.00
    output_cost_per_1m: float = 15.00

    def cost_for(self, input_tokens: int, output_tokens: int) -> float:
        return (input_tokens / 1_000_000) * self.input_cost_per_1m + \
               (output_tokens / 1_000_000) * self.output_cost_per_1m


@dataclass
class IterationRecord:
    """Record for a single agent loop iteration."""

    iteration: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    retries: int = 0
    tool_calls: list = field(default_factory=list)
    notes: str = ""


@dataclass
class LoopStats:
    """Aggregated stats for a full agent loop session."""

    session_id: str
    total_iterations: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    total_retries: int = 0
    total_tool_calls: int = 0
    killed: bool = False
    kill_reason: Optional[str] = None
    warnings: list = field(default_factory=list)
    records: list = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    def summary(self) -> str:
        status = f"KILLED ({self.kill_reason})" if self.killed else "COMPLETED"
        lines = [
            f"Session : {self.session_id}",
            f"Status  : {status}",
            f"Iters   : {self.total_iterations}",
            f"Tokens  : {self.total_tokens:,}  (in={self.total_input_tokens:,}  out={self.total_output_tokens:,})",
            f"Cost    : ${self.total_cost_usd:.4f}",
            f"Retries : {self.total_retries}",
            f"Tools   : {self.total_tool_calls}",
        ]
        if self.warnings:
            lines.append(f"Warnings: {len(self.warnings)}")
        return "\n".join(lines)
