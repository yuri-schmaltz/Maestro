"""Standalone launch checks; no model loads or changes to the running app."""
import ast
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


class StandaloneLaunchTests(unittest.TestCase):
    def test_explicit_host_wins_over_legacy_share(self):
        # Exercise the actual startup block without importing the model backend.
        source = (ROOT / 'app/launch.py').read_text()
        start = source.index('    # Explicit standalone settings')
        end = source.index('    # Port resolution:', start)
        import textwrap
        code = compile(ast.parse(textwrap.dedent(source[start:end])), 'launch-host', 'exec')
        from unittest.mock import patch
        cases = [
            ({}, '127.0.0.1'),
            ({'PINOKIO_SHARE_LOCAL': 'true'}, '0.0.0.0'),
            ({'PINOKIO_SHARE_LOCAL': 'false'}, '127.0.0.1'),
            ({'SERVER_NAME': '127.0.0.1', 'PINOKIO_SHARE_LOCAL': 'true'}, '127.0.0.1'),
            ({'SERVER_NAME': '0.0.0.0', 'PINOKIO_SHARE_LOCAL': 'false'}, '0.0.0.0'),
            ({'SERVER_NAME': '  ', 'PINOKIO_SHARE_LOCAL': 'true'}, '0.0.0.0'),
        ]
        for environment, expected in cases:
            with self.subTest(environment=environment), patch.dict(os.environ, environment, clear=True):
                namespace = {'os': os}
                exec(code, namespace)
                self.assertEqual(namespace['host'], expected)

    def test_invalid_ports_fail_before_starting(self):
        for args in [[], ['0'], ['65536'], ['-1'], ['abc'], ['--share']]:
            with self.subTest(args=args):
                result = subprocess.run(['bash', str(ROOT / 'start_local.sh'), '--port', *args], capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertIn('ERRO:', result.stderr)

    def test_start_and_stop_with_isolated_http_backend(self):
        for share in [False, True]:
            with self.subTest(share=share), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                for script in ['start_local.sh', 'stop_local.sh']:
                    shutil.copy(ROOT / script, root / script)
                (root / 'app/env/bin').mkdir(parents=True)
                (root / 'app/env/bin/python').symlink_to(sys.executable)
                (root / 'ui/dist').mkdir(parents=True)
                (root / 'ui/dist/index.html').write_text('test')
                (root / 'app/launch.py').write_text('''import http.server, os
from pathlib import Path
Path("host.txt").write_text(os.environ["SERVER_NAME"])
http.server.HTTPServer((os.environ["SERVER_NAME"], int(os.environ["SERVER_PORT"])), http.server.SimpleHTTPRequestHandler).serve_forever()
''')
                with socket.socket() as probe:
                    probe.bind(('127.0.0.1', 0))
                    port = probe.getsockname()[1]
                env = dict(os.environ, PINOKIO_SHARE_LOCAL='false' if share else 'true', http_proxy='http://127.0.0.1:1', ALL_PROXY='http://127.0.0.1:1')
                try:
                    result = subprocess.run(['bash', str(root / 'start_local.sh'), '--port', str(port), *(['--share'] if share else [])], env=env, capture_output=True, text=True, timeout=30)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertEqual((root / 'app/host.txt').read_text(), '0.0.0.0' if share else '127.0.0.1')
                    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                    with opener.open(f'http://127.0.0.1:{port}/', timeout=2) as response:
                        self.assertEqual(response.status, 200)
                finally:
                    stopped = subprocess.run(['bash', str(root / 'stop_local.sh')], capture_output=True, text=True, timeout=15)
                self.assertEqual(stopped.returncode, 0, stopped.stdout + stopped.stderr)
                self.assertFalse((root / 'app/.launcher.pid').exists())
                with socket.socket() as probe:
                    self.assertNotEqual(probe.connect_ex(('127.0.0.1', port)), 0)


if __name__ == '__main__':
    unittest.main()
