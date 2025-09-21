#!/usr/bin/env bash

if [ -f .env ]; then
	set -a
	. .env
	set +a
fi

# Create folders only if they do not exist
if [ ! -d ".work/voice" ]; then
	mkdir -p .work/voice
fi

if [ ! -d ".data/db" ]; then
	mkdir -p .data/db
	chmod 0777 .data/db
fi

if [ ! -d ".dapr/state" ]; then
	mkdir -p .dapr/state
fi

docker-compose up -d
