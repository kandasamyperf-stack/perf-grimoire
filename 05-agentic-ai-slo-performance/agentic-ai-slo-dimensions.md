# Agentic AI SLO Dimensions

*My view, based on production experience — not an official standard.*

Traditional SLOs measure infrastructure health: latency, availability, error rate, throughput.
That's fine for request-response APIs and microservices, where those dimensions cover most of
what actually goes wrong.

Agentic systems break that assumption. The infrastructure can be completely healthy while the
system fails at the task level. A `200 OK` means the infrastructure responded. It says nothing
about whether the agent actually got the job done.

Here's the number that made this real for me: an 8-step agent workflow where each step succeeds
95% of the time only completes 66 of 100 workflows end to end. 34 fail silently. No alert fires,
because every individual step reported success. Push each step to 99% and you get 92 complete —
that's not a 4-point improvement, it's 26 more people per 100 actually getting what they asked
for. Teams measuring SLOs at the span level will never catch this gap. That's what the five
dimensions below are for.

Full visual version: [`agentic-ai-slo-carousel.pdf`](./agentic-ai-slo-carousel.pdf)

---

## 1. Task Completion Rate

Every layer can log success while the workflow never actually finishes. I've seen this play out
at 500 cases an hour: 160 came back with a response but never completed the workflow correctly.
Sub-agents handed back partial output, the orchestrator accepted it and passed it forward, and
nothing downstream ever flagged it. No timeout, no error. Every step said success.

Delivering a response and completing a workflow correctly are not the same event, and most
monitoring setups treat them as if they were.

**Instrument it by** tracking two separate numbers — traces that finished, and traces that
finished *correctly*. The gap between them is the SLO.

**Target:** X% of traces reaching verified completion within Y steps and Z token budget. Set
this per workflow type. A global number hides more than it reveals here.

## 2. Step Efficiency

A task can succeed and still be a problem. An agent that takes 18 steps for something with a
4-step baseline is behaving unpredictably, even if it eventually gets there — more tokens, more
latency, and usually a sign something upstream changed.

I think of the baseline step count as the contract. Anything well above it is the system telling
you it renegotiated that contract without asking.

Track average steps per task per workflow type, and give yourself two weeks of stable production
traffic before you trust the baseline. From there, alert when the average climbs past 150% of
baseline — but tune that threshold per task type. A research agent and a lookup agent don't share
a step budget.

## 3. LLM Capacity and Throttling

When a provider throttles you mid-workflow, the agent stalls or just fails the task — and your
API dashboard shows nothing but "latency went up." A single trace can fire 10 to 50 LLM calls
depending on how the workflow branches, so any capacity plan built around single-call assumptions
is going to be wrong, consistently, in the same direction.

Plan capacity at the trace level. The request level was never the right unit for this.

Aggregate throttling events per trace, not per request — one trace that got throttled three
times is a worse signal than three separate traces each throttled once. For anything
business-critical, the target should be zero throttling events, with TPM limits tuned per
workflow based on how much that workflow actually matters.

## 4. Average Tokens Per Trace

This one's the leading indicator I'd watch first if I could only pick one. Token usage per trace
can spike right after an agent change while every per-call metric, and even total cost, still
looks fine that week. It catches context accumulation, loops, and retrieval drift before they
turn into a cost problem three weeks later.

One example: a billing agent running around 8,000 tokens per trace jumped to 24,000 after a new
tool got added. Nothing else moved. The trace-level number caught it before the monthly invoice
did.

Sum input and output tokens across every generation span inside a single trace, and track the
daily average — Langfuse or whatever observability tool you're already on works fine. Alert when
the 7-day rolling average clears the 4-week baseline by more than 2 standard deviations, and
recheck this specifically after any agent change, prompt edit, or new tool.

## 5. Cost Per Successful Task

Cost per request undercounts the real cost, because it spreads failed attempts across the
denominator instead of charging them to anything. Take 100 attempts, 70 completed correctly,
$50 spent: cost per attempt is $0.50, but cost per successful task is $0.71. That 21-cent gap is
just the 30 failed runs, still sitting in the bill.

Retries are the quiet driver here — every retry adds cost without adding a completion, so a
climbing retry rate inflates this number faster than total spend alone would suggest.

Tag cost at the trace level by task type, and don't average across task types with different
complexity — a simple lookup and a multi-step research task shouldn't share a cost baseline.
Set the SLO as acceptable variance around that baseline, and revisit it whenever retry rate
moves.

---

## Where I'd start

If you're setting these up for the first time, don't try to land all five in one sprint:

1. Task completion rate — verified at trace level, not span level
2. Step efficiency — steps per task against baseline
3. LLM capacity and throttling — rate-limit impact at trace level
4. Average tokens per trace — drift after agent changes
5. Cost per successful task — including retries and failures

One dimension per sprint is realistic. Trying to instrument all five at once usually means none
of them get done properly.

There's a sixth one I'm circling but haven't fully defined yet: output consistency — same input,
same outcome, within some acceptable variance. Non-determinism you're not measuring is just a
reliability gap you haven't found yet.

Bottom line: agentic SLOs aren't a checklist you copy — they're an engineering discipline you
build. Define the budget, measure against it, alert when it's breached.
