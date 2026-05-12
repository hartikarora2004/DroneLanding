#!/usr/bin/env python3
"""
Train a neural network to predict anchor weights for weighted trilateration.

Dataset format
--------------
A folder contains many files named like:
    (x,y,z).txt   or   (x,y,z)

Example:
    (1.25,0.80,1.10).txt

Inside each file are lines like:
    Node1 | Node2 | Node3 | Node4 : ---- | ---- | 30.0 | 46.0  (cm)

Each valid line is treated as one sample.
Ground truth (x,y,z) comes from the filename.

This first version:
- converts all ranges to meters
- skips lines with any missing anchor ("----")
- trains a small NN to predict 4 positive weights
- uses differentiable weighted trilateration during training
- compares weighted vs unweighted trilateration RMSE

Usage
-----
python train.py \
    --data-dir ./testData \
    --anchors-json ./anchors.json \
    --gt-unit cm \
    --epochs 100 \
    --batch-size 32

anchors.json format
-------------------
{
  "Node1": [0.0, 0.0, 0.0],
  "Node2": [4.0, 0.0, 0.0],
  "Node3": [0.0, 4.0, 0.0],
  "Node4": [0.0, 0.0, 3.0]
}
"""

from __future__ import annotations

import argparse
import json
import random
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Sequence, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset


NODE_ORDER = ["Node1", "Node2", "Node3", "Node4"]

# .txt extension is optional to support both "(x,y,z).txt" and "(x,y,z)" filenames
FILE_GT_PATTERN = re.compile(
    r"^\(\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*\)(\.txt)?$"
)

LINE_PATTERN = re.compile(
    r"Node1\s*\|\s*Node2\s*\|\s*Node3\s*\|\s*Node4\s*:\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\((cm|m)\)",
    re.IGNORECASE,
)


@dataclass
class Sample:
    ranges_m: np.ndarray   # shape (4,)
    gt_m: np.ndarray       # shape (3,)
    file_name: str
    line_idx: int


class RangeDataset(Dataset):
    def __init__(self, ranges: np.ndarray, gt: np.ndarray):
        assert ranges.ndim == 2 and ranges.shape[1] == 4
        assert gt.ndim == 2 and gt.shape[1] == 3
        self.ranges = torch.tensor(ranges, dtype=torch.float32)
        self.gt = torch.tensor(gt, dtype=torch.float32)

    def __len__(self) -> int:
        return self.ranges.shape[0]

    def __getitem__(self, idx: int):
        return self.ranges[idx], self.gt[idx]


class WeightNet(nn.Module):
    """
    Predicts 4 bounded positive weights from 4 normalized ranges.
    """
    def __init__(self, in_dim: int = 4, hidden_dim: int = 64, out_dim: int = 4,
                 w_min: float = 0.2, w_max: float = 2.0):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, out_dim),
        )
        self.w_min = w_min
        self.w_max = w_max

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        raw = self.net(x)
        # keep weights positive and bounded
        weights = self.w_min + (self.w_max - self.w_min) * torch.sigmoid(raw)
        return weights


class Normalizer:
    def __init__(self, mean: np.ndarray, std: np.ndarray):
        self.mean = mean.astype(np.float32)
        self.std = np.where(std < 1e-8, 1.0, std).astype(np.float32)

    def transform(self, x: np.ndarray) -> np.ndarray:
        return (x - self.mean) / self.std

    def as_dict(self) -> dict:
        return {
            "mean": self.mean.tolist(),
            "std": self.std.tolist(),
        }


def set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def parse_gt_from_filename(path: Path, gt_unit: str) -> np.ndarray:
    match = FILE_GT_PATTERN.match(path.name)
    if not match:
        raise ValueError(f"Filename does not match '(x,y,z)[.txt]': {path.name}")

    gt = np.array([
        float(match.group(1)),
        float(match.group(2)),
        float(match.group(3)),
    ], dtype=np.float32)

    # Keep gt in its original unit (cm). Anchors must be in the same unit.
    if gt_unit.lower() not in ("cm", "m"):
        raise ValueError(f"Unsupported gt unit: {gt_unit}")

    return gt


