# Dapr Agent Flow – Copilot App Instructions

Pub/Sub and Service Invocation Convention
- Always use `DaprClient` (from `dapr.clients`) to publish events to pub/sub topics or make service invocations.
- Do NOT use `requests` or direct HTTP calls to the Dapr API for these operations.
- `DaprClient` will automatically wrap your data in a CloudEvent envelope for pub/sub.
- At the top-level entrypoint of every app (orchestrator, agent, worker, etc.), ensure the root logger is configured so all module loggers emit to console. Use this pattern:

Logging convention for all root modules:

  import logging
  level = os.getenv("DAPR_LOG_LEVEL", "info").upper()
  root = logging.getLogger()
  if not root.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
      fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
      datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)
  root.setLevel(getattr(logging, level, logging.INFO))

This ensures all logs are visible and consistently formatted.

Scope
- Focus on application code: Dapr Workflows orchestrating Dapr Agents (LLM + tools). Minimal runtime notes included for multi-app runs.

Big picture
- Goal: Build personal productivity flows with Dapr Workflows coordinating Dapr Agents.
- Style: Orchestrator/Activity pattern. Orchestrators stay deterministic; Activities perform I/O and call agents/services.

Solution layout
- workflows/: Dapr Workflow orchestrators (e.g., `workflows/voice2action.py`, `workflows/todo_capture.py`).
- activities/: Dapr Workflow activities doing I/O (e.g., `activities/downloader_activity.py`, `activities/fetch_calendar.py`).
- agents/ (optional): Agent step implementations, prompts/config, tools, routing (e.g., `agents/inbox_agent.py`, `agents/downloader_agent.py`).
- models/: Pydantic/dataclass request/response contracts shared across workflows/activities.
- services/: Thin adapters to external APIs (Graph, Gmail, Notion, http client, storage, etc.).
  - Group capabilities by module: one capability per file (e.g., `services/onedrive.py`, `services/state_store.py`, `services/http_client.py`). Keep these stateless.
- services/workflow/: Workflow runtime and supporting publisher/subscriber apps (e.g., `worker_voice2action.py` hosts WorkflowRuntime and a Flask HTTP subscriber for Dapr pub/sub; `worker.py` publishes schedule events).
- services/ui/: Minimal UI helpers or launchers (e.g., `services/ui/authenticator.py`). Place any CLI/UI entrypoints here if needed.
- services/intent_orchestrator/ (optional): If using an intent-based orchestrator service, host it here (e.g., `app.py`). Default ports:
  - Orchestrator service: 5100
  - Agents (examples): 5101, 5102

Signal handler workaround for FastAPI-based orchestrators/agents:
- For any FastAPI-based orchestrator or agent (using dapr-agents or similar), patch the `.stop()` method on the service/agent instance and its class to be an async function that returns None, before calling `.start()`. This prevents shutdown errors from signal handlers expecting a coroutine. Example:

    async def stop_ignore_args(*args, **kwargs):
        return None
    agent.stop = stop_ignore_args
    AgentClass.stop = stop_ignore_args
    await agent.start()

Apply this pattern to all orchestrator/agent entrypoints that use FastAPI or dapr-agents service mode.
Debugging convention for all root modules:
- At the top-level entrypoint of every app (orchestrator, agent, worker, etc.), add the following block to enable remote debugging if the `DEBUGPY_ENABLE` environment variable is set:

  if os.getenv("DEBUGPY_ENABLE", "0") == "1":
    debugpy.listen(("0.0.0.0", 5678))
    print("debugpy: Waiting for debugger attach on port 5678...")
    debugpy.wait_for_client()

This ensures a consistent debugging experience across all services.
- components/: Dapr components (pubsub, state, bindings). Keep secrets in secret stores, not code.

Scaffolding and app structure rules (repo-specific)
- Do NOT create new top-level app folders or a src/ directory. Put new files directly into the folders above.
- Reuse the single shared `requirements.txt` at the repo root. Do NOT create per-app requirements files.
- Reuse the common Dapr components in `components/`. Do NOT duplicate component manifests.
- When adding:
  - a new workflow: add a file under `workflows/` and register it in the existing worker under `services/workflow/`.
  - a new activity: add under `activities/` and register in the worker.
  - a new service adapter: add a new module under `services/` (one capability per file).
  - a new UI/CLI entrypoint: add under `services/ui/` (no frameworks unless requested).
- Do not add new virtualenv or dependency managers; use the existing repo setup (e.g., `requirements.txt`, `flake.nix`).
- Note: The pub/sub subscriber HTTP endpoint belongs to the workflow service (Flask in `services/workflow/`), not to `services/ui/`.

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
- Define agent step functions and config under agents/ when used. Keep system prompts, tool wiring, and routing policies nearby.
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
- Single shared `requirements.txt` (no per-app dependency files) and no `src/` folder.
- Services are split by capability into separate modules under `services/`.
- UI helpers/entrypoints live under `services/ui/`.

Scaffolding examples
- Minimal “hello agent” flow: `HelloWorld` orchestrator calls an activity that invokes a simple Agent with a single tool, returns a short summary string.
- Utility activity: HTTP GET wrapper under `activities/http_get.py` using a `services/http_client.py` adapter.
- Voice to Action: Poller orchestrator (single-shot) -> fan-out per-file child orchestrators -> activities download and mark state.
- Note: Example filenames are illustrative; create them only when needed.

Local multi-app run (Dapr)
- Run all apps with a single spec file:
  - `dapr run -f ./master.yaml` (includes `resourcesPath: ./components`). Orchestrator on 5100; agents on 5101/5102.
- Ensure the state store component sets `actorStateStore: true` so workflows/actors persist state.
- All services/workers/workflows reuse the common `components/` manifests.
- Pub/Sub: The workflow app exposes a Flask subscriber at `/schedule-voice2action` matching the configured topic (e.g., `voice2action-schedule`).

Secrets and configuration
- Do not embed secrets in code. Use a Dapr secret store and environment variables; activities read configuration via env and resolve secrets via Dapr if needed.
- Voice2Action env:
  - `ONEDRIVE_VOICE_INBOX`: OneDrive folder to poll.
  - `ONEDRIVE_VOICE_POLL_INTERVAL`: Poll cadence in seconds (used by the publisher to emit schedule events).
  - `VOICE_DOWNLOAD_DIR`: Local folder to save downloads (default `./downloads/voice`).
- Graph/OneDrive env (current implementation uses MSAL client credentials):
  - `MS_GRAPH_CLIENT_ID`, `MS_GRAPH_CLIENT_SECRET`, `MS_GRAPH_AUTHORITY` (default `https://login.microsoftonline.com/consumers`).
  - Tokens are persisted in the Dapr state store and refreshed automatically before expiry.
  - Token cache store (separate state store): set `TOKEN_STATE_STORE_NAME` (default `tokenstatestore`).
    - Component `components/tokenstate.yml` (default Redis) holds the token cache. Do not mix with workflow/actor state.
- State store env:
  - `STATE_STORE_NAME`: Dapr state store name for workflows/actors (default `workflowstatestore`).
  - `TOKEN_STATE_STORE_NAME`: Dapr state store name for auth/token cache (default `tokenstatestore`).
- Keep environment-specific details (components, app-ids/ports) outside application code.

References
- [Voice2Action Requirements](../voice2action-requirements.md)
- Dapr Workflows SDK docs (Python): orchestration patterns, deterministic constraints, activity signatures, and retries.