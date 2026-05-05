# 03 · mcp-load-forge

> Forge your MCP server under real load — before production does it for you.

Part of [perf-grimoire](https://github.com/kandasamyperf-stack/perf-grimoire) — the dark arts of performance engineering for agentic AI.

---

## What It Does

Most teams deploy MCP servers and assume they'll hold up under load. They don't test cold start latency, concurrent tool call throughput, or what happens when agent traffic spikes 2×. `mcp-load-forge` fills that gap.

It runs four load phases against any MCP server and tells you exactly where it breaks:

| Phase | What It Tests |
|---|---|
| **Cold Start** | First-connection latency — how slow is a cold MCP server? |
| **Ramp Up** | Gradual concurrency increase — does latency creep as VUs grow? |
| **Sustained** | Peak load held for N seconds — does the server stay stable? |
| **Spike** | Burst beyond peak — where is the breaking point? |

---

## Quick Start

```bash
# Install
pip install -e .

# Run against built-in mock MCP server (no real server needed)
mcp-load-forge

# Run against your real MCP server
mcp-load-forge --url http://localhost:8000 --tool echo --concurrency 20

# Tight budget — spike at 3× and fail if p99 > 500ms
mcp-load-forge --url http://localhost:8000 --concurrency 10 --spike 3.0 --p99-threshold 500
```

---

## Example Output

```
⚒️  MCP Load Forge starting against http://127.0.0.1:18080
   Peak VUs: 10  |  Spike: 20 VUs

  [cold_start] sampling 5 cold connections…
  [ramp_up] ramping to 10 VUs over 5s…
  [sustained] holding 10 VUs for 10s…
  [spike] firing spike at 20 VUs for 5s…

==============================================================
  MCP LOAD FORGE — Results
==============================================================
  Server  : http://127.0.0.1:18080
  Tool    : echo
  Peak VUs: 10
  Spike   : 20 VUs
--------------------------------------------------------------
  Cold Start   median=32.4ms  max=48.7ms
--------------------------------------------------------------
  Phase        p50      p95      p99    err%  calls
  ------------------------------------------------------
  Ramp Up    34.1ms   51.2ms   58.9ms   1.2%     50
  Sustained  33.8ms   49.7ms   55.3ms   0.8%    100
  Spike      41.2ms   78.4ms  112.6ms   3.1%     20
--------------------------------------------------------------
  Overall  p99=112.6ms  err=1.4%  throughput~10.0 rps
--------------------------------------------------------------
  Thresholds:
    p99 < 2000ms         ✅ PASS
    error rate < 5%      ✅ PASS
    cold start < 500ms   ✅ PASS
--------------------------------------------------------------
  ✅  FORGE PASSED — server held up under load
==============================================================
```

---

## Use in Code

```python
from mcp_load_forge import LoadForger, ForgeConfig

config = ForgeConfig(
    server_url="http://localhost:8000",
    tool_name="search",
    tool_args={"query": "forge-test"},
    concurrency=20,
    ramp_up_seconds=10,
    sustained_seconds=30,
    spike_multiplier=2.5,
    p99_threshold_ms=1000.0,
    error_rate_threshold=0.02,
)

forger = LoadForger(config)
result = forger.run(on_progress=print)

print(f"Passed: {result.passed}")
print(f"p99: {result.overall_p99_ms:.1f}ms")
print(f"Error rate: {result.overall_error_rate:.1%}")
print(f"Cold start median: {result.cold_start_median_ms:.1f}ms")

if not result.passed:
    for reason in result.failure_reasons:
        print(f"  FAIL: {reason}")
```

---

## CLI Reference

| Flag | Default | Description |
|---|---|---|
| `--url` | mock | MCP server URL (omit to use built-in mock) |
| `--tool` | `echo` | MCP tool name to call |
| `--concurrency` | `10` | Peak virtual users |
| `--ramp-up` | `5` | Ramp-up duration in seconds |
| `--sustained` | `10` | Sustained load duration in seconds |
| `--requests` | `100` | Total requests across all phases |
| `--spike` | `2.0` | Spike multiplier (e.g. 2.0 = 2× peak VUs) |
| `--p99-threshold` | `2000` | Fail if p99 latency exceeds this (ms) |
| `--error-threshold` | `0.05` | Fail if error rate exceeds this (fraction) |
| `--mock-port` | `18080` | Port for built-in mock server |
| `--mock-latency` | `30` | Mock server base latency (ms) |
| `--mock-error-rate` | `0.02` | Mock server error injection rate |

---

## Running Tests

```bash
pytest -v
```

## Security Scan

```bash
bandit -r mcp_load_forge/
pip-audit
```

---

## License

MIT © perf-grimoire contributors
