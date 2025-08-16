#!/bin/sh

docker exec -it dapr_redis redis-cli FLUSHALL
# sqlite3 .data/dapr_statestore.db "DELETE FROM state;"
# rm -rf .data/dapr_statestore.db
if ls *_state.json 1> /dev/null 2>&1; then
	rm *_state.json
fi
