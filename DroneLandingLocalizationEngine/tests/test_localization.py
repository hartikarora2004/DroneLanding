import math
import numpy as np
import pytest

from DroneLandingLocalizationEngine.localizationEngine.v1.localizationEngine import LocalizationEngine

# Anchor layout (cm):
#   Node1: [120,   0, 0]
#   Node2: [  0, 120, 0]
#   Node3: [120, 120, 0]
#   Node4: [  0,   0, 0]


def test_classInit():
    localization = LocalizationEngine()
    expected = {n: math.inf for n in ["Node1", "Node2", "Node3", "Node4"]}
    assert expected == localization._measurements


def test_single_measurement():
    """
    True position (60, 60, 0) is equidistant from all four anchors.
    d = sqrt((60-120)^2 + 60^2) = sqrt(7200) ≈ 84.853 cm
    """
    localization = LocalizationEngine()
    measurement = "Node1 | Node2 | Node3 | Node4 : 84.853 | 84.853 | 84.853 | 84.853 (cm)"
    result = localization.process(measurement)
    assert result is not None
    assert np.allclose([60, 60, 0], result, atol=5.0)


def test_asymmetric_measurement():
    """
    True position (30, 90, 0):
      Node1: sqrt((30-120)^2 + 90^2)        = sqrt(16200) ≈ 127.279 cm
      Node2: sqrt(30^2 + (90-120)^2)        = sqrt(1800)  ≈  42.426 cm
      Node3: sqrt((30-120)^2 + (90-120)^2)  = sqrt(9000)  ≈  94.868 cm
      Node4: sqrt(30^2 + 90^2)              = sqrt(9000)  ≈  94.868 cm
    """
    localization = LocalizationEngine()
    measurement = "Node1 | Node2 | Node3 | Node4 : 127.279 | 42.426 | 94.868 | 94.868 (cm)"
    result = localization.process(measurement)
    assert result is not None
    assert np.allclose([30, 90, 0], result, atol=10.0)


def test_missing_anchor_returns_none():
    """Any measurement with a missing anchor (----) should return None."""
    localization = LocalizationEngine()
    measurement = "Node1 | Node2 | Node3 | Node4 : ---- | 84.853 | 84.853 | 84.853 (cm)"
    result = localization.process(measurement)
    assert result is None


def test_multiple_measurements_ema_smoothing():
    """
    Feeding the same valid measurement twice should converge to the same result
    (EMA with alpha=0.5 on identical readings is stable).
    """
    localization = LocalizationEngine()
    measurement = "Node1 | Node2 | Node3 | Node4 : 84.853 | 84.853 | 84.853 | 84.853 (cm)"
    r1 = localization.process(measurement)
    r2 = localization.process(measurement)
    assert r1 is not None and r2 is not None
    assert np.allclose(r1, r2, atol=1.0)
