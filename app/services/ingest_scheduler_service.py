from datetime import datetime, timezone
from threading import Event, Lock, Thread


class IngestSchedulerService:
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
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._wake_event.clear()
        self._thread = Thread(target=self._run_loop, name="news-ingest-scheduler", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self._wake_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def trigger_now(self):
        self._wake_event.set()

    def state(self):
        with self._state_lock:
            return {
                "is_running": self._is_running,
                "last_tick_at": self._last_tick_at,
                "last_error": self._last_error,
                "interval_seconds": self.ingestion_service.interval_seconds(),
                "enabled": self.ingestion_service.is_enabled(),
            }

    def _set_running(self, running: bool):
        with self._state_lock:
            self._is_running = running

    def _set_tick(self, error: str = ""):
        with self._state_lock:
            self._last_tick_at = datetime.now(timezone.utc).isoformat()
            self._last_error = error

    def _execute_ingest(self):
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
        run_now = self.ingestion_service.run_on_start()
        interval = self.ingestion_service.interval_seconds()
        while not self._stop_event.is_set():
            if not run_now:
                _ = self._wake_event.wait(timeout=interval)
                if self._stop_event.is_set():
                    break
                self._wake_event.clear()

            run_now = self._execute_ingest()
