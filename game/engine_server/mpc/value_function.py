"""An approximate cost-to-go V(p) around obstacles, for use as a terminal cost (NumPy only).

The standard terminal cost |x_N - x_ref|_P^2 measures the straight-line distance to the
target. Behind a wall that is a poor estimate of the true cost-to-go, and the MPC can
get stuck in a local optimum. Here the cost-to-go is computed offline and given to
the solver as a smooth function:

1. geodesic_distance: shortest-path distance to the target on a grid, around the
   obstacle ellipses (Dijkstra, 8 neighbours): the "true" cost-to-go (a dynamic-
   programming solution of a simplified problem).
2. fit_rbf: least-squares fit of V(p) = sum_i alpha_i * exp(-|p - c_i|^2 / (2 sigma^2))
   with fixed centres c_i: linear function approximation, like a critic in RL.

The weights alpha are runtime parameters of the solver (model.py); the centres and
sigma are fixed for the 50 m field, so no level needs its own solver.
"""

from __future__ import annotations

import heapq
import math

import numpy as np

N_CENTRES = 11  # RBF centres per axis
SIGMA = 4.0  # [m] RBF width (centres are 5 m apart on a 50 m field)
FIELD = (0.0, 50.0)  # centres cover this square (AGENTS.md section 8: 50 m x 50 m)


def rbf_centres(n: int = N_CENTRES, lo: float = FIELD[0], hi: float = FIELD[1]) -> np.ndarray:
    g = np.linspace(lo, hi, n)
    return np.array([(x, y) for y in g for x in g])  # (n*n, 2)


def rbf_features(points, centres=None, sigma: float = SIGMA) -> np.ndarray:
    centres = rbf_centres() if centres is None else centres
    d2 = ((np.asarray(points, float)[:, None, :2] - centres[None]) ** 2).sum(-1)
    return np.exp(-d2 / (2.0 * sigma**2))


def geodesic_distance(p_min, p_max, ellipses, target, h: float = 0.5):
    """Shortest-path distance [m] from every grid node to the target, around the ellipses
    (each given by (center, E)). Returns (xs, ys, D) with D[iy, ix]; inf inside ellipses."""
    xs = np.arange(p_min[0], p_max[0] + 1e-9, h)
    ys = np.arange(p_min[1], p_max[1] + 1e-9, h)
    X, Y = np.meshgrid(xs, ys)
    free = np.ones(X.shape, bool)
    for c, E in ellipses:
        dx, dy = X - c[0], Y - c[1]
        free &= E[0][0] * dx * dx + 2 * E[0][1] * dx * dy + E[1][1] * dy * dy >= 1.0
    D = np.full(X.shape, np.inf)
    ix, iy = int(round((target[0] - xs[0]) / h)), int(round((target[1] - ys[0]) / h))
    D[iy, ix] = math.hypot(xs[ix] - target[0], ys[iy] - target[1])
    heap = [(D[iy, ix], iy, ix)]
    steps = [(dy, dx, h * math.hypot(dx, dy)) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dx or dy]
    ny, nx = X.shape
    while heap:
        d, i, j = heapq.heappop(heap)
        if d > D[i, j]:
            continue
        for di, dj, w in steps:
            a, b = i + di, j + dj
            if 0 <= a < ny and 0 <= b < nx and free[a, b] and d + w < D[a, b]:
                D[a, b] = d + w
                heapq.heappush(heap, (d + w, a, b))
    return xs, ys, D


def fit_rbf(xs, ys, D, centres=None, sigma: float = SIGMA, ridge: float = 1e-6) -> np.ndarray:
    """Least-squares RBF weights alpha so that V(p) ~ D on the free grid nodes."""
    X, Y = np.meshgrid(xs, ys)
    ok = np.isfinite(D)
    pts = np.stack([X[ok], Y[ok]], axis=1)
    Phi = rbf_features(pts, centres, sigma)
    A = Phi.T @ Phi + ridge * np.eye(Phi.shape[1])
    return np.linalg.solve(A, Phi.T @ D[ok])


def value(points, alpha, centres=None, sigma: float = SIGMA) -> np.ndarray:
    """V(p) for points (n, 2) with the fitted weights."""
    return rbf_features(points, centres, sigma) @ alpha
