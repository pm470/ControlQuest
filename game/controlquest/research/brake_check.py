"""Research debrief of Level 2, "Brake Check": recursive feasibility and terminal constraints."""

from .base import PaperRef, ResearchInfo

RESEARCH = ResearchInfo(
    level_id="brake_check",
    question=("How can an OCP that is feasible now become infeasible later, and how does a "
              "terminal constraint keep it feasible?"),
    takeaway=("A plan must end somewhere safe. Requiring every plan to end at rest keeps a way to "
              "stop in every plan."),
    problem=(r"MPC only plans $N$ steps ahead. A plan can be feasible now and still lead into a state "
             r"from which no feasible plan exists a few steps later: here, too fast and too close to "
             r"the wall. The standard remedy is a terminal constraint $x_N \in \mathcal{X}_f$ with a "
             r"control invariant set $\mathcal{X}_f$: from inside it, the system can stay within all "
             r"constraints forever. Then the previous plan, shifted by one step and extended inside "
             r"$\mathcal{X}_f$, is again feasible: recursive feasibility. Rest is such a set for the "
             r"ball: at $v = 0$, the input $u = 0$ keeps it at rest."),
    relevance=("Safety-critical controllers, such as automated cars merging into traffic, must never "
               "run into a situation without a safe continuation. Terminal sets are how MPC designs "
               "guarantee that, but finding them for nonlinear systems is hard."),
    shown=(r"Without the terminal stop, a short horizon lets the ball reach full speed. Once braking "
           r"needs more room than is left before the wall (the brake check turns red), no plan can "
           r"avoid the wall and the solver fails. With $v_N = 0$ every plan contains a stop, so the "
           r"controller stays feasible, at the price of a speed limit of about $a_{\max} N \Delta t$."),
    limits=("The guarantee holds here because the model is exact and nothing disturbs the ball. A "
            "solver failure is no proof of infeasibility; the evidence is physical (braking distance "
            "against the room to the wall). Feasibility alone is not stability or real-world safety."),
    papers=(
        PaperRef(
            key="2A",
            title=("Model Predictive Control for Lane Merging Automation With Recursive Feasibility "
                   "Guarantees and Its Experimental Validation"),
            authors="M. E. Geurts, A. Katriniok, E. Silvas, N. J. Brouwer, W. P. M. H. Heemels",
            year=2025,
            venue="IEEE Transactions on Control Systems Technology 33(2), 566–581",
            url="https://doi.org/10.1109/TCST.2024.3485306",
            doi="10.1109/TCST.2024.3485306",
            problem=("Merging an automated vehicle from two lanes into one in mixed traffic, then "
                     "continuing with (adaptive) cruise control, safely and comfortably."),
            approach=("One MPC (a mixed-integer QP) with a state-dependent safety distance and "
                      "velocity bounds, and terminal sets designed so that recursive feasibility, and "
                      "with it constraint satisfaction, is guaranteed; validated in experiments."),
            connection=(r"The same idea as $v_N = 0$: the terminal set guarantees that every plan has "
                        r"a safe continuation."),
            checked="Crossref (DOI) and the abstract (Semantic Scholar), 2026-11-19",
        ),
        PaperRef(
            key="2B",
            title="Nonlinear model predictive control based on K-step control invariant sets",
            authors="Z. Zhao, A. Girard, S. Olaru",
            year=2024,
            venue="European Journal of Control 80, 101040",
            url="https://doi.org/10.1016/j.ejcon.2024.101040",
            doi="10.1016/j.ejcon.2024.101040",
            problem=("Recursive feasibility needs a control invariant terminal set, but for nonlinear "
                     "systems such sets are often too complex to compute or use."),
            approach=("Use K-step control invariant sets, simpler generalisations of the classical "
                      "ones, computed with symbolic control, as the terminal constraint of a "
                      "nonlinear MPC."),
            connection=("Rest is an especially simple invariant set for the ball; for nonlinear "
                        "systems, building such a set is a research problem."),
            checked="Crossref (DOI) and the abstract (Semantic Scholar), 2026-11-19",
        ),
    ),
)
