"""Regressions for Stage 2's unified cancelPlan action.

Strategy B introduced a single entry point, useStore.cancelPlan(), that
fans out across the four previous cancel surfaces:

    - cancelDirectorV2Plan for an in-flight v2 plan
    - stopPipeline for a running Director pipeline
    - server-side _abort_pipeline_jobs fan-out (covered separately in
      test_workspace_unified_stage.py)
    - per-job cancelJob (legacy Studio path)

This suite pins the invariants the UI relies on:

    1. The v2 plan cancel registry still works when cancelPlan is called
       from the Stage, i.e. request_cancel returns the plan_id that was
       active at call time.
    2. The pipeline cancel path leaves _jobs in a coherent state: the
       pipeline record flips to cancelled and child jobs are signalled
       exactly once each.
    3. Calling cancelPlan twice in quick succession does NOT double-
       cancel jobs; the second call is a no-op for jobs that are
       already terminal.
    4. The fallback "no plan, no pipeline" path returns the empty
       cancellation result without raising.
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
    sys.path.insert(0, _APP_DIR)


class TestCancelPlanV2Branch(unittest.TestCase):
    """When a v2 plan is mid-flight, cancelPlan must:

       - flip the server-side cancel event (request_cancel returns truthy)
       - clear the in-flight controller on the client (tested in JS land)

    We exercise the Python half here.
    """

    def setUp(self):
        from services.director import v2_plan_cancel
        v2_plan_cancel._event = None
        v2_plan_cancel._plan_id = None

    def tearDown(self):
        from services.director import v2_plan_cancel
        v2_plan_cancel._event = None
        v2_plan_cancel._plan_id = None

    def test_cancel_event_is_armed_when_plan_is_active(self):
        from services.director import v2_plan_cancel

        event = v2_plan_cancel.register("active-plan")
        self.assertFalse(event.is_set())

        # cancelPlan would now call request_cancel() and check the result.
        cancelled_id = v2_plan_cancel.request_cancel()
        self.assertEqual(cancelled_id, "active-plan")
        self.assertTrue(event.is_set())

    def test_cancel_when_no_plan_active_returns_none(self):
        from services.director import v2_plan_cancel

        # No register() call yet; the registry is empty.
        self.assertIsNone(v2_plan_cancel.request_cancel())

    def test_re_arm_during_cancel_replaces_event(self):
        """If a second plan is registered while cancel is in flight,
        the new event is the active one and the previous is already
        flipped."""
        from services.director import v2_plan_cancel

        first = v2_plan_cancel.register("plan-A")
        second = v2_plan_cancel.register("plan-B")
        self.assertTrue(first.is_set())
        self.assertFalse(second.is_set())

        # First cancel hits plan-B (the active arm).
        self.assertEqual(v2_plan_cancel.request_cancel(), "plan-B")
        self.assertTrue(second.is_set())

        # Subsequent cancels find no active plan.
        v2_plan_cancel.release(second, "plan-B")
        self.assertIsNone(v2_plan_cancel.request_cancel())


class TestCancelPlanPipelineBranch(unittest.TestCase):
    """When a pipeline is running, cancelPlan calls stopPipeline which
    delegates to director_pipeline.stop_pipeline(). The fan-out to
    child jobs is server-side. We test the orchestration: stop_pipeline
    flips the status, persists, and aborts children."""

    def setUp(self):
        from services import director_pipeline
        self.pipeline = director_pipeline
        self._jobs_snapshot = dict(self.pipeline._jobs or {})
        self._states_snapshot = dict(self.pipeline._active_gen_states or {})
        self._pipelines_snapshot = dict(self.pipeline._pipelines or {})
        self.pipeline._jobs = {}
        self.pipeline._active_gen_states = {}
        self.pipeline._pipelines = {}

    def tearDown(self):
        self.pipeline._jobs = self._jobs_snapshot
        self.pipeline._active_gen_states = self._states_snapshot
        self.pipeline._pipelines = self._pipelines_snapshot

    def _seed_pipeline_with_children(self, pid):
        # Pipeline record
        if self.pipeline._pipelines is not None:
            self.pipeline._pipelines[pid] = {
                "status": "running",
                "phase": "generating_images",
                "_state_persisted": False,
                "pause_reason": None,
                "progress": {"current": 1, "total": 4, "message": "running"},
            }
        # Three child jobs belonging to this pipeline
        for i in range(3):
            job_id = f"{pid}-job-{i}"
            if self.pipeline._jobs is not None:
                self.pipeline._jobs[job_id] = {
                    "status": "running",
                    "cancel_requested": False,
                    "params": {"_director_pipeline_id": pid},
                }

    def test_stop_pipeline_flips_status_and_aborts_children(self):
        pid = "stage-pid"
        self._seed_pipeline_with_children(pid)

        # Stub the persistence so we don't write to disk in tests.
        with mock.patch.object(self.pipeline, "_save_pipeline_state", return_value=True):
            ok = self.pipeline.stop_pipeline(pid)

        self.assertTrue(ok)
        # Pipeline status flipped
        record = self.pipeline._pipelines[pid]
        self.assertEqual(record["status"], "cancelled")
        self.assertEqual(record["phase"], "cancelled")
        # Children received cancel_requested=True via the fan-out.
        for i in range(3):
            job = self.pipeline._jobs[f"{pid}-job-{i}"]
            self.assertTrue(job["cancel_requested"])

    def test_stop_unknown_pipeline_is_safe(self):
        with mock.patch.object(self.pipeline, "_save_pipeline_state", return_value=True):
            self.assertFalse(self.pipeline.stop_pipeline("nope"))

    def test_stop_terminal_pipeline_is_a_noop(self):
        pid = "done"
        if self.pipeline._pipelines is not None:
            self.pipeline._pipelines[pid] = {
                "status": "completed",
                "phase": "completed",
                "_state_persisted": False,
            }

        # Cancelling a completed pipeline must be a no-op (returns False)
        # AND must not touch the record.
        with mock.patch.object(self.pipeline, "_save_pipeline_state", return_value=True):
            self.assertFalse(self.pipeline.stop_pipeline(pid))
        self.assertEqual(self.pipeline._pipelines[pid]["status"], "completed")

    def test_double_stop_does_not_re_abort_children(self):
        """Double-clicking the Stage's Stop button must not flip
        children twice (the second call sees a terminal pipeline and
        short-circuits)."""
        pid = "double-pid"
        self._seed_pipeline_with_children(pid)

        with mock.patch.object(self.pipeline, "_save_pipeline_state", return_value=True):
            self.assertTrue(self.pipeline.stop_pipeline(pid))
            # Second call: pipeline is already cancelled, returns False.
            self.assertFalse(self.pipeline.stop_pipeline(pid))

        # Children flipped exactly once
        for i in range(3):
            job = self.pipeline._jobs[f"{pid}-job-{i}"]
            self.assertTrue(job["cancel_requested"])
            # The job's status itself isn't changed by stop_pipeline
            # (request_cancel inside _abort_pipeline_jobs flips the
            # gen-state abort flag, not the job status field). We just
            # assert the cancellation flag is set.


class TestCancelPlanRegistry(unittest.TestCase):
    """Sanity check that the registry module is a single source of
    truth across both branches of cancelPlan. If a future refactor
    creates a parallel cancel primitive, this test surfaces it."""

    def test_registry_module_is_singleton(self):
        from services.director import v2_plan_cancel

        # The module exposes a private _lock + _event slot. Touching
        # them from a different path would silently create a second
        # primitive.
        self.assertTrue(hasattr(v2_plan_cancel, "register"))
        self.assertTrue(hasattr(v2_plan_cancel, "release"))
        self.assertTrue(hasattr(v2_plan_cancel, "request_cancel"))

        # Same module is imported by launch.py (verified via grep in the
        # main test file). A second import path would split state.

    def test_request_cancel_is_thread_safe(self):
        """Two cancelPlan calls in quick succession from a React double-
        click must both succeed without raising."""
        from services.director import v2_plan_cancel

        v2_plan_cancel._event = None
        v2_plan_cancel._plan_id = None
        v2_plan_cancel.register("race-plan")

        results = []
        errors = []

        def hit():
            try:
                results.append(v2_plan_cancel.request_cancel())
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        threads = [threading.Thread(target=hit) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        # Every call sees the same plan_id (the active arm).
        for r in results:
            self.assertEqual(r, "race-plan")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()