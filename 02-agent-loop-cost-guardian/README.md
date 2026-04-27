# 02 — Agent Loop Cost Guardian

> Stop runaway agentic AI loops before they drain your token budget.

Part of [perf-grimoire](../) — performance engineering for agentic AI.

---

## The Problem

Agentic AI loops are unpredictable. One edge case triggers a retry storm. A misconfigured tool causes the agent to loop indefinitely. Before you notice, you've burned through thousands of tokens and a surprising bill.

Traditional try/except blocks don't help — by the time you catch an exception, the damage is done.

**Cost Guardian wraps your agent loop and kills it the moment any budget is exceeded** — tokens, USD spend, iteration count, or retry count.

---

## Features

- 🛑 **Hard kill** on token, cost, iteration, or retry budget breach
- ⚠️ **Early warnings** at configurable threshold (default 80% of any budget)
- 📊 **Rich CLI dashboard** showing live spend and progress bars
- 🔌 **Zero dependencies** on any specific LLM SDK — works with Anthropic, OpenAI, Gemini, or any API
- ✅ **Full test suite** — 18 tests covering all kill conditions and edge cases

---

## Installation

```bash
pip install -e ".[dev]"
```

---

## Quick Start

```python
from agent_cost_guardian import CostGuardian, BudgetExceededError
from agent_cost_guardian.models import BudgetConfig

config = BudgetConfig(
    max_tokens=30_000,
    max_cost_usd=0.50,
    max_iterations=10,
    max_retries=3,
)

guardian = CostGuardian(config)

try:
    with guardian.session("my-agent-run") as loop:
        for iteration in loop:
            # Your agent step
            response = call_your_llm(...)

            loop.record(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                tool_calls=["web_search"],   # optional — for tracking
            )

            # Done? Break normally
            if agent_is_done(response):
                loop.stop()

except BudgetExceededError as e:
    print(f"Loop killed: {e.reason}")

print(guardian.stats.summary())
```

---

## CLI Demo

Run a simulated runaway loop to see the guardian in action:

```bash
# Default: 20k tokens, $0.50, 15 iterations
cost-guardian

# Tight budget — will be killed quickly
cost-guardian --max-tokens 5000 --max-cost 0.05 --max-iterations 5

# High retry storm probability
cost-guardian --retry-prob 0.6 --max-retries 2
```

Example output:

```
🚀 Starting agent loop simulation
   Budget: 20,000 tokens | $0.50 | 15 iterations

  Iteration 1... tokens=1,842  cost=$0.0079
  Iteration 2... retry ⟳ tokens=3,914  cost=$0.0171
  Iteration 3... tokens=6,241  cost=$0.0278
  ...
  ⚠️  [CostGuardian] tokens at 81% of budget
  Iteration 9... tokens=21,047  cost=$0.0943
  🛑 Guardian killed the loop: token budget exceeded (21,047 > 20,000)

──────────────────────────────────────────────────────────────────
╭─────────────────────────── Agent Loop Cost Guardian ───────────╮
│ Metric      │ Used      │ Budget  │ % Used │
│ Tokens      │ 21,047    │ 20,000  │  105%  │
│ Cost (USD)  │ $0.0943   │ $0.50   │   19%  │
│ Iterations  │ 9         │ 15      │   60%  │
│ Retries     │ 1         │ 3       │   33%  │
│ Tool Calls  │ 12        │ —       │    —   │
╰────────────────────────────────────────────────────────────────╯
🛑 Loop killed: token budget exceeded (21,047 > 20,000)
```

---

## BudgetConfig Reference

| Parameter | Default | Description |
|---|---|---|
| `max_tokens` | 50,000 | Hard token limit (input + output combined) |
| `max_cost_usd` | $1.00 | Hard USD spend limit |
| `max_iterations` | 20 | Max agent loop iterations |
| `max_retries` | 5 | Max retries before abort |
| `warn_at_pct` | 0.80 | Warn when any budget hits this fraction |
| `input_cost_per_1m` | $3.00 | Input token cost per 1M (Claude Sonnet default) |
| `output_cost_per_1m` | $15.00 | Output token cost per 1M |

---

## Running Tests

```bash
pytest
```

## Security Scan

```bash
bandit -r agent_cost_guardian/
pip-audit
```

---

## License

MIT © perf-grimoire contributors
