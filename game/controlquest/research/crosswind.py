"""Research debrief of Level 4, "Crosswind": feedback, disturbances and how often to re-plan."""

from .base import PaperRef, ResearchInfo

RESEARCH = ResearchInfo(
    level_id="crosswind",
    question=("How often must an MPC re-plan to keep useful feedback under disturbances, when "
              "computation is limited?"),
    takeaway=("Re-planning is the feedback. Re-plan too rarely and disturbances act unchecked; "
              "re-plan at every step and you pay for every solve."),
    problem=(r"Between two solves the controller applies its old plan open-loop, and whatever the "
             r"model does not know (here, the wind) pushes the ball off that plan. Solving more often "
             r"corrects sooner but costs computation. A fixed interval $k$ has to suit the most "
             r"demanding moment of the whole run, even when most of the run is calm."),
    relevance=("Embedded controllers, battery-powered robots and networked systems have limited "
               "computing or communication. Event-triggered and self-triggered MPC solve only when "
               "needed: when the state drifts too far from the prediction, or when the cost reacts "
               "strongly, and less often when it is safe."),
    shown=(r"With $k = 1$ the budget runs out after a few seconds. With a large $k$ the wind pushes "
           r"the ball off its plan into a block between re-plans. In between, a $k$ with enough "
           r"obstacle margin reaches the star within the budget. The drift is the distance between "
           r"the ball and the prediction of the plan it follows, measured up to the moment that "
           r"plan is replaced; it grows roughly with the square of the open-loop time."),
    limits=(r"$k$ is fixed for the whole run: this is not event- or self-triggered MPC. The budget "
            r"counts solves, not computing time; the wind is the same in every run (fixed seed); "
            r"and the margin is a heuristic buffer, not a robust (tube) MPC."),
    papers=(
        PaperRef(
            key="5A",
            title="Event-based model predictive control for nonlinear systems with dynamic disturbance",
            authors="P. Li, T. Wang, Y. Kang, K. Li, Y.-B. Zhao",
            year=2022,
            venue="Automatica 145, 110533",
            url="https://doi.org/10.1016/j.automatica.2022.110533",
            doi="10.1016/j.automatica.2022.110533",
            problem=("Solving the MPC at every step uses computing resources, and a disturbance with "
                     "its own dynamics corrupts the predictions."),
            approach=("Event-triggered and self-triggered MPC that predict the disturbance: the OCP "
                      "is solved only at triggering instants, decided from the state prediction "
                      "error and the predicted disturbance."),
            connection=r"Here you chose one fixed $k$; these schemes decide when to re-plan from what happens.",
            checked="Crossref (DOI) and the abstract (Semantic Scholar), 2026-11-19",
        ),
        PaperRef(
            key="5B",
            title="A Sensitivity-Based Approach to Self-Triggered Nonlinear Model Predictive Control",
            authors="P. Conrad, K. Graichen",
            year=2024,
            venue="IEEE Access 12, 153243–153252",
            url="https://doi.org/10.1109/ACCESS.2024.3480522",
            doi="10.1109/ACCESS.2024.3480522",
            problem=("Self-triggered control saves resources, but its use for general nonlinear MPC, "
                     "where computation matters, was little explored."),
            approach=("Choose the next sampling time from how sensitive the MPC cost is (sample "
                      "sooner when it is), with a cost-decrease condition that guarantees asymptotic "
                      "stability."),
            connection=r"An adaptive $k$: re-plan often in sensitive moments, rarely when it is calm.",
            checked="Crossref (DOI) and the abstract (Semantic Scholar), 2026-11-19",
        ),
    ),
)
