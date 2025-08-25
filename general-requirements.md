# General Requirements

## Technical

**TR001**<a name="TR001"></a>: MS Graph authentication and token management
- Use MSAL Authorization Code Flow (delegated) for personal Microsoft accounts with scopes: `User.Read`, `Files.ReadWrite`, `Mail.Send`.
- Bootstrap once using the authenticator UI to obtain user consent and seed the MSAL token cache; after that, no manual token steps are required.
- Persist the MSAL token cache (including refresh tokens) in a Dapr state store for durability and reuse across restarts.
- State store name via `TOKEN_STATE_STORE_NAME` (default `tokenstatestore`), cache key: `global_ms_graph_token_cache`.
- OneDrive/Outlook services automatically refresh tokens before expiry; activities/tools do not handle tokens directly.
- Configuration via env (or secret store): `MS_GRAPH_CLIENT_ID`, `MS_GRAPH_CLIENT_SECRET`, `MS_GRAPH_AUTHORITY` (default `https://login.microsoftonline.com/consumers`).
- Optional (enterprise): For work/school tenants, Client Credentials Flow with application permissions may be supported; document separate scopes/authority and use a different cache key.

**TR002**<a name="TR002"></a>: Use OpenAI Whisper API for transcription and OpenAI models for classifications
- Use `OPENAI_API_KEY` (from environment or secret store) for authentication.
- For classifcation use model provided by `OPENAI_CLASSIFICATION_MODEL`, make `GPT-4.1-MINI` the default.

**TR003**<a name="TR003"></a>: Use Dapr Agent LLM based orchestrator to determine actions.
- Run the LLM Orchestrator service on port 5100 and agents on dedicated ports (e.g., 5101, 5102).
- Publish classification results to the orchestrator via Dapr pub/sub (component `pubsub`) on topic `IntentOrchestrator`.
- Each action identified shall be implemented as a tool available to the orchestrator/agents.
- Use <https://github.com/dapr/dapr-agents/tree/main/quickstarts/05-multi-agent-workflows/services> as scaffolding structure.

**TR004**<a name="TR004"></a>: Consider repository structure for layering
- Consider [repository structure in README.md](./README.md) carefully to decide where to split and place logic.
- Tiering rules (enforced):
    - Tier 1 (workers/entrypoints) is the single place that reads environment variables controlling runtime mode and folders. It computes and passes a minimal config into workflows.
    - Tiers 2/3 (workflows and activities) must not read mode/folder environment variables. They only consume values passed from Tier 1.
- Config contract passed from Tier 1:
    - `offline_mode` (bool)
    - `inbox_folder` (string)
    - `archive_folder` (string)
    - `download_folder` (string)
- Naming convention: Prefer `_folder` suffix for path-like settings (e.g., `inbox_folder`, `archive_folder`, `download_folder`).
- Tier 1 reads env only for these inputs, then publishes/schedules workflows with the config:
    - `OFFLINE_MODE`, `ONEDRIVE_VOICE_INBOX`, `ONEDRIVE_VOICE_ARCHIVE`, `LOCAL_VOICE_INBOX`, `LOCAL_VOICE_ARCHIVE`, `VOICE_DOWNLOAD_DIR`.
- Activities must validate required inputs (e.g., require `inbox_folder`/`archive_folder` where needed) and remain stateless and env-free for these settings, improving testability.
