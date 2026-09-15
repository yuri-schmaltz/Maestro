"""Tests for API authentication and path safety features."""

import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from fastapi import HTTPException
from app.services.security import (
    configure_security,
    verify_api_key,
    is_auth_required,
    get_active_api_key,
)
from app.shared.utils.path_safety import (
    is_safe_subpath,
    resolve_safe_path,
    require_safe_path,
)


class TestApiSecurity(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        configure_security(api_key=None, require_auth=False)

    def tearDown(self):
        configure_security(api_key=None, require_auth=False)

    async def test_auth_disabled_allows_request(self):
        configure_security(require_auth=False)
        self.assertFalse(is_auth_required())
        
        request = MagicMock()
        request.url.path = "/api/v1/projects"
        request.client.host = "192.168.1.50"
        
        # Não deve levantar exceção
        result = await verify_api_key(request)
        self.assertTrue(result)

    async def test_auth_required_rejects_unauthorized_external(self):
        token = configure_security(api_key="secret-test-token-123", require_auth=True, allow_unauthenticated_local=True)
        self.assertEqual(token, "secret-test-token-123")
        self.assertTrue(is_auth_required())
        
        request = MagicMock()
        request.url.path = "/api/v1/projects"
        request.client.host = "192.168.1.100"
        request.headers = {}
        request.query_params = {}

        with self.assertRaises(HTTPException) as ctx:
            await verify_api_key(request)
        self.assertEqual(ctx.exception.status_code, 401)

    async def test_auth_required_accepts_valid_bearer_token(self):
        configure_security(api_key="valid-key-999", require_auth=True)
        
        request = MagicMock()
        request.url.path = "/api/v1/director/pipeline/start"
        request.client.host = "192.168.1.100"
        request.headers = {"Authorization": "Bearer valid-key-999"}
        request.query_params = {}

        result = await verify_api_key(request)
        self.assertTrue(result)

    async def test_auth_required_allows_local_when_configured(self):
        configure_security(api_key="key-xyz", require_auth=True, allow_unauthenticated_local=True)
        
        request = MagicMock()
        request.url.path = "/api/v1/projects"
        request.client.host = "127.0.0.1"
        request.headers = {}
        request.query_params = {}

        result = await verify_api_key(request)
        self.assertTrue(result)

    async def test_auth_required_blocks_local_when_require_auth_is_strict(self):
        configure_security(api_key="strict-key", require_auth=True, allow_unauthenticated_local=False)
        
        request = MagicMock()
        request.url.path = "/api/v1/projects"
        request.client.host = "127.0.0.1"
        request.headers = {}
        request.query_params = {}

        with self.assertRaises(HTTPException) as ctx:
            await verify_api_key(request)
        self.assertEqual(ctx.exception.status_code, 401)


class TestPathSafety(unittest.TestCase):
    def setUp(self):
        self.temp_root = Path(__file__).resolve().parent

    def test_safe_subpath_detection(self):
        base = self.temp_root
        safe_child = base / "subdir" / "file.txt"
        self.assertTrue(is_safe_subpath(safe_child, base))
        self.assertTrue(is_safe_subpath(base, base))

        # Tentativa de escape com ..
        unsafe_escape = base / ".." / ".." / "other.txt"
        self.assertFalse(is_safe_subpath(unsafe_escape, base / "subdir"))

    def test_resolve_safe_path(self):
        base = self.temp_root
        allowed = [base / "allowed_dir"]
        
        # Teste de caminho seguro
        safe_path = base / "allowed_dir" / "music.wav"
        resolved = resolve_safe_path(safe_path, allowed)
        self.assertIsNotNone(resolved)
        
        # Teste de tentativa de traversal fora dos roots permitidos
        unsafe_path = base / "forbidden_dir" / "secret.txt"
        self.assertIsNone(resolve_safe_path(unsafe_path, allowed))

    def test_require_safe_path_raises_on_escape(self):
        allowed = [self.temp_root / "workspace"]
        with self.assertRaises(ValueError):
            require_safe_path(self.temp_root / "workspace" / ".." / "outside.txt", allowed)


if __name__ == "__main__":
    unittest.main()
