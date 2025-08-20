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

### Required Environment Variables

```bash

# OneDrive Configuration
ONEDRIVE_VOICE_INBOX="/folder/sub-folder"    # OneDrive folder path to monitor
ONEDRIVE_VOICE_POLL_INTERVAL=30              # Polling interval in seconds (min: 5)
ONEDRIVE_VOICE_ARCHIVE="/folder/archive-folder"  # OneDrive folder path to archive processed recordings (required)

# MS Graph Authentication (MSAL Client Credentials)
MS_GRAPH_CLIENT_ID="your-client-id"
MS_GRAPH_CLIENT_SECRET="your-client-secret"
MS_GRAPH_AUTHORITY="https://login.microsoftonline.com/consumers"  # Default

# OpenAI Configuration
OPENAI_API_KEY="your-openai-api-key"
OPENAI_CLASSIFICATION_MODEL="gpt-4.1-mini"    # Default model for classification

# Local Storage
LOCAL_VOICE_DOWNLOAD_FOLDER="./.work/voice"       # Local directory for downloads

# Email
SEND_MAIL_RECIPIENT="you@example.com"      # Recipient for all outgoing emails (FR007)

# Tasks (Webhook)
CREATE_TASK_WEBHOOK_URL="https://your.task.endpoint/ingest"  # Target webhook for creating tasks (FR008)
```

### Optional Environment Variables

```bash
# Dapr Configuration
STATE_STORE_NAME="workflowstatestore"                # Dapr state store component name
DAPR_PUBSUB_NAME="pubsub"                   # Dapr pub/sub component name
DAPR_LOG_LEVEL="info"                       # Logging level

# Intent Orchestrator Topic
DAPR_INTENT_ORCHESTRATOR_TOPIC="IntentOrchestrator"  # Pub/sub topic for intent orchestrator
# Token Cache State Store (MSAL)
TOKEN_STATE_STORE_NAME="tokenstatestore"     # Dapr state store component name for token cache

# Offline Mode (FR009)
OFFLINE_MODE="false"                        # Set to "true" to use local inbox/archive instead of OneDrive
LOCAL_VOICE_INBOX="./local_voice_inbox"     # Local folder for incoming audio files (used if OFFLINE_MODE=true)
LOCAL_VOICE_ARCHIVE="./local_voice_archive" # Local folder for archiving processed files (used if OFFLINE_MODE=true)

# Development/Debugging
DEBUGPY_ENABLE="0"                          # Enable remote debugging (1/0)
PYDEVD_DISABLE_FILE_VALIDATION="1"          # PyCharm debugging optimization
```

`OFFICE_TIMEZONE` (optional):

- Specifies the target timezone for all scheduling and time-related operations (e.g., `Europe/Berlin`, `US/Central`).
- If not set, the system timezone will be used as the default.
- The Tasker agent exposes tools (`get_office_timezone`, `get_office_timezone_offset`) to provide the effective timezone and offset to all other agents and workflow steps. Do not read this variable directly in other agents.

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