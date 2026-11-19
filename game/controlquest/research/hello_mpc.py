"""Research debrief of Level 0, "Hello, MPC" (tutorial): the receding-horizon loop."""

from .base import PaperRef, ResearchInfo

RESEARCH = ResearchInfo(
    level_id="hello_mpc",
    question=("How does solving one optimisation problem again and again become a feedback "
              "controller, and why does every solve have to be fast?"),
    takeaway=("One optimised plan is not the controller. The controller is the rule: measure, "
              "solve the OCP again, apply only the first input."),
    problem=(r"An OCP gives an open-loop plan: a whole input sequence computed from one state. On its "
             r"own it cannot react to anything that happens later. MPC turns it into feedback by "
             r"solving it again at every sample from the measured state $\hat{x}$ and applying only "
             r"$u_0$. The price is a full optimisation every $\Delta t$, so a solve has to finish well "
             r"within one sample."),
    relevance=("This loop is how MPC runs on cars, drones and process plants. In fast applications, "
               "such as racing drones, the OCP is solved many times per second. That is why solvers "
               "like acados, which this game uses, generate code tailored to the problem and exploit "
               "the structure of the OCP."),
    shown=("The tour followed one round of the loop. In the replay, the dashed plan moves along "
           "with the ball: a new plan from every new measurement, of which only the first input is "
           "used."),
    limits=("Here the model is exact and nothing disturbs the ball, so re-planning has nothing to "
            "correct yet (Crosswind changes that). The game computes the whole run first and replays "
            "it, so the replay speed says nothing about real-time execution."),
    papers=(
        PaperRef(
            key="0A",
            title=("Multi-Phase Optimal Control Problems for Efficient Nonlinear Model Predictive "
                   "Control With acados"),
            authors="J. Frey, K. Baumgärtner, G. Frison, M. Diehl",
            year=2025,
            venue="Optimal Control Applications and Methods 46(2), 827–845",
            url="https://doi.org/10.1002/oca.3234",
            doi="10.1002/oca.3234",
            free_url="https://arxiv.org/abs/2408.07382",
            problem=("Accurate MPC formulations can be expensive to solve at every sample, and they "
                     "are hard to set up in specialised solver software."),
            approach=("A multi-phase OCP interface for acados: different parts of the horizon can use "
                      "different discretisations, models and input parametrisations, so the solver "
                      "spends accuracy where it matters."),
            connection=("ControlQuest uses acados too, for a much simpler single-phase OCP solved at "
                        "every step."),
            checked="Crossref (DOI) and arXiv abstract, 2026-11-19",
        ),
        PaperRef(
            key="0B",
            title=("MPCC++: Model Predictive Contouring Control for Time-Optimal Flight with Safety "
                   "Constraints"),
            authors="M. Krinner, A. Romero, L. Bauersfeld, M. Zeilinger, A. Carron, D. Scaramuzza",
            year=2024,
            venue="Robotics: Science and Systems (RSS) 2024",
            url="https://roboticsconference.org/2024/program/papers/109/",
            free_url="https://arxiv.org/abs/2403.17551",
            problem="Racing a quadrotor at its physical limits, as fast as possible, without hitting the gates.",
            approach=("Model predictive contouring control with a track constraint and a terminal set "
                      "for safety, a model with a residual learned from real flight data, and "
                      "Bayesian optimisation to tune the controller."),
            connection=("A demanding real use of the loop you just watched. The later levels look at "
                        "the design choices it combines (cost tuning, terminal sets, obstacles, "
                        "feedback) one at a time."),
            checked="RSS 2024 programme page and arXiv abstract, 2026-11-19 (no DOI listed)",
        ),
    ),
)
