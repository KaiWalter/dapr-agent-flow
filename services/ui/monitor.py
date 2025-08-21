import os
import json
import logging

from cloudevents.sdk.event import v1
from dapr.ext.grpc import App
from dapr.clients.grpc._response import TopicEventResponse


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

# Debugpy remote debugging (repo convention)
if os.getenv("DEBUGPY_ENABLE", "0") == "1":
    import debugpy
    debugpy.listen(("0.0.0.0", 5678))
    print("debugpy: Waiting for debugger attach on port 5678...")
    debugpy.wait_for_client()


app = App()


@app.subscribe(pubsub_name="pubsub", topic="beacon_channel")
def on_beacon_channel(event: v1.Event) -> TopicEventResponse:
    try:
        source = None
        try:
            source = event.Source()
        except Exception:
            source = "unknown"

        raw = event.Data()
        if isinstance(raw, (bytes, bytearray)):
            try:
                raw = raw.decode("utf-8")
            except Exception:
                pass
        content = raw
        if isinstance(raw, str):
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    content = data.get("content", data)
                else:
                    content = data
            except Exception:
                content = raw
        elif isinstance(raw, dict):
            content = raw.get("content", raw)

        logger.info(f"{source} : {content}")
        return TopicEventResponse("success")
    except Exception as e:
        logger.exception("Failed to process beacon event: %s", e)
        return TopicEventResponse("retry")


# Health check for Dapr appcallback
app.register_health_check(lambda: logger.info("Healthy") or None)


if __name__ == "__main__":
    port = int(os.getenv("DAPR_APP_PORT", 5199))
    app.run(port)
