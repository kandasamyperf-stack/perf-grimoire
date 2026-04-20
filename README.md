# perf-grimoire

> The dark arts of performance engineering for agentic AI and MCP.

A weekly collection of fully functional performance engineering projects focused on agentic AI pipelines, MCP tool calls, and LLM observability.

Each topic is a standalone, runnable project with tests, security scans, and CI/CD.

---

## Topics

| # | Project | Focus | Status |
|---|---------|-------|--------|
| 01 | [MCP Tool Call Latency Profiler](./01-mcp-latency-profiler/) | p50/p95/p99 latency per MCP tool | ✅ Live |
| 02 | Coming Saturday | Agent memory benchmark | 🔜 Soon |
| 03 | Coming soon | LLM token throughput profiler | 📅 Planned |
| 04 | Coming soon | MCP server cold start analyser | 📅 Planned |

---

## What is perf-grimoire?

Performance engineering for agentic AI is still a dark art — most teams don't instrument their agent loops, don't know their p99 tool latencies, and don't catch regressions until production. This repo changes that.

Every Saturday a new project is added covering:
- MCP tool call performance
- Agent loop bottleneck detection
- LLM inference throughput
- Memory and context window efficiency
- Load testing agentic pipelines

---

## Philosophy

> "A grimoire is a book of spells too powerful for ordinary people. Performance engineering is the same — most teams avoid it until it's too late."

Each project in this repo is:
- Fully functional and runnable out of the box
- Security scanned before publishing (Bandit + pip-audit)
- Reviewed every Friday before Saturday publish
- Focused on real problems in production agentic systems

---

## Contributing

PRs welcome. All contributions must pass security scan and Friday review before Saturday publish.

## License

MIT © perf-grimoire contributors
