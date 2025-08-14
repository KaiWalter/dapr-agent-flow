## Dapr State Key Prefix Strategy

This project uses the Dapr state key prefix strategy `none` (see [Dapr docs](https://docs.dapr.io/developing-applications/building-blocks/state-management/howto-share-state/#specifying-a-state-prefix-strategy)), so that all Dapr applications in the solution can share state using the same key names. This is required for scenarios like sharing a Microsoft Graph token between authenticator and workflow apps.
# Dapr Agent Flow

With this repository I want to explore various personal productivity flows I already implemented using N8N, Logic Apps or PowerAutomate Flows with **Dapr Agents** framework.

> **DISCLAIMER** : almost to 95% created with GitHub Copilot

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

## Run all components

One-time install and prepare dependencies

```
source .venv/bin/activate
pip install -r requirements.txt
mkdir -p ./.data
```

One-time set credentials for MS Graph/OneDrive access. Once the flow was started that access information is stored in `statestore`.

```
export ONEDRIVE_VOICE_INBOX="Recordings/Inbox"
export MS_GRAPH_CLIENT_ID=""
export MS_GRAPH_CLIENT_SECRET=""
export MS_GRAPH_TOKEN=""
```

Start the flow

```
export ONEDRIVE_VOICE_INBOX="Recordings/Inbox"
dapr run -f master.yaml
```

