"""
This is the entry point of the code.
"""

from DroneLandingLocalizationEngine.settings import settings
from DroneLandingLocalizationEngine.queue.publisher import MeasurementQueue
from DroneLandingLocalizationEngine.serial.serialization import UwbSerialReader
from DroneLandingLocalizationEngine.localizationEngine.v1.localizationEngine import LocalizationEngine

if __name__ == "__main__":
    # print(settings.printAttributes(['NAME', 'BAUD', 'READ_TIMEOUT']))
    settings.printAttributes()
    localizationEngine = LocalizationEngine()
    serializer = UwbSerialReader()
    serializer.start()

    measurementQueue = MeasurementQueue(localizationEngine)
    measurementQueue.start_worker()
