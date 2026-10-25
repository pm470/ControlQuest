"""Talks to the MPC engine (Python + acados in Docker) over HTTP on localhost.

Uses Qt's asynchronous network manager, so the UI never freezes while waiting.
Endpoints (see engine_server/server.py):
    GET  /health -> {"status": "ok", "version": ..., "acados": bool, "levels": [...]}
    POST /run    -> RunResult JSON

    ticket = ctx.engine.request_run(RunRequest(...), parent=self)
    ticket.finished.connect(self.on_result)    # RunResult
    ticket.failed.connect(self.on_error)       # str
The ticket belongs to `parent`: if the parent widget is closed before the
engine answers, the answer is simply dropped.
"""

from __future__ import annotations

import json

from PySide6.QtCore import QByteArray, QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from shiboken6 import isValid

from ..core.config import ENGINE_POLL_INTERVAL_MS, ENGINE_RUN_TIMEOUT_MS, ENGINE_TIMEOUT_MS
from .protocol import EngineStatus, RunRequest, RunResult


class RunTicket(QObject):
    """One pending run. Emits exactly one of finished(RunResult) / failed(str)."""

    finished = Signal(object)
    failed = Signal(str)


class EngineClient(QObject):
    status_changed = Signal(object)  # EngineStatus

    def __init__(self, base_url: str, parent: QObject | None = None):
        super().__init__(parent)
        self._base_url = base_url.rstrip("/")
        self._nam = QNetworkAccessManager(self)
        self._health_reply: QNetworkReply | None = None
        self._announce = False
        self._status = EngineStatus("checking", "Looking for the MPC engine...")
        self._poll = QTimer(self)
        self._poll.setInterval(ENGINE_POLL_INTERVAL_MS)
        self._poll.timeout.connect(self.check_health)

    # --- status ------------------------------------------------------------------
    @property
    def status(self) -> EngineStatus:
        return self._status

    @property
    def base_url(self) -> str:
        return self._base_url

    def set_base_url(self, url: str) -> None:
        self._base_url = url.rstrip("/")
        self._set_status(EngineStatus("checking", "Looking for the MPC engine..."))
        self.check_health()

    def start_polling(self) -> None:
        self.check_health()
        self._poll.start()

    def stop_polling(self) -> None:
        self._poll.stop()

    def check_health(self, announce: bool = False) -> None:
        """Ask GET /health. announce=True emits status_changed even if nothing changed."""
        self._announce = self._announce or announce
        if self._health_reply is not None:  # previous check still running
            return
        request = QNetworkRequest(QUrl(f"{self._base_url}/health"))
        request.setTransferTimeout(ENGINE_TIMEOUT_MS)
        reply = self._nam.get(request)
        self._health_reply = reply
        reply.finished.connect(lambda: self._on_health(reply))

    def _on_health(self, reply: QNetworkReply) -> None:
        self._health_reply = None
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                self._set_status(EngineStatus("offline", "MPC engine offline",
                                              {"error": reply.errorString()}))
                return
            try:
                payload = json.loads(bytes(reply.readAll()).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                self._set_status(EngineStatus("warning", "MPC engine sent an invalid answer"))
                return
            self._set_status(EngineStatus.from_health(payload))
        finally:
            reply.deleteLater()

    def _set_status(self, status: EngineStatus) -> None:
        changed = (status.state, status.message) != (self._status.state, self._status.message)
        self._status = status
        if changed or (self._announce and status.state != "checking"):
            self.status_changed.emit(status)
        if status.state != "checking":
            self._announce = False

    # --- runs ---------------------------------------------------------------------------
    def request_run(self, run: RunRequest, parent: QObject | None = None) -> RunTicket:
        """Ask the engine to simulate one run; the answer arrives on the returned ticket."""
        ticket = RunTicket(parent if parent is not None else self)
        request = QNetworkRequest(QUrl(f"{self._base_url}/run"))
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        request.setTransferTimeout(ENGINE_RUN_TIMEOUT_MS)
        body = QByteArray(json.dumps(run.to_json()).encode("utf-8"))
        reply = self._nam.post(request, body)
        reply.finished.connect(lambda: self._on_run(reply, ticket))
        return ticket

    def _on_run(self, reply: QNetworkReply, ticket: RunTicket) -> None:
        try:
            if not isValid(ticket):  # the screen that asked is gone
                return
            raw = bytes(reply.readAll()).decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw) if raw else {}
            except ValueError:
                payload = {}
            if reply.error() != QNetworkReply.NetworkError.NoError:
                reason = payload.get("error") if isinstance(payload, dict) else None
                if not reason:
                    reason = ("The MPC engine is not reachable. Start it with "
                              "engine_server/start_engine (see game/README.md)."
                              if reply.error() == QNetworkReply.NetworkError.ConnectionRefusedError
                              else reply.errorString())
                ticket.failed.emit(str(reason))
                return
            try:
                ticket.finished.emit(RunResult.from_json(payload))
            except (KeyError, TypeError, ValueError) as exc:
                ticket.failed.emit(f"Invalid run result from the engine: {exc}")
        finally:
            reply.deleteLater()
