"""
UWB anchor weight predictor.

Loads the trained WeightNet and exposes a single predict() method that takes
a dict of {node_name: distance_cm} and returns a dict of {node_name: weight}.
The weights can be passed directly into a weighted trilateration solver.
"""

import numpy as np
import torch
import torch.nn as nn


_NODE_ORDER = ["Node1", "Node2", "Node3", "Node4"]


class _WeightNet(nn.Module):
    """MLP architecture — must match train_weighted_trilateration.py exactly."""
    def __init__(self, hidden):
        super().__init__()
        layers, in_d = [], 4
        for h in hidden:
            layers += [nn.Linear(in_d, h), nn.BatchNorm1d(h), nn.ReLU(), nn.Dropout(0.1)]
            in_d = h
        layers.append(nn.Linear(in_d, 4))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.softmax(self.net(x), dim=-1)


class AnchorWeightModel:
    """
    Loads a saved WeightNet checkpoint and predicts per-anchor weights.

    Usage
    -----
    model = AnchorWeightModel("path/to/weight_net.pt")
    weights = model.predict({"Node1": 68.0, "Node2": 77.0, "Node3": 76.0, "Node4": 107.0})
    # weights -> {"Node1": 0.12, "Node2": 0.31, "Node3": 0.48, "Node4": 0.09}
    """

    def __init__(self, model_path: str):
        ckpt = torch.load(model_path, map_location="cpu", weights_only=False)

        self._net = _WeightNet(hidden=ckpt["hidden"])
        self._net.load_state_dict(ckpt["model_state"])
        self._net.eval()

        self._r_mean = ckpt["r_mean"].astype(np.float32)
        self._r_std  = ckpt["r_std"].astype(np.float32)

    def predict(self, distances: dict) -> dict:
        """
        Parameters
        ----------
        distances : dict
            {node_name: distance_in_cm} for all four anchors.
            Must contain all of Node1, Node2, Node3, Node4.

        Returns
        -------
        dict
            {node_name: weight} — four positive weights that sum to 1.

        Raises
        ------
        ValueError
            If any of the four required nodes is missing from distances.
        """
        missing = [n for n in _NODE_ORDER if n not in distances]
        if missing:
            raise ValueError(f"Missing distances for anchors: {missing}")

        r = np.array([distances[n] for n in _NODE_ORDER], dtype=np.float32)
        r_norm = (r - self._r_mean) / self._r_std

        with torch.no_grad():
            w = self._net(torch.tensor(r_norm).unsqueeze(0)).squeeze().numpy()

        return {node: float(w[i]) for i, node in enumerate(_NODE_ORDER)}
