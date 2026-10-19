"""2D point-mass model: CasADi (for acados) and NumPy (for the plant).

States  x = [px, py, vx, vy]  -- what the system "is" (position [m], velocity [m/s]).
Controls u = [ax, ay]          -- what we choose (acceleration [m/s^2]).

Continuous time: p' = v, v' = a. With a held constant over one interval of
length dt (zero-order hold), the exact discrete-time update is

    p+ = p + dt * v + 0.5 * dt^2 * a
    v+ = v + dt * a
"""

import casadi as ca
import numpy as np
from acados_template import AcadosModel


def discrete_dynamics_casadi(x, u, dt: float):
    """Symbolic exact discretisation f_discrete(x, u)."""
    px, py, vx, vy = x[0], x[1], x[2], x[3]
    ax, ay = u[0], u[1]
    return ca.vertcat(
        px + dt * vx + 0.5 * dt**2 * ax,
        py + dt * vy + 0.5 * dt**2 * ay,
        vx + dt * ax,
        vy + dt * ay,
    )


def export_point_mass_model(dt: float, name: str = "point_mass_2d") -> AcadosModel:
    """acados model with discrete dynamics x_{k+1} = f_discrete(x_k, u_k).

    Same structure as export_pendulum_model() in exercise 07, but instead of an
    explicit ODE (f_expl_expr, integrated by ERK) we give acados the exact
    discrete map via disc_dyn_expr and use the DISCRETE integrator. This makes
    the OCP prediction identical to the NumPy plant below.
    """
    x = ca.SX.sym("x", 4)  # [px, py, vx, vy]
    u = ca.SX.sym("u", 2)  # [ax, ay]

    model = AcadosModel()
    model.name = name
    model.x = x
    model.u = u
    model.disc_dyn_expr = discrete_dynamics_casadi(x, u, dt)

    # meta information for plotting (as in the pendulum example)
    model.x_labels = ["$p_x$ [m]", "$p_y$ [m]", "$v_x$ [m/s]", "$v_y$ [m/s]"]
    model.u_labels = ["$a_x$ [m/s$^2$]", "$a_y$ [m/s$^2$]"]
    model.t_label = "$t$ [s]"
    return model


def casadi_step_function(dt: float) -> ca.Function:
    """CasADi function of the discrete dynamics, used for verification."""
    x = ca.SX.sym("x", 4)
    u = ca.SX.sym("u", 2)
    return ca.Function("f_discrete", [x, u], [discrete_dynamics_casadi(x, u, dt)])


def plant_step(x: np.ndarray, u: np.ndarray, dt: float) -> np.ndarray:
    """Independent NumPy implementation of the plant (the "real" system)."""
    x = np.asarray(x, dtype=float)
    u = np.asarray(u, dtype=float)
    p, v = x[:2], x[2:]
    return np.concatenate([p + dt * v + 0.5 * dt**2 * u, v + dt * u])
