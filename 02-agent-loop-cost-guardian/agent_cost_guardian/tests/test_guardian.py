"""Tests for Agent Loop Cost Guardian."""

import pytest
from agent_cost_guardian import CostGuardian, BudgetExceededError
from agent_cost_guardian.models import BudgetConfig, LoopStats
from agent_cost_guardian.tracker import LoopTracker


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tight_config():
    return BudgetConfig(
        max_tokens=5_000,
        max_cost_usd=0.10,
        max_iterations=5,
        max_retries=2,
        warn_at_pct=0.8,
        input_cost_per_1m=3.00,
        output_cost_per_1m=15.00,
    )


@pytest.fixture
def generous_config():
    return BudgetConfig(
        max_tokens=1_000_000,
        max_cost_usd=100.00,
        max_iterations=100,
        max_retries=10,
    )


# ── BudgetConfig ──────────────────────────────────────────────────────────────

def test_cost_calculation():
    cfg = BudgetConfig(input_cost_per_1m=3.00, output_cost_per_1m=15.00)
    cost = cfg.cost_for(1_000_000, 1_000_000)
    assert cost == pytest.approx(18.00)


def test_cost_zero_tokens():
    cfg = BudgetConfig()
    assert cfg.cost_for(0, 0) == 0.0


# ── CostGuardian — happy path ─────────────────────────────────────────────────

def test_loop_completes_within_budget(generous_config):
    guardian = CostGuardian(generous_config)
    iterations_run = 0
    with guardian.session("happy") as loop:
        for _ in loop:
            loop.record(input_tokens=100, output_tokens=50)
            iterations_run += 1
            if iterations_run >= 3:
                loop.stop()

    assert iterations_run == 3
    assert guardian.stats.total_iterations == 3
    assert not guardian.stats.killed


def test_stats_accumulate_correctly(generous_config):
    guardian = CostGuardian(generous_config)
    with guardian.session("acc") as loop:
        for _ in loop:
            loop.record(input_tokens=1000, output_tokens=500, tool_calls=["search"])
            if guardian.stats.total_iterations >= 3:
                loop.stop()

    s = guardian.stats
    assert s.total_input_tokens == 3000
    assert s.total_output_tokens == 1500
    assert s.total_tool_calls == 3
    assert s.total_cost_usd == pytest.approx(
        generous_config.cost_for(3000, 1500), rel=1e-4
    )


# ── CostGuardian — kill conditions ───────────────────────────────────────────

def test_kills_on_token_budget(tight_config):
    guardian = CostGuardian(tight_config)
    with pytest.raises(BudgetExceededError) as exc_info:
        with guardian.session("tok") as loop:
            for _ in loop:
                loop.record(input_tokens=3000, output_tokens=1000)

    assert "token" in exc_info.value.reason.lower()
    assert guardian.stats.killed


def test_kills_on_cost_budget():
    cfg = BudgetConfig(max_cost_usd=0.01, max_tokens=1_000_000, max_iterations=100)
    guardian = CostGuardian(cfg)
    with pytest.raises(BudgetExceededError) as exc_info:
        with guardian.session("cost") as loop:
            for _ in loop:
                loop.record(input_tokens=10_000, output_tokens=5_000)

    assert "cost" in exc_info.value.reason.lower()


def test_kills_on_iteration_limit(tight_config):
    guardian = CostGuardian(tight_config)
    with pytest.raises(BudgetExceededError) as exc_info:
        with guardian.session("iter") as loop:
            for _ in loop:
                loop.record(input_tokens=1, output_tokens=1)

    assert "iteration" in exc_info.value.reason.lower()


def test_kills_on_retry_limit(tight_config):
    guardian = CostGuardian(tight_config)
    with pytest.raises(BudgetExceededError) as exc_info:
        with guardian.session("retry") as loop:
            for _ in loop:
                loop.retry()
                loop.retry()
                loop.retry()  # exceeds max_retries=2
                loop.record(input_tokens=1, output_tokens=1)

    assert "retry" in exc_info.value.reason.lower()


# ── Warnings ─────────────────────────────────────────────────────────────────

def test_warnings_emitted_near_budget():
    cfg = BudgetConfig(
        max_tokens=10_000,
        max_cost_usd=1.00,
        max_iterations=100,
        warn_at_pct=0.5,
    )
    guardian = CostGuardian(cfg)
    with guardian.session("warn") as loop:
        for _ in loop:
            loop.record(input_tokens=5_001, output_tokens=0)
            loop.stop()

    assert len(guardian.stats.warnings) > 0


# ── LoopStats ─────────────────────────────────────────────────────────────────

def test_loop_stats_total_tokens():
    stats = LoopStats(session_id="test")
    stats.total_input_tokens = 1000
    stats.total_output_tokens = 500
    assert stats.total_tokens == 1500


def test_loop_stats_summary_contains_session_id():
    stats = LoopStats(session_id="abc-123")
    summary = stats.summary()
    assert "abc-123" in summary


def test_loop_stats_summary_shows_killed():
    stats = LoopStats(session_id="x", killed=True, kill_reason="test reason")
    summary = stats.summary()
    assert "KILLED" in summary
    assert "test reason" in summary


# ── LoopTracker ───────────────────────────────────────────────────────────────

def test_tracker_renders_without_error(generous_config):
    stats = LoopStats(session_id="t1")
    stats.total_input_tokens = 500
    stats.total_output_tokens = 200
    stats.total_iterations = 2
    tracker = LoopTracker(generous_config, stats)
    # Should not raise
    tracker.render()


def test_tracker_plain_fallback(generous_config, monkeypatch):
    """Test plain text fallback when Rich is unavailable."""
    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "rich":
            raise ImportError("mocked")
        return real_import(name, *args, **kwargs)

    stats = LoopStats(session_id="plain")
    tracker = LoopTracker(generous_config, stats)
    result = tracker._plain_render()
    assert "plain" in result
