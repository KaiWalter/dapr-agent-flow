import os
import logging
from flask import Flask, request


# Logging setup (repo convention)
level = os.getenv("DAPR_LOG_LEVEL", "info").upper()
root = logging.getLogger()
if not root.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)
root.setLevel(getattr(logging, level, logging.INFO))
logger = logging.getLogger("monitor")
# Suppress werkzeug INFO logs
logging.getLogger("werkzeug").setLevel(logging.WARNING)

# Debugpy remote debugging (repo convention)
if os.getenv("DEBUGPY_ENABLE", "0") == "1":
    import debugpy
    debugpy.listen(("0.0.0.0", 5678))
    print("debugpy: Waiting for debugger attach on port 5678...")
    debugpy.wait_for_client()

app = Flask(__name__)


# Dapr pub/sub subscription endpoint for beacon_channel
@app.route("/beacon_channel", methods=["POST"])
def on_beacon_channel():
    event = request.get_json()
    # Extract source and content from CloudEvent
    source = event.get("source")
    content = None
    data = event.get("data")
    if isinstance(data, dict):
        content = data.get("content")
    logger.info(f"{source} : {content}")
    return "", 200

# Dapr subscription discovery endpoint
@app.route("/dapr/subscribe", methods=["GET"])
def subscribe():
    return [
        {
            "pubsubname": "pubsub",
            "topic": "beacon_channel",
            "route": "beacon_channel"
        }
    ]

if __name__ == "__main__":
    port = int(os.getenv("DAPR_APP_PORT", 5199))
    app.run(host="0.0.0.0", port=port)