def parse_range_token(token: str, unit: str) -> float | None:
    token = token.strip()
    if token == "----":
        return None

    value = float(token)
    # Keep value in its original unit (cm). Anchors must be in the same unit.
    if unit.lower() not in ("cm", "m"):
        raise ValueError(f"Unsupported range unit: {unit}")

    return value


def load_samples(data_dir: Path, gt_unit: str) -> Tuple[List[Sample], dict]:
    samples: List[Sample] = []
    stats = {
        "num_files": 0,
        "num_lines_total": 0,
        "num_valid_samples": 0,
        "num_skipped_missing": 0,
        "num_skipped_unparsed": 0,
    }

    # Match both "(x,y,z).txt" and "(x,y,z)" (no extension)
    all_files = [p for p in sorted(data_dir.iterdir()) if p.is_file()]
    files = [p for p in all_files if FILE_GT_PATTERN.match(p.name)]
    stats["num_files"] = len(files)

    for file_path in files:
        gt = parse_gt_from_filename(file_path, gt_unit=gt_unit)

        with file_path.open("r", encoding="utf-8") as f:
            for idx, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue

                stats["num_lines_total"] += 1
                match = LINE_PATTERN.search(line)
                if not match:
                    stats["num_skipped_unparsed"] += 1
                    continue

                unit = match.group(5)
                range_tokens = [match.group(i) for i in range(1, 5)]
                parsed_ranges = [parse_range_token(tok, unit=unit) for tok in range_tokens]

                if any(v is None for v in parsed_ranges):
                    stats["num_skipped_missing"] += 1
                    continue

                sample = Sample(
                    ranges_m=np.array(parsed_ranges, dtype=np.float32),
                    gt_m=gt.copy(),
                    file_name=file_path.name,
                    line_idx=idx,
                )
                samples.append(sample)
                stats["num_valid_samples"] += 1

    if not samples:
        raise RuntimeError("No usable samples found.")

    return samples, stats


def split_samples(samples: Sequence[Sample], seed: int):
    indices = list(range(len(samples)))
    rng = random.Random(seed)
    rng.shuffle(indices)

    n = len(indices)
    n_train = int(0.8 * n)
    n_val = int(0.1 * n)

    train = [samples[i] for i in indices[:n_train]]
    val = [samples[i] for i in indices[n_train:n_train + n_val]]
    test = [samples[i] for i in indices[n_train + n_val:]]

    return train, val, test


def stack_samples(samples: Sequence[Sample]) -> Tuple[np.ndarray, np.ndarray]:
    ranges = np.stack([s.ranges_m for s in samples], axis=0)
    gt = np.stack([s.gt_m for s in samples], axis=0)
    return ranges, gt


def compute_normalizer(x: np.ndarray) -> Normalizer:
    return Normalizer(mean=x.mean(axis=0), std=x.std(axis=0))


def load_anchors(anchors_json: Path) -> np.ndarray:
    with anchors_json.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    anchors = []
    for node in NODE_ORDER:
        if node not in raw:
            raise KeyError(f"Anchor config missing {node}")
        anchors.append(raw[node])

    anchors_np = np.array(anchors, dtype=np.float32)
    if anchors_np.shape != (4, 3):
        raise ValueError("anchors.json must define exactly four 3D anchor coordinates")

    return anchors_np


def solve_weighted_trilateration_torch(
    ranges_m: torch.Tensor,
    weights: torch.Tensor,
    anchors_m: torch.Tensor,
    num_iters: int = 8,
    damping: float = 1e-3,
) -> torch.Tensor:
    """
    Differentiable Gauss-Newton weighted trilateration.

    ranges_m : (B, 4)
    weights  : (B, 4)
    anchors_m: (4, 3)

    returns:
        p: (B, 3)
    """
    device = ranges_m.device
    batch_size = ranges_m.shape[0]

    # initial guess: anchor centroid
    p = anchors_m.mean(dim=0, keepdim=True).repeat(batch_size, 1).to(device)
    eye3 = torch.eye(3, device=device).unsqueeze(0).repeat(batch_size, 1, 1)

    for _ in range(num_iters):
        diff = p.unsqueeze(1) - anchors_m.unsqueeze(0)             # (B,4,3)
        pred = torch.linalg.norm(diff, dim=2).clamp_min(1e-6)      # (B,4)
        residual = pred - ranges_m                                 # (B,4)

        # Jacobian of range wrt position
        J = diff / pred.unsqueeze(-1)                              # (B,4,3)

        sqrt_w = torch.sqrt(weights.clamp_min(1e-6))
        Jw = J * sqrt_w.unsqueeze(-1)
        rw = residual * sqrt_w

        H = torch.bmm(Jw.transpose(1, 2), Jw) + damping * eye3    # (B,3,3)
        g = torch.bmm(Jw.transpose(1, 2), rw.unsqueeze(-1))       # (B,3,1)

        delta = torch.linalg.solve(H, -g).squeeze(-1)             # (B,3)
        p = p + delta

    return p


