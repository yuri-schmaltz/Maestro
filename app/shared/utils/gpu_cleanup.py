"""Hardware resources, CUDA VRAM cleanup, and dynamic disk safety utilities."""

import gc
import os
import shutil
from typing import Optional

try:
    import torch
    _HAS_TORCH = True
except ImportError:
    torch = None
    _HAS_TORCH = False


def force_cuda_cleanup() -> dict:
    """Perform aggressive garbage collection and purge PyTorch CUDA cache.
    
    Safe to call even on machines without CUDA or without PyTorch installed.
    Returns memory metrics if available.
    """
    gc.collect()
    metrics = {"cuda_available": False, "freed_mb": 0.0}
    
    if _HAS_TORCH and torch.cuda.is_available():
        try:
            before = torch.cuda.memory_allocated()
            torch.cuda.empty_cache()
            if hasattr(torch.cuda, "ipc_collect"):
                torch.cuda.ipc_collect()
            after = torch.cuda.memory_allocated()
            metrics["cuda_available"] = True
            metrics["freed_mb"] = max(0.0, (before - after) / (1024 * 1024))
            metrics["vram_allocated_mb"] = after / (1024 * 1024)
            metrics["vram_reserved_mb"] = torch.cuda.memory_reserved() / (1024 * 1024)
        except Exception as exc:
            metrics["error"] = str(exc)
            
    return metrics


def estimate_required_disk_gb(
    clip_count: int,
    resolution_preset: str = "720p",
    has_audio: bool = True,
    fps: float = 24.0,
    average_clip_duration_s: float = 4.0,
) -> float:
    """Calculate realistic estimated disk space required for a Director run.
    
    Considers start-images, keyframes, uncompressed raw clip renders, audio slices,
    and final concatenated multi-track assembly plus a safety buffer.
    """
    clip_count = max(1, int(clip_count or 1))
    is_high_res = any(k in str(resolution_preset).lower() for k in ("1080", "1440", "4k", "2160"))
    
    # 720p: ~350 MB por clipe (start frame PNG + raw MP4 + slice WAV + intermediate joins)
    # 1080p+: ~850 MB por clipe
    base_clip_mb = 850.0 if is_high_res else 350.0
    
    # Duração ajusta o tamanho proporcionalmente (base é 4s)
    duration_factor = max(0.5, float(average_clip_duration_s) / 4.0)
    clip_footprint_mb = base_clip_mb * duration_factor
    
    # Total de dados brutos
    total_clips_mb = clip_count * clip_footprint_mb
    
    # Concatenação final (vídeo + áudio completo)
    final_join_mb = total_clips_mb * 0.4
    
    # Buffer de segurança para evitar corrupção por disco cheio (mínimo 5 GB)
    safety_buffer_gb = 5.0
    
    total_estimated_gb = ((total_clips_mb + final_join_mb) / 1024.0) + safety_buffer_gb
    return round(max(5.0, total_estimated_gb), 2)


def check_disk_space(
    target_dir: str,
    required_gb: float,
) -> tuple[bool, float, float]:
    """Check if target_dir has at least required_gb free space.
    
    Returns (has_space: bool, free_gb: float, required_gb: float).
    """
    try:
        real_path = os.path.realpath(target_dir)
        usage = shutil.disk_usage(real_path)
        free_gb = round(usage.free / (1024 ** 3), 2)
        return (free_gb >= required_gb, free_gb, required_gb)
    except Exception:
        # Em montagens exóticas onde disk_usage falhe, permite continuar
        return (True, 999.0, required_gb)
