"""Single place for all tunable settings of the point-mass MPC example.
"""

from dataclasses import dataclass, field, replace

import numpy as np

from obstacles import ellipse_from_corners


def _arr(*values):
    return field(default_factory=lambda: np.array(values, dtype=float))


def _corners(*blocks):
    return field(default_factory=lambda: [np.array(b, dtype=float) for b in blocks])


@dataclass
class PointMassConfig:
    # --- timing -------------------------------------------------------------
    dt: float = 0.1             # sampling interval [s]
    N: int = 30                 # prediction horizon [intervals]; T = N * dt
    t_sim_max: float = 60.0     # maximum closed-loop simulation duration [s]

    # --- scenario: state x = [px, py, vx, vy] -------------------------------
    x_start: np.ndarray = _arr(5.0, 5.0, 0.0, 0.0)
    x_target: np.ndarray = _arr(40.0, 35.0, 0.0, 0.0)  # zero velocity: stop there

    # --- cost weights (the "true" objective, see setup_ocp.py) --------------
    Q: np.ndarray = field(default_factory=lambda: np.diag([10.0, 10.0, 1.0, 1.0]))
    R: np.ndarray = field(default_factory=lambda: np.diag([0.1, 0.1]))
    P_factor: float = 10.0  # terminal weight P = P_factor * Q

    # --- componentwise bounds ----------------------------------------------
    a_max: float = 2.0  # |ax|, |ay| <= a_max [m/s^2]
    v_max: float = 2.0  # |vx|, |vy| <= v_max [m/s]
    p_min: np.ndarray = _arr(0.0, 0.0)  # workspace lower corner [m]
    p_max: np.ndarray = _arr(50.0, 50.0)  # workspace upper corner [m]

    # --- obstacles: 4 corners (any order) per block -------------------------
    # The solver avoids the smallest ellipse containing the corners; [] = none.
    obstacle_corners: list = _corners(
        [(12, 10), (17, 10), (10, 12), (10, 17)],
        [(25, 20), (32, 20), (25, 32), (32, 32)],
    )
    obstacle_margin: float = 0.1  # extra clearance added to each semi-axis [m]

    # --- closed-loop termination & checks -----------------------------------
    pos_tol: float = 0.05  # ||p - p_target|| < pos_tol [m]
    speed_tol: float = 0.05  # ||v|| < speed_tol [m/s]
    bound_tol: float = 1e-5  # numerical tolerance for constraint checks

    # --- code generation ----------------------------------------------------
    model_name: str = "point_mass_2d"  # unique: does not clash with the pendulum
    output_dir: str = "output"  # relative to this folder; ignored by git

    @property
    def T(self) -> float:
        """Prediction duration [s]."""
        return self.N * self.dt

    @property
    def P(self) -> np.ndarray:
        return self.P_factor * self.Q

    @property
    def x_lb(self) -> np.ndarray:
        return np.concatenate([self.p_min, [-self.v_max, -self.v_max]])

    @property
    def x_ub(self) -> np.ndarray:
        return np.concatenate([self.p_max, [self.v_max, self.v_max]])

    @property
    def obstacles(self) -> list:
        """Ellipses used as constraints, one per block in obstacle_corners."""
        return [ellipse_from_corners(c, self.obstacle_margin) for c in self.obstacle_corners]

    @property
    def u_lb(self) -> np.ndarray:
        return np.full(2, -self.a_max)

    @property
    def u_ub(self) -> np.ndarray:
        return np.full(2, self.a_max)

    def with_changes(self, **kwargs) -> "PointMassConfig":
        """Return a validated copy with some fields replaced."""
        cfg = replace(self, **kwargs)
        cfg.validate()
        return cfg

    def check_state(self, x, name: str) -> np.ndarray:
        """Validate shape, finiteness and bounds of a state vector."""
        x = np.asarray(x, dtype=float).reshape(-1)
        if x.shape != (4,):
            raise ValueError(f"{name} must have 4 entries [px, py, vx, vy], got shape {x.shape}.")
        if not np.all(np.isfinite(x)):
            raise ValueError(f"{name} contains non-finite values: {x}.")
        lb, ub = self.x_lb, self.x_ub
        bad = (x < lb - self.bound_tol) | (x > ub + self.bound_tol)
        if np.any(bad):
            names = ["px", "py", "vx", "vy"]
            details = ", ".join(
                f"{names[i]}={x[i]:g} not in [{lb[i]:g}, {ub[i]:g}]" for i in np.flatnonzero(bad)
            )
            raise ValueError(f"{name} violates the configured bounds: {details}.")
        return x

    def check_free(self, x, name: str, obstacles=None) -> np.ndarray:
        """check_state, plus: the position must lie outside every obstacle ellipse."""
        x = self.check_state(x, name)
        for j, ell in enumerate(self.obstacles if obstacles is None else obstacles):
            if ell.h(x) < 1.0 - self.bound_tol:
                raise ValueError(f"{name} position ({x[0]:g}, {x[1]:g}) lies inside obstacle {j} "
                                 f"(ellipse around corners {ell.corners.tolist()}).")
        return x

    def validate(self) -> None:
        """Reject invalid settings with a useful message."""
        if not (np.isfinite(self.dt) and self.dt > 0):
            raise ValueError(f"dt must be a positive number, got {self.dt}.")
        if isinstance(self.N, bool) or not isinstance(self.N, (int, np.integer)) or self.N < 1:
            raise ValueError(f"N must be a positive integer, got {self.N!r}.")
        if not (self.t_sim_max > 0):
            raise ValueError(f"t_sim_max must be positive, got {self.t_sim_max}.")
        if not (self.a_max > 0 and self.v_max > 0):
            raise ValueError(f"a_max and v_max must be positive, got {self.a_max}, {self.v_max}.")
        p_min = np.asarray(self.p_min, dtype=float)
        p_max = np.asarray(self.p_max, dtype=float)
        if p_min.shape != (2,) or p_max.shape != (2,) or np.any(p_min >= p_max):
            raise ValueError(f"Workspace needs p_min < p_max componentwise, got {p_min}, {p_max}.")
        for name, M, n in [("Q", self.Q, 4), ("R", self.R, 2)]:
            M = np.asarray(M, dtype=float)
            if M.shape != (n, n):
                raise ValueError(f"{name} must be {n}x{n}, got shape {M.shape}.")
            if not np.allclose(M, M.T) or np.min(np.linalg.eigvalsh(M)) < 0:
                raise ValueError(f"{name} must be symmetric positive semidefinite.")
        if np.min(np.linalg.eigvalsh(np.asarray(self.R, dtype=float))) <= 0:
            raise ValueError("R must be positive definite.")
        if not (self.P_factor >= 0):
            raise ValueError(f"P_factor must be nonnegative, got {self.P_factor}.")
        if not (self.pos_tol > 0 and self.speed_tol > 0 and self.bound_tol >= 0):
            raise ValueError("pos_tol and speed_tol must be positive, bound_tol nonnegative.")
        if not (np.isfinite(self.obstacle_margin) and self.obstacle_margin >= 0):
            raise ValueError(f"obstacle_margin must be nonnegative, got {self.obstacle_margin}.")
        for j, c in enumerate(self.obstacle_corners):
            c = np.asarray(c, dtype=float)
            if c.shape != (4, 2) or not np.all(np.isfinite(c)):
                raise ValueError(f"obstacle {j} needs 4 finite corners (x, y), got {c.tolist()}.")
            if np.linalg.matrix_rank(c[1:] - c[0], tol=1e-9) < 2:
                raise ValueError(f"obstacle {j} corners are collinear (no area): {c.tolist()}.")
        obstacles = self.obstacles
        self.x_start = self.check_free(self.x_start, "x_start", obstacles)
        self.x_target = self.check_free(self.x_target, "x_target", obstacles)
