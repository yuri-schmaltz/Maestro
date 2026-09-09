"""Non-destructive per-scene alternatives, kept in the existing project file."""
import copy
import time


def take_snapshot(clip, kind):
    filename_key = 'video_filename' if kind == 'video' else 'start_image_filename'
    keys = {'video_prompt', 'image_prompt', 'window_prompts', 'keyframe_prompts',
            'keyframe_filenames', 'start_image_filename', 'video_stale'}
    keys.update(key for key in clip if key.startswith('_director_'))
    return {'filename': clip.get(filename_key), 'created_at': time.time(),
            'settings': {key: copy.deepcopy(clip[key]) for key in keys if key in clip}}


def record_take(previous, current, kind):
    history_key = f'{kind}_takes'
    takes = copy.deepcopy(previous.get(history_key) or [])
    for clip in (previous, current):
        take = take_snapshot(clip, kind)
        if take['filename'] and not any(t['filename'] == take['filename'] for t in takes):
            takes.append(take)
    if previous.get('tag') == 'good':
        current.clear()
        current.update(copy.deepcopy(previous))
    current[history_key] = takes


def select_take(clip, kind, filename):
    if kind not in {'video', 'image'}:
        raise ValueError('Invalid take type')
    take = next((t for t in clip.get(f'{kind}_takes', []) if t['filename'] == filename), None)
    if not take:
        raise ValueError('Take does not belong to this scene')
    if kind == 'video':
        clip.update(copy.deepcopy(take['settings']))
        clip['video_filename'] = filename
        clip['tag'] = 'good'
    else:
        clip['start_image_filename'] = filename
        clip['image_prompt'] = take['settings'].get('image_prompt', clip.get('image_prompt', ''))
        clip['video_stale'] = bool(clip.get('video_filename'))
        clip['tag'] = 'needs_work'
