"""The OCP "recipe": builds the acados problem for one problem *shape*.

Only things that change the size/structure of the problem are arguments here
(horizon N, sampling time dt). Everything a level or the player can change
(weights, bounds, target, model gain) is only a placeholder here and is set at
runtime by controller.py, without recompiling.

The OCP solved at every MPC step (PRD 4 / "Your OCP"):

    min   sum_{k=0}^{N-1} dt * ( |x_k - x_ref|_Q^2 + |u_k|_R^2 ) + |x_N - x_ref|_P^2
    s.t.  x_0 = measured state
          x_{k+1} = f(x_k, u_k; g)                 (model.py)
          u_min <= u_k <= u_max                     k = 0..N-1
          x_min <= x_k <= x_max                     k = 1..N  (workspace + speed)

acados uses  c_k * 1/2 * |y - y_ref|_W^2  with y = [x; u], so W = 2*blkdiag(Q, R),
W_e = 2*P and cost_scaling c_k = dt (stages), 1 (terminal) give exactly the cost above.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from acados_template import AcadosOcp

from .model import NU, NX, export_model


def shape_name(N: int) -> str:
    """Unique name per problem shape (acados needs unique names per compiled solver)."""
    return f"cq_N{N}"


def build_ocp(N: int, dt: float, build_dir: Path) -> AcadosOcp:
    name = shape_name(N)
    ocp = AcadosOcp()
    ocp.model = export_model(name, dt)
    ny = NX + NU

    # --- cost: linear least squares on y = [x; u] (weights set at runtime) ---
    ocp.cost.cost_type = "LINEAR_LS"
    ocp.cost.cost_type_e = "LINEAR_LS"
    ocp.cost.Vx = np.vstack([np.eye(NX), np.zeros((NU, NX))])
    ocp.cost.Vu = np.vstack([np.zeros((NX, NU)), np.eye(NU)])
    ocp.cost.Vx_e = np.eye(NX)
    ocp.cost.W = np.eye(ny)  # placeholder -> controller.set_weights
    ocp.cost.W_e = np.eye(NX)  # placeholder
    ocp.cost.yref = np.zeros(ny)  # placeholder -> controller.set_target
    ocp.cost.yref_e = np.zeros(NX)

    # --- constraints (values are placeholders -> controller.set_bounds) ---
    ocp.constraints.idxbu = np.arange(NU)
    ocp.constraints.lbu = -np.ones(NU)
    ocp.constraints.ubu = np.ones(NU)
    ocp.constraints.idxbx = np.arange(NX)
    ocp.constraints.lbx = -np.ones(NX)
    ocp.constraints.ubx = np.ones(NX)
    ocp.constraints.idxbx_e = np.arange(NX)
    ocp.constraints.lbx_e = -np.ones(NX)
    ocp.constraints.ubx_e = np.ones(NX)
    ocp.constraints.x0 = np.zeros(NX)  # fixed to the measured state before every solve

    ocp.parameter_values = np.ones(1)  # model gain g

    # --- solver options ---
    opts = ocp.solver_options
    opts.N_horizon = N
    opts.tf = N * dt
    opts.cost_scaling = np.append(np.full(N, dt), 1.0)
    opts.integrator_type = "DISCRETE"
    opts.nlp_solver_type = "SQP"
    opts.hessian_approx = "GAUSS_NEWTON"  # exact for LS cost + linear dynamics
    opts.qp_solver = "PARTIAL_CONDENSING_HPIPM"
    opts.qp_tol = 1e-8
    opts.tol = 1e-6
    opts.nlp_solver_max_iter = 100
    opts.print_level = 0

    ocp.name = name
    build_dir.mkdir(parents=True, exist_ok=True)
    ocp.code_gen_opts.code_export_directory = str(build_dir / f"c_generated_code_{name}")
    ocp.code_gen_opts.json_file = str(build_dir / f"{name}.json")
    return ocp
