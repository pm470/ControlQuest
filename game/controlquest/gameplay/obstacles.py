"""Obstacle ellipses on the game side: what the solver avoids around each block.

The same maths as engine_server/mpc/obstacles.py (minimum-area ellipse around the 4
corners, each semi-axis enlarged by the margin). The game needs it before any run:
to draw the dashed ellipses and to reject waypoints placed inside one. The engine
stays the authority and checks waypoints again.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Ellipse:
    center: tuple[float, float]
    E: np.ndarray  # (2, 2): ellipse = {p : (p - c)^T E (p - c) <= 1}

    def contains(self, x: float, y: float) -> bool:
        d = np.array([x, y]) - self.center
        return float(d @ self.E @ d) < 1.0

    def boundary(self, n: int = 72) -> list[tuple[float, float]]:
        """Points on the ellipse outline (world coordinates), for drawing."""
        lam, V = np.linalg.eigh(self.E)
        t = np.linspace(0.0, 2.0 * math.pi, n, endpoint=False)
        pts = np.array(self.center)[:, None] + V @ (np.stack([np.cos(t), np.sin(t)]) / np.sqrt(lam)[:, None])
        return [(float(x), float(y)) for x, y in pts.T]


def _min_enclosing_ellipse(points, tol=1e-10, max_iter=10_000):
    """Minimum-area ellipse containing all points (Khachiyan's algorithm): (c, E)."""
    P = np.asarray(points, dtype=float)
    n, d = P.shape
    Qm = np.vstack([P.T, np.ones(n)])
    u = np.full(n, 1.0 / n)
    for _ in range(max_iter):
        X = Qm @ np.diag(u) @ Qm.T
        M = np.einsum("ij,ji->i", Qm.T @ np.linalg.inv(X), Qm)
        j = np.argmax(M)
        step = (M[j] - d - 1) / ((d + 1) * (M[j] - 1))
        u_new = (1 - step) * u
        u_new[j] += step
        done = np.linalg.norm(u_new - u) < tol
        u = u_new
        if done:
            break
    c = P.T @ u
    E = np.linalg.inv(P.T @ np.diag(u) @ P - np.outer(c, c)) / d
    E /= max(1.0, np.max(np.einsum("ni,ij,nj->n", P - c, E, P - c)))
    return c, E


def ellipse_from_corners(corners, margin: float = 0.0) -> Ellipse:
    c, E = _min_enclosing_ellipse(corners)
    lam, V = np.linalg.eigh(E)
    axes = 1.0 / np.sqrt(lam) + margin
    return Ellipse(center=(float(c[0]), float(c[1])), E=V @ np.diag(1.0 / axes**2) @ V.T)


def level_ellipses(blocks, margin: float) -> list[Ellipse]:
    return [ellipse_from_corners(b, margin) for b in blocks]
