"""
This is the entry point of the code.
"""

from DroneLandingLocalizationEngine.settings import settings
from DroneLandingLocalizationEngine.queue.publisher import MeasurementQueue
from DroneLandingLocalizationEngine.serial.serialization import UwbSerialReader
from DroneLandingLocalizationEngine.localizationEngine.v1.localizationEngine import LocalizationEngine
import time
import signal
import sys

if __name__ == "__main__":
    # print(settings.printAttributes(['NAME', 'BAUD', 'READ_TIMEOUT']))
    settings.printAttributes()
    localizationEngine = LocalizationEngine()
    measurementQueue = MeasurementQueue(localizationEngine)
    measurementQueue.start_worker()
    serializer = UwbSerialReader(output_queue=measurementQueue._q)
    serializer.start()

    # keep the process alive until Ctrl+C, then shut down cleanly
    def shutdown(signum=None, frame=None):
        print("Shutting down...")
        serializer.stop()
        measurementQueue.stop_worker()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown()