def rmse_3d(pred: np.ndarray, gt: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.sum((pred - gt) ** 2, axis=1))))


def mae_xyz(pred: np.ndarray, gt: np.ndarray) -> np.ndarray:
    return np.mean(np.abs(pred - gt), axis=0)


def normalize_batch(batch_ranges_m: torch.Tensor, range_norm: Normalizer, device: torch.device) -> torch.Tensor:
    batch_np = batch_ranges_m.detach().cpu().numpy()
    batch_norm = range_norm.transform(batch_np)
    return torch.tensor(batch_norm, dtype=torch.float32, device=device)


def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    range_norm: Normalizer,
    anchors_m: torch.Tensor,
    device: torch.device,
    solver_iters: int,
    reg_lambda: float,
) -> float:
    model.train()
    total_loss = 0.0
    total_count = 0

    for batch_ranges_m, batch_gt_m in loader:
        batch_ranges_m = batch_ranges_m.to(device)
        batch_gt_m = batch_gt_m.to(device)

        batch_ranges_norm = normalize_batch(batch_ranges_m, range_norm, device)
        weights = model(batch_ranges_norm)

        pred_pos = solve_weighted_trilateration_torch(
            ranges_m=batch_ranges_m,
            weights=weights,
            anchors_m=anchors_m,
            num_iters=solver_iters,
        )

        pos_loss = F.mse_loss(pred_pos, batch_gt_m)
        reg_loss = ((weights - 1.0) ** 2).mean()
        loss = pos_loss + reg_lambda * reg_loss

        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
        optimizer.step()

        batch_size = batch_ranges_m.shape[0]
        total_loss += float(loss.item()) * batch_size
        total_count += batch_size

    return total_loss / max(total_count, 1)


@torch.no_grad()
def eval_loss(
    model: nn.Module,
    loader: DataLoader,
    range_norm: Normalizer,
    anchors_m: torch.Tensor,
    device: torch.device,
    solver_iters: int,
    reg_lambda: float,
) -> float:
    model.eval()
    total_loss = 0.0
    total_count = 0

    for batch_ranges_m, batch_gt_m in loader:
        batch_ranges_m = batch_ranges_m.to(device)
        batch_gt_m = batch_gt_m.to(device)

        batch_ranges_norm = normalize_batch(batch_ranges_m, range_norm, device)
        weights = model(batch_ranges_norm)

        pred_pos = solve_weighted_trilateration_torch(
            ranges_m=batch_ranges_m,
            weights=weights,
            anchors_m=anchors_m,
            num_iters=solver_iters,
        )

        pos_loss = F.mse_loss(pred_pos, batch_gt_m)
        reg_loss = ((weights - 1.0) ** 2).mean()
        loss = pos_loss + reg_lambda * reg_loss

        batch_size_val = batch_ranges_m.shape[0]
        total_loss += float(loss.item()) * batch_size_val
        total_count += batch_size_val

    return total_loss / max(total_count, 1)


