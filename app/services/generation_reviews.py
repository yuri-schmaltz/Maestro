"""Durable, single-use approvals of prepared generation requests.

Preparation and submission are injected: this module never imports GPU code.
A confirmed request is read from disk, never reconstructed from browser state.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import secrets
import threading
import time
from pathlib import Path


class GenerationReviews:
    def __init__(self, root):
        self.root = Path(root)
        self.lock = threading.RLock()
        # Workers do not survive a process restart. Ready plans remain usable.
        for path in self.root.glob('*.json'):
            try:
                review = json.loads(path.read_text(encoding='utf-8'))
                if review.get('status') == 'planning':
                    review.update(status='failed', error='Planning was interrupted. Prepare a new plan.')
                    self._write(review)
            except (OSError, ValueError):
                continue

    def _path(self, review_id):
        if len(review_id) != 32 or any(c not in '0123456789abcdef' for c in review_id):
            raise ValueError('Invalid review id')
        return self.root / f'{review_id}.json'

    def _write(self, review):
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(review['id'])
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(review, ensure_ascii=False), encoding='utf-8')
        os.replace(temp, path)

    def get(self, review_id):
        with self.lock:
            return json.loads(self._path(review_id).read_text(encoding='utf-8'))

    def create(self, params):
        with self.lock:
            review = dict(id=secrets.token_hex(16), status='planning',
                          created_at=time.time(), source=copy.deepcopy(params))
            self._write(review)
            return review

    def prepare(self, review_id, prepare):
        try:
            review = self.get(review_id)
            prepared = prepare(copy.deepcopy(review['source']))
            params = prepared['params']
            if params.get('prompt_enhancer'):
                params.setdefault('_review_notes', []).append('Renderer prompt rewriting is disabled for this approved request. Edit or enhance the prompt before approval.')
            params['prompt_enhancer'] = ''
            if params.get('_deferred_prompt_enhance') or params.get('_deferred_generation_prepare'):
                raise ValueError('The plan still contains deferred AI work')
            if int(params.get('seed', -1)) < 0:
                params['seed'] = secrets.randbelow(2**31)
            # Detect changed/missing source media when a reviewed job starts.
            assets = {}
            def visit(value):
                if isinstance(value, dict):
                    for key, item in value.items():
                        if key not in {'_review_ui', '_review_original_prompt'}:
                            visit(item)
                elif isinstance(value, list):
                    for item in value:
                        visit(item)
                elif isinstance(value, str) and len(value) < 4096:
                    try:
                        if os.path.isabs(value) and os.path.isfile(value):
                            with open(value, 'rb') as handle:
                                assets[value] = hashlib.file_digest(handle, 'sha256').hexdigest()
                    except (OSError, ValueError):
                        raise ValueError('Unable to fingerprint a source asset')
            visit(params)
            with self.lock:
                review = self.get(review_id)
                if review['status'] != 'planning':
                    return
                review.update(status='ready', prepared=prepared, assets=assets)
                self._write(review)
        except Exception as exc:
            with self.lock:
                review = self.get(review_id)
                review.update(status='failed', error=str(getattr(exc, 'detail', exc)))
                self._write(review)

    def revise(self, review_id, prompt, window_prompts):
        with self.lock:
            previous = self.get(review_id)
            if previous['status'] != 'ready':
                raise ValueError('Only a ready plan can be edited')
            if not isinstance(prompt, str) or not prompt.strip():
                raise ValueError('Prompt must not be empty')
            prepared = copy.deepcopy(previous['prepared'])
            params = prepared['params']
            key = 'h3_window_prompts' if params.get('h3_window_prompts') else 'ltx_window_prompts'
            original_windows = params.get(key) or []
            if not isinstance(window_prompts, list) or len(window_prompts) != len(original_windows) or not all(isinstance(p, str) and p.strip() for p in window_prompts):
                raise ValueError('Preserve the number of windows and provide each prompt')
            params['prompt'] = prompt
            if original_windows:
                params[key] = window_prompts
                if params.get('multi_prompts_gen_type') == 3:
                    params['prompt'] = '\n---CLIP_BOUNDARY---\n'.join(window_prompts)
                elif key == 'ltx_window_prompts':
                    params['prompt'] = '\n'.join(window_prompts)
            for plan_key in ('h3_window_plan', 'ltx_window_plan'):
                plan = prepared.get(plan_key)
                if isinstance(plan, dict):
                    plan['window_prompts'] = window_prompts
                    for i, window in enumerate(plan.get('windows', [])):
                        if i < len(window_prompts):
                            window['prompt'] = window_prompts[i]
            revision = dict(previous, id=secrets.token_hex(16), parent_id=review_id,
                            prepared=prepared, created_at=time.time())
            self._write(revision)
            return revision

    def confirm(self, review_id, submit, held=False):
        with self.lock:
            review = self.get(review_id)
            if review['status'] == 'submitted':
                return review['submission']
            if review['status'] != 'ready':
                raise ValueError('This plan is not ready for approval')
            self.validate_assets(review)
            prepared = copy.deepcopy(review['prepared'])
            prepared['params']['_generation_review_id'] = review_id
            prepared['params']['_generation_review_assets'] = review.get('assets', {})
            result = submit(prepared, held)
            review.update(status='submitted', approved_at=time.time(), submission=result)
            self._write(review)
            return result

    @staticmethod
    def validate_assets(review):
        for path, digest in review.get('assets', {}).items():
            try:
                with open(path, 'rb') as handle:
                    actual = hashlib.file_digest(handle, 'sha256').hexdigest()
            except OSError:
                actual = None
            if actual != digest:
                raise ValueError(f'Source media changed after review: {Path(path).name}. Prepare a new plan.')
