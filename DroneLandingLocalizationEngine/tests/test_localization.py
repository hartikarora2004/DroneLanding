import pytest
import math
import numpy as np

from DroneLandingLocalizationEngine.localizationEngine.v1.localizationEngine import LocalizationEngine

def test_classInit():
    localization = LocalizationEngine()
    init_values = {"A1" : math.inf, "A2" : math.inf, "A3" : math.inf, "A4" : math.inf}
    assert init_values == localization._measurements

def test_single_measurement():
    measurement = "A1 | A2 | A3 | A4 : 86.602 | 86.602 | 86.602 | 86.602 (cm)"
    localization = LocalizationEngine()
    result = localization.process(measurement)
    true_res = [50, 50, 50]
    # print("Computed values : ", result)
    assert np.allclose(true_res, result, rtol=1e-1, atol=1e-1)

    measurement = "A1 | A2 | A3 | A4 :  346.410 | 300 | 300 | 244.948 (cm)"
    localization = LocalizationEngine()
    result = localization.process(measurement)
    true_res = [200, 200, 200]
    # print("Computed values : ", result)
    assert np.allclose(true_res, result, rtol=1e-1, atol=1e-1)

    measurement = "A1 | A2 | A3 | A4 :  ---- | 300 | 300 | 244.948 (cm)"
    localization = LocalizationEngine()
    result = localization.process(measurement)

    # print("Computed values : ", result)
    assert result == None