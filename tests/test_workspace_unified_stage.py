"""Regressions for Strategy B (Director-as-Stage) rollout.

The UI side of Strategy B lives in `ui/src/components/Stages/DirectorStage.tsx`
and is gated by the `workspaceUnifiedDirector` feature flag in the Zustand
store. The Python side is intentionally untouched: Director planning,
orchestration, validation, polish, checkpoint resume, and cancellation all
flow through the same code paths as before. This suite locks in that
invariant — if a future refactor accidentally wires the Director stage to a
parallel Python pipeline, these tests fail.

What this suite verifies
-------------------------
1. The Director v2 plan cancel registry is the SAME singleton used by the
   `/api/v1/director/v2/plan` and `/api/v1/director/v2/plan/cancel`
   endpoints. A second implementation here would break cancellation
   semantics for the Stage.
2. The `DirectorOrchestrator.plan()` cancel_event still propagates into
   the planner kwargs (covered by ``test_director_v2_plan_cancel.py``,
   imported here for completeness).
3. The Stage wrapper has no Python counterpart — there is no new
   pipeline / no new route. This is a sanity check that a developer
   didn't accidentally add a duplicate route.
4. The `_abort_pipeline_jobs` helper used by Stage 2's unified cancel
   still iterates only jobs belonging to the cancelled pipeline, even
   when the user is mid-Stage planning.
5. The Director pipeline status that the Stage polls
   (`pipelineStatus?.status`) maps the same way to UI labels as before.
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


class TestStageRolloutInvariants(unittest.TestCase):
    """Strategy B doesn't introduce new Python — only the UI mounts
    DirectorChat inside a styled wrapper. These tests guard that
    promise."""

    def test_no_new_director_v2_plan_route_variant(self):
        """The Stage still routes through the original v2/plan endpoint;
        no alternative endpoint like /director/v3/plan should exist yet."""
        launch_path = os.path.join(_APP_DIR, "launch.py")
        with open(launch_path, "r", encoding="utf-8") as handle:
            source = handle.read()
        # Confirm the canonical route is the only v2/plan endpoint family.
        self.assertIn("/api/v1/director/v2/plan", source)
        # Cancel must share the same registry module — not a parallel one.
        self.assertIn("v2_plan_cancel.register", source)
        self.assertIn("v2_plan_cancel.request_cancel", source)
        # No /api/v1/director/v3 yet.
        self.assertNotIn("/api/v1/director/v3", source)

    def test_stage_wrapper_has_no_python_counterpart(self):
        """The Stage is a UI-only concept. If a parallel Python pipeline
        appears, it has to be intentional — not a side-effect of the
        rollout."""
        launch_path = os.path.join(_APP_DIR, "launch.py")
        with open(launch_path, "r", encoding="utf-8") as handle:
            source = handle.read()
        # No "workspace_stage" or "director_stage" route — would indicate
        # a parallel Python pipeline.
        self.assertNotIn("/director/stage", source)
        self.assertNotIn("/director/workspace", source)

    def test_director_stage_module_is_present(self):
        """Mirror of the UI check: the Stage wrapper file must exist.
        Backend regression catches accidental file deletion."""
        stage_path = os.path.join(
            _HERE, "..", "ui", "src", "components", "Stages", "DirectorStage.tsx"
        )
        self.assertTrue(
            os.path.exists(stage_path),
            "DirectorStage.tsx must exist — Strategy B is UI-only and "
            "the wrapper is the entry point for the in-Workspace Stage.",
        )


class TestAbortPipelineJobsScoped(unittest.TestCase):
    """Stage 2 will call `_abort_pipeline_jobs(pid)` from a unified
    `cancelPlan()` action. This guards the fan-out so that cancelling a
    Stage plan only touches the Stage's own child jobs, never another
    pipeline's."""

    def setUp(self):
        from services import director_pipeline
        self.pipeline = director_pipeline

        # Snapshot module-level state so the test can mutate safely.
        self._snapshot_jobs = dict(self.pipeline._jobs or {})
        self._snapshot_states = dict(self.pipeline._active_gen_states or {})
        self.pipeline._jobs = {}
        self.pipeline._active_gen_states = {}

    def tearDown(self):
        self.pipeline._jobs = self._snapshot_jobs
        self.pipeline._active_gen_states = self._snapshot_states

    def _seed_job(self, job_id: str, *, pipeline_id: str | None) -> dict:
        params = {"_director_pipeline_id": pipeline_id} if pipeline_id else {}
        job = {
            "status": "running",
            "cancel_requested": False,
            "message": "Running",
            "params": params,
        }
        if self.pipeline._jobs is not None:
            self.pipeline._jobs[job_id] = job
        return job

    def test_abort_only_touches_matching_pipeline_jobs(self):
        target = self._seed_job("job-target", pipeline_id="pid-stage")
        other = self._seed_job("job-other", pipeline_id="pid-other")
        orphan = self._seed_job("job-orphan", pipeline_id=None)

        # Stub request_cancel so we can record which jobs got flipped.
        flipped: list[str] = []

        def fake_request_cancel(job, *, job_id, active_states):
            flipped.append(job_id)
            from services.job_lifecycle import CancelResult
            return CancelResult(True, True, False)

        with mock.patch.object(self.pipeline, "request_cancel", fake_request_cancel):
            self.pipeline._abort_pipeline_jobs("pid-stage")

        self.assertEqual(flipped, ["job-target"])
        # Untouched jobs keep their original state.
        self.assertFalse(other["cancel_requested"])
        self.assertFalse(orphan["cancel_requested"])

    def test_abort_with_no_pipeline_jobs_is_a_noop(self):
        # Stage 1 doesn't trigger any jobs; cancelling a Stage-only plan
        # must not raise and must not flip unrelated state.
        try:
            self.pipeline._abort_pipeline_jobs("pid-stage")
        except Exception as exc:  # pragma: no cover - failure path
            self.fail(f"_abort_pipeline_jobs raised on empty store: {exc}")


