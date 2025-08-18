
# Dapr Agent Flow

This repository explores personal productivity flows using the **Dapr Agents** framework, implementing voice-to-action workflows that automatically process voice recordings and execute appropriate actions.

> **DISCLAIMER**: Almost 95% created with GitHub Copilot

The implementation is based on a [N8N](https://n8n.io) flow that monitors voice recordings on OneDrive, transcribes them, classifies the content, and determines whether to create tasks or send email notifications.

![](images/original-n8n-flow.png)

## Voice2Action Workflow

The Voice2Action workflow implements an end-to-end voice processing pipeline with three main stages:

### FR001: OneDrive Voice Recording Download
- Polls a OneDrive folder for new voice recordings (`audio/x-wav` and `audio/mpeg` files only)
- Downloads only files not previously processed
- Automatic polling at configurable intervals
- Uses MSAL client credentials flow for Graph API authentication

### FR002: Voice Transcription  
- Transcribes voice recordings using OpenAI Whisper API
- Stores transcription in JSON format alongside the original file
- Preserves file structure and metadata

- Uses Dapr Agents with Intent Orchestrator to analyze transcriptions
- Determines appropriate actions based on content:
  - **Task Creation**: Creates todo items for detected commands/reminders
  - **Email Fallback**: Sends email notifications for general notes
- Implements agent-based architecture with specialized agents


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

Set up your credentials (store securely in production):

```bash
# OneDrive/Graph Configuration  
export ONEDRIVE_VOICE_INBOX="/Recordings/Inbox"
export MS_GRAPH_CLIENT_ID="your-azure-app-client-id"
export MS_GRAPH_CLIENT_SECRET="your-azure-app-client-secret"

# OpenAI Configuration
export OPENAI_API_KEY="your-openai-api-key"
```

### 3. Run the Complete System

Start all services using the Dapr multi-app runner:

```bash
dapr run -f master.yaml
```

This starts:
- **authenticator** (port 5000): Initial Graph authentication helper
- **workflows**: Workflow polling and orchestration worker  
- **worker-voice2action** (port 5001): Voice2Action workflow worker with pub/sub subscriber
- **intent-orchestrator** (port 5100): Intent-based action planning orchestrator
- **agent-taskplanner** (port 5101): Task creation agent
- **agent-fallback-emailer** (port 5102): Email notification agent

### 4. Initial Authentication

With delegated MSAL tokens, no manual token provisioning is required after the first interactive consent; tokens are refreshed automatically and stored durably in the `tokenstatestore`.

Optionally, if using an interactive flow, you can use the authenticator service:
```bash
# Navigate to http://localhost:5000 to complete OAuth flow
# Tokens are automatically stored in Dapr state store for reuse
```

Note: The authenticator requests scopes: User.Read, Files.ReadWrite, and Mail.Send. If you previously authenticated without Mail.Send, re-run the authenticator once to grant the additional scope before sending email (FR007).

### Task Webhook Contract (FR008)

The OfficeAutomation agent creates tasks by POSTing to `CREATE_TASK_WEBHOOK_URL` with this exact JSON body:

```
{
  "title": "some title",
  "due": "optional - ISO8601 datetime",
  "reminder": "optional - ISO8601 datetime"
}
```

Fields `due` and `reminder` are omitted when not provided. The Tasker agent tools provide timezone details to help you build proper ISO8601 strings with offsets.

## Monitoring and Logs

- **Workflow State**: Check Dapr state store for workflow execution status
- **Agent States**: Individual agents maintain state in `{AgentName}_state.json` files
- **File Processing**: Monitor `./.work/voice/` for processed recordings and transcriptions
- **Logs**: All services output structured logs with correlation IDs for tracing

## Development

The codebase follows Dapr Agents best practices:
- **Deterministic Orchestrators**: No I/O operations in workflow orchestrators
- **Idempotent Activities**: All activities support retry and state recovery
- **Event-Driven Architecture**: Pub/sub messaging between workflows and agents
- **Structured Logging**: Consistent logging format with correlation tracking

See [voice2action-requirements.md](./voice2action-requirements.md) for detailed functional and technical requirements.

