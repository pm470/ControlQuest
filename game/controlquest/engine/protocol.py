"""Messages exchanged with the MPC engine (PRD 9.4), as plain dataclasses.

This file is the contract between the UI and the engine in Docker; keep it in
sync with engine_server/server.py. Everything is JSON-serialisable.

Status: only the health check is used so far. RunRequest / RunResult are
first drafts to fill in when the first level becomes playable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

PROTOCOL_VERSION = 1


@dataclass
class EngineStatus:
    """Result of GET /health, as seen by the UI."""

    state: str  # "checking" | "online" | "warning" | "offline"
    message: str  # short text for the UI
    details: dict[str, Any] = field(default_factory=dict)  # raw server answer

    @property
    def online(self) -> bool:
        return self.state in ("online", "warning")

    @classmethod
    def from_health(cls, payload: dict[str, Any]) -> EngineStatus:
        if payload.get("status") != "ok":
            return cls("warning", "MPC engine answered, but not OK", payload)
        if not payload.get("acados", False):
            return cls("warning", "MPC engine online (acados missing)", payload)
        return cls("online", "MPC engine online", payload)


@dataclass
class RunRequest:
    """POST /run: everything the engine needs to simulate one level run."""

    level_id: str
    knobs: dict[str, Any]  # knob name -> value, e.g. {"r": 0.5, "N": 30}
    waypoints: list[tuple[float, float]] = field(default_factory=list)
    protocol: int = PROTOCOL_VERSION

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RunResult:
    """Answer of POST /run (PRD 9.4). Steps/events are kept as raw dicts for now."""

    outcome: str  # "success" | "crash_block" | "crash_wall" | "controller_failure" | "time_out"
    stars: int = 0
    metrics: dict[str, float] = field(default_factory=dict)
    messages: list[str] = field(default_factory=list)  # "What happened" sentences
    steps: list[dict[str, Any]] = field(default_factory=list)  # t, x, u, plan, status, ...
    events: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> RunResult:
        return cls(
            outcome=str(payload["outcome"]),
            stars=int(payload.get("stars", 0)),
            metrics=dict(payload.get("metrics", {})),
            messages=list(payload.get("messages", [])),
            steps=list(payload.get("steps", [])),
            events=list(payload.get("events", [])),
        )
