#!/bin/sh

sqlite3 .data/agentstatestore.db "DELETE FROM state;"
sqlite3 .data/workflowstatestore.db "DELETE FROM state;"