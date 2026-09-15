"""Path safety and traversal validation utilities for Cue Studio / Maestro."""

import os
from pathlib import Path
from typing import Sequence, Optional


def is_safe_subpath(path: str | Path, base: str | Path) -> bool:
    """Return True if `path` resolves to a path strictly inside (or equal to) `base`."""
    try:
        base_real = Path(base).resolve()
        target_real = Path(path).resolve()
        
        # No Windows, paths em unidades de disco diferentes causam erro no is_relative_to
        if os.name == "nt":
            if base_real.drive.lower() != target_real.drive.lower():
                return False
                
        return target_real == base_real or base_real in target_real.parents
    except (ValueError, OSError):
        return False


def resolve_safe_path(
    user_path: str | Path,
    allowed_roots: Sequence[str | Path],
    must_exist: bool = False,
) -> Optional[Path]:
    """Resolve `user_path` and ensure it is enclosed within at least one of `allowed_roots`.
    
    Returns the resolved Path if safe, or None if it escapes all allowed roots or does not exist (if must_exist=True).
    """
    if not user_path:
        return None
        
    try:
        target = Path(user_path).resolve()
        if must_exist and not target.exists():
            return None
            
        for root in allowed_roots:
            if not root:
                continue
            if is_safe_subpath(target, root):
                return target
                
        return None
    except (ValueError, OSError):
        return None


def require_safe_path(
    user_path: str | Path,
    allowed_roots: Sequence[str | Path],
    description: str = "Path",
    must_exist: bool = False,
) -> Path:
    """Resolve `user_path` or raise ValueError with a clear security message."""
    safe = resolve_safe_path(user_path, allowed_roots, must_exist=must_exist)
    if safe is None:
        raise ValueError(
            f"Security Error: {description} '{user_path}' is outside allowed workspace/storage directories."
        )
    return safe
