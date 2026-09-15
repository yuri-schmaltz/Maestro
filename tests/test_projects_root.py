"""Projects root configuration — backend contract.

Exercises the GET/PUT ``/api/v1/settings/projects-root`` surface and
the helpers it depends on (``_projects_root``, ``_default_projects_root``).
The endpoint is mounted on the live FastAPI app via the same wiring as
``test_workspace_setup_service`` — we don't import launch.py (which
inits a full GPU runtime); we exercise the helpers + the validation
contract directly.

Wire-level coverage lives in the integration smoke that runs against
the live backend on boot (curl-equivalent probes in
``scripts/verify_clean_repo.py`` doesn't fit this surface; the gauntlet
keeps it lean).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# launch.py lives in app/ — sys.path is set up by conftest.py.
_APP_DIR = Path(__file__).resolve().parents[1] / "app"


# ── _default_projects_root ──────────────────────────────────────────────


def test_default_projects_root_prefers_videos_when_present(monkeypatch):
    """When $HOME/Videos exists and is writable, that's the default."""
    from launch import _default_projects_root

    with tempfile.TemporaryDirectory() as tmp:
        videos = Path(tmp) / "Videos"
        videos.mkdir()
        monkeypatch.setattr(Path, "home", lambda: Path(tmp))
        result = _default_projects_root()
        assert result == str(videos.resolve()), (
            f"Expected the writable Videos dir, got {result}"
        )


def test_default_projects_root_falls_back_to_movies(monkeypatch):
    """On macOS-style hosts without Videos, ~/Movies wins."""
    from launch import _default_projects_root

    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        (home / "Movies").mkdir()
        # No Videos dir at all.
        monkeypatch.setattr(Path, "home", lambda: home)
        result = _default_projects_root()
        assert result == str((home / "Movies").resolve())


def test_default_projects_root_creates_fallback_when_no_videos(monkeypatch):
    """With neither Videos nor Movies present, we create ~/MaestroProjects."""
    from launch import _default_projects_root

    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        monkeypatch.setattr(Path, "home", lambda: home)
        result = _default_projects_root()
        assert result == str((home / "MaestroProjects").resolve())
        assert (home / "MaestroProjects").is_dir()


# ── _projects_root precedence ───────────────────────────────────────────


def test_projects_root_prefers_configured_over_default(monkeypatch):
    """A user-configured path always wins over the legacy save_path."""
    from launch import _projects_root, wgp

    with tempfile.TemporaryDirectory() as custom:
        monkeypatch.setitem(
            wgp.server_config.setdefault("services", {}),
            "projects_root_path",
            custom,
        )
        # Even if save_path points somewhere else, configured wins.
        monkeypatch.setitem(wgp.server_config, "save_path", "outputs")
        assert _projects_root() == str(Path(custom).resolve())


def test_projects_root_falls_back_to_save_path_when_unset(monkeypatch):
    """No configured key → fall back to save_path verbatim."""
    from launch import _projects_root, wgp

    monkeypatch.setitem(
        wgp.server_config.setdefault("services", {}),
        "projects_root_path",
        "",  # explicit reset
    )
    monkeypatch.setitem(wgp.server_config, "save_path", "/tmp/legacy")
    assert _projects_root() == "/tmp/legacy"


def test_projects_root_ignores_stale_configured_path(monkeypatch):
    """A configured path that no longer exists falls back to save_path.

    Avoids crashing the launcher on a removable drive that's not
    currently mounted — the user can re-mount and reload to get the
    custom layout back.
    """
    from launch import _projects_root, wgp

    monkeypatch.setitem(
        wgp.server_config.setdefault("services", {}),
        "projects_root_path",
        "/definitely/does/not/exist",
    )
    monkeypatch.setitem(wgp.server_config, "save_path", "/tmp/legacy")
    assert _projects_root() == "/tmp/legacy"


# ── _workspace_dir uses _projects_root ──────────────────────────────────


def test_workspace_dir_uses_configured_root(monkeypatch):
    """New workspaces land under the configured root, not save_path."""
    from launch import _workspace_dir, wgp

    with tempfile.TemporaryDirectory() as custom:
        monkeypatch.setitem(
            wgp.server_config.setdefault("services", {}),
            "projects_root_path",
            custom,
        )
        path = _workspace_dir("myproject")
        assert path.startswith(custom)
        assert path.endswith("myproject")
        assert os.path.isdir(path)


