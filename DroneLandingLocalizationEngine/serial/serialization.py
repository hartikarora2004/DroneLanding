"""
UWB serial reader and parser.

Reads lines from the COM port defined in ``settings`` (e.g., COM6) and parses
pipe-separated fields such as:

    A1 | A2 | A3 | A4 | 1 | ... | 2 | ...

Measurements that are missing (represented by ``...`` or blanks) are returned
as ``None``. Parsed records are pushed to an optional queue supplied by the
caller.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from typing import Dict, Optional

try:
    import serial  # pyserial
except ImportError as exc:  # pragma: no cover - import-time guard
    raise ImportError("pyserial is required for UwbSerialReader") from exc

from DroneLandingLocalizationEngine.settings import settings

class UwbReading:
    values: Dict[str, Optional[float]]
    raw: str


class UwbSerialReader:

    def __init__(
        self,
        port: Optional[str] = None,
        baudrate: int = 115_200,
        timeout: float = 0.1,
        output_queue=None,
    ) -> None:
        self.port = port or settings.get("COMPORT")
        self.baudrate = int(settings.get("BAUD", baudrate))
        self.timeout = float(settings.get("READ_TIMEOUT", timeout))
        self._queue = output_queue
        self._stop = threading.Event()
        self._ser: Optional[serial.Serial] = None

    def start(self) -> None:
        self._stop.clear()
        try:
            self._ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
        except Exception as e:
            print("Error initilization serialization engine : ", e)
        print("Port opened")        
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if getattr(self, "_thread", None):
            self._thread.join(timeout=1)
        if self._ser and self._ser.is_open:
            self._ser.close()

    def _loop(self) -> None:
        assert self._ser, "Serial port not opened"
        while not self._stop.is_set():
            line_bytes = self._ser.readline()
            if not line_bytes:
                continue
            line = line_bytes.decode(errors="ignore").strip()
            print(line)
            if not line:
                continue
            print("Publishing line : ", line)
            if self._queue is not None:
                self._queue.put(line)

    