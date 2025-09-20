#!/usr/bin/env bash

# Thoroughly clear Dapr state + pubsub data from Redis.
# Adds pattern-based deletion so you can wipe Dapr artifacts without necessarily nuking the whole Redis instance.
# If you DO want a total wipe, pass --flush-all
#
# Supported env vars:
#   REDIS_HOST (default: localhost)
#   REDIS_PORT (default: 6379)
#   REDIS_PASSWORD (optional)
#   REDIS_DB (default: 0)   # Only affects pattern deletes; FLUSHALL ignores DB selection
#
# Exit codes:
#   0 success
#   1 failure

set -euo pipefail

REDIS_HOST=${REDIS_HOST:-localhost}
REDIS_PORT=${REDIS_PORT:-6379}
REDIS_DB=${REDIS_DB:-0}
REDIS_PASSWORD=${REDIS_PASSWORD:-}
FORCE_FLUSH_ALL=false

if [[ ${1:-} == "--flush-all" || ${1:-} == "-f" ]]; then
	FORCE_FLUSH_ALL=true
fi

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
warn() { printf '\033[33mWARN:\033[0m %s\n' "$*"; }
info() { printf '\033[36mINFO:\033[0m %s\n' "$*"; }
err()  { printf '\033[31mERR :\033[0m %s\n' "$*" >&2; }

redis_base=(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB")
if [[ -n $REDIS_PASSWORD ]]; then
	redis_base+=( -a "$REDIS_PASSWORD" )
fi

run_redis() { "${redis_base[@]}" "$@"; }

if ! command -v redis-cli >/dev/null 2>&1; then
	err "redis-cli not found in PATH"
	exit 1
fi

bold "Clearing Dapr state + pubsub data from Redis ($REDIS_HOST:$REDIS_PORT db $REDIS_DB)"

if $FORCE_FLUSH_ALL; then
	warn "Executing FLUSHALL (this removes ALL data across ALL Redis databases)."
	run_redis FLUSHALL
	info "FLUSHALL completed."
	exit 0
fi

# Key patterns associated with Dapr state stores / pubsub / workflows / actors.
# Adjust / extend if you introduce new component names.
PATTERNS=(
	# Explicit component names (state stores)
	'workflowstatestore*'
	'agentstatestore*'
	'memorystatestore*'
	# Dapr workflow / actor / generic prefixes sometimes used
	'dapr:workflow:*'
	'dapr:actors:*'
	'actors:*'
	'wf:*'
	# Pub/Sub (conservative generic patterns; Redis pubsub component may create these)
	'pubsub:*'
	'pubsub||*'
	# Generic appId||key style (may over-match; keep last so earlier deletes reduce scan)
	'*||*'
)

deleted_total=0
scanned_total=0

delete_keys() {
	local pattern=$1
	local batch_keys
	local count=0
	# Use --scan for cursor-based iteration (safer for large keyspaces)
	while IFS= read -r key; do
		batch_keys+="$key\n"
		((count++)) || true
		((scanned_total++)) || true
		# Delete in batches of 100 for efficiency
		if (( count == 100 )); then
			printf "%s" "$batch_keys" | xargs -r -d '\n' "${redis_base[@]}" DEL >/dev/null
			((deleted_total+=count)) || true
			batch_keys=""
			count=0
		fi
	done < <(run_redis --raw --scan --pattern "$pattern")
	# Flush remainder
	if [[ -n ${batch_keys:-} ]]; then
		printf "%s" "$batch_keys" | xargs -r -d '\n' "${redis_base[@]}" DEL >/dev/null
		((deleted_total+=count)) || true
	fi
	info "Pattern '$pattern' -> deleted so far: $deleted_total (scanned: $scanned_total)"
}

for pat in "${PATTERNS[@]}"; do
	delete_keys "$pat"
done

bold "Summary"
info "Total keys scanned (matches across patterns, may include duplicates): $scanned_total"
info "Total keys deleted: $deleted_total"

if (( deleted_total == 0 )); then
	warn "No matching Dapr-related keys were found. If you expected data, verify DB/host or use --flush-all."
fi

info "Done. Use '--flush-all' to wipe entire Redis if necessary."