"""Core CostGuardian — enforces budgets and kills runaway loops."""

import uuid
import logging
from contextlib import contextmanager
from typing import Iterator, Optional

from .models import BudgetConfig, IterationRecord, LoopStats

logger = logging.getLogger("cost_guardian")


class BudgetExceededError(RuntimeError):
    """Raised when a hard budget limit is hit."""

    def __init__(self, reason: str, stats: LoopStats):
        super().__init__(reason)
        self.stats = stats
        self.reason = reason


class CostGuardian:
    """
    Wraps an agent loop and enforces token, cost, and iteration budgets.

    Usage
    -----
    config = BudgetConfig(max_tokens=30_000, max_cost_usd=0.50, max_iterations=10)
    guardian = CostGuardian(config)

    with guardian.session("my-run") as loop:
        for _ in loop:
            # your agent step here
            response = call_llm(...)
            loop.record(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                tool_calls=["web_search"],
            )

    print(guardian.stats.summary())
    """

    def __init__(self, config: Optional[BudgetConfig] = None):
        self.config = config or BudgetConfig()
        self._stats: Optional[LoopStats] = None

    @property
    def stats(self) -> Optional[LoopStats]:
        return self._stats

    @contextmanager
    def session(self, session_id: Optional[str] = None) -> Iterator["_LoopHandle"]:
        """Context manager that yields a loop handle and enforces budgets."""
        sid = session_id or str(uuid.uuid4())[:8]
        self._stats = LoopStats(session_id=sid)
        handle = _LoopHandle(self.config, self._stats)
        try:
            yield handle
        except BudgetExceededError:
            raise
        finally:
            # Emit final summary to logger
            logger.info("\n" + self._stats.summary())


class _LoopHandle:
    """
    Iterable handle returned by CostGuardian.session().
    Tracks per-iteration state and enforces kill conditions.
    """

    def __init__(self, config: BudgetConfig, stats: LoopStats):
        self._config = config
        self._stats = stats
        self._iteration = 0
        self._iter_retries = 0
        self._stopped = False

    # ------------------------------------------------------------------
    # Iteration protocol
    # ------------------------------------------------------------------

    def __iter__(self):
        return self

    def __next__(self):
        if self._stopped:
            raise StopIteration
        self._check_limits()
        self._iteration += 1
        self._iter_retries = 0
        self._stats.total_iterations = self._iteration
        return self._iteration

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self,
        input_tokens: int,
        output_tokens: int,
        retries: int = 0,
        tool_calls: Optional[list] = None,
        notes: str = "",
    ) -> IterationRecord:
        """
        Record usage for the current iteration.
        Call this after each LLM response inside your agent loop.
        """
        tool_calls = tool_calls or []
        cost = self._config.cost_for(input_tokens, output_tokens)

        rec = IterationRecord(
            iteration=self._iteration,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            retries=retries,
            tool_calls=tool_calls,
            notes=notes,
        )

        # Accumulate
        self._stats.total_input_tokens += input_tokens
        self._stats.total_output_tokens += output_tokens
        self._stats.total_cost_usd += cost
        self._stats.total_retries += retries
        self._stats.total_tool_calls += len(tool_calls)
        self._stats.records.append(rec)

        self._emit_warnings()
        self._check_limits()
        return rec

    def retry(self) -> None:
        """Signal that the current iteration is being retried."""
        self._iter_retries += 1
        self._stats.total_retries += 1
        cfg = self._config
        if self._iter_retries >= cfg.max_retries:
            self._kill(f"retry limit ({cfg.max_retries}) exceeded on iteration {self._iteration}")

    def stop(self) -> None:
        """Manually stop the loop cleanly (no error raised)."""
        self._stopped = True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_limits(self):
        cfg = self._config
        s = self._stats

        if s.total_tokens > cfg.max_tokens:
            self._kill(f"token budget exceeded ({s.total_tokens:,} > {cfg.max_tokens:,})")

        if s.total_cost_usd > cfg.max_cost_usd:
            self._kill(f"cost budget exceeded (${s.total_cost_usd:.4f} > ${cfg.max_cost_usd:.2f})")

        if self._iteration >= cfg.max_iterations:
            self._kill(f"iteration limit reached ({self._iteration} >= {cfg.max_iterations})")

    def _emit_warnings(self):
        cfg = self._config
        s = self._stats
        threshold = cfg.warn_at_pct

        checks = [
            (s.total_tokens / cfg.max_tokens, f"tokens at {s.total_tokens / cfg.max_tokens:.0%} of budget"),
            (s.total_cost_usd / cfg.max_cost_usd, f"cost at ${s.total_cost_usd:.4f} ({s.total_cost_usd / cfg.max_cost_usd:.0%} of budget)"),
            (self._iteration / cfg.max_iterations, f"iteration {self._iteration}/{cfg.max_iterations}"),
        ]

        for ratio, msg in checks:
            if ratio >= threshold and msg not in s.warnings:
                s.warnings.append(msg)
                logger.warning(f"[CostGuardian] ⚠️  {msg}")

    def _kill(self, reason: str):
        self._stats.killed = True
        self._stats.kill_reason = reason
        logger.error(f"[CostGuardian] 🛑 Loop killed — {reason}")
        raise BudgetExceededError(reason, self._stats)
