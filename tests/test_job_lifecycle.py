"""Unit tests for background generation job lifecycle, cancellation, and queue safety."""

import unittest
import threading
import time
from app.services.job_lifecycle import (
    acquire_generation_slot,
    generation_slot,
    is_cancel_requested,
    release_held,
    request_cancel,
    snapshot_job,
    try_requeue,
    try_start,
    update_job,
    finish_job,
    register_abort_state,
    unregister_abort_state,
    collect_job_outputs,
    record_job_outputs,
)


class TestJobLifecycleAndBackgroundQueue(unittest.TestCase):
    def test_job_transitions_held_to_queued_to_running_to_completed(self):
        job = {"id": "job-1", "status": "held", "created_at": time.time()}

        # 1. Held -> Queued (release_held)
        self.assertTrue(release_held(job, message="Queued"))
        self.assertEqual(job["status"], "queued")
        self.assertEqual(job["message"], "Queued")

        # 2. Queued -> Running (try_start)
        self.assertTrue(try_start(job, started_at=time.time()))
        self.assertEqual(job["status"], "running")

        # 3. Running -> Completed (finish_job)
        self.assertTrue(finish_job(job, "completed", message="Done"))
        self.assertEqual(job["status"], "completed")
        self.assertEqual(job["message"], "Done")

    def test_cancellation_wins_over_late_start_and_completion(self):
        job = {"id": "job-2", "status": "running", "created_at": time.time()}
        active_states = {}
        worker_abort_state = {"abort": False}

        # Registrar estado de abort para o worker
        registered = register_abort_state(
            job, "job-2", active_states, worker_abort_state
        )
        self.assertTrue(registered)
        self.assertFalse(worker_abort_state["abort"])

        # Solicitar cancelamento
        cancel_res = request_cancel(
            job, job_id="job-2", active_states=active_states
        )
        self.assertTrue(cancel_res.changed)
        self.assertTrue(cancel_res.was_running)
        self.assertTrue(cancel_res.abort_signalled)
        self.assertTrue(worker_abort_state["abort"])
        self.assertEqual(job["status"], "cancelled")

        # Tentar finalizar como 'completed' depois de cancelado DEVE falhar
        finished = finish_job(job, "completed", message="Late success")
        self.assertFalse(finished)
        self.assertEqual(job["status"], "cancelled")
        self.assertEqual(job["message"], "Cancelled")

    def test_generation_slot_concurrency_and_cancellation(self):
        lock = threading.Lock()
        job = {"id": "job-3", "status": "queued"}

        # Adquirir slot com sucesso
        with generation_slot(lock, job, poll_interval=0.01) as acquired:
            self.assertTrue(acquired)
            self.assertTrue(lock.locked())

        self.assertFalse(lock.locked())

        # Se cancel_requested for True, não deve adquirir
        job["cancel_requested"] = True
        with generation_slot(lock, job, poll_interval=0.01) as acquired:
            self.assertFalse(acquired)

    def test_record_and_snapshot_job(self):
        job = {
            "id": "job-4",
            "status": "running",
            "output_files": ["shot_01.mp4"],
        }
        record_job_outputs(
            job, ["shot_02.mp4"], clip_output_files={0: "shot_01.mp4", 1: "shot_02.mp4"}
        )
        snap = snapshot_job(job)

        self.assertEqual(len(snap["output_files"]), 2)
        self.assertIn("shot_01.mp4", snap["output_files"])
        self.assertIn("shot_02.mp4", snap["output_files"])
        self.assertEqual(snap["clip_output_files"]["0"], "shot_01.mp4")
        self.assertEqual(snap["clip_output_files"]["1"], "shot_02.mp4")


if __name__ == "__main__":
    unittest.main()
