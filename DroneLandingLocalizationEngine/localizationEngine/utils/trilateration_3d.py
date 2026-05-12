import numpy as np
from scipy.optimize import least_squares

def trilateration_3d(anchor_locations, anchor_distances, anchor_weights=None):
    """
    Parameters
    ----------
    anchor_locations : dict  {name: [x, y, z]}
    anchor_distances : dict  {name: distance_cm}
    anchor_weights   : dict  {name: weight} or None (uniform weights)
    """
    anchor_coordinates = []
    distances = []
    weights = []

    for name in anchor_distances:
        anchor_coordinates.append(anchor_locations[name])
        distances.append(anchor_distances[name])
        weights.append(anchor_weights[name] if anchor_weights else 1.0)

    anchor_coordinates = np.array(anchor_coordinates)
    distances = np.array(distances)
    weights = np.array(weights)

    def residuals(p):
        return weights * (np.linalg.norm(anchor_coordinates - p, axis=1) - distances)

    p0 = anchor_coordinates.mean(axis=0) + np.array([0, 0, 1.0])

    result = least_squares(residuals, p0)
    return result.x
