# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Email: security@perf-grimoire.dev (or open a private GitHub Security Advisory).

You will receive a response within 48 hours. We aim to patch and release within 7 days of confirmed reports.

## Security design

- **No credentials recorded.** The profiler captures tool names, durations, and error type strings only. It does not log tool arguments or return values by default.
- **No network calls.** The profiler is entirely local — no telemetry is phoned home.
- **Output is pure data.** JSON/CSV/Markdown exports contain no executable code.
- **Dependency surface is minimal.** The only runtime dependency is `rich` for terminal rendering.

## Running the security scan locally

```bash
pip install bandit pip-audit
bandit -r mcp_latency_profiler/ --severity-level medium
pip-audit
```
