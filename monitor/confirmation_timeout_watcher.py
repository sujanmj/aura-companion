from __future__ import annotations

import time
from typing import Any

from memory.sqlite_store import AuraMemoryStore
from runtime.heartbeat import RuntimeHeartbeat
from safety.confirmation_engine import ConfirmationEngine


class ConfirmationTimeoutWatcher:
    def __init__(self, store: AuraMemoryStore, interval_seconds: int = 5) -> None:
        self.store = store
        self.interval_seconds = interval_seconds
        self.confirmation_engine = ConfirmationEngine(store)

    def _beat(
        self,
        user_id: int,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        RuntimeHeartbeat(self.store, user_id).beat(
            "confirmation_timeout_watcher",
            metadata=metadata,
        )

    def process_once(self, user_id: int, limit: int = 20) -> list[dict[str, Any]]:
        self._beat(user_id, metadata={"mode": "once"})
        results = self.confirmation_engine.expire_due_confirmations(user_id, limit=limit)
        for result in results:
            print(
                f"- confirmation_id={result['confirmation_id']} "
                f"status={result['status']}"
            )
        return results

    def run_forever(
        self,
        user_id: int,
        interval_seconds: int = 5,
        limit: int = 20,
    ) -> None:
        print("AURA_CONFIRMATION_TIMEOUT_WATCHER_START")
        try:
            while True:
                self._beat(
                    user_id,
                    metadata={
                        "mode": "forever",
                        "interval_seconds": interval_seconds,
                    },
                )
                self.process_once(user_id, limit=limit)
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("\nAURA_CONFIRMATION_TIMEOUT_WATCHER_STOPPED")
