#!/usr/bin/env python3
"""Clean-repo boundary guard.

Fails CI if any tracked file looks like:

  1. A model checkpoint / weight blob outside the curated `app/ckpts/`
     allowlist (we explicitly track a small set of starter safetensors
     for offline first-launch; anything else is a leak).
  2. A leaked dataset (`.csv`, `.parquet`, `.arrow`, `.tsv`) or a
     large raw audio/image bundle (>20 MB) — these belong in external
     storage, not git.
  3. An accidental credential: bearer tokens, common API key formats
     (HuggingFace, CivitAI, OpenAI, Anthropic, GitHub), or PEM-encoded
     private keys embedded in tracked source.
  4. Maintainer-only artefacts that the public repo must never expose
     (release-readiness checklist, internal development notes).

The check is deliberately conservative — it operates on `git ls-files`
so `.gitignore` exclusions are respected, but it does NOT require a
network connection. It is the same script that runs in CI and locally
via `python scripts/verify_clean_repo.py`. Exit 0 = clean; exit 1 =
rejected (with a per-violation report on stderr).

Design notes:
  * Pure stdlib (no `requests`, no `tomllib`) so the script can run
    before any project dependency is installed.
  * Idempotent and side-effect-free — safe to wire into pre-commit.
  * All thresholds and patterns are constants at the top of the file
    so maintainers can adjust without re-reading the body.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent

# Directories where large weight files are explicitly expected and allowed.
# Keep narrow — anything that lands OUTSIDE this list is a leak.
CKPT_ALLOWLIST_DIRS = {
    "app/ckpts",
}

# File extensions that mark a file as a "weight / dataset blob" we
# never want in tracked source (CKPT_ALLOWLIST_DIRS excepted).
WEIGHT_EXTENSIONS = {
    ".safetensors",
    ".ckpt",
    ".pt",
    ".pth",
    ".bin",
    ".gguf",
    ".onnx",
    ".h5",
    ".hdf5",
    ".tflite",
    ".pb",
    ".npz",
    ".npy",
    ".parquet",
    ".arrow",
    ".feather",
    ".pkl",
    ".pickle",
}

# Plain-text data formats that have no business in tracked source.
DATASET_EXTENSIONS = {
    ".csv",
    ".tsv",
    ".jsonl",
    ".ndjson",
}

# Files above this many bytes are flagged when they're not a curated
# weight. 20 MB is well below the model files we deliberately ship
# (.safetensors is git-lfs territory; everything else is suspect).
LARGE_FILE_BYTES = 20 * 1024 * 1024

# Paths that are explicitly maintained as private and must never be
# committed. .gitignore covers these for new checkouts; this list
# catches anyone who `git add -f`'d them in.
PRIVATE_PATHS = {
    "docs/release_todo.md",
    "docs/development",
    "ENVIRONMENT",
    ".claude",
}

# Credential patterns. Each regex is applied to the file contents of
# every tracked text file. False positives are reported with their
# path so maintainers can decide whether to allowlist.
CREDENTIAL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("HuggingFace token",
     re.compile(r"\b(hf_[A-Za-z0-9]{20,})\b")),
    ("OpenAI API key",
     re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("Anthropic API key",
     re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    ("GitHub fine-grained PAT",
     re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("GitHub classic PAT",
     re.compile(r"\bghp_[A-Za-z0-9]{30,}\b")),
    ("CivitAI API key",
     re.compile(r"\bCIVITAI_API_KEY\s*=\s*['\"]?[A-Za-z0-9]{32,}['\"]?")),
    ("Generic bearer token",
     re.compile(r"(?i)Bearer\s+[A-Za-z0-9_\-]{40,}")),
    ("PEM private key header",
     re.compile(r"-----BEGIN (RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----")),
)

# Extensions eligible for credential scanning. Binary blobs (e.g.
# safetensors) are skipped even if they live inside the allowlist.
TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yml", ".yaml",
    ".toml", ".cfg", ".ini", ".md", ".txt", ".sh", ".html", ".css",
    ".xml", ".env", ".example",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tracked_files() -> list[str]:
    """Return the list of files tracked by git (relative paths)."""
    proc = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    )
    raw = proc.stdout.decode("utf-8", errors="replace")
    return [p for p in raw.split("\x00") if p]


def _in_ckpt_allowlist(rel_path: str) -> bool:
    return any(
        rel_path == d or rel_path.startswith(d + "/")
        for d in CKPT_ALLOWLIST_DIRS
    )


def _is_text_file(rel_path: str) -> bool:
    suffix = Path(rel_path).suffix.lower()
    return suffix in TEXT_EXTENSIONS or rel_path in {".gitignore", ".gitattributes"}


def _check_weights_and_datasets(files: list[str]) -> list[str]:
    """Flag any weight / dataset blob that lives outside the allowlist."""
    violations: list[str] = []
    for rel in files:
        suffix = Path(rel).suffix.lower()
        if _in_ckpt_allowlist(rel):
            continue
        if suffix in WEIGHT_EXTENSIONS:
            violations.append(
                f"[weights] {rel}: extension {suffix} is not allowed "
                f"outside {sorted(CKPT_ALLOWLIST_DIRS)}"
            )
        elif suffix in DATASET_EXTENSIONS:
            violations.append(
                f"[dataset] {rel}: extension {suffix} must not be tracked; "
                "move to external storage"
            )
    return violations


def _check_large_files(files: list[str]) -> list[str]:
    """Flag text/source files above LARGE_FILE_BYTES (binary weights are
    caught above and skipped here via the allowlist)."""
    violations: list[str] = []
    for rel in files:
        if _in_ckpt_allowlist(rel):
            continue
        full = REPO_ROOT / rel
        try:
            size = full.stat().st_size
        except FileNotFoundError:
            continue
        if size > LARGE_FILE_BYTES:
            violations.append(
                f"[oversize] {rel}: {size} bytes exceeds {LARGE_FILE_BYTES} "
                "and is not a curated ckpt"
            )
    return violations


def _check_private_paths(files: list[str]) -> list[str]:
    """Reject files that should never be tracked."""
    violations: list[str] = []
    for rel in files:
        for private in PRIVATE_PATHS:
            if rel == private or rel.startswith(private + "/"):
                violations.append(
                    f"[private] {rel}: must not be tracked (covered by "
                    ".gitignore but `git add -f` may have leaked it)"
                )
                break
    return violations


def _check_credentials(files: list[str]) -> list[str]:
    """Scan text files for embedded secrets / API keys."""
    violations: list[str] = []
    for rel in files:
        if not _is_text_file(rel):
            continue
        full = REPO_ROOT / rel
        try:
            text = full.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for label, pattern in CREDENTIAL_PATTERNS:
            match = pattern.search(text)
            if match is None:
                continue
            violations.append(
                f"[credential:{label}] {rel}: matched `{match.group(0)[:12]}…`"
            )
            break  # one violation per file is enough
    return violations


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main(argv: list[str]) -> int:
    if not (REPO_ROOT / ".git").exists():
        print(
            "verify_clean_repo: not a git checkout — skipping (running this "
            "script outside a repo is intentional for ad-hoc tarballs)",
            file=sys.stderr,
        )
        return 0

    files = _tracked_files()
    if not files:
        print("verify_clean_repo: no tracked files — skipping", file=sys.stderr)
        return 0

    violations: list[str] = []
    violations.extend(_check_weights_and_datasets(files))
    violations.extend(_check_large_files(files))
    violations.extend(_check_private_paths(files))
    violations.extend(_check_credentials(files))

    if violations:
        print(
            f"verify_clean_repo: {len(violations)} violation(s) found:",
            file=sys.stderr,
        )
        for line in violations:
            print(f"  - {line}", file=sys.stderr)
        print(
            "\nFix: move the listed files out of the repo (or .gitignore "
            "them and `git rm --cached`), and rotate any leaked secrets "
            "before force-pushing.",
            file=sys.stderr,
        )
        return 1

    print(
        f"verify_clean_repo: clean ({len(files)} tracked files audited)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))