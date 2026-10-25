"""Messages exchanged with the MPC engine (PRD 9.4), as plain dataclasses.

This file is the contract between the UI and the engine in Docker; keep it in
sync with engine_server/server.py and engine_server/level_rules/. Everything
is JSON-serialisable and uses plain lists (the UI does not need NumPy).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

PROTOCOL_VERSION = 1
ENGINE_VERSION = "0.3.0"  # the engine_server version this game expects (engine_server/server.py)

# outcome name -> (label for the player, ui.theme colour name)
OUTCOMES = {
    "success": ("Target reached!", "SUCCESS"),
    "battery_empty": ("Battery empty", "DANGER"),
    "time_out": ("Time out", "NEUTRAL"),
    "controller_failure": ("Controller failure", "WARNING"),
    "crash_wall": ("Crash", "DANGER"),
    "crash_block": ("Crash", "DANGER"),
}


@dataclass
class EngineStatus:
    """Result of GET /health, as seen by the UI."""

    state: str  # "checking" | "online" | "outdated" | "warning" | "offline"
    message: str  # short text for the UI
    details: dict[str, Any] = field(default_factory=dict)  # raw server answer

    @property
    def online(self) -> bool:
        return self.state in ("online", "outdated", "warning")

    @property
    def can_run(self) -> bool:
        """True if the engine can actually compute levels (acados present)."""
        return self.state in ("online", "outdated")

    @classmethod
    def from_health(cls, payload: dict[str, Any]) -> EngineStatus:
        if payload.get("status") != "ok":
            return cls("warning", "MPC engine answered, but not OK", payload)
        if not payload.get("acados", False):
            return cls("warning", "MPC engine online (acados missing)", payload)
        if payload.get("version") != ENGINE_VERSION:
            return cls("outdated", f"MPC engine outdated (v{payload.get('version')}, game expects "
                                   f"v{ENGINE_VERSION}): restart it", payload)
        return cls("online", "MPC engine online", payload)


@dataclass
class RunRequest:
    """POST /run: everything the engine needs to simulate one level run."""

    level_id: str
    knobs: dict[str, Any]  # knob name -> value, e.g. {"q_p": 10, "q_v": 1, "r": 0.1}
    waypoints: list[tuple[float, float]] = field(default_factory=list)
    protocol: int = PROTOCOL_VERSION

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        if not data["waypoints"]:  # levels without waypoints don't expect the key
            data.pop("waypoints")
        data.pop("protocol")
        return data


@dataclass
class Trajectory:
    """Replay data: n applied inputs, n+1 states, one plan per MPC solve
    (n solves, or n+1 if the last solve failed). Per-solve lists have the length of plans."""

    dt: float
    t: list[float]  # n+1
    x: list[list[float]]  # n+1 states [px, py, vx, vy]
    u: list[list[float]]  # n inputs [ax, ay]
    plans: list[list[list[float]]]  # one per solve, each (N+1) x 4; plan k computed at t[k]
    energy: list[float]  # n+1 cumulative sum dt*|u|^2
    solve_time_ms: list[float] = field(default_factory=list)  # per solve
    iterations: list[int] = field(default_factory=list)  # per solve (SQP iterations)
    costs: list[float | None] = field(default_factory=list)  # per solve: optimal OCP cost J*
    status: list[int] = field(default_factory=list)  # per solve: acados status (0 = ok)

    @property
    def n_solves(self) -> int:
        return len(self.plans)

    def solve_at(self, t: float) -> int:
        """Index of the MPC solve whose plan is active at replay time t."""
        return min(self.index_at(t)[0], max(0, self.n_solves - 1))

    def time_of_solve(self, k: int) -> float:
        """Replay time of solve k."""
        return k * self.dt

    @property
    def duration(self) -> float:
        return self.t[-1] if self.t else 0.0

    def index_at(self, t: float) -> tuple[int, float]:
        """Sample k with t_k <= t < t_{k+1}, and the fraction of the way to k+1."""
        n = len(self.t) - 1
        k = max(0, min(n, int(t / self.dt + 1e-9)))
        frac = 0.0 if k >= n else min(1.0, max(0.0, t / self.dt - k))
        return k, frac

    def interp(self, series: list[float], t: float) -> float:
        """Linear interpolation of a per-sample series (length n+1), e.g. energy."""
        k, frac = self.index_at(t)
        nxt = series[min(k + 1, len(series) - 1)]
        return series[k] + frac * (nxt - series[k])

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> Trajectory:
        return cls(dt=float(d["dt"]), t=list(d["t"]), x=list(d["x"]), u=list(d["u"]),
                   plans=list(d["plans"]), energy=list(d["energy"]),
                   solve_time_ms=list(d.get("solve_time_ms", [])),
                   iterations=list(d.get("iterations", [])),
                   costs=list(d.get("costs", [])), status=list(d.get("status", [])))


@dataclass
class RunResult:
    """Answer of POST /run (PRD 9.4)."""

    level_id: str
    outcome: str  # key of OUTCOMES
    stars: int
    metrics: dict[str, float]  # time, energy, distance_left, max_accel, max_speed, ...
    messages: list[str]  # "What happened" sentences
    knobs: dict[str, float]  # the values actually used (clamped to their range)
    trajectory: Trajectory

    @property
    def success(self) -> bool:
        return self.outcome == "success"

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> RunResult:
        return cls(
            level_id=str(payload["level_id"]),
            outcome=str(payload["outcome"]),
            stars=int(payload.get("stars", 0)),
            metrics=dict(payload.get("metrics", {})),
            messages=list(payload.get("messages", [])),
            knobs=dict(payload.get("knobs", {})),
            trajectory=Trajectory.from_json(payload["trajectory"]),
        )
