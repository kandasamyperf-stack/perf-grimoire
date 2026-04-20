# MCP Tool Call Latency Profiler

> Part of [**perf-grimoire**](https://github.com/perf-grimoire) — the dark arts of performance engineering for agentic AI.

Instrument, measure, and visualise the latency of every MCP tool invocation in your agentic AI pipeline. Pinpoint which tools are your p99 bottlenecks, track latency drift across agent loops, and export results for CI gating or dashboards.

```
┌──────────────────────────────────────────────────────────────────┐
│  Session summary                                                  │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────────┐   │
│  │ 30 calls │ 8 tools  │ 1.2/s    │ 2 errors │ p99: 612ms   │   │
│  └──────────┴──────────┴──────────┴──────────┴──────────────┘   │
│                                                                    │
│  Tool                   Calls  p50     p95     p99   Flame        │
│  llm_summarise             6  481ms   598ms  612ms  ████████████  │
│  web_search                7  315ms   412ms  489ms  ████████▊     │
│  api_call_github           4  271ms   389ms  401ms  ███████▍      │
│  code_executor             5  203ms   284ms  301ms  █████▌        │
│  vector_search             3   91ms   118ms  124ms  ██▍           │
│  filesystem_read           3   18ms    22ms   24ms  ▍             │
└──────────────────────────────────────────────────────────────────┘
```

## Why this exists

MCP agents chain multiple tool calls per loop. A single slow tool — an LLM summariser, a web search, a vector store retrieval — compounds across hundreds of agent steps. Without instrumentation, you're flying blind. This profiler gives you:

- **Per-tool p50/p95/p99** latency breakdown
- **Flame-style bar charts** in the terminal (no browser needed)
- **Agent-loop heatmaps** — see which loops are slow
- **Error rate tracking** per tool
- **JSON / CSV / Markdown** exports for CI pipelines and dashboards
- **Zero-config wrapping** of any async MCP tool function

## Quick start

```bash
pip install mcp-latency-profiler

# Run the built-in demo (no MCP server needed)
python -m mcp_latency_profiler demo

# More agent loops
python -m mcp_latency_profiler demo --loops 10 --calls 8
```

## Instrument your own MCP tools

### Option 1 — wrap existing tool functions

```python
from mcp_latency_profiler.core.profiler import MCPLatencyProfiler

profiler = MCPLatencyProfiler(slow_threshold_ms=300)

# Wrap any async MCP tool function
search = profiler.wrap_tool("web_search", original_search_fn)
read   = profiler.wrap_tool("filesystem_read", original_read_fn)

# Use exactly as before — profiler records every call transparently
result = await search("agentic AI performance")
```

### Option 2 — context manager for manual blocks

```python
async with profiler.measure("custom_tool"):
    result = await some_mcp_operation()
```

### Option 3 — agent loop integration

```python
for iteration in range(max_loops):
    profiler.next_loop()          # track which loop each call belongs to

    async with profiler.measure("plan"):
        plan = await llm.plan(state)

    async with profiler.measure("execute"):
        result = await tools.run(plan)
```

## Generate reports

```python
from mcp_latency_profiler.core.dashboard import print_full_report
from mcp_latency_profiler.exporters.reporters import save_report

# Rich terminal report
print_full_report(profiler)

# Save for CI or dashboards
save_report(profiler, "latency.json",     fmt="json")
save_report(profiler, "latency.csv",      fmt="csv")
save_report(profiler, "latency_report.md", fmt="markdown")
```

## Access raw statistics

```python
stats = profiler.get_stats()

for tool_name, s in stats.items():
    print(f"{tool_name}: p50={s.p50:.1f}ms  p95={s.p95:.1f}ms  p99={s.p99:.1f}ms")

# Gate on SLOs in tests / CI
assert stats["web_search"].p99 < 600, "web_search p99 exceeded 600ms SLO"

# Inspect slow / failed calls
slow   = profiler.get_slow_calls(threshold_ms=500)
failed = profiler.get_failed_calls()
```

## CI integration

Add a latency gate to your CI pipeline:

```yaml
- name: Run agent benchmark
  run: python benchmark.py --output latency.json

- name: Enforce SLOs
  run: |
    python - <<'EOF'
    import json, sys
    data = json.load(open("latency.json"))
    slos = {"web_search": 600, "llm_summarise": 800}
    violations = []
    for tool, limit in slos.items():
        p99 = data["tool_stats"].get(tool, {}).get("latency_ms", {}).get("p99", 0)
        if p99 > limit:
            violations.append(f"{tool} p99={p99:.1f}ms > {limit}ms SLO")
    if violations:
        print("SLO VIOLATIONS:", *violations, sep="\n  ")
        sys.exit(1)
    EOF
```

## Security

- No credentials, tokens, or secrets are ever recorded or exported
- Tool names and error messages are captured as strings — avoid passing secrets as tool arguments
- All exports are pure data — no code execution in output files
- Run `bandit -r mcp_latency_profiler/` to verify static analysis

See [SECURITY.md](SECURITY.md) for the full disclosure policy.

## Project structure

```
mcp_latency_profiler/
├── core/
│   ├── profiler.py      # Async instrumentation engine, ToolCallRecord, ToolStats
│   └── dashboard.py     # Rich terminal renderer — tables, flame bars, heatmaps
├── exporters/
│   └── reporters.py     # JSON, CSV, Markdown exporters
├── tests/
│   └── test_profiler.py # Unit + security tests (stdlib only)
└── __main__.py          # CLI: demo, replay modes
```

## Roadmap

- [ ] OpenTelemetry trace export (OTLP)
- [ ] Prometheus metrics endpoint
- [ ] Async live dashboard (refresh every N seconds)
- [ ] Integration example with LangGraph + MCP
- [ ] SQLite backend for long-running session persistence

## Contributing

PRs welcome. All submissions must pass:
1. `python -m pytest mcp_latency_profiler/tests/ -v`
2. `bandit -r mcp_latency_profiler/ --severity-level medium`
3. Friday review by a maintainer before Saturday push

## License

MIT © perf-grimoire contributors
