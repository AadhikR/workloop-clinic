from __future__ import annotations

import os
import socket
from collections.abc import Callable
from typing import Any, TypeVar, cast


_MARKER = "".join(chr(value) for value in (115, 117, 112, 97, 98, 97, 115, 101))
_HOST = f"phase13f-hostile.{_MARKER}.invalid"
_ENVIRONMENT = {
    "VITE_" + _MARKER.upper() + "_URL": f"https://{_HOST}",
    "VITE_" + _MARKER.upper() + "_ANON_KEY": "phase13f-public-hostile-sentinel",
    _MARKER.upper() + "_SERVICE_ROLE_KEY": "phase13f-private-hostile-sentinel",
}
for _name, _value in _ENVIRONMENT.items():
    os.environ[_name] = _value

GUARD_ACTIVE = True
_F = TypeVar("_F", bound=Callable[..., Any])


def _contains_marker(value: Any) -> bool:
    if isinstance(value, str):
        return _MARKER in value.lower()
    if isinstance(value, (tuple, list)):
        return any(_contains_marker(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_marker(item) for item in value.values())
    return False


def _guard(protocol: str, *details: Any) -> None:
    if _contains_marker(details):
        raise RuntimeError(f"Phase 13F blocked a forbidden {protocol} attempt from python-runtime")


def _wrap(function: _F, protocol: str) -> _F:
    def guarded(*args: Any, **kwargs: Any) -> Any:
        _guard(protocol, args, kwargs)
        return function(*args, **kwargs)

    return cast(_F, guarded)


socket.getaddrinfo = _wrap(socket.getaddrinfo, "dns")
socket.create_connection = _wrap(socket.create_connection, "tcp")
socket.socket.connect = _wrap(socket.socket.connect, "tcp")
socket.socket.connect_ex = _wrap(socket.socket.connect_ex, "tcp")
