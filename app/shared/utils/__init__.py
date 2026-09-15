def __getattr__(name: str):
    if name in ('FlowDPMSolverMultistepScheduler', 'get_sampling_sigmas', 'retrieve_timesteps'):
        from .fm_solvers import (FlowDPMSolverMultistepScheduler, get_sampling_sigmas, retrieve_timesteps)
        return locals()[name]
    if name == 'FlowUniPCMultistepScheduler':
        from .fm_solvers_unipc import FlowUniPCMultistepScheduler
        return FlowUniPCMultistepScheduler
    if name in ('force_cuda_cleanup', 'estimate_required_disk_gb', 'check_disk_space'):
        from .gpu_cleanup import force_cuda_cleanup, estimate_required_disk_gb, check_disk_space
        return locals()[name]
    if name in ('is_safe_subpath', 'resolve_safe_path', 'require_safe_path'):
        from .path_safety import is_safe_subpath, resolve_safe_path, require_safe_path
        return locals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    'HuggingfaceTokenizer', 'get_sampling_sigmas', 'retrieve_timesteps',
    'FlowDPMSolverMultistepScheduler', 'FlowUniPCMultistepScheduler',
    'force_cuda_cleanup', 'estimate_required_disk_gb', 'check_disk_space',
    'is_safe_subpath', 'resolve_safe_path', 'require_safe_path'
]


