"""Standalone launch checks; no model loads or changes to the running app."""
import ast
import http.server
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


class _VersionedHandler(http.server.BaseHTTPRequestHandler):
    """Minimal HTTP backend that mimics Maestro's /health/version and
    / routing. Used by the ensure_service tests so the bootstrapper has
    something real to probe against. The reported version is configurable
    per-instance via self.server.reported_version.  # type: ignore[attr-defined]"""

    def log_message(self, format, *args):  # silence stderr noise in tests
        pass

    def do_GET(self):
        if self.path == "/health/version":
            payload = json.dumps({
                "name": "maestro",
                "version": getattr(self.server, "reported_version", "0.0.0+unknown"),
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        # Default route — respond 200 so probe_index_alive() is true.
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"OK")


_VERSIONED_BACKEND_SCRIPT = '''
import http.server, json, sys

_VERSION = sys.argv[2]

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a, **k):
        pass
    def do_GET(self):
        if self.path == "/health/version":
            payload = json.dumps({"name": "maestro", "version": _VERSION}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        else:
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"OK")

http.server.HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
'''


def _spin_versioned_backend(version: str) -> tuple[subprocess.Popen, int]:
    """Spawn a background HTTP server in a separate Python process that
    reports `version` on /health/version and answers 200 on /.
    Returns (process, port). Caller is responsible for process.kill().

    We use a subprocess (not a thread) because the bootstrapper kills the
    holder by PID via `ss`; a same-process HTTP server running in a
    thread shares FDs with pytest that block subprocess.run's pipe
    handling when the bootstrapper sends SIGTERM."""
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    proc = subprocess.Popen(
        [sys.executable, '-c', _VERSIONED_BACKEND_SCRIPT, str(port), version],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    # Wait for the listener to be ready to serve HTTP — not just bind.
    # We confirm by issuing a real HTTP GET via urllib (the bootstrapper
    # uses curl, but urllib matches pytest's stdlib better and avoids
    # picking up HTTP_PROXY).
    deadline = time.time() + 3.0
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/health/version', timeout=0.5) as response:
                if response.status == 200:
                    body = response.read().decode('utf-8')
                    data = json.loads(body)
                    if data.get('version') == version:
                        return proc, port
        except Exception as exc:
            last_err = exc
            time.sleep(0.05)
    proc.kill()
    proc.wait()
    raise RuntimeError(f"backend failed to serve /health/version in time: {last_err}")


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


    def test_ensure_service_skips_when_version_matches(self):
        """If a Maestro with the same VERSION is already on the port,
        start_local.sh must print (skipped) and exit 0 without relaunching."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for script in ['start_local.sh', 'stop_local.sh']:
                shutil.copy(ROOT / script, root / script)
            # Pin the expected version to whatever the running backend reports.
            (root / 'VERSION').write_text('9.9.9-test')
            version = '9.9.9-test'
            proc, port = _spin_versioned_backend(version)
            try:
                # Stage a venv + a stub launch.py so the script can run the
                # full bring-up path IF the version check doesn't short-circuit.
                # We expect the version check to short-circuit (no relaunch),
                # but the script touches these files in §1 before probing, so
                # they must exist.
                (root / 'app/env/bin').mkdir(parents=True)
                (root / 'app/env/bin/python').symlink_to(sys.executable)
                (root / 'app/launch.py').write_text(
                    'import http.server, os\n'
                    'http.server.HTTPServer((os.environ["SERVER_NAME"], int(os.environ["SERVER_PORT"])), '
                    'http.server.SimpleHTTPRequestHandler).serve_forever()\n'
                )
                # --no-build so the script never touches ui/dist; --force would
                # defeat the probe (we explicitly want the probe path).
                result = subprocess.run(
                    ['bash', str(root / 'start_local.sh'), '--port', str(port), '--no-build'],
                    capture_output=True, text=True, timeout=15,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('(skipped)', result.stdout)
                self.assertIn(version, result.stdout)
                # The pidfile must NOT have been written — no relaunch happened.
                self.assertFalse((root / 'app/.launcher.pid').exists())
            finally:
                proc.kill()
                proc.wait(timeout=2)

    def test_ensure_service_restarts_on_version_mismatch(self):
        """If the running Maestro reports a DIFFERENT version, start_local.sh
        must kill the holder and bring up a fresh backend bound to the port."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for script in ['start_local.sh', 'stop_local.sh']:
                shutil.copy(ROOT / script, root / script)
            (root / 'VERSION').write_text('9.9.9-test')
            # The fake backend reports an OLD version.
            proc, port = _spin_versioned_backend('0.0.0-stale')
            try:
                # Stage a minimal app/env so the launcher can exec it.
                (root / 'app/env/bin').mkdir(parents=True)
                (root / 'app/env/bin/python').symlink_to(sys.executable)
                (root / 'ui/dist').mkdir(parents=True)
                (root / 'ui/dist/index.html').write_text('test')
                # Stub launch.py — a simple HTTP server bound to SERVER_PORT.
                (root / 'app/launch.py').write_text(
                    'import http.server, os\n'
                    'http.server.HTTPServer((os.environ["SERVER_NAME"], int(os.environ["SERVER_PORT"])), '
                    'http.server.SimpleHTTPRequestHandler).serve_forever()\n'
                )
                try:
                    result = subprocess.run(
                        ['bash', str(root / 'start_local.sh'), '--port', str(port), '--no-build'],
                        capture_output=True, text=True, timeout=30,
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn('Stale build detectado', result.stdout)
                    self.assertNotIn('(skipped)', result.stdout)
                    self.assertTrue((root / 'app/.launcher.pid').exists())
                finally:
                    subprocess.run(['bash', str(root / 'stop_local.sh')], capture_output=True, text=True, timeout=10)
            finally:
                proc.kill()
                proc.wait(timeout=2)

    def test_ensure_service_force_bypasses_probe(self):
        """--force must skip the probe path entirely and always restart."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for script in ['start_local.sh', 'stop_local.sh']:
                shutil.copy(ROOT / script, root / script)
            (root / 'VERSION').write_text('9.9.9-test')
            proc, port = _spin_versioned_backend('9.9.9-test')
            try:
                (root / 'app/env/bin').mkdir(parents=True)
                (root / 'app/env/bin/python').symlink_to(sys.executable)
                (root / 'ui/dist').mkdir(parents=True)
                (root / 'ui/dist/index.html').write_text('test')
                (root / 'app/launch.py').write_text(
                    'import http.server, os\n'
                    'http.server.HTTPServer((os.environ["SERVER_NAME"], int(os.environ["SERVER_PORT"])), '
                    'http.server.SimpleHTTPRequestHandler).serve_forever()\n'
                )
                try:
                    result = subprocess.run(
                        ['bash', str(root / 'start_local.sh'), '--port', str(port), '--no-build', '--force'],
                        capture_output=True, text=True, timeout=30,
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn('--force ativo', result.stdout)
                    self.assertNotIn('(skipped)', result.stdout)
                    self.assertTrue((root / 'app/.launcher.pid').exists())
                finally:
                    subprocess.run(['bash', str(root / 'stop_local.sh')], capture_output=True, text=True, timeout=10)
            finally:
                proc.kill()
                proc.wait(timeout=2)

    def test_ensure_service_kills_foreign_holder_and_restarts(self):
        """If the port is held by a foreign HTTP server (no /health/version
        route, but still answering), start_local.sh must treat it as stale,
        kill it, and bring up a fresh Maestro. This is the realistic case
        the script handles on a developer machine where another dev server
        is squatting on the port."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for script in ['start_local.sh', 'stop_local.sh']:
                shutil.copy(ROOT / script, root / script)
            (root / 'VERSION').write_text('9.9.9-test')
            # Foreign HTTP server: answers 200 on / but no /health/version.
            # Run in a separate process so kill-by-PID works cleanly.
            with socket.socket() as probe:
                probe.bind(('127.0.0.1', 0))
                port = probe.getsockname()[1]
            foreign_script = '''
import http.server, sys
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a, **k): pass
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"OK")
http.server.HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
'''
            foreign = subprocess.Popen(
                [sys.executable, '-c', foreign_script, str(port)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            try:
                # Wait for the foreign server to bind.
                deadline = time.time() + 2.0
                while time.time() < deadline:
                    try:
                        with socket.create_connection(('127.0.0.1', port), timeout=0.2):
                            break
                    except OSError:
                        time.sleep(0.02)
                (root / 'app/env/bin').mkdir(parents=True)
                (root / 'app/env/bin/python').symlink_to(sys.executable)
                (root / 'ui/dist').mkdir(parents=True)
                (root / 'ui/dist/index.html').write_text('test')
                (root / 'app/launch.py').write_text(
                    'import http.server, os\n'
                    'http.server.HTTPServer((os.environ["SERVER_NAME"], int(os.environ["SERVER_PORT"])), '
                    'http.server.SimpleHTTPRequestHandler).serve_forever()\n'
                )
                try:
                    result = subprocess.run(
                        ['bash', str(root / 'start_local.sh'), '--port', str(port), '--no-build'],
                        capture_output=True, text=True, timeout=30,
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    # The script must have detected the holder was stale and
                    # proceeded to launch a fresh backend. The banner text
                    # is one of two forms depending on whether the holder
                    # reported a version or not (foreign server has no
                    # /health/version route → "não responde /health/version").
                    self.assertTrue(
                        'Stale build detectado' in result.stdout
                        or 'não responde /health/version' in result.stdout,
                        f'expected stale detection banner; got: {result.stdout}',
                    )
                    self.assertTrue((root / 'app/.launcher.pid').exists())
                finally:
                    subprocess.run(['bash', str(root / 'stop_local.sh')], capture_output=True, text=True, timeout=10)
            finally:
                foreign.kill()
                foreign.wait(timeout=2)

    def test_ensure_service_reports_correct_version(self):
        """The expected version read from VERSION file must appear in the
        bootstrapper's startup banner and final summary, so operators can
        confirm what version is actually running."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for script in ['start_local.sh', 'stop_local.sh']:
                shutil.copy(ROOT / script, root / script)
            (root / 'VERSION').write_text('7.7.7-test')
            (root / 'app/env/bin').mkdir(parents=True)
            (root / 'app/env/bin/python').symlink_to(sys.executable)
            (root / 'ui/dist').mkdir(parents=True)
            (root / 'ui/dist/index.html').write_text('test')
            (root / 'app/launch.py').write_text(
                'import http.server, os\n'
                'http.server.HTTPServer((os.environ["SERVER_NAME"], int(os.environ["SERVER_PORT"])), '
                'http.server.SimpleHTTPRequestHandler).serve_forever()\n'
            )
            try:
                with socket.socket() as probe:
                    probe.bind(('127.0.0.1', 0))
                    port = probe.getsockname()[1]
                result = subprocess.run(
                    ['bash', str(root / 'start_local.sh'), '--port', str(port), '--no-build'],
                    capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('7.7.7-test', result.stdout)
            finally:
                subprocess.run(['bash', str(root / 'stop_local.sh')], capture_output=True, text=True, timeout=10)


if __name__ == '__main__':
    unittest.main()
