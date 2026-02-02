import numpy as np
import pytest

from DroneLandingLocalizationEngine.localizationEngine.utils.kalman_filter import PositionKalman3D


def simulate_constant_velocity_3d(
    n: int,
    dt: float,
    p0=(0.0, 0.0, 0.0),
    v=(1.0, -0.5, 0.2),
):
    """
    Returns:
        true_pos: (n, 3)
    """
    p0 = np.asarray(p0, dtype=float)
    v = np.asarray(v, dtype=float)

    t = np.arange(n, dtype=float) * dt
    true_pos = p0[None, :] + t[:, None] * v[None, :]
    return true_pos


def add_gaussian_noise(x: np.ndarray, std: float, seed: int = 0):
    rng = np.random.default_rng(seed)
    return x + rng.normal(0.0, std, size=x.shape)


def rmse(a: np.ndarray, b: np.ndarray) -> float:
    diff = a - b
    return float(np.sqrt(np.mean(np.sum(diff * diff, axis=1))))


def test_output_shape_and_finite():
    dt = 0.1
    kf = PositionKalman3D(dt=dt, init_pos=[0, 0, 0])

    out = kf.update([1.0, 2.0, 3.0])
    assert out.shape == (3,)
    assert np.all(np.isfinite(out))


def test_constant_position_smoothing_reduces_jitter():
    """
    If the true position is constant and measurements are noisy,
    the KF output should be less jittery than the raw measurements.
    """
    dt = 0.1
    n = 200
    true_pos = np.tile(np.array([[5.0, -2.0, 1.5]]), (n, 1))
    meas = add_gaussian_noise(true_pos, std=0.5, seed=42)

    kf = PositionKalman3D(dt=dt, init_pos=meas[0])

    est = np.zeros_like(meas)
    for i in range(n):
        est[i] = kf.update(meas[i])

    # Compare per-axis standard deviation around the mean
    meas_std = np.std(meas, axis=0)
    est_std = np.std(est, axis=0)

    # Expect KF to reduce jitter on average.
    assert est_std.mean() < meas_std.mean()

    # Also: estimates should not drift far away from the mean true position
    assert np.linalg.norm(est.mean(axis=0) - true_pos[0]) < 0.5


def test_constant_velocity_tracking_improves_rmse_vs_raw():
    """
    For a constant-velocity trajectory, the KF should reduce RMSE compared
    to raw noisy position measurements (after a short warm-up).
    """
    dt = 0.1
    n = 300
    true_pos = simulate_constant_velocity_3d(n=n, dt=dt, p0=(0, 0, 0), v=(1.2, -0.4, 0.1))
    meas = add_gaussian_noise(true_pos, std=0.7, seed=7)

    # Choose meas_var close to std^2; process_var tuned moderately
    kf = PositionKalman3D(dt=dt, init_pos=meas[0], meas_var=0.7**2, process_var=2.0)

    est = np.zeros_like(meas)
    for i in range(n):
        est[i] = kf.update(meas[i])

    # Ignore initial transient
    burn = 20
    raw_err = rmse(meas[burn:], true_pos[burn:])
    kf_err = rmse(est[burn:], true_pos[burn:])

    assert kf_err < raw_err


def test_reasonable_velocity_estimate_emerges():
    """
    Even though we only measure position, the filter should infer velocity over time.
    We check that the estimated velocity is roughly aligned with true velocity.
    """
    dt = 0.05
    n = 400
    v_true = np.array([0.8, 0.2, -0.3], dtype=float)
    true_pos = simulate_constant_velocity_3d(n=n, dt=dt, p0=(2, -1, 0.5), v=v_true)
    meas = add_gaussian_noise(true_pos, std=0.3, seed=123)

    kf = PositionKalman3D(dt=dt, init_pos=meas[0], meas_var=0.3**2, process_var=1.0)

    for i in range(n):
        kf.update(meas[i])

    # Access internal state to inspect velocity estimate
    v_est = kf._kf.x[3:6, 0].copy()

    # Directional agreement: cosine similarity should be high
    cos_sim = float(np.dot(v_est, v_true) / (np.linalg.norm(v_est) * np.linalg.norm(v_true) + 1e-12))
    assert cos_sim > 0.85

    # Magnitude should be in the ballpark
    assert np.linalg.norm(v_est - v_true) < 0.5


def test_handles_weird_inputs_gracefully():
    """
    Basic sanity: accepts list/tuple/np arrays and returns finite values.
    """
    dt = 0.1
    kf = PositionKalman3D(dt=dt, init_pos=(0.0, 0.0, 0.0))

    inputs = [
        [1, 2, 3],
        (1.1, 2.1, 3.1),
        np.array([0.9, 2.2, 2.8], dtype=float),
    ]
    for z in inputs:
        out = kf.update(z)
        assert out.shape == (3,)
        assert np.all(np.isfinite(out))
