"""Research debrief of Level 1, "The Price of Speed": tuning the cost is a multi-objective problem."""

from .base import PaperRef, ResearchInfo

RESEARCH = ResearchInfo(
    level_id="price_of_speed",
    question=("How do the MPC weights trade off competing goals, and why is tuning them an "
              "optimisation problem of its own?"),
    takeaway=("The weights decide the behaviour. No setting is best at everything; there are only "
              "better and worse trade-offs between speed and effort."),
    problem=(r"The stage cost $\ell = q_p\|p - p_\star\|^2 + q_v\|v\|^2 + r\|u\|^2$ mixes goals that "
             r"pull against each other: getting to the target quickly and using little actuation. "
             r"Only the ratios of the weights matter, but how the closed loop behaves for given "
             r"weights is hard to predict. So engineers try settings in simulation and compare them "
             r"on external measures (here: time and effort), not on the cost value, which changes "
             r"with the weights themselves."),
    relevance=("In vehicles the same trade-off is speed or tracking against comfort and fuel or "
               "battery use. Tuning many weights by hand is slow, so recent work treats the "
               "closed-loop simulation as a black box and searches the weights automatically for good "
               "trade-offs."),
    shown=(r"Each run tested one weight setting. Aggressive weights accelerate and brake at full "
           r"power and empty the battery; very gentle ones creep towards the target and run out of "
           r"time. Settings in between reach the star, some faster, some with less effort."),
    limits=(r"The “energy” is the effort measure $\sum \Delta t\,\|u\|^2$, not physical energy in "
            r"joules, and the battery is a game rule that stops the run, not a constraint in the OCP. "
            r"Your runs compare the settings you tried; they do not reveal the best possible "
            r"trade-offs (the true Pareto front)."),
    papers=(
        PaperRef(
            key="1A",
            title="What Is the Best Way to Optimally Parameterize the MPC Cost Function for Vehicle Guidance?",
            authors="D. Stenger, R. Ritschel, F. Krabbes, R. Voßwinkel, H. Richter",
            year=2023,
            venue="Mathematics 11(2), 465",
            url="https://doi.org/10.3390/math11020465",
            doi="10.3390/math11020465",
            problem=("Tuning the MPC of an automated vehicle for comfort and for lateral and "
                     "longitudinal tracking: many weights, conflicting requirements, expensive "
                     "simulations, and some settings whose simulation cannot even be completed."),
            approach=("Treat tuning as a multi-objective optimisation and compare sample-efficient "
                      "search methods (particle swarm, the genetic algorithm NSGA-II, Bayesian "
                      "optimisation), with a way to handle the failed simulations."),
            connection=("Every run you made evaluated one weight vector in a closed-loop simulation: "
                        "the same black-box setting, tuned by hand."),
            checked="Crossref (DOI, incl. abstract), 2026-11-19; the brief listed only 4 of the 5 authors",
        ),
        PaperRef(
            key="1B",
            title="An Automatic Tuning MPC with Application to Ecological Cruise Control",
            authors="M. Abtahi, M. Rabbani, S. Nazari",
            year=2023,
            venue="IFAC-PapersOnLine 56(3), 265–270",
            url="https://doi.org/10.1016/j.ifacol.2023.12.035",
            doi="10.1016/j.ifacol.2023.12.035",
            # no "Free version (arXiv)" link in the game (the user, 2026-11-19); the preprint
            # https://arxiv.org/abs/2309.09358 is still cited in docs/RESEARCH.md
            problem=("An ecological cruise control saves fuel using a preview of the road grade, but "
                     "how well it works depends strongly on the cost-function weights."),
            approach=("Solve the fuel-optimal problem offline with dynamic programming, find matching "
                      "MPC weights by inverse optimisation, and train a neural network that sets the "
                      "weights online."),
            connection=("As in this level, the weights decide how much actuation (there: fuel) the "
                        "closed loop uses; the paper automates what you did by hand."),
            checked="Crossref (DOI) and arXiv abstract, 2026-11-19",
        ),
    ),
)
