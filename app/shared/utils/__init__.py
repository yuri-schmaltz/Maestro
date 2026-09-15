def __getattr__(name: str):
    if name in ('FlowDPMSolverMultistepScheduler', 'get_sampling_sigmas', 'retrieve_timesteps'):
        from .fm_solvers import (FlowDPMSolverMultistepScheduler, get_sampling_sigmas, retrieve_timesteps)
        return locals()[name]
    if name == 'FlowUniPCMultistepScheduler':
        from .fm_solvers_unipc import FlowUniPCMultistepScheduler
        return FlowUniPCMultistepScheduler
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    'HuggingfaceTokenizer', 'get_sampling_sigmas', 'retrieve_timesteps',
    'FlowDPMSolverMultistepScheduler', 'FlowUniPCMultistepScheduler'
]

