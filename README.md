# perf-grimoire

> The arts of performance engineering for agentic AI, LLM inference, and cloud infrastructure scalability, resilience, and observability.

A collection of fully functional performance engineering projects focused on
agentic AI performance architecture, LLM performance, MCP, observability,Chaos Engineering
and cloud scalability.

Each topic is a standalone, runnable project with tests, security scans, and CI/CD.

---

## Topics

| # | Project | Focus | Goal |
|---|---------|-------|------|
| 01 | [MCP Tool Call Latency Profiler](./01-mcp-latency-profiler/) | p50/p95/p99 latency per MCP tool | Instrument every MCP tool call in an agentic pipeline, measure individual latency with p50/p95/p99 percentiles, identify bottleneck tools slowing down agent loops, and export a flame-style terminal dashboard plus JSON/CSV/Markdown reports for CI gating and observability dashboards. |
| 02 | [Agent Loop Cost Guardian](https://github.com/kandasamyperf-stack/perf-grimoire/blob/main/02-agent-loop-cost-guardian) | Token, cost & iteration budgets | Wrap any agentic loop with hard kill limits on token spend, USD cost, iteration count, and retry storms. Emits early warnings at 80% of any budget and terminates the loop instantly when a limit is breached — before runaway costs hit your bill. |

---

## What is perf-grimoire?

## What is this?

Most teams building agentic AI systems focus on what their agents can do —
not how fast, how efficiently, or how reliably they do it.

Performance engineering for agentic AI, LLM inference, and cloud infrastructure
is still largely unexplored territory. When your agent calls 10 MCP tools per
loop, runs 100 loops per task, and serves 1000 concurrent users — latency
compounds, memory bloats, cloud costs explode, infrastructure cracks under load,
and observability gaps make debugging nearly impossible.

perf-grimoire exists to change that.

This is a practical, hands-on collection of performance engineering projects
covering the full stack of agentic AI systems and the cloud infrastructure
that runs them:

- **MCP tool call latency** — measure, profile and optimise every tool
  invocation in your agent pipeline
- **Agent loop bottleneck detection** — find where your agent spends time
  and why loops slow down over iterations
- **LLM inference throughput** — benchmark token generation speed,
  concurrency limits, and model serving efficiency
- **Memory and context window efficiency** — track memory growth, context
  bloat, and token consumption per agent session
- **Load testing agentic pipelines** — simulate real-world concurrent agent
  traffic and find breaking points before production does
- **Cloud infrastructure scalability** — measure how your agentic system
  scales on AWS, GCP, and Azure — cost per agent call, auto-scaling
  behaviour, horizontal scaling limits, and cold start penalties
- **Cloud infrastructure resilience** — test failure scenarios, region
  failovers, retry storms, circuit breaker behaviour, and graceful
  degradation under infrastructure stress
- **Observability for AI systems** — instrument your agents with distributed
  traces, metrics, and structured logs so you always know what is happening
  inside your pipeline in production — across every service, every cloud
  region, and every agent loop

---

## Philosophy

> "A grimoire is a master reference of techniques too advanced for most to attempt. Performance engineering is the same — the knowledge exists, but few teams apply it until production breaks."

Each project in this repo is:
- Fully functional and runnable with minimal setup
- Security scanned and dependency audited before every publish
- Tested with a full suite of unit and security tests
- Focused on real problems in production agentic AI, LLM, and cloud infrastructure systems
- Applicable to any cloud environment

---

## Contributing

PRs welcome. All contributions must pass security scan before publish.

## License

MIT © perf-grimoire contributors
