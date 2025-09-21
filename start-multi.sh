#!/usr/bin/env bash

# clear state
echo "Cleaning up previous state..."
redis-cli FLUSHALL
[ -d .dapr/logs ] && rm -rf .dapr/logs
[ -d .dapr/state ] && rm -rf .dapr/state

# folders to clean
folders=(.work/voice .work .data/local_voice_inbox .data/local_voice_archive)
for folder in "${folders[@]}"; do
  files=("$folder"/*)
  found_file=false
  for f in "${files[@]}"; do
    if [ -f "$f" ]; then
      found_file=true
      break
    fi
  done
  if $found_file; then
    find "$folder" -maxdepth 1 -type f -exec rm {} +
  fi
done

# Proactively kill any lingering daprd/app processes from a previous crash to avoid
# duplicate RabbitMQ consumer tag errors (NOT_ALLOWED - attempt to reuse consumer tag ...)
echo "Ensuring no lingering Dapr/app processes are running..."
apps_to_kill=(agent-facilitator orchestrator-intent agent-office-automation monitor web-monitor workflows worker-voice2action authenticator)
for pattern in "${apps_to_kill[@]}"; do
  # Kill python module processes
  pkill -f "python -m .*${pattern}" 2>/dev/null || true
  # Kill sidecars with matching app id in args
  pkill -f "daprd.*--app-id ${pattern}" 2>/dev/null || true
done

# Also kill any orphan overall daprd processes older than 1 hour (safety net)
if command -v ps >/dev/null 2>&1; then
  now_epoch=$(date +%s)
  while read -r pid etime cmd; do
    # Skip header
    if [ "$pid" = "PID" ]; then continue; fi
    # If elapsed time is in the form [[dd-]hh:]mm:ss, convert hours when >= 01:00:00
    # Simple heuristic: if contains '-' or starts with ..:..:.. and hour >=1, kill
    if echo "$etime" | grep -Eq '^[0-9]+-' || echo "$etime" | grep -Eq '^[0-9]{2}:[0-9]{2}:[0-9]{2}'; then
      # Could be long-running; if it's a daprd keep only if we just cleaned; kill anyway to ensure clean slate
      if echo "$cmd" | grep -q 'daprd'; then
        kill "$pid" 2>/dev/null || true
      fi
    fi
  done < <(ps -eo pid,etime,command | grep daprd | grep -v grep)
fi

echo "Process cleanup complete."

# activate virtualenv only if not already in .venv
if [ -z "${VIRTUAL_ENV:-}" ] || [ "$(basename "$VIRTUAL_ENV")" != ".venv" ]; then
  if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
  else
    echo "Warning: .venv not found at .venv/bin/activate; continuing without activating a venv" >&2
  fi
fi

# Start Jaeger container if not already running
if ! docker ps --format '{{.Names}}' | grep -q '^jaeger$'; then
  if docker ps -a --format '{{.Names}}' | grep -q '^jaeger$'; then
    echo "Starting existing Jaeger container..."
    docker start jaeger
  else
    echo "Running new Jaeger container..."
    docker run -d --name jaeger \
      -p 4317:4317 \
      -p 16686:16686 \
      jaegertracing/all-in-one:latest
  fi
else
  echo "Jaeger container already running."
fi

# Load environment variables from .env file if it exists
if [ -f .env ]; then
  set -a
  . .env
  set +a
fi

# Start all Dapr applications
dapr run -f master.yaml &
pid=$!

# Ensure all child processes are killed on script exit
trap "pgrep -P $pid | xargs kill && kill $pid" INT HUP

# wait for basic boot and list errors
sleep 15
grep "level=error" .dapr/logs/*

wait $pid
