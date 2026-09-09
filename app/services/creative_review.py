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


def retime_scene_plan(timeline, plans, images, slots, fps=24, minimum=1, step=1):
    """Apply an explicit edit decision without inventing or dropping soundtrack time."""
    import math
    if not timeline or not isinstance(slots, list) or not 1 <= len(slots) <= 200:
        raise ValueError('A timeline needs between 1 and 200 scenes')
    result, new_plans, new_images = [], [], []
    previous = float(timeline[0]['start'])
    for slot in slots:
        if not isinstance(slot, dict) or not isinstance(slot.get('sources'), list) or not slot['sources']:
            raise ValueError('Invalid scene source')
        sources = slot['sources']
        if any(type(i) is not int or not 0 <= i < len(timeline) for i in sources):
            raise ValueError('Invalid scene source')
        try:
            start, end = float(slot['clip']['start']), float(slot['clip']['end'])
        except (KeyError, TypeError, ValueError):
            raise ValueError('Invalid scene interval')
        if not math.isfinite(start) or not math.isfinite(end) or end <= start or abs(start - previous) > .001:
            raise ValueError('Scene intervals must be continuous and positive')
        if (end - start) * fps < minimum - 1:
            raise ValueError('Scene is shorter than the model minimum')
        previous = end
        clip = copy.deepcopy(timeline[sources[0]])
        clip.update(start=start, end=end, duration_frames=minimum + max(0, round(((end-start)*fps-minimum)/step))*step)
        clip['beat_count'] = 0
        result.append(clip)
        new_plans.append({'_director_scene_interval': [start, end], 'image_prompt': plans[sources[0]].get('image_prompt', ''),
                          'video_prompt': '\n'.join(dict.fromkeys(plans[i].get('video_prompt', '') for i in sources))})
        new_images.append(images[sources[0]] if sources[0] < len(images) else '')
    if abs(previous - float(timeline[-1]['end'])) > .001:
        raise ValueError('Scene editing must preserve soundtrack duration')
    return result, new_plans, new_images
