# Dapr Agent Flow

This repository explores personal productivity flows using the **Dapr Agents** framework, implementing voice-to-action workflows that automatically process voice recordings and execute appropriate actions.

> **DISCLAIMER**: Almost 95% created with GitHub Copilot

The implementation is based on a [N8N](https://n8n.io) flow that monitors voice recordings on OneDrive, transcribes them, classifies the content, and determines whether to create tasks or send email notifications.

![](images/original-n8n-flow.png)

## Voice2Action Workflow

Basic flow as implemented here - see [my post](https://dev.to/kaiwalter/dipping-into-dapr-agentic-workflows-fbi) for more background:

1. polling on OneDrive, downloading and transcribing the voice recording runs in a deterministic workflow
2. transcript is then handed to LLM-orchestrated agents which have instructions to figure out what to do with the transcription
3. agents to make use of tools (probably MCP servers in the future) to interact with the outside world

## Repository Structure

### Top Level / Tier 1 Structure

The structure leans into structures provided by [quickstart samples](https://github.com/dapr/dapr-agents/tree/main/quickstarts). Some polishing is still required, but I wanted to get the code out there to get feedback and learnings from the community.

[Dapr Multi-App Run](https://docs.dapr.io/developing-applications/local-development/multi-app-dapr-run/multi-app-overview/) file `master.yaml` points to the top-level applications and entry points:

- **services/ui/authenticator** : a small web UI that redirects into a MS Entra ID login which on callback serializes the access and refresh tokens into a Dapr state store;
  from there token information is picked up to authenticate for OneDrive and OpenAI API calls by the other services;
  basic idea is to make the login once and let the workflow processes run in the background without further interaction
- **services/workflow/worker** : runs the main polling loop at a timed interval to kick off the workflow, and the workflows to come, with a pub/sub signal;
  with that I achieve some loose coupling between the workflow and the main loop (instead of using child workflows or alike)
- **services/workflow/worker_voice2action** : defines the deterministic steps of the main Voice-2-Action workflow;
  schedules a new instance when receiving pub/sub event from the main worker **services/workflow/worker**
- **services/intent_orchestrator/app** : bringing a LLM orchestrator for intent processing into standby, waiting for pub/sub events from **services/workflow/worker_voice2action** publish intent orchestrator activity
- **services/intent_orchestrator/agent_tasker** : participating in above orchestration as a utility agent which delivers information required for the flow like the transcript or time zone information
- **services/intent_orchestrator/agent_office_automation** : participating in above orchestration to fulfill all tasks which connect the flow to office automation, like creating tasks or sending emails
- **services/ui/monitor** : a small console app listening to and printing the LLM orchestration broadcast messages to allow for a better understanding of the flow; this is absolutely required to fine-tune the instructions to the orchestrator and the agents

### Tier 2 Elements

- **workflows/voicetoaction / voice2action_poll_orchestrator** : orchestrating the activities to list the files on OneDrive, marking new files and handing of each single file to child workflow ...
- **workflows/voicetoaction / voice2action_per_file_orchestrator** : ... orchestrating in sequential order: download recording, transcription, publish to intent workflow and then archive the file

### Tier 3 Elements

On this level in folder **activities** are workflow activities defined in modules which are referenced by deterministic workflows.

### Tier 4 Elements

Folder **services** directly contains helper services which are used by workflow activities or agents.

### Other Elements

Folder **components** holds all Dapr resource components used by all applications. Important to note is, that **state stores are segregated for their purpose**: for workflow state, for agent state and for token state. This is required as these state types require different configuration for prefixing state keys and the ability to hold actors.

Folder **models** contains common model definitions used by the workflow elements and agents.

## Environment Configuration

### Environment Variable Cross Reference

The following table shows which environment variables are used by which Python and Node.js applications, and the corresponding Docker Compose service name.

| Environment Variable           | Application (Entrypoint)                        | Docker Compose Service         |
|-------------------------------|-------------------------------------------------|-------------------------------|
| DAPR_APP_PORT                 | All apps (Python & Node.js)                     | authenticator, workflows, worker-voice2action, orchestrator-intent, agent-task-planner, agent-office-automation, web-monitor |
| DAPR_LOG_LEVEL                | All apps (Python & Node.js)                     | authenticator, workflows, worker-voice2action, orchestrator-intent, agent-task-planner, agent-office-automation, web-monitor |
| DAPR_API_MAX_RETRIES          | All apps (Python & Node.js)                     | authenticator, workflows, worker-voice2action, orchestrator-intent, agent-task-planner, agent-office-automation, web-monitor |
| DAPR_AGENTS_STATE_DIR         | All Python apps                                 | authenticator, workflows, worker-voice2action, orchestrator-intent, agent-task-planner, agent-office-automation |
| MS_GRAPH_AUTHORITY            | Authenticator, worker-voice2action, agent-office-automation | authenticator, worker-voice2action, agent-office-automation |
| MS_GRAPH_CLIENT_ID            | Authenticator, worker-voice2action, agent-office-automation | authenticator, worker-voice2action, agent-office-automation |
| MS_GRAPH_CLIENT_SECRET        | Authenticator, worker-voice2action, agent-office-automation | authenticator, worker-voice2action, agent-office-automation |
| ONEDRIVE_VOICE_INBOX          | workflows (worker.py)                           | workflows                     |
| ONEDRIVE_VOICE_ARCHIVE        | workflows (worker.py)                           | workflows                     |
| ONEDRIVE_VOICE_POLL_INTERVAL  | workflows (worker.py)                           | workflows                     |
| LOCAL_VOICE_DOWNLOAD_FOLDER   | workflows, worker-voice2action, orchestrator-intent, agent-task-planner, agent-office-automation | workflows, worker-voice2action, orchestrator-intent, agent-task-planner, agent-office-automation |
| LOCAL_VOICE_INBOX             | workflows (worker.py)                           | workflows                     |
| LOCAL_VOICE_ARCHIVE           | workflows (worker.py)                           | workflows                     |
| OFFLINE_MODE                  | workflows (worker.py)                           | workflows                     |
| DEBUGPY_ENABLE                | workflows, worker-voice2action, agent-task-planner | workflows, worker-voice2action, agent-task-planner |
| PYDEVD_DISABLE_FILE_VALIDATION| worker-voice2action, agent-task-planner, agent-office-automation | worker-voice2action, agent-task-planner, agent-office-automation |
| PYTHONUNBUFFERED              | All Python apps                                 | authenticator, workflows, worker-voice2action, orchestrator-intent, agent-task-planner, agent-office-automation |
| OPENAI_API_KEY                | worker-voice2action, orchestrator-intent, agent-task-planner, agent-office-automation | worker-voice2action, orchestrator-intent, agent-task-planner, agent-office-automation |
| OFFICE_TIMEZONE               | agent-task-planner                              | agent-task-planner            |
| SEND_MAIL_RECIPIENT           | agent-office-automation                         | agent-office-automation       |
| CREATE_TASK_WEBHOOK_URL       | agent-office-automation                         | agent-office-automation       |

> **Note:**  
> - All Dapr-enabled applications use `DAPR_APP_PORT`, `DAPR_LOG_LEVEL`, and `DAPR_API_MAX_RETRIES`.
> - Some variables (e.g., `MS_GRAPH_*`, `OPENAI_API_KEY`) are only required for specific capabilities.

## Required Environment Variables

| Environment Variable           | Default Value                                 | Purpose                                                                                 |
|-------------------------------|-----------------------------------------------|-----------------------------------------------------------------------------------------|
| ONEDRIVE_VOICE_INBOX          | (none)                                       | OneDrive folder path to monitor for new recordings                                      |
| ONEDRIVE_VOICE_POLL_INTERVAL  | 30                                           | Polling interval in seconds (min: 5)                                                    |
| ONEDRIVE_VOICE_ARCHIVE        | (none)                                       | OneDrive folder path to archive processed recordings                                    |
| MS_GRAPH_CLIENT_ID            | (none)                                       | Azure AD application client ID for MS Graph                                             |
| MS_GRAPH_CLIENT_SECRET        | (none)                                       | Azure AD application client secret for MS Graph                                         |
| MS_GRAPH_AUTHORITY            | https://login.microsoftonline.com/consumers   | Azure AD authority endpoint for MS Graph                                                |
| OPENAI_API_KEY                | (none)                                       | OpenAI API key for transcription/classification                                         |
| OPENAI_CLASSIFICATION_MODEL   | gpt-4.1-mini                                 | Default model for classification                                                        |
| LOCAL_VOICE_DOWNLOAD_FOLDER   | ./.work/voice                                | Local directory for downloads                                                           |
| SEND_MAIL_RECIPIENT           | (none)                                       | Recipient for all outgoing emails (FR007)                                               |
| CREATE_TASK_WEBHOOK_URL       | (none)                                       | Target webhook URL for creating tasks (FR008)                                           |
| TRANSCRIPTION_TERMS_FILE      | (none)                                       | Optional path to a text file with one term per line to bias transcription (FR002)       |

## Optional Environment Variables

| Environment Variable           | Default Value                                 | Purpose                                                                                 |
|-------------------------------|-----------------------------------------------|-----------------------------------------------------------------------------------------|
| STATE_STORE_NAME               | workflowstatestore                           | Dapr state store component name for workflow/actor state                                |
| DAPR_PUBSUB_NAME               | pubsub                                       | Dapr pub/sub component name                                                             |
| DAPR_LOG_LEVEL                 | info                                         | Logging level                                                                           |
| DAPR_API_MAX_RETRIES           | (none)                                       | Max retries for Dapr API calls (if supported by SDK/app)                                |
| DAPR_INTENT_ORCHESTRATOR_TOPIC | IntentOrchestrator                           | Pub/sub topic for intent orchestrator                                                   |
| TOKEN_STATE_STORE_NAME         | tokenstatestore                              | Dapr state store component name for token cache                                         |
| OFFLINE_MODE                   | false                                        | Use local inbox/archive instead of OneDrive (FR009)                                     |
| LOCAL_VOICE_INBOX              | ./local_voice_inbox                          | Local folder for incoming audio files (used if OFFLINE_MODE=true)                       |
| LOCAL_VOICE_ARCHIVE            | ./local_voice_archive                        | Local folder for archiving processed files (used if OFFLINE_MODE=true)                  |
| OFFICE_TIMEZONE                | (system timezone)                            | Target timezone for scheduling/time operations (used by Tasker agent only).<br/>Specifies the target timezone for all scheduling and time-related operations (e.g., `Europe/Berlin`, `US/Central`).<br/>If not set, the system timezone will be used as the default.<br/>The Tasker agent exposes tools (`get_office_timezone`, `get_office_timezone_offset`) to provide the effective timezone and offset to all other agents and workflow steps. Do not read this variable directly in other agents. |

### Common Terms for Transcription (FR002)

You can improve transcription accuracy by providing a list of domain-specific terms.

- Create a UTF-8 text file with one term per line. Blank lines and lines starting with `#` are ignored.
- Set `TRANSCRIPTION_TERMS_FILE` to the absolute path of this file. Example:

```bash
export TRANSCRIPTION_TERMS_FILE="$PWD/config/transcription_terms.txt"
```

The workflow will pass these terms to the OpenAI Whisper API as a biasing prompt.

## Quick Start

### 1. Setup Dependencies

```bash
# Install dependencies (Python virtual environment recommended)
pip install -r requirements.txt

# Create necessary directories
mkdir -p ./.work/voice
```

### 2. Configure Environment

Set up your credentials (store securely in production) in file `.env`:

```bash
# OneDrive/Graph Configuration
export ONEDRIVE_VOICE_INBOX="/Recordings/Inbox"
export MS_GRAPH_CLIENT_ID="your-azure-app-client-id"
export MS_GRAPH_CLIENT_SECRET="your-azure-app-client-secret"

# OpenAI Configuration
export OPENAI_API_KEY="your-openai-api-key"
```

### Run the Complete System

Maintain your environment variables in `.env` in this format:

```env
export ONEDRIVE_VOICE_INBOX="/Recordings/Inbox"
export ONEDRIVE_VOICE_ARCHIVE="/Recordings/Processed"
export OFFICE_TIMEZONE="Europe/Berlin"
```

Start all services using the Dapr multi-app runner:

```bash
dapr init
./start-multi.sh
```

or with Docker Compose

```bash
dapr init --slim
./start-docker-compose.sh
```

> be sure to clean up with `dapr uninstall --all` when switchting between these local hosting modes.

## Debugging

### Redis pub/sub not triggering 

How to check Redis (Dapr uses Redis Streams by default):

- Open a shell in the Dapr Redis container:
  - docker exec -it dapr_redis redis-cli
- Inspect the stream for the topic:
  - XINFO STREAM voice2action-schedule
  - XRANGE voice2action-schedule - +
- Check consumer groups (created when a subscriber registers):
  - XINFO GROUPS voice2action-schedule
  - If no groups listed, the subscriber wasn’t registered.
- Inspect pending for a group (replace <group> with the app-id of the subscriber sidecar, often dapr-<app-id>):
  - XPENDING voice2action-schedule <group>