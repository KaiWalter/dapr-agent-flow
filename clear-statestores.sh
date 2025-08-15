#!/bin/sh

docker exec -it dapr_redis redis-cli FLUSHALL
# sqlite3 .data/dapr_statestore.db "DELETE FROM state;"
# rm -rf .data/dapr_statestore.db
rm *_state.json
