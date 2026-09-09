"""Contract tests for LLM-provider credential resolution."""

from __future__ import annotations

import os
import sys
import unittest


_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_APP = os.path.join(_ROOT, "app")
if _APP not in sys.path:
    sys.path.insert(0, _APP)

from services import llm_service


class TestProviderApiKey(unittest.TestCase):
    def setUp(self):
        self.services = {
            "llm_remote_api_key": "sk-remote",
            "openai_api_key": "sk-openai",
            "anthropic_api_key": "sk-anthropic",
            "minimax_api_key": "sk-minimax",
        }

    def test_each_provider_gets_only_its_own_credential(self):
        for provider, expected in (
            ("remote", "sk-remote"),
            ("openai", "sk-openai"),
            ("anthropic", "sk-anthropic"),
            ("minimax", "sk-minimax"),
        ):
            with self.subTest(provider=provider):
                self.assertEqual(
                    llm_service.provider_api_key(provider, self.services),
                    expected,
                )

    def test_local_unknown_and_unconfigured_providers_send_no_key(self):
        for provider in ("local", "", "bogus", None):
            with self.subTest(provider=provider):
                self.assertEqual(
                    llm_service.provider_api_key(provider, self.services),
                    "",
                )
        self.assertEqual(llm_service.provider_api_key("remote", {}), "")

    def test_every_credential_setting_is_persistable(self):
        launch_path = os.path.join(_APP, "launch.py")
        with open(launch_path, "r", encoding="utf-8") as handle:
            source = handle.read()
        for setting in llm_service.PROVIDER_API_KEY_SETTING.values():
            with self.subTest(setting=setting):
                self.assertIn(f'"{setting}"', source)

    def test_director_uses_the_shared_mapping(self):
        path = os.path.join(_APP, "services", "director_pipeline.py")
        with open(path, "r", encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn("llm_service.provider_api_key(", source)


class TestApiHeaders(unittest.TestCase):
    def setUp(self):
        self.saved = (llm_service._provider, llm_service._api_key)

    def tearDown(self):
        llm_service._provider, llm_service._api_key = self.saved

    def _headers_for(self, provider, key):
        llm_service._provider = provider
        llm_service._api_key = key
        return llm_service._api_headers()

    def test_remote_uses_bearer_token(self):
        self.assertEqual(
            self._headers_for("remote", "sk-remote").get("Authorization"),
            "Bearer sk-remote",
        )

    def test_anthropic_uses_its_native_headers(self):
        headers = self._headers_for("anthropic", "sk-anthropic")
        self.assertEqual(headers.get("x-api-key"), "sk-anthropic")
        self.assertEqual(headers.get("anthropic-version"), "2023-06-01")
        self.assertNotIn("Authorization", headers)

    def test_minimax_uses_anthropic_style_headers(self):
        # MiniMax M3 is Anthropic-compatible on the wire: x-api-key + the
        # same anthropic-version header, no Bearer.
        headers = self._headers_for("minimax", "sk-minimax")
        self.assertEqual(headers.get("x-api-key"), "sk-minimax")
        self.assertEqual(headers.get("anthropic-version"), "2023-06-01")
        self.assertNotIn("Authorization", headers)

    def test_local_and_keyless_remote_send_no_auth(self):
        self.assertNotIn("Authorization", self._headers_for("local", ""))
        self.assertNotIn("Authorization", self._headers_for("remote", ""))


class TestAnthropicBaseUrl(unittest.TestCase):
    """MiniMax M3 rides on the Anthropic-compatible wire format, so we
    only need to redirect the base URL — the request body is identical.
    """

    def setUp(self):
        self.saved = (llm_service._provider, llm_service._remote_url)

    def tearDown(self):
        llm_service._provider, llm_service._remote_url = self.saved

    def _url_for(self, provider, remote_url):
        llm_service._provider = provider
        llm_service._remote_url = remote_url
        return llm_service._anthropic_base_url()

    def test_anthropic_defaults_to_public_api(self):
        self.assertEqual(
            self._url_for("anthropic", ""),
            "https://api.anthropic.com",
        )

    def test_anthropic_uses_configured_remote_url_when_set(self):
        self.assertEqual(
            self._url_for("anthropic", "https://proxy.internal"),
            "https://proxy.internal",
        )

    def test_minimax_defaults_to_minimax_api(self):
        self.assertEqual(
            self._url_for("minimax", ""),
            "https://api.minimax.com",
        )

    def test_minimax_honors_configured_remote_url(self):
        # Self-hosted MiniMax-compatible gateways are valid — we always
        # prefer the user's URL over the default.
        self.assertEqual(
            self._url_for("minimax", "https://minimax-gateway.local"),
            "https://minimax-gateway.local",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
