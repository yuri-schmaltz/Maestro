"""Director v2 plan cancellation registry.

The Director v2 chat (the "Writing scenes..." spinner in the sidebar)
runs an LLM generation that can take tens of seconds. The client wants
to abort the wait immediately, and the server-side worker thread should
short-circuit between token reads instead of consuming GPU for an
orphan completion.

This module keeps a single ``threading.Event`` slot for the most
recently-armed plan. The HTTP handler calls ``register`` when a plan
request lands and ``release`` when it returns; the cancel endpoint calls
``request_cancel`` to flip the flag from a separate request thread.

Only one plan runs at a time in practice — the UI's "Plan Shots" button
is single-shot and the worker thread blocks the HTTP handler until the
LLM stream finishes — so a singleton slot is enough. A double-click on
"Plan Shots" re-arms the slot: the orphaned worker's event is flipped
so its next cancellation checkpoint raises and the request unwinds.
"""

from __future__ import annotations

import threading
from typing import Optional


_lock = threading.Lock()
_event: Optional[threading.Event] = None
_plan_id: Optional[str] = None


def register(plan_id: str) -> threading.Event:
    """Arm a fresh cancel event for ``plan_id`` and return it.

    If a previous plan's event is still armed, it is flipped first so
    the orphaned worker thread exits on its next cancellation check
    rather than leaking into a third generation.
    """
    global _event, _plan_id
    event = threading.Event()
    with _lock:
        if _event is not None:
            _event.set()
        _event = event
        _plan_id = plan_id
    return event


def release(event: threading.Event, plan_id: str) -> None:
    """Clear the slot once planning finishes, raises, or is cancelled.

    Only clears the slot when it still owns the caller's event — a
    double-arm race could have already replaced it, in which case we
    leave the new owner's state alone.
    """
    global _event, _plan_id
    with _lock:
        if _event is event and _plan_id == plan_id:
            _event = None
            _plan_id = None


def request_cancel() -> Optional[str]:
    """Flip the armed event (if any) and return the plan_id that was cancelled.

    Returns ``None`` if no plan is currently running, so the HTTP handler
    can answer ``{"cancelled": False}`` without raising.
    """
    with _lock:
        event = _event
        plan_id = _plan_id
    if event is None:
        return None
    event.set()
    return plan_id