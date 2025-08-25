
# Voice2Action Requirements

## Functional

Consider technical requirements in [general requirements document](./general-requirements.md)

- **FR001**: Download new voice recordings
	- Download new recordings from a OneDrive folder specified by `ONEDRIVE_VOICE_INBOX` in the format `/folder/sub-folder`.
	- Only files not yet downloaded are fetched.
	- System polls automatically at an interval set by `ONEDRIVE_VOICE_POLL_INTERVAL` (seconds).
	- For each new recording, a separate workflow instance is started to handle the download.
	- only accept `audio/x-wav` and `audio/mpeg` file types
	- relevant: [TR001](./general-requirements.md#TR001)


- **FR002**: Transcribe downloaded voice recording
	- Transcribe the recording and store the transcription in JSON format aside the recording file but replacing the extension with `.json`.
	- After transcription, invoke the intent orchestration process to handle classification and action planning.
	- Use a list of common terms that are provided in a plain text file by the user to make transcription more accurate.
	- If common terms file is not specified, do not pass to transcription process.
	- If common terms file is specified but does not exist, log a warning.
	- relevant: [TR002](./general-requirements.md#TR002)

- **FR003**: Plan and Execute Actions
	- The intent orchestration process uses the transcription to plan and execute actions in an LLM agentic, LLM based flow [see `TR003`].
	- Create an action to create a task in a to do list - leave the implementation empty for the moment - when the LLM detects a command or instruction to create a task or set a reminder.
	- As a fallback action, if no other action is detected, create an action to send an email - leave the implementation empty for the moment.
	- relevant: [TR002](./general-requirements.md#TR002)
	- see also: [TR003](./general-requirements.md#TR003)

- **FR004**: Monitor LLM based workflow
	- As a user I want to have a separate UI application that listens to and displays the conversation flow (intent workflow chat history) so that I can observe the decision and processing logic to further improve the classification prompt and the agent instructions.
	- Call it `monitor`.
	- Monitor shall listen to the same topic (`beacon_channel`) as the agents involved in the intent workflow.
	- For a start, logging the conversation is sufficient. No web UI is required.
	- relevant: [TR003](./general-requirements.md#TR003)

- **FR005**: Time zone (Single Source of Truth)
	- The system must provide a single source of truth for the target timezone, determined by the environment variable `OFFICE_TIMEZONE` (e.g., `Europe/Berlin`, `US/Central`). If not set, the system timezone is used.
	- This logic is implemented in the Tasker agent, which exposes tools to retrieve the effective timezone and offset.
	- All other agents and workflow steps must use these Tasker agent tools to obtain timezone information for scheduling and time-related operations, rather than reading the environment variable directly.

- **FR006**: After processing archive recording
	- When transcription is concluded move the recording file on OneDrive to a folder specified by environment variable `ONEDRIVE_VOICE_ARCHIVE` in the format `/folder/sub-folder`.
	- If a file with the same name already exists in the target folder, delete that one first and then conduct the move operation.
	- relevant: [TR001](./general-requirements.md#TR001)

- **FR007**: Sending emails
	- Send emails using Outlook (personal).
	- The recipent is always the same address. Take it from the environment variable `SEND_MAIL_RECIPIENT`.
	- This logic is implemented in the Office Automation agent.
	- relevant: [TR001](./general-requirements.md#TR001)

- **FR008**: Create to-do item
	- To-do items need to be created in a space outside personal MS Graph/Outlook/OneDrive domain.
	- Hence to create a to-do item a HTTP POST webhook is to be called.
	- This logic is implemented in the Office Automation agent.
	- Take the target URL from the environment variable `CREATE_TODO_ITEM_WEBHOOK_URL`.
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
	-  relevant: [TR004](./general-requirements.md#TR004)

-- **FR010**: Web-based LLM workflow monitor
	- Additionally to `FR004` a simple web SPA is required to observe conversation flow of LLM orchestrator and agents.
	- Call it `web-monitor`.
	- Monitor shall listen to the same topic (`beacon_channel`) as the agents involved in the intent workflow.
	- The web SPA shall use signaling to let the web backend app send updates to the web frontend.
	- Let the design be a nice and modern chat like rendering.
	- Monitor shall start together with the other Dapr applications and use all common settings.
	- Monitor shall be implemented with Node.js.
	- relevant: [TR003](./general-requirements.md#TR003)

