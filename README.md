# Dapr Agent Flow

With this repository I want to explore various personal productivity flows I already implemented using N8N, Logic Apps or PowerAutomate Flows with **Dapr Agents** framework.


## Voice2Action workflow

The workflow `Voice2Action` polls a OneDrive folder and downloads new voice recordings to a local inbox.

- Required env vars:
  - `ONEDRIVE_VOICE_INBOX`: path under OneDrive root to poll
  - `ONEDRIVE_VOICE_POLL_INTERVAL`: seconds between polls
  - `VOICE2ACTION_DOWNLOADER_CONFIG`: JSON containing Graph access (see below)
- Optional env vars:
  - `VOICE_LOCAL_INBOX`: local folder to write downloads (default `./data/voice_inbox`)

Downloader config JSON example for `VOICE2ACTION_DOWNLOADER_CONFIG`:
```
{
  "folder_path": "VoiceUploads",
  "access_token": "<graph_access_token>",
  "graph_base_url": "https://graph.microsoft.com/v1.0"
}
```

Start worker with Dapr components:
```
dapr run --app-id workflow-worker --app-port 8001 --resources-path ./components -- python -m services.workflow.worker
```

Start a workflow instance (single-shot or bounded testing):
```
python -m services.workflow.client  # optionally set env CORR_ID, IDEMPOTENCY_KEY
```

Notes
- Only files not previously downloaded are fetched by comparing last-modified checkpoint (`since`).
- Polling cadence is controlled by `ONEDRIVE_VOICE_POLL_INTERVAL` via a deterministic workflow timer.


## Voice2Action FR001 (OneDrive polling and download)

Environment variables:
- `ONEDRIVE_VOICE_INBOX`: OneDrive folder path to poll (e.g., `/Voice/Inbox`).
- `ONEDRIVE_VOICE_POLL_INTERVAL`: Poll interval in seconds (default 30, min 5).
- `MS_GRAPH_TOKEN`: OAuth token for Microsoft Graph (bearer). Use a Dapr secret store in production.
- `VOICE_DOWNLOAD_DIR`: Local directory for downloaded files (default `./downloads/voice`).
- `STATE_STORE_NAME`: Dapr state store component name (default `statestore`).
- `START_VOICE_POLL`: `1` to auto-start poller on worker boot (default `1`).

Run locally:

```bash
pip install -r requirements.txt
# In one terminal
dapr run --app-id workflows --app-port 3500 --resources-path ./components -- python -m services.workflow.worker
```

Notes:
- Orchestrator is deterministic: only schedules activities and timers.
- Activities perform I/O to OneDrive via Microsoft Graph and track idempotency in the state store.


## Run all components with Dapr Multi-App

Specs are in `apps/`. Start everything with your local `components/`:

```
dapr run -f ./apps --resources-path ./components
```

Apps:
- workflow-worker (8001): services.workflow.worker
- llm-orchestrator (8004): services.llm_orchestrator.app
- agents-api (8010): services.agents_api.app

Then start a Voice2Action instance if desired:

```
python -m services.workflow.client
```

