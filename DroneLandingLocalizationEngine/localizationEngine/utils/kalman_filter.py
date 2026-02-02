import numpy as np
from filterpy.kalman import KalmanFilter

class PositionKalman3D:
    """
    3D Constant-Velocity Kalman Filter
    Input: noisy [x, y, z]
    Output: filtered [x, y, z]
    """

    def __init__(self, dt: float,
                 init_pos,
                 init_vel=(0, 0, 0),
                 meas_var: float = 0.25,
                 process_var: float = 1.0):

        self._dt = float(dt)
        self._kf = KalmanFilter(dim_x=6, dim_z=3)

        dt = self._dt

        # State transition (constant velocity)
        self._kf.F = np.array([
            [1, 0, 0, dt, 0, 0],
            [0, 1, 0, 0, dt, 0],
            [0, 0, 1, 0, 0, dt],
            [0, 0, 0, 1,  0, 0],
            [0, 0, 0, 0,  1, 0],
            [0, 0, 0, 0,  0, 1]
        ], dtype=float)

        # Measurement model (position only)
        self._kf.H = np.array([
            [1, 0, 0, 0, 0, 0],
            [0, 1, 0, 0, 0, 0],
            [0, 0, 1, 0, 0, 0],
        ], dtype=float)

        # Measurement noise
        self._kf.R = np.eye(3) * meas_var

        # Process noise (from random acceleration model)
        q = process_var
        dt2, dt3, dt4 = dt*dt, dt*dt*dt, dt*dt*dt*dt

        q_pos = dt4/4 * q
        q_cross = dt3/2 * q
        q_vel = dt2 * q

        self._kf.Q = np.array([
            [q_pos,   0,     0,     q_cross, 0,       0],
            [0,     q_pos,   0,     0,     q_cross,   0],
            [0,       0,   q_pos,   0,       0,     q_cross],
            [q_cross, 0,     0,     q_vel,   0,       0],
            [0,     q_cross, 0,     0,     q_vel,     0],
            [0,       0,   q_cross, 0,       0,     q_vel],
        ], dtype=float)

        # Initial state
        self._kf.x = np.zeros((6, 1))
        self._kf.x[0:3, 0] = np.asarray(init_pos).reshape(3)
        self._kf.x[3:6, 0] = np.asarray(init_vel).reshape(3)

        # Initial uncertainty
        self._kf.P = np.eye(6) * 1000.0

    def update(self, noisy_pos):
        z = np.asarray(noisy_pos).reshape(3, 1)
        self._kf.predict()
        self._kf.update(z)
        return self._kf.x[0:3, 0].copy()
