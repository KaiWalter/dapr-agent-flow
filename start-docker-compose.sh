#!/bin/bash

if [ -f .env ]; then
	set -a
	. .env
	set +a
fi

docker-compose up -d
