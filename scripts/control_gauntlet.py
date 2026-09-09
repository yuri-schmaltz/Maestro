"""Repeatable control-flow checks. Requires Starlette and requests in Python.

Usage: python scripts/control_gauntlet.py [--browser http://127.0.0.1:5173]
Browser checks additionally require Playwright Chromium and a Vite dev server.
"""
import argparse
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--browser')
args = parser.parse_args()
suites = [
    'test_generation_review_flow.py', 'test_director_projects_queue.py',
    'test_director_pipeline_status.py', 'test_director_cancellation.py',
    'test_settings_roundtrip.py', 'test_h3_window_planner.py',
    'test_editor_projects.py', 'test_director_prompt_integrity.py',
]
checks = [([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', suite], root) for suite in suites]
checks += [(['npm', 'run', 'test:control'], root / 'ui'), (['npm', 'run', 'build'], root / 'ui')]
if args.browser:
    checks.append(([sys.executable, 'tests/browser_control_gauntlet.py', args.browser], root))
failed = []
for command, cwd in checks:
    result = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    label = ' '.join(command)
    print(f"{'PASS' if result.returncode == 0 else 'FAIL'} {label}", flush=True)
    if result.returncode:
        failed.append(label)
        print(result.stdout[-12000:], flush=True)
    else:
        for line in result.stdout.splitlines():
            if line.startswith(('Ran ', 'Control gauntlet:', 'Browser gauntlet')):
                print('  ' + line, flush=True)
if failed:
    print(f'{len(failed)} check(s) failed.')
    sys.exit(1)
print(f'All {len(checks)} gauntlet checks passed.')