@torch.no_grad()
def predict_positions(
    model: nn.Module,
    loader: DataLoader,
    range_norm: Normalizer,
    anchors_m: torch.Tensor,
    device: torch.device,
    solver_iters: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Returns (pred_weighted, pred_unweighted, gt) — all numpy arrays of shape (N, 3).
    pred_unweighted uses uniform weights=1 as a baseline.
    """
    model.eval()
    preds_w, preds_u, gts = [], [], []

    for batch_ranges_m, batch_gt_m in loader:
        batch_ranges_m = batch_ranges_m.to(device)

        batch_ranges_norm = normalize_batch(batch_ranges_m, range_norm, device)
        weights = model(batch_ranges_norm)

        pred_w = solve_weighted_trilateration_torch(
            ranges_m=batch_ranges_m,
            weights=weights,
            anchors_m=anchors_m,
            num_iters=solver_iters,
        )

        uniform_w = torch.ones_like(weights)
        pred_u = solve_weighted_trilateration_torch(
            ranges_m=batch_ranges_m,
            weights=uniform_w,
            anchors_m=anchors_m,
            num_iters=solver_iters,
        )

        preds_w.append(pred_w.cpu().numpy())
        preds_u.append(pred_u.cpu().numpy())
        gts.append(batch_gt_m.numpy())

    return (
        np.concatenate(preds_w, axis=0),
        np.concatenate(preds_u, axis=0),
        np.concatenate(gts, axis=0),
    )


def write_accuracy_report(
    report_path: Path,
    train_history: List[Tuple[float, float]],
    val_history: List[Tuple[float, float]],
    test_weighted_rmse: float,
    test_unweighted_rmse: float,
    test_weighted_mae: np.ndarray,
    test_unweighted_mae: np.ndarray,
    args: argparse.Namespace,
):
    improvement_pct = (
        (test_unweighted_rmse - test_weighted_rmse) / test_unweighted_rmse * 100
        if test_unweighted_rmse > 0 else 0.0
    )

    with report_path.open("w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("  Weight Model Training — Accuracy Report\n")
        f.write(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 60 + "\n\n")

        f.write("[Training Configuration]\n")
        f.write(f"  data_dir    : {args.data_dir}\n")
        f.write(f"  anchors_json: {args.anchors_json}\n")
        f.write(f"  gt_unit     : {args.gt_unit}\n")
        f.write(f"  epochs      : {args.epochs}\n")
        f.write(f"  batch_size  : {args.batch_size}\n")
        f.write(f"  lr          : {args.lr}\n")
        f.write(f"  reg_lambda  : {args.reg_lambda}\n")
        f.write(f"  seed        : {args.seed}\n\n")

        f.write("[Training / Validation Loss History]\n")
        f.write(f"  {'Epoch':>6}  {'Train Loss':>12}  {'Val Loss':>12}\n")
        f.write(f"  {'-'*6}  {'-'*12}  {'-'*12}\n")
        for epoch, (tl, vl) in enumerate(zip(train_history, val_history), start=1):
            f.write(f"  {epoch:>6}  {tl:>12.6f}  {vl:>12.6f}\n")
        f.write("\n")

        f.write("[Test Set Results]\n")
        f.write(f"  Weighted trilateration RMSE   : {test_weighted_rmse:.2f} cm\n")
        f.write(f"  Unweighted trilateration RMSE : {test_unweighted_rmse:.2f} cm\n")
        f.write(f"  RMSE improvement              : {improvement_pct:+.1f}%\n\n")

        f.write("  MAE per axis — weighted  :"
                f"  X = {test_weighted_mae[0]:.2f} cm"
                f"  Y = {test_weighted_mae[1]:.2f} cm"
                f"  Z = {test_weighted_mae[2]:.2f} cm\n")
        f.write("  MAE per axis — unweighted:"
                f"  X = {test_unweighted_mae[0]:.2f} cm"
                f"  Y = {test_unweighted_mae[1]:.2f} cm"
                f"  Z = {test_unweighted_mae[2]:.2f} cm\n")

        # ── Overfitting Analysis ──────────────────────────────────────────────
        f.write("\n[Overfitting Analysis]\n")

        best_val_epoch = int(np.argmin(val_history)) + 1
        best_val       = float(np.min(val_history))
        final_train    = train_history[-1]
        final_val      = val_history[-1]

        # Generalisation gap = val - train  (positive means val > train, i.e. some overfit)
        gap_epoch1     = val_history[0]  - train_history[0]
        gap_best       = val_history[best_val_epoch - 1] - train_history[best_val_epoch - 1]
        gap_final      = final_val - final_train

        # How much did val loss creep up after its best point?
        val_degradation     = final_val - best_val
        val_degradation_pct = val_degradation / best_val * 100 if best_val > 0 else 0.0

        # Count epochs where val loss was strictly rising (consecutive increases)
        rising_streak = 0
        max_rising_streak = 0
        streak_start = 0
        for i in range(1, len(val_history)):
            if val_history[i] > val_history[i - 1]:
                if rising_streak == 0:
                    streak_start = i
                rising_streak += 1
                max_rising_streak = max(max_rising_streak, rising_streak)
            else:
                rising_streak = 0

        # Verdict
        if val_degradation_pct > 5 and gap_final > gap_epoch1 * 1.5:
            verdict = "OVERFIT — val loss rose significantly after best epoch and gap widened."
        elif val_degradation_pct > 2:
            verdict = "MILD OVERFIT — val loss crept up slightly after best epoch."
        elif gap_final < 0:
            verdict = "NO OVERFIT — train loss exceeds val loss (model may be underfitting)."
        else:
            verdict = "NO OVERFIT — val loss stable and generalisation gap did not widen."

        f.write(f"  Best val loss          : {best_val:.6f}  (epoch {best_val_epoch})\n")
        f.write(f"  Final train loss       : {final_train:.6f}\n")
        f.write(f"  Final val loss         : {final_val:.6f}\n")
        f.write(f"  Val loss after best    : {val_degradation:+.6f}  ({val_degradation_pct:+.2f}%)\n\n")
        f.write(f"  Generalisation gap (val - train):\n")
        f.write(f"    Epoch 1              : {gap_epoch1:+.6f}\n")
        f.write(f"    Best-val epoch ({best_val_epoch:>3}) : {gap_best:+.6f}\n")
        f.write(f"    Final epoch          : {gap_final:+.6f}\n\n")
        f.write(f"  Longest consecutive val-loss rising streak : {max_rising_streak} epoch(s)\n\n")
        f.write(f"  Verdict: {verdict}\n")

    print(f"Accuracy report saved -> {report_path}")


def main():
    parser = argparse.ArgumentParser(description="Train WeightNet for UWB anchor weighting")
    parser.add_argument("--data-dir",     type=Path, default=Path("testData"),
                        help="Folder with (x,y,z)[.txt] measurement files")
    parser.add_argument("--anchors-json", type=Path, default=Path("anchors.json"),
                        help="JSON file with anchor 3-D coordinates")
    parser.add_argument("--gt-unit",      default="cm", choices=["m", "cm"],
                        help="Unit of ground-truth coordinates in filenames")
    parser.add_argument("--epochs",       type=int,   default=100)
    parser.add_argument("--batch-size",   type=int,   default=32)
    parser.add_argument("--lr",           type=float, default=1e-3)
    parser.add_argument("--reg-lambda",   type=float, default=1e-3, dest="reg_lambda")
    parser.add_argument("--solver-iters", type=int,   default=8,    dest="solver_iters")
    parser.add_argument("--hidden-dim",   type=int,   default=64,   dest="hidden_dim")
    parser.add_argument("--seed",         type=int,   default=42)
    parser.add_argument("--output-dir",   type=Path,  default=Path("."),
                        help="Directory for saved model and accuracy report")
    args = parser.parse_args()

    set_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # ── Data ──────────────────────────────────────────────────────────────────
    print(f"\nLoading samples from {args.data_dir} …")
    samples, data_stats = load_samples(args.data_dir, gt_unit=args.gt_unit)
    print(f"  Files found      : {data_stats['num_files']}")
    print(f"  Lines parsed     : {data_stats['num_lines_total']}")
    print(f"  Valid samples    : {data_stats['num_valid_samples']}")
    print(f"  Skipped (missing): {data_stats['num_skipped_missing']}")
    print(f"  Skipped (unparse): {data_stats['num_skipped_unparsed']}")

    train_samples, val_samples, test_samples = split_samples(samples, seed=args.seed)
    print(f"\nSplit: train={len(train_samples)}  val={len(val_samples)}  test={len(test_samples)}")

    train_ranges, train_gt = stack_samples(train_samples)
    val_ranges,   val_gt   = stack_samples(val_samples)
    test_ranges,  test_gt  = stack_samples(test_samples)

    range_norm = compute_normalizer(train_ranges)

    train_loader = DataLoader(RangeDataset(train_ranges, train_gt),
                              batch_size=args.batch_size, shuffle=True,  drop_last=False)
    val_loader   = DataLoader(RangeDataset(val_ranges,   val_gt),
                              batch_size=args.batch_size, shuffle=False, drop_last=False)
    test_loader  = DataLoader(RangeDataset(test_ranges,  test_gt),
                              batch_size=args.batch_size, shuffle=False, drop_last=False)

    # ── Anchors ───────────────────────────────────────────────────────────────
    anchors_np = load_anchors(args.anchors_json)
    anchors_t  = torch.tensor(anchors_np, dtype=torch.float32, device=device)
    print(f"\nAnchor positions (m):\n{anchors_np}")

    # ── Model & optimiser ────────────────────────────────────────────────────
    model = WeightNet(hidden_dim=args.hidden_dim).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=10
    )

    print(f"\nTraining WeightNet for {args.epochs} epochs …\n")
    print(f"  {'Epoch':>6}  {'Train Loss':>12}  {'Val Loss':>12}  {'LR':>10}")
    print(f"  {'-'*6}  {'-'*12}  {'-'*12}  {'-'*10}")

    train_history: List[Tuple[float, float]] = []
    val_history:   List[Tuple[float, float]] = []

    best_val_loss = float("inf")
    best_state    = None

    for epoch in range(1, args.epochs + 1):
        tl = train_one_epoch(
            model, train_loader, optimizer, range_norm,
            anchors_t, device, args.solver_iters, args.reg_lambda,
        )
        vl = eval_loss(
            model, val_loader, range_norm,
            anchors_t, device, args.solver_iters, args.reg_lambda,
        )
        scheduler.step(vl)
        train_history.append(tl)
        val_history.append(vl)

        lr_now = optimizer.param_groups[0]["lr"]
        print(f"  {epoch:>6}  {tl:>12.6f}  {vl:>12.6f}  {lr_now:>10.2e}")

        if vl < best_val_loss:
            best_val_loss = vl
            best_state = {k: v.clone() for k, v in model.state_dict().items()}

    # ── Restore best weights ──────────────────────────────────────────────────
    if best_state is not None:
        model.load_state_dict(best_state)
    print(f"\nBest val loss: {best_val_loss:.6f}")

    # ── Test evaluation ───────────────────────────────────────────────────────
    pred_w, pred_u, gt_test = predict_positions(
        model, test_loader, range_norm, anchors_t, device, args.solver_iters
    )

    test_weighted_rmse   = rmse_3d(pred_w, gt_test)
    test_unweighted_rmse = rmse_3d(pred_u, gt_test)
    test_weighted_mae    = mae_xyz(pred_w, gt_test)
    test_unweighted_mae  = mae_xyz(pred_u, gt_test)

    print(f"\n[Test Results]")
    print(f"  Weighted RMSE   : {test_weighted_rmse:.2f} cm")
    print(f"  Unweighted RMSE : {test_unweighted_rmse:.2f} cm")
    improvement = (test_unweighted_rmse - test_weighted_rmse) / test_unweighted_rmse * 100
    print(f"  RMSE improvement: {improvement:+.1f}%")

    # ── Save model ────────────────────────────────────────────────────────────
    args.output_dir.mkdir(parents=True, exist_ok=True)
    model_path = args.output_dir / "weight_model.pt"
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "model_config": {
                "hidden_dim": args.hidden_dim,
                "w_min": model.w_min,
                "w_max": model.w_max,
            },
            "normalizer": range_norm.as_dict(),
            "anchors":    anchors_np.tolist(),
            "node_order": NODE_ORDER,
            "best_val_loss": best_val_loss,
        },
        model_path,
    )
    print(f"\nModel saved -> {model_path}")

    # ── Accuracy report ───────────────────────────────────────────────────────
    report_path = args.output_dir / "accuracy_report.txt"
    write_accuracy_report(
        report_path,
        train_history,
        val_history,
        test_weighted_rmse,
        test_unweighted_rmse,
        test_weighted_mae,
        test_unweighted_mae,
        args,
    )


if __name__ == "__main__":
    main()