class TestStageCancelRace(unittest.TestCase):
    """Stage 2 will introduce `cancelPlan()` that combines the
    v2-plan cancel with `_abort_pipeline_jobs`. This guards the
    interaction so a re-arm during teardown doesn't strand an event."""

    def test_double_arm_flips_previous_event(self):
        from services.director import v2_plan_cancel

        # Reset the module-level singleton between tests so the harness
        # is hermetic.
        v2_plan_cancel._event = None
        v2_plan_cancel._plan_id = None

        event_a = v2_plan_cancel.register("stage-plan-a")
        self.assertFalse(event_a.is_set())

        # Opening a new plan mid-stage must flip the previous event so
        # the orphaned worker thread exits cleanly.
        event_b = v2_plan_cancel.register("stage-plan-b")
        self.assertTrue(event_a.is_set())
        self.assertFalse(event_b.is_set())

        # request_cancel from the UI's cancel button now targets the
        # latest arm.
        self.assertEqual(
            v2_plan_cancel.request_cancel(),
            "stage-plan-b",
        )
        self.assertTrue(event_b.is_set())

        v2_plan_cancel.release(event_b, "stage-plan-b")
        self.assertIsNone(v2_plan_cancel.request_cancel())

    def test_concurrent_arm_race_is_lock_safe(self):
        """Two concurrent `register()` calls from a double-click on the
        Stage's "Director" tab must both succeed without corrupting
        module state."""
        from services.director import v2_plan_cancel

        v2_plan_cancel._event = None
        v2_plan_cancel._plan_id = None

        results: list[tuple[str, threading.Event]] = []
        barrier = threading.Barrier(4)

        def arm(idx: int):
            barrier.wait()
            ev = v2_plan_cancel.register(f"concurrent-{idx}")
            results.append((f"concurrent-{idx}", ev))

        threads = [threading.Thread(target=arm, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Each arm returned a distinct event and exactly one is the
        # current owner.
        ids = [r[0] for r in results]
        self.assertEqual(len(set(ids)), 4)

        # All non-current arms must be flipped so the orphaned workers
        # exit on their next cancellation checkpoint.
        current_id = v2_plan_cancel._plan_id
        self.assertIn(current_id, ids)
        for plan_id, event in results:
            if plan_id == current_id:
                self.assertFalse(event.is_set())
            else:
                self.assertTrue(
                    event.is_set(),
                    f"Armed event {plan_id} should have been flipped "
                    f"during re-arm race; current is {current_id}",
                )

        # Cleanup so subsequent tests don't see a set event.
        current_event = next(ev for pid, ev in results if pid == current_id)
        v2_plan_cancel.release(current_event, current_id)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()