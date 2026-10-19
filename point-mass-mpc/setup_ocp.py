import os

import casadi as ca
import numpy as np
from acados_template import ACADOS_INFTY, AcadosOcp

from config import PointMassConfig
from point_mass_model import export_point_mass_model

HERE = os.path.dirname(os.path.abspath(__file__))


def setup_ocp(cfg: PointMassConfig) -> AcadosOcp:
    """Create an ocp object to formulate the OCP for the 2D point mass.

    Decision variables (chosen by the solver): x_0..x_N and u_0..u_{N-1}.
    Parameters/references (chosen by us, not optimised): the initial state
    x0_bar and the target x_target, both of which can be changed between
    solves without regenerating code.

    Intended objective:
        J = sum_{k=0}^{N-1} dt * [ |x_k - x_ref|_Q^2 + |u_k|_R^2 ] + |x_N - x_ref|_P^2
    Obstacle j (ellipse c_j, E_j), on stages 1..N:
        h_j(x_k) = (p_k - c_j)^T E_j (p_k - c_j) >= 1
    """
    cfg.validate()

    # create ocp object to formulate the OCP
    ocp = AcadosOcp()
    # set model
    ocp.model = export_point_mass_model(cfg.dt, cfg.model_name)

    nx = ocp.model.x.rows()
    nu = ocp.model.u.rows()
    ny = nx + nu

    # ======================= set cost =======================
    # NOTE: LINEAR_LS: cost_k = c_k * 0.5 * (Vx x + Vu u - yref)^T W (Vx x + Vu u - yref)
    #       where c_k = cost_scaling[k], which acados defaults to dt for the
    #       stages and 1 for the terminal stage (we set it explicitly below).
    # Hence W = 2 * blkdiag(Q, R) and W_e = 2 * P reproduce J exactly; the dt
    # is applied once, by cost_scaling, not inside W.
    ocp.cost.cost_type = "LINEAR_LS"  # the output y = [x; u] is linear
    ocp.cost.cost_type_e = "LINEAR_LS"

    # stage output y = Vx x + Vu u = [x; u]
    ocp.cost.Vx = np.vstack([np.eye(nx), np.zeros((nu, nx))])
    ocp.cost.Vu = np.vstack([np.zeros((nx, nu)), np.eye(nu)])
    # terminal output y_e = x
    ocp.cost.Vx_e = np.eye(nx)

    # weight matrices
    W = np.zeros((ny, ny))
    W[:nx, :nx] = cfg.Q
    W[nx:, nx:] = cfg.R
    ocp.cost.W = 2.0 * W
    ocp.cost.W_e = 2.0 * cfg.P

    # references (stage: [x_target; 0; 0], terminal: x_target).
    # Stage 0 uses the same cost as stages 1..N-1 (cost_type_0 defaults to it).
    ocp.cost.yref = np.concatenate([cfg.x_target, np.zeros(nu)])
    ocp.cost.yref_e = cfg.x_target.copy()

    # ============== set constraints ================
    # Actuator constraints: -a_max <= ax, ay <= a_max on every stage 0..N-1
    ocp.constraints.lbu = cfg.u_lb
    ocp.constraints.ubu = cfg.u_ub
    ocp.constraints.idxbu = np.arange(nu)

    # State bounds (workspace + velocity) on stages 1..N-1 ...
    ocp.constraints.lbx = cfg.x_lb
    ocp.constraints.ubx = cfg.x_ub
    ocp.constraints.idxbx = np.arange(nx)
    # ... and on the terminal state x_N (penalised, not forced to the target)
    ocp.constraints.lbx_e = cfg.x_lb
    ocp.constraints.ubx_e = cfg.x_ub
    ocp.constraints.idxbx_e = np.arange(nx)

    # Obstacles: nonlinear constraints 1 <= h_j(x) < inf on stages 1..N-1 and N
    # (stage 0 needs none: x_0 is fixed to the measurement). Smooth quadratic
    # in p, so the NLP is nonconvex but differentiable everywhere.
    obstacles = cfg.obstacles
    if obstacles:
        p = ocp.model.x[:2]
        d = [p - ca.DM(e.center) for e in obstacles]
        h = ca.vertcat(*[dj.T @ ca.DM(e.E) @ dj for dj, e in zip(d, obstacles)])
        ocp.model.con_h_expr = h
        ocp.model.con_h_expr_e = h
        ocp.constraints.lh = np.ones(len(obstacles))
        ocp.constraints.uh = np.full(len(obstacles), ACADOS_INFTY)  # one-sided (HPIPM)
        ocp.constraints.lh_e = np.ones(len(obstacles))
        ocp.constraints.uh_e = np.full(len(obstacles), ACADOS_INFTY)

    # Initial-state constraint x_0 = x0_bar on all 4 components (this sets
    # lbx_0 = ubx_0 = x0, idxbx_0 = [0,1,2,3]). Will be changed in the closed loop.
    ocp.constraints.x0 = cfg.x_start.copy()

    # ============== set ocp options ================
    # prediction horizon (dt fixed, so T grows with N)
    ocp.solver_options.N_horizon = cfg.N
    ocp.solver_options.tf = cfg.T
    ocp.solver_options.cost_scaling = np.append(np.full(cfg.N, cfg.dt), 1.0)

    # additional ocp options
    ocp.solver_options.integrator_type = "DISCRETE"  # uses model.disc_dyn_expr
    ocp.solver_options.nlp_solver_type = "SQP"
    # Gauss-Newton: exact for the LS cost + linear dynamics; it ignores the
    # curvature of the obstacle constraints (keeps the QP Hessian convex).
    ocp.solver_options.hessian_approx = "GAUSS_NEWTON"
    ocp.solver_options.qp_solver = "PARTIAL_CONDENSING_HPIPM"  # acados default, as in ex. 07
    # Obstacles make the NLP nonconvex: plain full-step SQP can cycle near an
    # ellipse (e.g. target straight behind it). A small Levenberg-Marquardt term
    # (lm * I added to the QP Hessian) damps the steps; the converged solution is
    # unchanged. 1e-2 was the best of 1e-3..1; merit backtracking was much worse.
    ocp.solver_options.levenberg_marquardt = 1e-2
    ocp.solver_options.nlp_solver_max_iter = 200  # hardest tested solve needs ~85
    ocp.solver_options.qp_tol = 1e-8
    ocp.solver_options.tol = 1e-6
    ocp.solver_options.print_level = 0

    # unique name and code location: does not overwrite the pendulum's files
    ocp.name = f"{cfg.model_name}_ocp"
    out = os.path.join(HERE, cfg.output_dir)
    ocp.code_gen_opts.code_export_directory = os.path.join(out, f"c_generated_code_{cfg.model_name}")
    ocp.code_gen_opts.json_file = os.path.join(out, f"{ocp.name}.json")

    return ocp
