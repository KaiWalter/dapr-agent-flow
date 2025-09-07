#!/usr/bin/env bash

# folders to clean
folders=(.dapr/logs .dapr_state .work/voice .work .data/local_voice_inbox .data/local_voice_archive)
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
		  -p 4317:4317  \
		  -p 16686:16686 \
		  jaegertracing/all-in-one:latest
	fi
else
	echo "Jaeger container already running."
fi

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

wait $pid
