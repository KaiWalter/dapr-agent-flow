# Dapr Agent Flow – Copilot App Instructions

Scope
- Focus on application code: Dapr Workflows orchestrating Dapr Agents (LLM + tools). Minimal runtime notes included for multi-app runs.

Big picture
- Goal: Build personal productivity flows with Dapr Workflows coordinating Dapr Agents.
- Style: Orchestrator/Activity pattern. Orchestrators stay deterministic; Activities perform I/O and call agents/services.

Solution layout
- workflows/: Dapr Workflow orchestrators (e.g., `workflows/voice2action.py`, `workflows/todo_capture.py`).
- activities/: Dapr Workflow activities doing I/O (e.g., `activities/downloader_activity.py`, `activities/fetch_calendar.py`).
- agents/: Agent step implementations, prompts/config, tools, routing (e.g., `agents/inbox_agent.py`, `agents/downloader_agent.py`).
- models/: Pydantic/dataclass request/response contracts shared across workflows/activities.
- services/: Thin adapters to external APIs (Graph, Gmail, Notion, http client, storage, etc.).
- services/workflow/: Workflow worker and optional clients (`worker.py`, `client.py`).
- services/llm_orchestrator/: If using an LLM-first orchestrator service, host it here (e.g., `app.py`).
- components/: Dapr components (pubsub, state, bindings). Keep secrets in secret stores, not code.

Choosing Workflow vs LLM Orchestration
- Use Dapr Workflow orchestrator when you need:
  - Durable, long-running coordination (minutes to weeks), deterministic replay, checkpoints.
  - Fan-out/fan-in of multiple activities, retries/backoff, timers, external events.
  - Clear business steps where each step is an idempotent activity.
- Use an LLM Orchestrator (agent-driven loop) when you need:
  - Short-lived conversational/tool-using reasoning loops with dynamic tool selection.
  - Heuristic decision-making where prompt state drives next action.
  - Pluggable agents and memory policies.
- Compose them:
  - Orchestrator invokes a single agent step as an Activity (one activity = one agent/tool step).
  - Persist durable IDs/checkpoints in workflow state; store large or long-term memory in a state store addressed by IDs.

Workflows (dapr.ext.workflow)
- Keep orchestrators pure: no network/IO, no time.sleep; only schedule activities/timers.
- Pass small, serializable payloads (dicts/JSON). Version orchestrators via module/function names.
- Two patterns for cadence:
  - Long-lived workflow with deterministic timers (`create_timer`) to loop.
  - Single-shot workflow that does one cycle and completes; schedule it externally on a cadence (recommended here).
- Use `RetryOptions` around `ctx.call_activity` for transient faults when needed.
- Current repo pattern: single-shot orchestrator -> list/plan -> fan-out child orchestrators -> complete.
- Prefer passing function objects to `ctx.call_activity(...)` and `ctx.call_child_workflow(...)` for refactor-safety. If using strings, ensure they match registered names exactly.

Activities
- Perform all side effects (HTTP calls, files, service invocation, bindings).
- Function signature: `def activity(ctx, input: dict) -> dict`.
- Register activities in the worker and call them by passing the function object from the orchestrator.
- Make activities idempotent (accept correlation/idempotency keys from workflow input if needed; here we use PENDING/DOWNLOADED keys in state store).
- Wrap API calls under services/ to keep activities thin and testable.
- Name activities to reflect intent.

Agents (Dapr Agents framework)
- Define agent step functions and config under agents/. Keep system prompts, tool wiring, and routing policies nearby.
- Register tools that wrap services/ calls; type inputs/outputs via models/.
- Invoke agents only from Activities, never from orchestrators. Prefer one activity = one agent step.

Cross-component communication
- Prefer Dapr service invocation for synchronous calls between Activities and agent-hosted APIs.
- Use pub/sub for fire-and-forget notifications; keep workflow state in the orchestrator.
- Store durable info (checkpoints/memory) in a Dapr state store, referenced by IDs passed through workflow context.

Conventions
- File naming: snake_case.py; function names reflect intent (e.g., `plan_day_orchestrator`, `send_email_activity`).
- Logging: use a helper (e.g., `wf_log`) to mirror `ctx.log(...)` into the Python logger `voice2action` for visibility in process logs.
- Inputs/Outputs: define Pydantic models in models/ and serialize to dicts when crossing workflow/activity boundaries.
- When calling activities/child workflows, pass function objects to avoid name mismatches.

Scaffolding examples
- Minimal “hello agent” flow: `HelloWorld` orchestrator calls an activity that invokes a simple Agent with a single tool, returns a short summary string.
- Utility activity: HTTP GET wrapper under `activities/http_get.py` using a `services/http_client.py` adapter.
- Voice to Action: Poller orchestrator (single-shot) -> fan-out per-file child orchestrators -> activities download and mark state.

Local multi-app run (Dapr)
- Run all apps with a single spec file:
  - `dapr run -f ./master.yaml` (includes `resourcesPath: ./components`, `logLevel: debug`, and `enableAPILogging: true`).
- Ensure the state store component sets `actorStateStore: true` so workflows/actors persist state.

Secrets and configuration
- Do not embed secrets in code. Use a Dapr secret store and environment variables; activities read configuration via env and resolve secrets via Dapr if needed.
- Voice2Action env:
  - `ONEDRIVE_VOICE_INBOX`: OneDrive folder to poll.
  - `ONEDRIVE_VOICE_POLL_INTERVAL`: Poll cadence in seconds (used by the worker to schedule the single-shot poll orchestrator).
- Keep environment-specific details (components, app-ids/ports) outside application code.

References
- Dapr Agents quickstarts and patterns (use local quickstarts repo for scaffolds).
- Dapr Workflows SDK docs (Python): orchestration patterns, deterministic constraints, activity signatures, and retries.