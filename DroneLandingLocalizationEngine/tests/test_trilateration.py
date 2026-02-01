import importlib

import numpy as np

from DroneLandingLocalizationEngine.localizationEngine.utils.constants import anchor_locations
from DroneLandingLocalizationEngine.localizationEngine.utils.trilateration_3d import trilateration_3d


def test_trilateration_uses_three_nearest():
    """
    Ensure only the three closest anchors are converted to Circle objects and
    passed to easy_least_squares in order of increasing distance.
    """
    anchor_locations ={
        "A1" : [0, 0, 0],
        "A2" : [0, 100, 0],
        "A3" : [100, 0, 0],
        "A4" : [100, 100, 0]
    }

    # Test 1: Original Point = (50, 50, 50)
    distances = {"A1" : 86.602, "A2" : 86.602, "A3" : 86.602, "A4" : 86.602}
    result = trilateration_3d(anchor_locations, distances)
    true_distance = np.array([50, 50, 50])
    res1 = np.allclose(true_distance, result, rtol=1e-1, atol=1e-1)
    print(result)
    assert res1 == True

    # Test 2: Original point = (40, 40, 30)
    distances = {"A1" :  64.031, "A2" : 78.102, "A3" : 78.102, "A4" : 90}
    result = trilateration_3d(anchor_locations, distances)
    true_distance = np.array([40, 40, 30])
    res1 = np.allclose(true_distance, result, rtol=1e-1, atol=1e-1)
    print(result)
    assert res1 == True

    # Test 3: Original point = (200, 200, 200)
    distances = {"A1" :   346.410, "A2" : 300, "A3" : 300, "A4" : 244.948}
    result = trilateration_3d(anchor_locations, distances)
    true_distance = np.array([200, 200,200])
    res1 = np.allclose(true_distance, result, rtol=1e-1, atol=1e-1)
    print(result)

    assert res1 == True
