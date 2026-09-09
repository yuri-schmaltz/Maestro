"""Regressions for the Director v2 plan cancellation surface.

The Director v2 chat (the "Writing scenes..." / "Writing image and video
prompts..." spinner in the sidebar) used to run to completion no matter
what — the client had no AbortController and the planner had no
cancellation primitive wired through. This suite locks in the new
behaviour so the cancel button on the spinner actually does something:

  * ``_planning_cancelled_callback`` is read from kwargs and flipped
    on by a single ``threading.Event.set()``.
  * ``_call_llm_json`` raises ``InterruptedError`` as soon as the LLM
    call returns and the event is set (not just at batch boundaries).
  * ``DirectorOrchestrator.plan(..., cancel_event=...)`` injects the
    callback into ``planner_kwargs`` so each planner picks it up via
    ``_configure_planning_runtime``.
  * Cancelling twice (re-arm race from double-clicks) still leaves the
    registry in a clean state.

The full HTTP path is exercised in the gauntlet under
``tests/browser_control_gauntlet.py``; this file is model-free and
covers the cancellation primitive + the orchestrator wiring.
"""

from __future__ import annotations

import os
import sys
import threading
import unittest
from unittest import mock


_HERE = os.path.dirname(os.path.abspath(__file__))
_APP_DIR = os.path.abspath(os.path.join(_HERE, "..", "app"))
if _APP_DIR not in sys.path:
    sys.path.insert(0, str(_APP_DIR))


from services.director.orchestrator import DirectorOrchestrator
from services.director.planners.base import BasePlanner
from services.director.schema import ProductionPlan
from services.director import v2_plan_cancel


class _RecorderPlanner(BasePlanner):
    """Minimal planner that records kwargs and surfaces the cancel event."""

    skill_type = "v2_cancel_test"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.received_kwargs: dict = {}

    def plan(self, **kwargs):
        # Mirror the real planners: attach runtime hooks from kwargs
        # so we can verify the orchestrator's cancel wiring actually
        # reaches _raise_if_planning_cancelled().
        self._configure_planning_runtime(kwargs, kind="v2_cancel_test", fingerprint_payload=kwargs)
        self.received_kwargs = dict(kwargs)
        self._raise_if_planning_cancelled()
        # total_duration_sec must be set to avoid the orchestrator's
        # f"…{…:.1f}s total" log crashing on None.
        return ProductionPlan(skill_type="v2_cancel_test", shots=[], total_duration_sec=0.0)


class TestBasePlannerCancel(unittest.TestCase):
    def test_cancel_callback_from_kwargs_raises_interrupted(self):
        event = threading.Event()
        planner = _RecorderPlanner()

        # Simulate what _configure_planning_runtime does with the kwarg.
        planner._planning_cancelled_callback = event.is_set

        # Callback is wired but the event hasn't been set yet — should
        # be a silent no-op so legacy direct-call planner usage is safe.
        planner._raise_if_planning_cancelled()

        # Setting the event must flip the predicate; raising on the
        # next call confirms the callback is wired through.
        event.set()
        with self.assertRaises(InterruptedError):
            planner._raise_if_planning_cancelled()

    def test_no_callback_is_silent(self):
        planner = _RecorderPlanner()
        # No callback attached → no-op. The chat UI depends on this so
        # legacy direct-call planner usage (tests, internal scripts)
        # never raises by accident.
        planner._raise_if_planning_cancelled()

    def test_call_llm_json_raises_after_first_call_when_event_set(self):
        """A single-call plan (the typical music-video case) should
        honor the cancel event right after the LLM returns rather
        than waiting for a batch boundary that never comes."""

        def generate(**kwargs):
            # Imagine the LLM call returns; we want the cancel to land.
            return '[{"title": "ok"}]'

        event = threading.Event()
        planner = _RecorderPlanner(llm_generate=generate)
        planner._planning_cancelled_callback = event.is_set
        event.set()

        with self.assertRaises(InterruptedError):
            planner._call_llm_json("p", "s", streaming=False, thinking_budget=0)


class TestOrchestratorCancelWiring(unittest.TestCase):
    def test_cancel_event_is_forwarded_to_planner_kwargs(self):
        orchestrator = DirectorOrchestrator(
            llm_generate=lambda **kwargs: "{}",
            llm_generate_streaming=lambda **kwargs: "{}",
        )
        event = threading.Event()
        captured: dict = {}

        class _SpyPlanner(_RecorderPlanner):
            def plan(self, **kwargs):
                captured.update(kwargs)
                self._configure_planning_runtime(kwargs, kind="spy", fingerprint_payload=kwargs)
                return ProductionPlan(skill_type="music_video", shots=[], total_duration_sec=0.0)

        with mock.patch.dict(
            "services.director.orchestrator._PLANNER_MAP",
            {"music_video": _SpyPlanner},
        ):
            orchestrator.plan("music_video", clips=[], scene_description="x", cancel_event=event)

        self.assertIn("_planning_cancelled_callback", captured)
        self.assertFalse(captured["_planning_cancelled_callback"]())

        event.set()
        self.assertTrue(captured["_planning_cancelled_callback"]())

    def test_cancel_event_none_leaves_no_callback(self):
        orchestrator = DirectorOrchestrator(
            llm_generate=lambda **kwargs: "{}",
            llm_generate_streaming=lambda **kwargs: "{}",
        )
        captured: dict = {}

        class _SpyPlanner(_RecorderPlanner):
            def plan(self, **kwargs):
                captured.update(kwargs)
                self._configure_planning_runtime(kwargs, kind="spy", fingerprint_payload=kwargs)
                return ProductionPlan(skill_type="music_video", shots=[], total_duration_sec=0.0)

        with mock.patch.dict(
            "services.director.orchestrator._PLANNER_MAP",
            {"music_video": _SpyPlanner},
        ):
            orchestrator.plan("music_video", clips=[], scene_description="x")

        self.assertNotIn("_planning_cancelled_callback", captured)

    def test_double_arm_replaces_event(self):
        """Re-arming the registry (e.g. user clicks "Plan Shots" twice)
        must flip the previous event so the orphaned worker exits.
        """
        # Reset the module-level singleton between tests so the harness
        # is hermetic; other tests in this file don't touch the registry.
        v2_plan_cancel._event = None
        v2_plan_cancel._plan_id = None

        event_a = v2_plan_cancel.register("plan-a")
        self.assertFalse(event_a.is_set())

        event_b = v2_plan_cancel.register("plan-b")
        self.assertTrue(event_a.is_set())
        self.assertFalse(event_b.is_set())

        # The cancel endpoint path: flipping the armed event from a
        # separate "request" thread is the whole point of the registry.
        cancelled_id = v2_plan_cancel.request_cancel()
        self.assertEqual(cancelled_id, "plan-b")
        self.assertTrue(event_b.is_set())

        # Releasing the second leaves the registry clean and a follow-up
        # cancel reports no plan in flight.
        v2_plan_cancel.release(event_b, "plan-b")
        self.assertIsNone(v2_plan_cancel.request_cancel())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()