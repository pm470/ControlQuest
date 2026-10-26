"""The ball: a 2D point mass (double integrator), as the controller sees it.

State x = [px, py, vx, vy] (m, m/s), input u = [ax, ay] (m/s^2).
With u held constant over one sample (zero-order hold) the exact discrete step is

    p+ = p + dt*v + 0.5*dt^2*g*u
    v+ = v + dt*g*u

g is the *model actuator gain*: 1 means "the ball does exactly what I command".
It is a runtime parameter of the solver (Level 4 changes it), not a constant.

The parameter vector also holds MAX_OBSTACLES ellipse slots (cx, cy, E11, E12, E22),
used by the obstacle constraints in ocp.py:  p = [g, slot_1, ..., slot_MAX_OBSTACLES].
"""

from __future__ import annotations

import casadi as ca
from acados_template import AcadosModel

NX, NU = 4, 2  # state and input sizes
MAX_OBSTACLES = 6  # ellipse slots compiled into every solver (PRD 9.3)
OBSTACLE_PARAMS = 5  # cx, cy, E11, E12, E22
NP = 1 + MAX_OBSTACLES * OBSTACLE_PARAMS
UNUSED_SLOT = (-100.0, -100.0, 0.01, 0.0, 0.01)  # 10 m circle far off the map: h > 200 on it


def discrete_dynamics(x, u, g, dt: float):
    """Symbolic exact discretisation (works for CasADi symbols and NumPy arrays)."""
    return ca.vertcat(
        x[0] + dt * x[2] + 0.5 * dt**2 * g * u[0],
        x[1] + dt * x[3] + 0.5 * dt**2 * g * u[1],
        x[2] + dt * g * u[0],
        x[3] + dt * g * u[1],
    )


def obstacle_h(x, p):
    """h_j = (pos - c_j)^T E_j (pos - c_j) for every slot j; the OCP requires h_j >= 1."""
    h = []
    for j in range(MAX_OBSTACLES):
        cx, cy, e11, e12, e22 = (p[1 + j * OBSTACLE_PARAMS + i] for i in range(OBSTACLE_PARAMS))
        dx, dy = x[0] - cx, x[1] - cy
        h.append(e11 * dx * dx + 2 * e12 * dx * dy + e22 * dy * dy)
    return ca.vertcat(*h)


def export_model(name: str, dt: float) -> AcadosModel:
    """acados model with discrete dynamics x_{k+1} = f(x_k, u_k; g)."""
    x = ca.SX.sym("x", NX)
    u = ca.SX.sym("u", NU)
    p = ca.SX.sym("p", NP)  # [model actuator gain g, obstacle slots]

    model = AcadosModel()
    model.name = name
    model.x = x
    model.u = u
    model.p = p
    model.disc_dyn_expr = discrete_dynamics(x, u, p[0], dt)
    return model
