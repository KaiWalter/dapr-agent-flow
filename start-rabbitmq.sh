#!/usr/bin/env bash

# Start RabbitMQ container if not already running
if ! docker ps --format '{{.Names}}' | grep -q '^rabbitmq$'; then
  if docker ps -a --format '{{.Names}}' | grep -q '^rabbitmq$'; then
    echo "Starting existing RabbitMQ container..."
    docker start rabbitmq
  else
    echo "Running new RabbitMQ container..."
    docker run -d --name rabbitmq \
      -p 5672:5672 \
      -p 15672:15672 \
      rabbitmq:4-management
  fi
else
  echo "RabbitMQ container already running."
fi

# Robust RabbitMQ readiness check (management API or diagnostics)
wait_for_rabbitmq() {
  local timeout_secs=${RABBITMQ_READY_TIMEOUT:-120}
  local start_ts=$(date +%s)
  local mgmt_url="http://localhost:15672/api/health/checks/alarms" # lightweight endpoint

  echo "Waiting for RabbitMQ readiness (timeout ${timeout_secs}s)..."
  echo " - Checking management API (${mgmt_url}) or docker exec diagnostics"

  while true; do
    # 1) Try management API (guest:guest is default in vanilla image for localhost access)
    if command -v curl >/dev/null 2>&1; then
      if curl -s -u guest:guest -o /dev/null -w '%{http_code}' "$mgmt_url" 2>/dev/null | grep -q '^200$'; then
        echo "RabbitMQ ready (management API responding 200)."
        return 0
      fi
    fi

    # 2) Fallback to rabbitmq-diagnostics ping inside container
    if docker exec rabbitmq rabbitmq-diagnostics -q ping >/dev/null 2>&1; then
      echo "RabbitMQ ready (rabbitmq-diagnostics ping successful)."
      return 0
    fi

    # 3) As a last resort, look for startup complete log line (non-authoritative)
    if docker logs rabbitmq 2>&1 | grep -q "Server startup complete"; then
      echo "RabbitMQ seems ready (log indicates startup complete)."
      return 0
    fi

    # Timeout handling
    local now_ts=$(date +%s)
    if [ $((now_ts - start_ts)) -ge $timeout_secs ]; then
      echo "WARNING: RabbitMQ not confirmed ready within ${timeout_secs}s; proceeding anyway."
      return 1
    fi
    sleep 2
  done
}

wait_for_rabbitmq
