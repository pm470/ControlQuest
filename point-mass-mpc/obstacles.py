"""Obstacle geometry (NumPy only): polygon given by 4 corners -> enclosing ellipse.

An obstacle is the convex hull of its 4 corners (the "block"). For the solver
it is replaced by the minimum-area ellipse that contains all corners, so

    ellipse  = { p : (p - c)^T E (p - c) <= 1 }
    avoid it:  h(p) = (p - c)^T E (p - c) >= 1        (smooth, no min/max)

Since the ellipse contains the block, keeping h >= 1 keeps the ball out of the block.
"""

from dataclasses import dataclass

import numpy as np


@dataclass
class Ellipse:
    center: np.ndarray  # c, (2,)
    E: np.ndarray  # shape matrix, (2, 2), symmetric positive definite
    corners: np.ndarray  # the 4 corners of the block it approximates, (4, 2)

    @property
    def semi_axes(self) -> np.ndarray:
        """Semi-axis lengths [m], along the eigenvectors of E."""
        return 1.0 / np.sqrt(np.linalg.eigvalsh(self.E))

    def h(self, p) -> np.ndarray:
        """(p - c)^T E (p - c) for points p (..., 2); >= 1 means outside."""
        d = np.asarray(p, dtype=float)[..., :2] - self.center
        return np.einsum("...i,ij,...j->...", d, self.E, d)

    def boundary(self, n=200) -> np.ndarray:
        """Points on the ellipse boundary, (n, 2), for plotting."""
        lam, V = np.linalg.eigh(self.E)
        t = np.linspace(0, 2 * np.pi, n)
        circle = np.stack([np.cos(t), np.sin(t)])
        return (self.center[:, None] + V @ (circle / np.sqrt(lam)[:, None])).T

    def polygon(self) -> np.ndarray:
        """Corners ordered counter-clockwise around their centroid (convex hull of 4 points)."""
        m = self.corners.mean(axis=0)
        ang = np.arctan2(self.corners[:, 1] - m[1], self.corners[:, 0] - m[0])
        return self.corners[np.argsort(ang)]

    def block_depth(self, p) -> np.ndarray:
        """How far points p (n, 2) lie inside the block [m]; <= 0 means outside."""
        V = self.polygon()
        edges = np.roll(V, -1, axis=0) - V
        normals = np.stack([edges[:, 1], -edges[:, 0]], axis=1)  # outward for CCW order
        normals /= np.linalg.norm(normals, axis=1, keepdims=True)
        # signed distance to each edge line (positive = outside that edge)
        dist = np.einsum("nki,ki->nk", np.asarray(p, dtype=float)[:, None, :] - V[None], normals)
        return -dist.max(axis=1)


def min_enclosing_ellipse(points, tol=1e-10, max_iter=10_000):
    """Minimum-area ellipse containing all points (Khachiyan's algorithm).

    Returns (c, E) with (p - c)^T E (p - c) <= 1 for every point p.
    """
    P = np.asarray(points, dtype=float)
    n, d = P.shape
    Qm = np.vstack([P.T, np.ones(n)])  # lifted points, (d+1, n)
    u = np.full(n, 1.0 / n)  # weights of the points
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
    # the iteration is approximate: rescale so every point is exactly inside
    E /= max(1.0, np.max(np.einsum("ni,ij,nj->n", P - c, E, P - c)))
    return c, E


def ellipse_from_corners(corners, margin=0.0) -> Ellipse:
    """Enclosing ellipse of 4 corners, each semi-axis enlarged by `margin` [m]."""
    corners = np.asarray(corners, dtype=float)
    c, E = min_enclosing_ellipse(corners)
    lam, V = np.linalg.eigh(E)
    axes = 1.0 / np.sqrt(lam) + margin
    return Ellipse(center=c, E=V @ np.diag(1.0 / axes**2) @ V.T, corners=corners)
