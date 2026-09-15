"""Tests for hardware resource management, CUDA cleanup, and dynamic disk safety."""

import unittest
from pathlib import Path
from app.shared.utils.gpu_cleanup import (
    force_cuda_cleanup,
    estimate_required_disk_gb,
    check_disk_space,
)


class TestHardwareAndResourceSafety(unittest.TestCase):
    def test_force_cuda_cleanup_safe_execution(self):
        # Execução segura em qualquer ambiente (com ou sem GPU)
        metrics = force_cuda_cleanup()
        self.assertIsInstance(metrics, dict)
        self.assertIn("cuda_available", metrics)
        self.assertIn("freed_mb", metrics)

    def test_estimate_required_disk_gb_scales_with_clips(self):
        # 1 clipe em 720p
        small = estimate_required_disk_gb(1, resolution_preset="720p")
        # 10 clipes em 720p
        medium = estimate_required_disk_gb(10, resolution_preset="720p")
        # 10 clipes em 1080p
        large = estimate_required_disk_gb(10, resolution_preset="1080p")

        self.assertGreater(medium, small)
        self.assertGreater(large, medium)
        self.assertGreaterEqual(small, 5.0)  # Garante buffer mínimo de 5GB

    def test_check_disk_space_current_directory(self):
        # Checa se o diretório atual tem pelo menos 1GB livre
        has_space, free_gb, needed_gb = check_disk_space(Path("."), 1.0)
        self.assertIsInstance(has_space, bool)
        self.assertGreater(free_gb, 0.0)
        self.assertEqual(needed_gb, 1.0)

    def test_check_disk_space_fails_when_unreasonable_space_demanded(self):
        # Requisitar 999999 GB deve acusar falta de espaço
        has_space, free_gb, needed_gb = check_disk_space(Path("."), 999999.0)
        self.assertFalse(has_space)
        self.assertLess(free_gb, needed_gb)


if __name__ == "__main__":
    unittest.main()
