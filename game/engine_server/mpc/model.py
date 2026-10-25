"""The ball: a 2D point mass (double integrator), as the controller sees it.

State x = [px, py, vx, vy] (m, m/s), input u = [ax, ay] (m/s^2).
With u held constant over one sample (zero-order hold) the exact discrete step is

    p+ = p + dt*v + 0.5*dt^2*g*u
    v+ = v + dt*g*u

g is the *model actuator gain*: 1 means "the ball does exactly what I command".
It is a runtime parameter of the solver (Level 4 changes it), not a constant.
"""

from __future__ import annotations

import casadi as ca
from acados_template import AcadosModel

NX, NU = 4, 2  # state and input sizes


def discrete_dynamics(x, u, g, dt: float):
    """Symbolic exact discretisation (works for CasADi symbols and NumPy arrays)."""
    return ca.vertcat(
        x[0] + dt * x[2] + 0.5 * dt**2 * g * u[0],
        x[1] + dt * x[3] + 0.5 * dt**2 * g * u[1],
        x[2] + dt * g * u[0],
        x[3] + dt * g * u[1],
    )


def export_model(name: str, dt: float) -> AcadosModel:
    """acados model with discrete dynamics x_{k+1} = f(x_k, u_k; g)."""
    x = ca.SX.sym("x", NX)
    u = ca.SX.sym("u", NU)
    g = ca.SX.sym("g", 1)  # model actuator gain (parameter)

    model = AcadosModel()
    model.name = name
    model.x = x
    model.u = u
    model.p = g
    model.disc_dyn_expr = discrete_dynamics(x, u, g, dt)
    return model
