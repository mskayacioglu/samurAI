"""Background scheduler for periodic news ingestion."""

from datetime import datetime, timezone
from threading import Event, Lock, Thread


class IngestSchedulerService:
    """Run ingest jobs periodically and expose scheduler state."""

    def __init__(self, ingestion_service, logger=None):
        self.ingestion_service = ingestion_service
        self.logger = logger
        self._thread = None
        self._stop_event = Event()
        self._wake_event = Event()
        self._state_lock = Lock()
        self._is_running = False
        self._last_tick_at = ""
        self._last_error = ""

    def start(self):
        """Start the scheduler thread unless it is already running."""
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._wake_event.clear()
        self._thread = Thread(target=self._run_loop, name="news-ingest-scheduler", daemon=True)
        self._thread.start()

    def stop(self):
        """Signal the scheduler thread to stop and wait briefly for it."""
        self._stop_event.set()
        self._wake_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def trigger_now(self):
        """Wake the scheduler so it runs an ingest cycle immediately."""
        self._wake_event.set()

    def state(self):
        """Return current scheduler state for the status endpoint."""
        with self._state_lock:
            return {
                "is_running": self._is_running,
                "last_tick_at": self._last_tick_at,
                "last_error": self._last_error,
                "interval_seconds": self.ingestion_service.interval_seconds(),
                "enabled": self.ingestion_service.is_enabled(),
            }

    def _set_running(self, running: bool):
        """Update the running flag under the scheduler state lock."""
        with self._state_lock:
            self._is_running = running

    def _set_tick(self, error: str = ""):
        """Record the latest scheduler tick and optional error message."""
        with self._state_lock:
            self._last_tick_at = datetime.now(timezone.utc).isoformat()
            self._last_error = error

    def _execute_ingest(self):
        """Run one ingest cycle and report whether the run hit its cap."""
        self._set_running(True)
        try:
            stats = self.ingestion_service.run_once(logger=self.logger)
            self._set_tick("")
            if self.logger is not None:
                self.logger.info(
                    "ingest_run_completed processed=%s saved=%s summaries=%s",
                    stats.get("processed_entries", 0),
                    stats.get("saved_items", 0),
                    stats.get("summaries_written", 0),
                )
            return bool(stats.get("run_capped"))
        except Exception as exc:
            self._set_tick(str(exc))
            if self.logger is not None:
                self.logger.exception("ingest_run_failed error=%s", str(exc)[:200])
            return False
        finally:
            self._set_running(False)

    def _run_loop(self):
        """Run ingest cycles until stopped, respecting interval and wake events."""
        run_now = self.ingestion_service.run_on_start()
        interval = self.ingestion_service.interval_seconds()
        while not self._stop_event.is_set():
            if not run_now:
                _ = self._wake_event.wait(timeout=interval)
                if self._stop_event.is_set():
                    break
                self._wake_event.clear()

            run_now = self._execute_ingest()
