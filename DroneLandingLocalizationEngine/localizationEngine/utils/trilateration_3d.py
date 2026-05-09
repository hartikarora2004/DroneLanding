import numpy as np
from scipy.optimize import least_squares

def trilateration_3d(anchor_locations, anchor_distances):
    anchor_coordinates = []
    distances = []
    for name in anchor_distances:
        anchor_coordinates.append(anchor_locations[name])
        distances.append(anchor_distances[name])

    anchor_coordinates = np.array(anchor_coordinates)
    distances = np.array(distances)

    def residuals(p):
        return np.linalg.norm(anchor_coordinates - p, axis=1) - distances

    p0 = anchor_coordinates.mean(axis = 0) + np.array([0, 0, 1.0]) 

    result = least_squares(residuals, p0)
    return result.x
