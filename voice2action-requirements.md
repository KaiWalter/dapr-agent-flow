
# Voice2Action Requirements (Minimal)

## Functional

- **FR001**: Download new voice recordings
	- Download new recordings from a OneDrive folder specified by `ONEDRIVE_VOICE_INBOX`.
	- Only files not yet downloaded are fetched.
	- System polls automatically at an interval set by `ONEDRIVE_VOICE_POLL_INTERVAL` (seconds).
	- For each new recording, a separate workflow instance is started to handle the download.
    - only accept `audio/x-wav` and `audio/mpeg` file types

## Technical

- **TR001**: Keep access token to MS Graph alive
	- Provide the access token to MS Graph once via `MS_GRAPH_TOKEN` (env or secret).
	- Token is refreshed automatically before expiry.
	- Refresh token can be stored in the local state store.
