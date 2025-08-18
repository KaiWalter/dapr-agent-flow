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

# remove file markers from REDIS
redis-cli KEYS *voice_inbox_downloaded* | xargs -r redis-cli DEL
redis-cli KEYS *voice_inbox_pending* | xargs -r redis-cli DEL

source .venv/bin/activate
source <(cat .env)

# Ensure web-monitor Node deps are installed
if [ -f services/ui/web_monitor/package-lock.json ]; then
	npm --prefix services/ui/web_monitor ci || npm --prefix services/ui/web_monitor install
else
	npm --prefix services/ui/web_monitor install
fi

dapr run -f master.yaml &
pid=$!

trap "pgrep -P $pid | xargs kill && kill $pid" INT HUP

wait $pid
