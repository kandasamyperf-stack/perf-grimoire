"""CLI entry point — demo simulation of a runaway agent loop."""

import argparse
import random
import time
import logging

from agent_cost_guardian import CostGuardian, BudgetExceededError
from agent_cost_guardian.models import BudgetConfig
from agent_cost_guardian.tracker import LoopTracker

logging.basicConfig(level=logging.INFO, format="%(message)s")


def simulate_llm_call(iteration: int) -> dict:
    """Simulate an LLM API call with realistic token counts."""
    # Simulate token creep — loops that go long tend to use more tokens
    base_in = random.randint(800, 1_500)
    base_out = random.randint(200, 600)
    creep = 1 + (iteration * 0.05)
    return {
        "input_tokens": int(base_in * creep),
        "output_tokens": int(base_out * creep),
        "tool_calls": random.sample(
            ["web_search", "read_file", "write_file", "call_api"], k=random.randint(0, 2)
        ),
    }


def run_demo(
    max_tokens: int,
    max_cost: float,
    max_iterations: int,
    max_retries: int,
    retry_probability: float,
):
    config = BudgetConfig(
        max_tokens=max_tokens,
        max_cost_usd=max_cost,
        max_iterations=max_iterations,
        max_retries=max_retries,
    )

    guardian = CostGuardian(config)

    print(f"\n🚀 Starting agent loop simulation")
    print(f"   Budget: {max_tokens:,} tokens | ${max_cost:.2f} | {max_iterations} iterations\n")

    killed = False
    try:
        with guardian.session("demo-run") as loop:
            for iteration in loop:
                print(f"  Iteration {iteration}...", end=" ", flush=True)

                # Simulate retry storms
                if random.random() < retry_probability:
                    loop.retry()
                    print(f"retry ⟳", end=" ", flush=True)

                response = simulate_llm_call(iteration)
                loop.record(
                    input_tokens=response["input_tokens"],
                    output_tokens=response["output_tokens"],
                    tool_calls=response["tool_calls"],
                )

                total_cost = guardian.stats.total_cost_usd
                total_tokens = guardian.stats.total_tokens
                print(f"tokens={total_tokens:,}  cost=${total_cost:.4f}")
                time.sleep(0.05)  # simulate network latency

    except BudgetExceededError as e:
        print(f"\n🛑 Guardian killed the loop: {e.reason}\n")
        killed = True

    # Final dashboard
    print("\n" + "─" * 60)
    tracker = LoopTracker(config, guardian.stats)
    tracker.render()

    if not killed:
        print("\n✅ Loop completed within all budget limits.")


def main():
    parser = argparse.ArgumentParser(
        description="Agent Loop Cost Guardian — demo simulation"
    )
    parser.add_argument("--max-tokens", type=int, default=20_000)
    parser.add_argument("--max-cost", type=float, default=0.50)
    parser.add_argument("--max-iterations", type=int, default=15)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument(
        "--retry-prob",
        type=float,
        default=0.2,
        help="Probability of a retry per iteration (0.0–1.0)",
    )
    args = parser.parse_args()

    run_demo(
        max_tokens=args.max_tokens,
        max_cost=args.max_cost,
        max_iterations=args.max_iterations,
        max_retries=args.max_retries,
        retry_probability=args.retry_prob,
    )


if __name__ == "__main__":
    main()
