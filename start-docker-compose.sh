#!/bin/bash

if [ -f .env ]; then
	set -a
	. .env
	set +a
fi

# Create folders only if they do not exist
if [ ! -d ".work/voice" ]; then
	mkdir -p .work/voice
fi

if [ ! -d ".data/mq" ]; then
	mkdir -p .data/mq
fi

if [ ! -d ".data/db" ]; then
	mkdir -p .data/db
	# For Postgres, set ownership so the container can write:
	sudo chown -R 999:999 .data/db
fi

docker-compose up -d