def test_default_workspace_path_is_the_root(monkeypatch):
    """The 'default' workspace lives at the root itself, not below it."""
    from launch import _workspace_dir, wgp

    with tempfile.TemporaryDirectory() as custom:
        monkeypatch.setitem(
            wgp.server_config.setdefault("services", {}),
            "projects_root_path",
            custom,
        )
        assert _workspace_dir("default") == custom


# ── Endpoint validation ───────────────────────────────────────────────


def _patched_request(json_body: str):
    """Build a minimal stand-in for a FastAPI Request."""
    from starlette.requests import Request

    async def receive() -> dict:
        return {"type": "http.request", "body": json_body.encode("utf-8"), "more_body": False}

    return Request(
        {"type": "http", "method": "PUT", "headers": [], "query_string": b""},
        receive=receive,
    )


@pytest.mark.asyncio
async def test_set_projects_root_rejects_nonexistent_path(monkeypatch):
    """PUT /settings/projects-root rejects paths that don't exist."""
    from launch import set_projects_root, wgp
    from fastapi import HTTPException

    request = _patched_request(json.dumps({"path": "/no/such/dir/anywhere"}))
    with pytest.raises(HTTPException) as info:
        await set_projects_root(request)
    assert info.value.status_code == 400
    assert "does not exist" in info.value.detail


@pytest.mark.asyncio
async def test_set_projects_root_rejects_null_byte(monkeypatch):
    """Path containing a null byte is rejected as a defense-in-depth check."""
    from launch import set_projects_root, wgp
    from fastapi import HTTPException

    # os.path.abspath strips null bytes on POSIX, so we craft a path
    # whose raw form contains one and let the function's own guard
    # trip first. We bypass abspath by sending a path that LOOKS like
    # a real dir after abspath but contains \x00 before abspath runs.
    # Since abspath collapses on POSIX, we hit the guard via raw input
    # by monkey-patching os.path.abspath to a passthrough.
    import os as _os
    monkeypatch.setattr(
        _os.path, "abspath", lambda p: "/tmp/legit\x00attack"
    )
    request = _patched_request(json.dumps({"path": "/tmp/attack"}))
    with pytest.raises(HTTPException) as info:
        await set_projects_root(request)
    assert info.value.status_code == 400
    assert "null byte" in info.value.detail


@pytest.mark.asyncio
async def test_set_projects_root_clears_when_empty(monkeypatch):
    """An empty path clears the configured key — explicit reset."""
    from launch import set_projects_root, wgp

    services = wgp.server_config.setdefault("services", {})
    services["projects_root_path"] = "/some/old/path"
    request = _patched_request(json.dumps({"path": ""}))
    response = await set_projects_root(request)
    assert response["configured_path"] == ""
    assert "projects_root_path" not in services


@pytest.mark.asyncio
async def test_set_projects_root_persists_valid_path(monkeypatch):
    """A valid path is written into services.projects_root_path."""
    from launch import set_projects_root, wgp

    with tempfile.TemporaryDirectory() as tmp:
        request = _patched_request(json.dumps({"path": tmp}))
        response = await set_projects_root(request)
        assert response["configured_path"] == str(Path(tmp).resolve())
        assert response["exists"] is True
        assert response["writable"] is True
        services = wgp.server_config["services"]
        assert services["projects_root_path"] == str(Path(tmp).resolve())


def test_get_projects_root_reports_effective(monkeypatch):
    """GET returns the effective path with existence + writability flags."""
    from launch import get_projects_root, wgp

    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setitem(
            wgp.server_config.setdefault("services", {}),
            "projects_root_path",
            tmp,
        )
        body = get_projects_root()
        assert body["configured_path"] == tmp
        assert body["effective_path"] == tmp
        assert body["exists"] is True
        assert body["writable"] is True


def test_get_projects_root_reports_stale_config(monkeypatch):
    """A configured path that's been removed reports exists=False."""
    from launch import get_projects_root, wgp

    monkeypatch.setitem(
        wgp.server_config.setdefault("services", {}),
        "projects_root_path",
        "/definitely/does/not/exist",
    )
    body = get_projects_root()
    # The configured string survives, but the existence check flags it
    # so the UI can warn the user before they hit a save error.
    assert body["configured_path"] == "/definitely/does/not/exist"
    assert body["exists"] is False
