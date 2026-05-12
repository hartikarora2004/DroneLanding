"""
This is the localization Engine.
"""
import math
import time

from DroneLandingLocalizationEngine.localizationEngine.utils.constants import anchor_locations
from DroneLandingLocalizationEngine.localizationEngine.utils.trilateration_3d import trilateration_3d
from DroneLandingLocalizationEngine.localizationEngine.utils.kalman_filter import PositionKalman3D
from DroneLandingLocalizationEngine.localizationEngine.utils.parser import parse_anchor_locations  # consider renaming
from DroneLandingLocalizationEngine.model.model import AnchorWeightModel
from DroneLandingLocalizationEngine.settings.settings import Settings

class LocalizationEngine:
    def __init__(self):
        self._anchor_locations = anchor_locations
        self._measurements = {}
        self._alpha = 0.5
        self._dt = 1.0

        for anchor in self._anchor_locations:
            self._measurements[anchor] = math.inf

        self._kalman_filter = PositionKalman3D(dt=self._dt, init_pos=[0, 0, 0], init_vel=[0, 0, 0])

        # Loaded once here — no per-call overhead
        model_path = Settings().get("MODEL_PATH")
        self._weight_model = AnchorWeightModel(model_path)

        self._output_file = "corrected_positions.txt"

        with open(self._output_file, "w") as f:
            f.write("timestamp,x,y,z\n")

    def _store_result(self, corrected_result):
        if corrected_result is None:
            return

        timestamp = time.time()

        # NEW: append corrected result to file
        with open(self._output_file, "a") as f:
            f.write(f"{timestamp} : {corrected_result}\n")


    def process(self, measurement):
        measurement_map = parse_anchor_locations(measurement)
        if measurement_map == None:
            return None
        for anchor, new_val in measurement_map.items():
            if new_val is None:
                continue

            old_val = self._measurements.get(anchor, math.inf)
            if old_val == math.inf:
                self._measurements[anchor] = float(new_val)
            else:
                self._measurements[anchor] = self._alpha * float(new_val) + (1 - self._alpha) * old_val

        valid_distances = {
            a: d for a, d in self._measurements.items()
            if d != math.inf and math.isfinite(d)
        }

        if len(valid_distances) < 4:
            print("Invalid result")
            return None

        weights = self._weight_model.predict(valid_distances)
        trilateration_result = trilateration_3d(self._anchor_locations, valid_distances, anchor_weights=weights)

        corrected_result = self._kalman_filter.update(trilateration_result)
        print("Corrected_result : ", corrected_result )

        self._store_result(f'{measurement} : {corrected_result}')

        return corrected_result
