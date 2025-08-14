
# Voice2Action Requirements (Minimal)

## Functional

- **FR001**: Download new voice recordings
	- Download new recordings from a OneDrive folder specified by `ONEDRIVE_VOICE_INBOX`.
	- Only files not yet downloaded are fetched.
	- System polls automatically at an interval set by `ONEDRIVE_VOICE_POLL_INTERVAL` (seconds).
	- For each new recording, a separate workflow instance is started to handle the download.
    - only accept `audio/x-wav` and `audio/mpeg` file types

## Technical

- **TR001**: MS Graph authentication and token management
	- Use MSAL client credentials flow with `MS_GRAPH_CLIENT_ID`, `MS_GRAPH_CLIENT_SECRET` (from environment or secret store).
	- Store the MSAL token cache (including refresh tokens) in the Dapr state store for durability and reuse across restarts.
	- Tokens are refreshed automatically before expiry by the OneDrive service; activities/services do not handle tokens directly.
	- No manual token provisioning is required after initial configuration; all token management is handled transparently.
