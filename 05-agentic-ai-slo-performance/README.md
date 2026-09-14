# 05 — Agentic AI SLO & Performance

Notes on defining SLOs for agentic AI systems, infrastructure metrics tell you the
system responded. They don't tell you whether the reasoning behind the task was right.

My views, my experience. Not my employer's.

## Why I started writing this down

An agentic workflow can pass every infrastructure SLO — latency in range, zero errors,
full uptime — and still fail the task silently. A `200 OK` just means the infrastructure
responded. It doesn't mean the agent got the job done.

That gap is what this folder is about. Five SLO dimensions that actually catch it, plus
how I've been instrumenting and alerting on each one.

## What's in here

- [`agentic-ai-slo-dimensions.md`](./agentic-ai-slo-dimensions.md) — the full write-up:
  all five dimensions, how to instrument them, how to set targets
- [`agentic-ai-slo-carousel.pdf`](./agentic-ai-slo-carousel.pdf) — the same five
  dimensions as a slide walkthrough

## The five dimensions, briefly

1. **Task Completion Rate** — did it actually finish, verified at the trace level, not just the span level
2. **Step Efficiency** — steps per task against a real baseline, not a guess
3. **LLM Capacity & Throttling** — measured per trace, since one trace can fire 10-50 calls
4. **Average Tokens Per Trace** — the earliest warning you'll get, before it shows up as cost
5. **Cost Per Successful Task** — not cost per attempt; retries hide in that number otherwise

There's a sixth I'm still working out — output consistency — but I'm not confident enough
in how to instrument it yet to write it up properly.

## If you're starting from zero

Pick one dimension and give it a sprint. Trying to stand up all five at once usually means
none of them get finished. I'd start with average token count per traces it's the one most likely
to already be broken without anyone noticing.
