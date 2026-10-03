"""Signal / event system.

A lightweight, thread-agnostic implementation of Godot-style signals.  A
:class:`Signal` can be ``connect`` ed to any callable; when ``emit`` is called
the registered callables are invoked with the supplied arguments.  Signals are
the primary decoupling mechanism between nodes (a node never needs a hard
reference to another node to react to its events).
"""
from __future__ import annotations

from typing import Any, Callable, List, Tuple


class SignalError(Exception):
    pass


class SignalConnection:
    """A single connection between a signal and a callable."""

    __slots__ = ("callable", "flags")

    def __init__(self, cb: Callable, flags: int = 0):
        self.callable = cb
        self.flags = flags

    def __eq__(self, o):
        return isinstance(o, SignalConnection) and o.callable is self.callable

    def __hash__(self):
        return id(self.callable)


class Signal:
    """Observable event emitter."""

    # connection flags
    CONNECT_PERSIST = 0
    CONNECT_ONESHOT = 1

    def __init__(self, name: str = ""):
        self.name = name
        self._connections: List[Tuple[SignalConnection, Any]] = []

    # ------------------------------------------------------------------
    def connect(self, callable_: Callable, flags: int = CONNECT_PERSIST) -> None:
        conn = SignalConnection(callable_, flags)
        for c, _ in self._connections:
            if c == conn:
                # already connected -> re-register flags
                c.flags = flags
                return
        self._connections.append((conn, None))

    def disconnect(self, callable_: Callable) -> None:
        self._connections = [c for c in self._connections
                             if c[0].callable is not callable_]

    def is_connected(self, callable_: Callable) -> bool:
        return any(c[0].callable is callable_ for c in self._connections)

    def emit(self, *args: Any) -> None:
        to_remove = []
        for conn, _ in self._connections:
            try:
                conn.callable(*args)
            except Exception as exc:  # keep other listeners alive
                import traceback
                traceback.print_exc()
                print(f"[Signal:{self.name}] listener raised: {exc}")
            if conn.flags & Signal.CONNECT_ONESHOT:
                to_remove.append(conn.callable)
        for cb in to_remove:
            self.disconnect(cb)

    def clear(self) -> None:
        self._connections.clear()

    def __len__(self) -> int:
        return len(self._connections)


class SignalEmitter:
    """Mixin that gives a class a dictionary of named :class:`Signal` objects."""

    def __init__(self, *signal_names: str):
        self.signals: dict = {}
        for n in signal_names:
            self.signals[n] = Signal(n)

    def add_signal(self, name: str) -> Signal:
        if name not in self.signals:
            self.signals[name] = Signal(name)
        return self.signals[name]

    def get_signal(self, name: str) -> Signal:
        if name not in self.signals:
            raise SignalError(f"no signal named '{name}'")
        return self.signals[name]

    def connect(self, name: str, cb: Callable) -> None:
        self.get_signal(name).connect(cb)

    def disconnect(self, name: str, cb: Callable) -> None:
        self.get_signal(name).disconnect(cb)

    def emit(self, name: str, *args: Any) -> None:
        if name in self.signals:
            self.signals[name].emit(*args)
