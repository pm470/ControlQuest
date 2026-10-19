"""Single place for all tunable settings of the point-mass MPC example.

Change the defaults here, or create a modified copy in code, e.g.

    cfg = PointMassConfig(x_target=np.array([2.0, 9.0, 0.0, 0.0]), N=40)

and pass it to the controller / simulation. Nothing in the controller
implementation needs to be edited.
"""

from dataclasses import dataclass, field, replace

import numpy as np


def _arr(*values):
    return field(default_factory=lambda: np.array(values, dtype=float))


@dataclass
class PointMassConfig:
    # --- timing -------------------------------------------------------------
    dt: float = 0.1  # sampling interval [s] (kept fixed when N changes)
    N: int = 30  # prediction horizon [intervals]; T = N * dt
    t_sim_max: float = 20.0  # maximum closed-loop simulation duration [s]

    # --- scenario: state x = [px, py, vx, vy] -------------------------------
    x_start: np.ndarray = _arr(1.0, 1.0, 0.0, 0.0)
    x_target: np.ndarray = _arr(8.0, 7.0, 0.0, 0.0)  # zero velocity: stop there

    # --- cost weights (the "true" objective, see setup_ocp.py) --------------
    Q: np.ndarray = field(default_factory=lambda: np.diag([10.0, 10.0, 1.0, 1.0]))
    R: np.ndarray = field(default_factory=lambda: np.diag([0.1, 0.1]))
    P_factor: float = 10.0  # terminal weight P = P_factor * Q

    # --- componentwise bounds ----------------------------------------------
    a_max: float = 2.0  # |ax|, |ay| <= a_max [m/s^2]
    v_max: float = 2.0  # |vx|, |vy| <= v_max [m/s]
    p_min: np.ndarray = _arr(0.0, 0.0)  # workspace lower corner [m]
    p_max: np.ndarray = _arr(10.0, 10.0)  # workspace upper corner [m]

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
        self.x_start = self.check_state(self.x_start, "x_start")
        self.x_target = self.check_state(self.x_target, "x_target")
