"""Pure approval contracts shared by Director review and regression tests."""
import copy
import hashlib
import json


def review_digest(reason, plans, images=None, render_params=None):
    payload = {'stage': reason, 'plans': plans}
    if reason in {'review_images', 'review_render'}:
        payload['images'] = images or []
    if reason == 'review_render':
        payload['render_params'] = render_params
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def apply_review_edits(original, submitted, locks=None):
    if not isinstance(submitted, list) or len(submitted) != len(original):
        raise ValueError('Review must preserve the number of scenes')
    allowed = {'image_prompt', 'video_prompt', 'window_prompts', 'keyframe_prompts'}
    result = copy.deepcopy(original)
    for i, patch in enumerate(submitted):
        if not isinstance(patch, dict):
            raise ValueError('Invalid scene')
        locked = set((locks or {}).get(str(i), []))
        for key in allowed & patch.keys():
            value = patch[key]
            if key in locked and value != original[i].get(key):
                raise ValueError(f'Scene {i + 1}: {key} is locked')
            if key.endswith('_prompts'):
                if not isinstance(value, list) or not all(isinstance(x, str) and x.strip() for x in value):
                    raise ValueError(f'Scene {i + 1}: invalid prompts')
            elif not isinstance(value, str):
                raise ValueError(f'Scene {i + 1}: invalid prompt')
            result[i][key] = value
    return result
