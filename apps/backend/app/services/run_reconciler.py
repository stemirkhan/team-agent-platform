"""Background reconciliation for active host-backed runs."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.services.run_service_factory import build_run_service

logger = logging.getLogger(__name__)


class RunReconciler:
    """Poll active runs and advance lifecycle state outside request read paths."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.session_factory = session_factory
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the background reconciliation loop once."""
        if not self.settings.run_reconciler_enabled or self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="run-reconciler",
        )
        self._thread.start()

    def stop(self) -> None:
        """Request loop shutdown and wait briefly for the thread to exit."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=max(self.settings.run_reconciler_interval_seconds, 1.0) + 1.0)
            self._thread = None

    def reconcile_once(self) -> int:
        """Run one reconciliation pass over currently active runs."""
        processed = 0
        with self.session_factory() as db:
            service = build_run_service(db, self.settings)
            active_runs = service.list_reconcilable_runs(limit=self.settings.run_reconciler_batch_size)
            for run in active_runs:
                try:
                    service.reconcile_run_entity(run)
                    processed += 1
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to reconcile run %s.", run.id)
        return processed

    def _run_loop(self) -> None:
        """Poll active runs until shutdown is requested."""
        while not self._stop_event.is_set():
            try:
                self.reconcile_once()
            except Exception:  # noqa: BLE001
                logger.exception("Run reconciler loop failed.")
            self._stop_event.wait(self.settings.run_reconciler_interval_seconds)
