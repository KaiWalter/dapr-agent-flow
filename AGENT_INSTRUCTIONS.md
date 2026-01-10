# Agent Instructions for dapr-agent-flow-main

## Overview
This repository (`dapr-agent-flow-main`) implementation of a personal productivity agents application. It depends on the Dapr Agents framework, which is located in the sibling directory `../dapr-agents`.

## Workspace Structure
- **Application**: `@[../dapr-agent-flow-main]`
  - Contains the service implementations and business logic for the productivity agents.
- **Framework**: `@[../dapr-agents]`
  - Contains the source code for the `dapr-agents` library.
  - **Do not modify the framework code** unless explicitly instructed to fix a bug or add a feature to the library itself. Focus on the application code.

## Code Generation Guidelines

When generating code for this application, you must adhere to the following rules:

1.  **Library Compatibility**: All generated code must be compatible with the `dapr-agents` library found in `../dapr-agents`.
2.  **Integration Pattern**: Follow the patterns established in the `dapr-agents` quickstarts, specifically `@[../dapr-agents/quickstarts/05-multi-agent-workflows/services/workflow-llm]`.

## Implementation Pattern

Based on the reference implementation, services should follow this structure:

### 1. Imports
Import necessary components from `dapr_agents` and `dapr.ext.workflow`.

```python
import dapr.ext.workflow as wf
from dapr_agents.agents.configs import (
    AgentExecutionConfig,
    AgentPubSubConfig,
    AgentRegistryConfig,
    AgentStateConfig,
)
from dapr_agents.agents.orchestrators.llm import LLMOrchestrator
# ... other agent types
from dapr_agents.storage.daprstores.stateservice import StateStoreService
from dapr_agents.workflow.runners import AgentRunner
```

### 2. Configuration
Configure the agent using environment variables and the config classes.

```python
pubsub = AgentPubSubConfig(
    pubsub_name=os.getenv("PUBSUB_NAME", "messagepubsub"),
    agent_topic=os.getenv("AGENT_TOPIC", "topic.name"),
    broadcast_topic=os.getenv("BROADCAST_TOPIC", "broadcast.topic"),
)

state = AgentStateConfig(
    store=StateStoreService(
        store_name=os.getenv("WORKFLOW_STATE_STORE", "workflowstatestore"),
        key_prefix="agent.prefix:",
    ),
)
# ... Registry and Execution configs
```

### 3. Service Execution
Use `AgentRunner` to run the agent/orchestrator.

```python
orchestrator = LLMOrchestrator(
    # ... params
    runtime=wf.WorkflowRuntime(),
)

runner = AgentRunner()
try:
    runner.serve(orchestrator, port=8004)
finally:
    runner.shutdown(orchestrator)
```

## Reference
For detailed implementation examples, look at:
`@[../dapr-agents/quickstarts/05-multi-agent-workflows/services/workflow-llm/app.py]`
