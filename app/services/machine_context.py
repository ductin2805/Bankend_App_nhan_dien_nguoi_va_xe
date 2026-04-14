"""Machine-scoped request context helpers."""

from contextvars import ContextVar, Token


_current_machine_id: ContextVar[str] = ContextVar("current_machine_id", default="default")


def set_current_machine_id(machine_id: str) -> Token:
    return _current_machine_id.set((machine_id or "default").strip() or "default")


def reset_current_machine_id(token: Token) -> None:
    _current_machine_id.reset(token)


def get_current_machine_id() -> str:
    return _current_machine_id.get()