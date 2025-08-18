
# Voice2Action Requirements (Minimal)

## Functional

### Voice to Action workflow

- **FR001**: Download new voice recordings
	- Download new recordings from a OneDrive folder specified by `ONEDRIVE_VOICE_INBOX` in the format `/folder/sub-folder`.
	- Only files not yet downloaded are fetched.
	- System polls automatically at an interval set by `ONEDRIVE_VOICE_POLL_INTERVAL` (seconds).
	- For each new recording, a separate workflow instance is started to handle the download.
    - only accept `audio/x-wav` and `audio/mpeg` file types
	- relevant: `TR001`


- **FR002**: Transcribe downloaded voice recording
	- Transcribe the recording and store the transcription in JSON format aside the recording file but replacing the extension with `.json`.
	- After transcription, invoke the intent orchestration process to handle classification and action planning.
	- relevant: `TR002`

- **FR003**: Plan and Execute Actions
	- The intent orchestration process uses the transcription to plan and execute actions in an LLM agentic, LLM based flow [see `TR003`].
	- Create an action to create a task in a to do list - leave the implementation empty for the moment - when the LLM detects a command or instruction to create a task or set a reminder.
	- As a fallback action, if no other action is detected, create an action to send an email - leave the implementation empty for the moment.
	- relevant: `TR002`

- **FR004**: Monitor LLM based workflow
	- As a user I want to have a separate UI application that listens to and displays the conversation flow (intent workflow chat history) so that I can observe the decision and processing logic to further improve the classification prompt and the agent instructions.
	- Call it `monitor`.
	- Monitor shall listen to the same topic (`beacon_channel`) as the agents involved in the intent workflow.
	- For a start, logging the conversation is sufficient. No web UI is required.
	- relevant: `TR003`

- **FR005**: Time zone (Single Source of Truth)
	- The system must provide a single source of truth for the target timezone, determined by the environment variable `OFFICE_TIMEZONE` (e.g., `Europe/Berlin`, `US/Central`). If not set, the system timezone is used.
	- This logic is implemented in the Tasker agent, which exposes tools to retrieve the effective timezone and offset.
	- All other agents and workflow steps must use these Tasker agent tools to obtain timezone information for scheduling and time-related operations, rather than reading the environment variable directly.

- **FR006**: After processing archive recording
	- When transcription is concluded move the recording file on OneDrive to a folder specified by environment variable `ONEDRIVE_VOICE_ARCHIVE` in the format `/folder/sub-folder`.
	- If a file with the same name already exists in the target folder, delete that one first and then conduct the move operation.
	- relevant: `TR001`

- **FR007**: Sending emails
	- Send emails using Outlook (personal).
	- The recipent is always the same address. Take it from the environment variable `SEND_MAIL_RECIPIENT`.
	- This logic is implemented in the Office Automation agent.
	- relevant: `TR001`

- **FR008**: Create task
	- Tasks need to be created in a space outside personal MS Graph/Outlook/OneDrive domain.
	- Hence to create a task a HTTP POST webhook is to be called.
	- This logic is implemented in the Office Automation agent.
	- Take the target URL from the environment variable `CREATE_TASK_WEBHOOK_URL`.
	- POST body needs to have exactly below structure with optional due and reminder:

```json
{
	"title": "some title",
	"due": "optional - due date in ISO8601 format",
	"reminder": "optional - reminder in ISO8601 format"
}
```

- **FR009**: Offline Recordings Mode
	- As a user I want to be able to set the system in an offline mode, where files are not downloaded from OneDrive but from the local filesystem.
	- I want to be able to set this mode explcitily with environment variable `OFFLINE_MODE` which need to have the value **true** - case-insensitive.
	- In such a case not OneDrive is polled [see FR001] but a folder on the local system specified by `LOCAL_VOICE_INBOX` in the format `/folder/inbox-folder`.
	- The same applies for archiving the file [see FR006] on the local system specified by `LOCAL_VOICE_ARCHIVE` in the format `/folder/archive-folder`.
	- Create both folders in case those do not exist yet.
	- Sending emails or creating tasks still uses online capabilities.
	- Existing workflows are to be used. Just the points which interact with OneDrive needs to be switchable to local filesystem.
	-  relevant: `TR004`

-- **FR010**: Web-based LLM workflow monitor
	- Additionally to `FR004` a simple web SPA is required to observe conversation flow of LLM orchestrator and agents.
	- Call it `web-monitor`.
	- Monitor shall listen to the same topic (`beacon_channel`) as the agents involved in the intent workflow.
	- The web SPA shall use signaling to let the web backend app send updates to the web frontend.
	- Let the design be a nice and modern chat like rendering.
	- Monitor shall start together with the other Dapr applications and use all common settings.
	- Monitor shall be implemented with Node.js.
	- relevant: `TR003`

## Technical

- **TR001**: MS Graph authentication and token management
	- Use MSAL Authorization Code Flow (delegated) for personal Microsoft accounts with scopes: `User.Read`, `Files.ReadWrite`, `Mail.Send`.
	- Bootstrap once using the authenticator UI to obtain user consent and seed the MSAL token cache; after that, no manual token steps are required.
	- Persist the MSAL token cache (including refresh tokens) in a Dapr state store for durability and reuse across restarts.
		- State store name via `TOKEN_STATE_STORE_NAME` (default `tokenstatestore`), cache key: `global_ms_graph_token_cache`.
	- OneDrive/Outlook services automatically refresh tokens before expiry; activities/tools do not handle tokens directly.
	- Configuration via env (or secret store): `MS_GRAPH_CLIENT_ID`, `MS_GRAPH_CLIENT_SECRET`, `MS_GRAPH_AUTHORITY` (default `https://login.microsoftonline.com/consumers`).
	- Optional (enterprise): For work/school tenants, Client Credentials Flow with application permissions may be supported; document separate scopes/authority and use a different cache key.

- **TR002**: Use OpenAI Whisper API for transcription and OpenAI models for classifications
    - Use `OPENAI_API_KEY` (from environment or secret store) for authentication.
	- For classifcation use model provided by `OPENAI_CLASSIFICATION_MODEL`, make `GPT-4.1-MINI` the default.

- **TR003**: Use Dapr Agent LLM based orchestrator to determine actions.
	- Run the LLM Orchestrator service on port 5100 and agents on dedicated ports (e.g., 5101, 5102).
	- Publish classification results to the orchestrator via Dapr pub/sub (component `pubsub`) on topic `IntentOrchestrator`.
	- Each action identified shall be implemented as a tool available to the orchestrator/agents.
	- Use <https://github.com/dapr/dapr-agents/tree/main/quickstarts/05-multi-agent-workflows/services> as scaffolding structure.

- **TR004**: Consider repository structure for layering
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
