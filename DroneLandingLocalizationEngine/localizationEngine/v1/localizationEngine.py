"""
This is the localization Engine.
"""
import math
from DroneLandingLocalizationEngine.localizationEngine.utils.constants import anchor_locations
from DroneLandingLocalizationEngine.localizationEngine.utils.trilateration_3d import trilateration_3d
from DroneLandingLocalizationEngine.localizationEngine.utils.kalman_filter import PositionKalman3D
from DroneLandingLocalizationEngine.localizationEngine.utils.parser import parse_anchor_locations  # consider renaming

class LocalizationEngine:
    def __init__(self):
        self._anchor_locations = anchor_locations
        self._measurements = {}
        self._alpha = 0.8
        self._dt = 1.0

        for anchor in self._anchor_locations:
            self._measurements[anchor] = math.inf

        self._kalman_filter = PositionKalman3D(dt=self._dt, init_pos=[0, 0, 0], init_vel=[0, 0, 0])

    def process(self, measurement):
        measurement_map = parse_anchor_locations(measurement)
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
            return None

        trilateration_result = trilateration_3d(self._anchor_locations, valid_distances)

        corrected_result = self._kalman_filter.update(trilateration_result)
        return corrected_result
