from flask import Flask, redirect, request, send_file, make_response
from services.state_store import StateStore
import base64
import io
import json
import logging
import os
import msal
import time

# Configuration
CLIENT_ID = os.getenv("MS_GRAPH_CLIENT_ID")
CLIENT_SECRET = os.getenv("MS_GRAPH_CLIENT_SECRET")
AUTHORITY = os.getenv("MS_GRAPH_AUTHORITY", "https://login.microsoftonline.com/common")
REDIRECT_URI = "http://localhost:5000/signin-oidc"
SCOPE = "User.Read Files.ReadWrite.All"
TOKEN_STATE_KEY = "global_ms_graph_token_state"

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
    # Step 1: Redirect user to Microsoft login
    auth_url = (
        f"{AUTHORITY}/oauth2/v2.0/authorize?"
        f"client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}"
        f"&response_mode=query&scope={SCOPE.replace(' ', '%20')}"
    )
    return redirect(auth_url)

@app.route("/signin-oidc")
def signin_oidc():
    # Step 2: Receive code and exchange for token using msal
    code = request.args.get("code")
    if not code:
        return "No code provided", 400
    msal_app = msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=AUTHORITY,
        client_credential=CLIENT_SECRET,
    )
    result = msal_app.acquire_token_by_authorization_code(
        code,
        scopes=SCOPE.split(),
        redirect_uri=REDIRECT_URI,
    )
    logger.debug(result)
    if "access_token" not in result:
        logger.error(f"Token request failed: {result.get('error_description', result)}")
        return f"Token request failed: {result.get('error_description', result)}", 400
    # Store in statestore
    state = StateStore()
    expires_in = int(result.get("expires_in", 3600))
    expires_at = int(time.time()) + expires_in
    token_data = {
        "access_token": result["access_token"],
        "expires_at": expires_at,
        "refresh_token": result.get("refresh_token"),
    }
    logger.debug(token_data)
    state.set(TOKEN_STATE_KEY, json.dumps(token_data))
    logger.info("Token stored in statestore.")
    return "Authentication successful! Token stored. You may close this window."

if __name__ == "__main__":
    app.run(port=5000)
