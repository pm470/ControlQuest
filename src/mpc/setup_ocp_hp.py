import casadi as ca
import numpy as np
from acados_template import AcadosOcp, AcadosModel


def export_pendulum_model() -> AcadosModel:
    model_name = 'pendulum_ode'

    # constants
    g = 9.81 # gravity constant [m/s^2]
    l = 0.8 # length of the rod [m]
    m_cart = ca.SX.sym('m') #1. # mass of the cart [kg]
    m = 0.1 # mass of the ball [kg]

    # set up states & controls
    x1 = ca.SX.sym('x1')
    theta = ca.SX.sym('theta')
    v1 = ca.SX.sym('v1')
    dtheta = ca.SX.sym('dtheta')

    x = ca.vertcat(x1, theta, v1, dtheta)

    F = ca.SX.sym('F')
    u = ca.vertcat(F)

    # xdot
    x1_dot = ca.SX.sym('x1_dot')
    theta_dot = ca.SX.sym('theta_dot')
    v1_dot = ca.SX.sym('v1_dot')
    dtheta_dot = ca.SX.sym('dtheta_dot')

    xdot = ca.vertcat(x1_dot, theta_dot, v1_dot, dtheta_dot)

    # dynamics
    cos_theta = ca.cos(theta)
    sin_theta = ca.sin(theta)
    denominator = m_cart + m - m*cos_theta*cos_theta
    f_expl_expr = ca.vertcat(v1,
                     dtheta,
                     (-m*l*sin_theta*dtheta*dtheta + m*g*cos_theta*sin_theta+F)/denominator,
                     (-m*l*cos_theta*sin_theta*dtheta*dtheta + F*cos_theta+(m_cart+m)*g*sin_theta)/(l*denominator)
                     )

    model = AcadosModel()
    model.x = x
    model.xdot = xdot
    model.u = u
    model.p = m_cart
    model.name = model_name
    model.f_expl_expr = f_expl_expr

    # store meta information
    model.x_labels = ['$x$ [m]', r'$\theta$ [rad]', '$v$ [m]', r'$\dot{\theta}$ [rad/s]']
    model.u_labels = ['$F$']
    model.t_label = '$t$ [s]'
    
    return model


def setup_ocp(Fmax: float, N_horizon: int, Tf: float) -> AcadosOcp:
    """Create an ocp object to formulate the OCP for the cartpole system.
    
    Args:
        Fmax: Maximum force that can be applied to the cart.
        N_horizon: Number of steps in the prediction horizon.
        Tf: Total time horizon of the prediction horizon.
    """
    # TODO Exercise 1.2: Fill in the blanks in this method
    # create ocp object to formulate the OCP
    ocp = AcadosOcp()
    # set model
    ocp.model = export_pendulum_model()
    ocp.parameter_values = np.array([1.])

    nx = ocp.model.x.rows()

    # ======================= set cost =======================
    # NOTE: NONLINEAR_LS pseudo: 0.5 * (y_expr - yref)^T W (y_expr - yref)
    ocp.cost.cost_type = 'NONLINEAR_LS'
    ocp.cost.cost_type_e = 'NONLINEAR_LS'

    # weight matrices
    ocp.cost.W = np.diag([1e3, 1e3, 1e-2, 1e-2, 1e-2])  # state and input weights
    ocp.cost.W_e = ocp.cost.W[:nx, :nx]

    # expressions for ys
    x = ocp.model.x
    u = ocp.model.u
    # NOTE (use x and u from the two lines above here)
    ocp.model.cost_y_expr = ca.vertcat(x, u)
    ocp.model.cost_y_expr_e = x

    # references
    ocp.cost.yref = np.zeros((nx + 1,))  # desired state and input
    ocp.cost.yref_e = ocp.cost.yref[:nx]

    # ============== set constraints ================
    # Actuator constraints
    # NOTE: Use Fmax
    ocp.constraints.lbu = np.array([-Fmax])
    ocp.constraints.ubu = np.array([+Fmax])
    ocp.constraints.idxbu = np.array([0])

    # Will be changed in the closed loop
    ocp.constraints.x0 = np.array([0.0, np.pi, 0.0, 0.0])

    # ============== set ocp options ================
    # prediction horizon
    dt0 = Tf/N_horizon
    ocp.solver_options.time_steps = np.array([dt0]*8 + [4*dt0]*2)
    ocp.solver_options.N_horizon = ocp.solver_options.time_steps.shape[0]
    ocp.solver_options.tf = np.sum(ocp.solver_options.time_steps)

    ocp.solver_options.hessian_approx = 'GAUSS_NEWTON'
    ocp.solver_options.qp_tol = 1e-4
    ocp.solver_options.tol = 1e-3
    ocp.solver_options.integrator_type = "ERK"
    # ocp.solver_options.globalization = 'MERIT_BACKTRACKING'
    # ocp.solver_options.nlp_solver_type = "SQP_RTI"
    ocp.solver_options.nlp_solver_max_iter = 2
    ocp.solver_options.qp_solver_cond_N = int(ocp.solver_options.N_horizon/4)
    
    ocp.name = "pendulum_ocp_hp"
    return ocp