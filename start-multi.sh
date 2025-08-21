#!/bin/bash

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

# # remove file markers from REDIS
# redis-cli KEYS *voice_inbox_downloaded* | xargs -r redis-cli DEL
# redis-cli KEYS *voice_inbox_pending* | xargs -r redis-cli DEL

# activate virtualenv only if not already in .venv
if [ -z "${VIRTUAL_ENV:-}" ] || [ "$(basename "$VIRTUAL_ENV")" != ".venv" ]; then
	if [ -f .venv/bin/activate ]; then
		source .venv/bin/activate
	else
		echo "Warning: .venv not found at .venv/bin/activate; continuing without activating a venv" >&2
	fi
fi

if [ -f .env ]; then
	set -a
	. .env
	set +a
fi

dapr run -f master.yaml &
pid=$!

trap "pgrep -P $pid | xargs kill && kill $pid" INT HUP

wait $pid
