from __future__ import annotations

import os
from typing import Optional
from dapr.clients import DaprClient


STATE_STORE_NAME = os.getenv("STATE_STORE_NAME", "statestore")


class StateStore:
    def __init__(self):
        self.client = DaprClient()

    def get(self, key: str) -> Optional[str]:
        res = self.client.get_state(store_name=STATE_STORE_NAME, key=key)
        if res and res.data:
            return res.data.decode("utf-8")
        return None

    def set(self, key: str, value: str) -> None:
        self.client.save_state(store_name=STATE_STORE_NAME, key=key, value=value)

    def delete(self, key: str) -> None:
        self.client.delete_state(store_name=STATE_STORE_NAME, key=key)
