"""Obstacle geometry (NumPy only): a block given by 4 corners -> the ellipse the solver avoids.

A block is the convex hull of its 4 corners: what the player sees and what crashes
are checked against. The solver never sees blocks; it sees the minimum-area ellipse
containing the corners, each semi-axis enlarged by a margin (AGENTS.md section 8):

    ellipse = { p : (p - c)^T E (p - c) <= 1 }      avoid it:  h(p) >= 1  (smooth)

Since the ellipse contains the block, keeping h >= 1 keeps the ball out of the block.
(Ported from point-mass-mpc/obstacles.py; the game's copy is controlquest/gameplay/obstacles.py.)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Ellipse:
    center: np.ndarray  # c, (2,)
    E: np.ndarray  # shape matrix, (2, 2), symmetric positive definite

    def h(self, p) -> np.ndarray:
        """(p - c)^T E (p - c) for points p (..., 2); >= 1 means outside."""
        d = np.asarray(p, dtype=float)[..., :2] - self.center
        return np.einsum("...i,ij,...j->...", d, self.E, d)

    def distance(self, p) -> float:
        """Approximate distance [m] from point p to the ellipse boundary (0 inside)."""
        return max(0.0, (float(np.sqrt(self.h(p))) - 1.0) / float(np.sqrt(np.linalg.eigvalsh(self.E)).max()))


def min_enclosing_ellipse(points, tol=1e-10, max_iter=10_000):
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
    E /= max(1.0, np.max(np.einsum("ni,ij,nj->n", P - c, E, P - c)))  # every corner inside
    return c, E


def ellipse_from_corners(corners, margin: float = 0.0) -> Ellipse:
    """Enclosing ellipse of a block's corners, each semi-axis enlarged by `margin` [m]."""
    c, E = min_enclosing_ellipse(corners)
    lam, V = np.linalg.eigh(E)
    axes = 1.0 / np.sqrt(lam) + margin
    return Ellipse(center=c, E=V @ np.diag(1.0 / axes**2) @ V.T)


def _ccw(corners) -> np.ndarray:
    """Corners ordered counter-clockwise around their centroid."""
    C = np.asarray(corners, dtype=float)
    m = C.mean(axis=0)
    return C[np.argsort(np.arctan2(C[:, 1] - m[1], C[:, 0] - m[0]))]


def block_depth(corners, p) -> np.ndarray:
    """How far points p (n, 2) lie inside the block [m]; <= 0 means outside."""
    V = _ccw(corners)
    edges = np.roll(V, -1, axis=0) - V
    normals = np.stack([edges[:, 1], -edges[:, 0]], axis=1)  # outward for CCW order
    normals /= np.linalg.norm(normals, axis=1, keepdims=True)
    dist = np.einsum("nki,ki->nk", np.asarray(p, dtype=float)[:, None, :] - V[None], normals)
    return -dist.max(axis=1)


def block_distance(corners, p) -> float:
    """Distance [m] from point p to the block (0 if inside)."""
    V = _ccw(corners)
    p = np.asarray(p, dtype=float)[:2]
    if block_depth(corners, p[None])[0] >= 0:
        return 0.0
    best = np.inf
    for a, b in zip(V, np.roll(V, -1, axis=0)):
        s = np.clip(np.dot(p - a, b - a) / np.dot(b - a, b - a), 0.0, 1.0)
        best = min(best, float(np.linalg.norm(p - (a + s * (b - a)))))
    return best


def first_hit(blocks, p0, p1, samples: int = 10):
    """First point on the segment p0 -> p1 that lies inside a block, as (block index, point),
    or None. The path within one sample (0.1 s, <= 0.2 m) is checked at `samples` points."""
    s = np.linspace(0.0, 1.0, samples + 1)[:, None]
    pts = (1 - s) * np.asarray(p0, float)[:2] + s * np.asarray(p1, float)[:2]
    hits = [(np.argmax(block_depth(b, pts) > 0), j) for j, b in enumerate(blocks)
            if np.any(block_depth(b, pts) > 0)]
    if not hits:
        return None
    i, j = min(hits)
    return j, pts[i]
