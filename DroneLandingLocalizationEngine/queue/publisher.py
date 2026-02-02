"""
Queue-backed publisher/consumer skeleton for UWB measurements.

Producers call `put(reading)` to enqueue parsed UWB readings.
An internal worker thread dequeues and forwards each reading to a supplied
`process` callable (e.g., the future LocalizationEngine.process).
"""

from __future__ import annotations

import queue
import threading
from typing import Optional


class MeasurementQueue:

    def __init__(self, localizationEngine, maxsize: int = 100) -> None:
        self._q: queue.Queue[str] = queue.Queue(maxsize=maxsize)
        self._worker: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._localizationEngine = localizationEngine

    def put(self, reading: str, block: bool = True, timeout: float | None = None) -> None:
        self._q.put(reading, block=block, timeout=timeout)

    def start_worker(self) -> None:
        """
        Start the consumer thread.

        `process_fn` should accept a `UwbReading` and perform localization
        (or any downstream work). It is called for every dequeued item.
        """
        if self._worker and self._worker.is_alive():
            return

        self._stop.clear()
        self._worker = threading.Thread(target=self._loop, daemon=True)
        self._worker.start()
        print("Started worker")

    def stop_worker(self) -> None:
        """Signal worker to stop and wait for it to exit."""
        self._stop.set()
        if self._worker:
            self._worker.join(timeout=1)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                item = self._q.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                print("Trying to process : ", item)
                self._localizationEngine.process(item)
            finally:
                self._q.task_done()


# Example wiring (optional reference):
# from DroneLandingLocalizationEngine.localization.engine import LocalizationEngine
# mq = MeasurementQueue(maxsize=50)
# engine = LocalizationEngine()
# mq.start_worker(engine.process)
# reader = UwbSerialReader(output_queue=mq._q)  # or call mq.put in reader loop
