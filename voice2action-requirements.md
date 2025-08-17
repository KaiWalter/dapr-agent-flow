
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
	- The recipent is always the same address. Take it from the environment variable `OUTLOOK_RECIPIENT`.
	- This logic is implemented in the Office Automation agent.
	- relevant: `TR001`

## Technical

- **TR001**: MS Graph authentication and token management
	- Use MSAL client credentials flow with `MS_GRAPH_CLIENT_ID`, `MS_GRAPH_CLIENT_SECRET` (from environment or secret store).
	- Store the MSAL token cache (including refresh tokens) in the Dapr state store for durability and reuse across restarts.
	- Tokens are refreshed automatically before expiry by the OneDrive service; activities/services do not handle tokens directly.
	- No manual token provisioning is required after initial configuration; all token management is handled transparently.

- **TR002**: Use OpenAI Whisper API for transcription and OpenAI models for classifications
    - Use `OPENAI_API_KEY` (from environment or secret store) for authentication.
	- For classifcation use model provided by `OPENAI_CLASSIFICATION_MODEL`, make `GPT-4.1-MINI` the default.

- **TR003**: Use Dapr Agent LLM based orchestrator to determine actions.
	- Run the LLM Orchestrator service on port 5100 and agents on dedicated ports (e.g., 5101, 5102).
	- Publish classification results to the orchestrator via Dapr pub/sub (component `pubsub`) on topic `IntentOrchestrator`.
	- Each action identified shall be implemented as a tool available to the orchestrator/agents.
	- Use <https://github.com/dapr/dapr-agents/tree/main/quickstarts/05-multi-agent-workflows/services> as scaffolding structure.
