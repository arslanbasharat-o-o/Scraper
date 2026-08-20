# Real-Time UI Plan

Plan date: 2026-07-24

## Transport Decision

Use polling for current job status. Status changes tolerate a delay of several
seconds, the Flask backend already exposes read-only status endpoints, and
polling keeps deployment and recovery simple.

Do not make Extractor results or History automatically real-time. Their updates
are user-triggered and unsolicited refresh could replace visible work.

## Screen Plan

| Screen | Business reason | Source | Transport | Frequency | Failure behavior |
| --- | --- | --- | --- | --- | --- |
| Automation | Run progress, ETA, pause/resume state | `/api/automation/jobs`, `/api/automation/runs` | Polling | Fast while active, slower while idle | No overlap, hidden-tab pause, retain last state |
| Menu Map | Background discovery progress | `/api/menu-map/jobs/<id>` | Polling | 2.5 seconds while healthy | Exponential backoff to 30 seconds, visible error, resume when visible |
| History | User reviews durable snapshots | Existing GET routes | Manual refresh | On demand | Preserve current list and show retry |
| Extractor | User starts a synchronous extraction | `/api/scrape` | One request with progress UI | On demand | Timeout/abort message and preserved input |

## Polling Requirements

- Never overlap requests.
- Use recursive timeouts, not fixed intervals.
- Pause when `document.hidden` where background updates are not useful.
- Resume immediately when visible.
- Clear timers on `pagehide`.
- Keep the last known good state during transient failure.
- Do not retry mutation requests automatically.
- Use compact list payloads and load heavy detail only on selection.

## SSE Evaluation

SSE may replace active polling if measured load or progress latency becomes a
problem. A future SSE endpoint would require authenticated same-origin streams,
event IDs, reconnection using `Last-Event-ID`, duplicate suppression, heartbeat
events, connection limits, and a polling fallback.

SSE is not currently justified because there are few local operators and
polling load is low after payload compaction.

## WebSocket Evaluation

WebSockets are not recommended. No workflow requires bidirectional
collaboration, chat, presence, or synchronized editing.

## Security

All status data flows through Flask; the browser never accesses SQLite directly.
Before internet exposure, status endpoints and any future stream must enforce
authenticated user access and supplier/job authorization.

## Test Strategy

- Source-contract tests for visibility pause, page-exit cleanup, backoff cap,
  and compact payload parameters.
- API tests for backward-compatible default and opt-in compact payloads.
- Botasaurus test that hides/restores the page and observes request timing.
- Network audit for overlapping status requests and responses at 400 or above.
- Server test confirming polling is read-only and cannot mutate job state.
