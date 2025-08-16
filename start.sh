#!/bin/bash

# folders to clean
folders=(.dapr/logs .dapr_state downloads/voice downloads)
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

source .venv/bin/activate
source <(cat .env)

dapr run -f master.yaml &
pid=$!

trap "pgrep -P $pid | xargs kill && kill $pid" INT HUP

wait $pid