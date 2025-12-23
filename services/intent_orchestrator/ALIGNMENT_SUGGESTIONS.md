# Alignment Suggestions for Intent Orchestrator

Based on a comparison with the `dapr-agents` library and the `workflow-llm` quickstart (and `frodo` service), the following improvements are suggested for the `intent_orchestrator` service to align with established patterns.

## 1. Adopt `AgentProfileConfig` for Durable Agents

**Files**: `agent_office_automation.py`, `agent_facilitator.py`
**Observation**: Currently, agent identity (name, role, goal, instructions) is passed directly to the `DurableAgent` constructor, or as loose arguments.
**Recommendation**: Use the `AgentProfileConfig` class to encapsulate these properties, as seen in the `frodo` quickstart.

```python
# Before
agent = DurableAgent(
    name="OfficeAutomation",
    role="Office Assistant",
    goal="...",
    instructions=[...],
    # ...
)

# After (Recommended)
from dapr_agents.agents.prompting import AgentProfileConfig

profile = AgentProfileConfig(
    name="OfficeAutomation",
    role="Office Assistant",
    goal="...",
    instructions=[...],
)

agent = DurableAgent(
    profile=profile,
    # ...
)
```

## 2. Switch to Async Execution Pattern

**Files**: `agent_office_automation.py`, `agent_facilitator.py`
**Observation**: The agents currently use a synchronous `main` function with `runner.serve()` and include a `_patch_stop` workaround. The `frodo` sample uses an async pattern which handles shutdown more gracefully.
**Recommendation**: Convert to `async def main()`, use `runner.register_routes()`, and `wait_for_shutdown()`.

```python
import asyncio
from dapr_agents.workflow.utils.core import wait_for_shutdown

async def main():
    # ... setup agent ...
    runner = AgentRunner()
    runner.register_routes(agent)
    await wait_for_shutdown()
    runner.shutdown(agent)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
```

## 3. Correct Orchestrator Initialization

**File**: `orchestrator.py`
**Observation**: The `LLMOrchestrator` is initialized without the `runtime` argument. The `workflow-llm` quickstart explicitly passes `runtime=wf.WorkflowRuntime()`.
**Recommendation**: Inject the workflow runtime.

```python
import dapr.ext.workflow as wf

orchestrator = LLMOrchestrator(
    # ...
    runtime=wf.WorkflowRuntime(),
    # ...
)
```

## 4. Remove Workarounds

**Files**: All three `agent_*.py` and `orchestrator.py`
**Observation**: `_patch_stop` is present in all files.
**Recommendation**: With the adoption of the async `wait_for_shutdown` pattern (or proper `runner.serve` usage for orchestrator), these patches should be removed to rely on the library's native behavior.

## 5. Align State Configuration

**Files**: `agent_office_automation.py`, `agent_facilitator.py`
**Observation**: `AgentStateConfig` is using `state_key`. The samples typically use `key_prefix` within the `StateStoreService`.
**Recommendation**: Verify if `state_key` is necessary for your specific keying strategy. If not, prefer `key_prefix` for consistency.

```python
# Recommended Pattern
state = AgentStateConfig(
    store=StateStoreService(store_name="store_name", key_prefix="agent_prefix:"),
)
```
