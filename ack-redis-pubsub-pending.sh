#!/usr/bin/env bash
# Usage: ./ack-redis-pubsub-pending.sh <stream> <group> <consumer>
# Examples:
# ./ack-redis-pubsub-pending.sh voice2action-schedule workflows workflows
# ./ack-redis-pubsub-pending.sh IntentOrchestrator orchestrator-intent orchestrator-intent


STREAM=${1:-voice2action-schedule}
GROUP=${2:-workflows}
CONSUMER=${3:-workflows}

# List all pending message IDs for the group and consumer
echo "Listing pending messages for stream '$STREAM', group '$GROUP', consumer '$CONSUMER'..."
PENDING_IDS=$(redis-cli XPENDING "$STREAM" "$GROUP" - + 1000 | awk -v consumer="$CONSUMER" 'NR%4==2 && $0==consumer{print prev} {prev=$0}')

if [ -z "$PENDING_IDS" ]; then
  echo "No pending messages for consumer '$CONSUMER'."
  exit 0
fi

echo "Acknowledging the following message IDs:"
echo "$PENDING_IDS"

for id in $PENDING_IDS; do
  redis-cli XACK "$STREAM" "$GROUP" "$id"
  # Delete the message from the stream after acknowledging
  redis-cli XDEL "$STREAM" "$id"
done

echo "Done."
echo "All pending messages acknowledged and deleted from stream '$STREAM'."
