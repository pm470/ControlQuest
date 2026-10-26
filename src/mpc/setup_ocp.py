import casadi as ca
import numpy as np
from acados_template import AcadosOcp, AcadosModel


def export_ball_model() -> AcadosModel:
    """Create a planar point-mass model for the app's ball."""
    model_name = 'ball_ode'
    mass = 0.1  # ball mass [kg]

    # State: position [m] and velocity [m/s] in the x and y directions.
    pos_x = ca.SX.sym('pos_x')
    pos_y = ca.SX.sym('pos_y')
    vel_x = ca.SX.sym('vel_x')
    vel_y = ca.SX.sym('vel_y')
    x = ca.vertcat(pos_x, pos_y, vel_x, vel_y)

    # Control: applied force [N] in the x and y directions.
    force_x = ca.SX.sym('force_x')
    force_y = ca.SX.sym('force_y')
    u = ca.vertcat(force_x, force_y)

    pos_x_dot = ca.SX.sym('pos_x_dot')
    pos_y_dot = ca.SX.sym('pos_y_dot')
    vel_x_dot = ca.SX.sym('vel_x_dot')
    vel_y_dot = ca.SX.sym('vel_y_dot')
    xdot = ca.vertcat(pos_x_dot, pos_y_dot, vel_x_dot, vel_y_dot)

    f_expl_expr = ca.vertcat(
        vel_x,
        vel_y,
        force_x / mass,
        force_y / mass,
    )

    model = AcadosModel()
    model.x = x
    model.xdot = xdot
    model.u = u
    model.name = model_name
    model.f_expl_expr = f_expl_expr

    model.x_labels = ['$x$ [m]', '$y$ [m]', '$v_x$ [m/s]', '$v_y$ [m/s]']
    model.u_labels = ['$F_x$ [N]', '$F_y$ [N]']
    model.t_label = '$t$ [s]'

    return model


def setup_ocp(Fmax: float, N_horizon: int, Tf: float) -> AcadosOcp:
    """Create an OCP for moving a point-mass ball in a plane.

    Args:
        Fmax: Maximum force magnitude available independently on each axis.
        N_horizon: Number of steps in the prediction horizon.
        Tf: Total time horizon of the prediction horizon.
    """
    ocp = AcadosOcp()
    ocp.model = export_ball_model()

    nx = ocp.model.x.rows()
    nu = ocp.model.u.rows()

    ocp.cost.cost_type = 'NONLINEAR_LS'
    ocp.cost.cost_type_e = 'NONLINEAR_LS'

    # Penalize position error most, then velocity, while discouraging excess force.
    ocp.cost.W = np.diag(np.array([1e3, 1e3, 1e-2, 1e-2, 1e-1, 1e-1]))
    ocp.cost.W_e = ocp.cost.W[:nx, :nx]

    x = ocp.model.x
    u = ocp.model.u
    ocp.model.cost_y_expr = ca.vertcat(x, u)
    ocp.model.cost_y_expr_e = x

    ocp.cost.yref = np.zeros(nx + nu)
    ocp.cost.yref_e = ocp.cost.yref[:nx]

    ocp.constraints.lbu = np.full(nu, -Fmax)
    ocp.constraints.ubu = np.full(nu, Fmax)
    ocp.constraints.idxbu = np.arange(nu)

    ocp.constraints.x0 = np.zeros(nx)

    ocp.solver_options.N_horizon = N_horizon
    ocp.solver_options.tf = Tf
    ocp.solver_options.hessian_approx = 'GAUSS_NEWTON'
    ocp.solver_options.integrator_type = 'ERK'
    ocp.solver_options.qp_tol = 1e-7
    ocp.solver_options.tol = 1e-3
    ocp.solver_options.globalization = 'MERIT_BACKTRACKING'
    ocp.name = 'ball_ocp'

    return ocp