from flask import Flask, redirect, request, send_file
from services.token_state_store import TokenStateStore
import base64
import io
import logging
import os
import msal

# Configuration
CLIENT_ID = os.getenv("MS_GRAPH_CLIENT_ID")
CLIENT_SECRET = os.getenv("MS_GRAPH_CLIENT_SECRET")
AUTHORITY = os.getenv("MS_GRAPH_AUTHORITY", "https://login.microsoftonline.com/consumers")
REDIRECT_URI = "http://localhost:5000/signin-oidc"
SCOPES = ["User.Read", "Files.ReadWrite"]
TOKEN_STATE_KEY = "global_ms_graph_token_cache"  # persist MSAL cache

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("authenticator")

@app.route('/favicon.ico')
def favicon():
    # 1x1 transparent PNG
    png_base64 = (
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII='
    )
    png_bytes = base64.b64decode(png_base64)
    return send_file(io.BytesIO(png_bytes), mimetype='image/png')

@app.route("/")
def index():
    # Create an MSAL app (cache optional here, used mainly after code redemption)
    msal_app = msal.ConfidentialClientApplication(
        client_id=CLIENT_ID,
        client_credential=CLIENT_SECRET,
        authority=AUTHORITY,
    )
    auth_url = msal_app.get_authorization_request_url(SCOPES, redirect_uri=REDIRECT_URI)
    return redirect(auth_url)

@app.route("/signin-oidc")
def signin_oidc():
    # Step 2: Receive code and exchange for token using msal
    code = request.args.get("code")
    if not code:
        return "No code provided", 400
    # Load existing cache (if any) so we keep accounts/refresh tokens
    cache = msal.SerializableTokenCache()
    state = TokenStateStore()
    raw = state.get(TOKEN_STATE_KEY)
    if raw:
        try:
            cache.deserialize(raw)
        except Exception:
            logger.warning("Failed to deserialize token cache; starting fresh.")
    msal_app = msal.ConfidentialClientApplication(
        client_id=CLIENT_ID,
        client_credential=CLIENT_SECRET,
        authority=AUTHORITY,
        token_cache=cache,
    )
    result = msal_app.acquire_token_by_authorization_code(
        code,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )
    logger.debug({k: v for k, v in result.items() if k != "access_token"})
    if "access_token" not in result:
        logger.error(f"Token request failed: {result.get('error_description', result)}")
        return f"Token request failed: {result.get('error_description', result)}", 400
    # Persist MSAL cache (includes refresh tokens and accounts)
    if cache.has_state_changed:
        state.set(TOKEN_STATE_KEY, cache.serialize())
    logger.info("MSAL token cache stored in tokenstatestore.")
    return "Authentication successful! Token stored. You may close this window."

if __name__ == "__main__":
    app.run(port=5000)
