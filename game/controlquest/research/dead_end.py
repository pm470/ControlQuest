"""Research debrief of Level 3, "Dead End": nonconvex constraints and local solvers."""

from .base import PaperRef, ResearchInfo

RESEARCH = ResearchInfo(
    level_id="dead_end",
    question=("Why can a local optimiser miss a route that exists, and is looking further ahead "
              "enough to escape a trap?"),
    takeaway=("MPC with a local solver is a local planner. On this map more foresight did not get "
              "it out of the trap; a better reference did."),
    problem=("With obstacles the OCP is nonconvex: there are separate families of plans (around the "
             "wall on one side or the other, or into the dead end), each with its own local "
             "solutions. SQP improves its starting guess, the previous plan, step by step and stays "
             "near it. If that guess leads into a dead end, the controller can stop in front of the "
             "wall even though a way around exists."),
    relevance=("Mobile robots, legged robots and cars meet concave obstacles all the time: rooms, "
               "parked cars, U-shaped spaces. Practical systems combine a local MPC with a global "
               "layer that supplies waypoints, safe corridors or better starting guesses."),
    shown=(r"The default and every longer horizon we measured ($N$ = 30, 60, 100 and 150) stop at "
           r"the same point, 0.2 m in front of the back wall; a longer horizon only makes each solve "
           r"slower. One waypoint above the U changes the reference, and the same local MPC then "
           r"finds its way."),
    limits=("That every horizon got stuck is what happened on this map, not a proof that a longer "
            "horizon can never help. Waypoints change the reference, not the solver's starting "
            "guess, and here you place them, not a global planner."),
    papers=(
        PaperRef(
            key="3A",
            title=("Global-Initialization-Based Model Predictive Control for Mobile Robots Navigating "
                   "Nonconvex Obstacle Environments"),
            authors="S.-M. Lee",
            year=2025,
            venue="Actuators 14(9), 454",
            url="https://doi.org/10.3390/act14090454",
            doi="10.3390/act14090454",
            problem=("A conventional optimisation-based MPC for a mobile robot can get stuck in a "
                     "local minimum among nonconvex obstacles."),
            approach=("Generate the optimiser's starting guess with a particle-swarm global search, "
                      "used only when needed; compared with a conventional IPOPT-based MPC in "
                      "ROS/Gazebo simulations."),
            connection=("The same trap as in this level. The paper changes the solver's starting "
                        "point; the game changes the reference."),
            checked="Crossref (DOI, incl. abstract), 2026-11-19",
        ),
        PaperRef(
            key="3B",
            title=("A Sequential MPC Approach to Reactive Planning for Bipedal Robots Using Safe "
                   "Corridors in Highly Cluttered Environments"),
            authors="K. S. Narkhede, A. M. Kulkarni, D. A. Thanki, I. Poulakakis",
            year=2022,
            venue="IEEE Robotics and Automation Letters 7(4), 11831–11838",
            url="https://doi.org/10.1109/LRA.2022.3204367",
            doi="10.1109/LRA.2022.3204367",
            free_url="https://arxiv.org/abs/2205.00156",
            problem="Reactive planning for a bipedal robot among many static and moving obstacles.",
            approach=("Split the free space into a corridor of overlapping obstacle-free polytopes "
                      "with waypoints, and drive the robot through it with a sequence of MPC "
                      "problems; tested in high-fidelity simulation with the robot Digit."),
            connection="Intermediate goals for a local MPC: what your waypoints do, found automatically.",
            checked=("Crossref (DOI) and the abstract (Semantic Scholar), 2026-11-19; the arXiv "
                     "preprint has a shorter title"),
        ),
    ),
)
