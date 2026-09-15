"""Tests for the hardware-accelerated aliases exposed by save_video().

The aliases ``h264_nvenc``, ``h264_amf``, ``h264_qsv``, ``h264_videotoolbox``
and ``h264_vaapi`` are only available on hosts where FFmpeg advertises the
matching encoder (and, for VAAPI, where a render node is reachable). These
tests cover both the always-present software codecs and the lazy resolver
behaviour — they never depend on the host actually owning a GPU.
"""
from __future__ import annotations

import importlib

import pytest


@pytest.fixture()
def audio_video():
    """Import audio_video lazily — it's a heavy module with optional deps."""
    return importlib.import_module("app.shared.utils.audio_video")


def test_software_codecs_still_returned(audio_video):
    """The legacy software codecs must keep their existing kwargs shape."""
    assert audio_video._get_codec_params("libx264_8", "mp4") == {
        "codec": "libx264", "quality": 8, "pixelformat": "yuv420p",
    }
    assert audio_video._get_codec_params("libx264_10", "mp4") == {
        "codec": "libx264", "quality": 10, "pixelformat": "yuv420p",
    }
    assert audio_video._get_codec_params("libx265_8", "mp4")["codec"] == "libx265"
    assert audio_video._get_codec_params("libx265_28", "mp4")["codec"] == "libx265"
    lossless_mkv = audio_video._get_codec_params("libx264_lossless", "mkv")
    assert lossless_mkv == {"codec": "ffv1", "pixelformat": "rgb24"}
    lossless_mp4 = audio_video._get_codec_params("libx264_lossless", "mp4")
    assert lossless_mp4["codec"] == "libx264"
    assert "-crf" in lossless_mp4["output_params"]


def test_unknown_codec_falls_back_to_libx264(audio_video):
    assert audio_video._get_codec_params("not-a-real-codec", "mp4") == {
        "codec": "libx264", "pixelformat": "yuv420p",
    }


def test_hw_aliases_have_consistent_shape(audio_video, monkeypatch):
    """Every detected HW alias must produce a kwargs dict imageio accepts.

    We monkeypatch the cached probe so the test is hermetic — it asserts
    the *contract* (codec name + pixel format + output_params list) without
    requiring a real GPU.
    """
    monkeypatch.setattr(
        audio_video, "_HW_VIDEO_ENCODERS",
        {
            "h264_nvenc": {
                "codec": "h264_nvenc", "pixelformat": "yuv420p",
                "output_params": ["-preset", "p5", "-rc", "vbr", "-cq", "19"],
            },
            "h264_amf": {
                "codec": "h264_amf", "pixelformat": "yuv420p",
                "output_params": ["-rc", "vbr", "-qp", "20"],
            },
            "h264_qsv": {
                "codec": "h264_qsv", "pixelformat": "yuv420p",
                "output_params": ["-preset", "medium", "-global_quality", "22"],
            },
            "h264_videotoolbox": {
                "codec": "h264_videotoolbox", "pixelformat": "yuv420p",
                "output_params": ["-b:v", "8M", "-realtime", "true"],
            },
            "h264_vaapi": {
                "codec": "h264_vaapi", "pixelformat": "yuv420p",
                "output_params": [
                    "-vaapi_device", "/dev/dri/renderD128",
                    "-rc_mode", "VBR", "-qp", "22",
                ],
            },
        },
    )
    audio_video._hw_video_encoders_table.cache_clear() if hasattr(
        audio_video._hw_video_encoders_table, "cache_clear"
    ) else None
    for alias, expected_codec in (
        ("h264_nvenc", "h264_nvenc"),
        ("h264_amf", "h264_amf"),
        ("h264_qsv", "h264_qsv"),
        ("h264_videotoolbox", "h264_videotoolbox"),
        ("h264_vaapi", "h264_vaapi"),
    ):
        params = audio_video._get_codec_params(alias, "mp4")
        assert params["codec"] == expected_codec
        assert params["pixelformat"] == "yuv420p"
        assert isinstance(params["output_params"], list)
        assert params["output_params"], f"empty output_params for {alias}"


def test_hw_aliases_drop_to_software_when_unavailable(audio_video, monkeypatch):
    """Asking for an HW alias that the probe didn't report must NOT crash.

    The contract is: fall back to libx264 (same behaviour as an unknown
    codec). This keeps the imageio call valid even on hosts where the
    user has a stale saved setting that targets a backend they later
    removed (e.g. macOS user who switched to a Linux box).
    """
    monkeypatch.setattr(audio_video, "_HW_VIDEO_ENCODERS", {})
    params = audio_video._get_codec_params("h264_nvenc", "mp4")
    assert params == {"codec": "libx264", "pixelformat": "yuv420p"}


def test_hw_video_output_codecs_exported(audio_video):
    """The dropdown in the UI should know which aliases to offer."""
    expected = {
        "h264_nvenc", "h264_amf", "h264_qsv",
        "h264_videotoolbox", "h264_vaapi",
    }
    assert expected.issubset(set(audio_video.HW_VIDEO_OUTPUT_CODECS))


def test_hw_probe_falls_back_when_editor_capabilities_missing(
    audio_video, monkeypatch
):
    """A probe failure (editor_projects not importable) must not raise.

    Some worker processes import audio_video without the editor module
    on the path. The lazy table has to swallow that gracefully and just
    return an empty dict so the rest of the module stays usable.
    """
    def _boom():
        raise ImportError("simulated missing editor_projects")
    monkeypatch.setattr(
        audio_video, "_hw_video_encoders", _boom
    )
    audio_video._HW_VIDEO_ENCODERS = None
    assert audio_video._hw_video_encoders_table() == {}
