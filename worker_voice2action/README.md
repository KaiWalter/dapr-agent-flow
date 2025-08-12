# worker_voice2action

This Dapr app subscribes to the `voice2action-schedule` pubsub topic and schedules the workflow when triggered by the main scheduler app.

## How it works
- The main scheduler publishes a message to the `voice2action-schedule` topic at each polling interval.
- This app receives the event and schedules the `voice2action_poll_orchestrator` workflow.

## Running locally

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run with Dapr:
   ```bash
   dapr run --app-id worker-voice2action --app-port 5001 --resources-path ./components -- python src/worker_voice2action.py
   ```

## Pubsub subscription

This app exposes a POST endpoint `/schedule-voice2action` for Dapr pubsub. Configure the pubsub component as needed in `components/pubsub.yaml`.
