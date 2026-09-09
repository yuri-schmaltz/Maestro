"""Gauntlet contracts: approval, persistence, edits, assets and alternatives."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from services.generation_reviews import GenerationReviews
from services.creative_review import apply_review_edits, review_digest
from services.scene_takes import record_take, select_take
from services import director_pipeline as pipeline


class TimelineEditTests(unittest.TestCase):
    def test_split_preserves_duration_sources_and_changes_review_digest(self):
        from services.creative_review import retime_scene_plan
        timeline = [{'start': 0, 'end': 10, 'section_label': 'verse'}]
        plans = [{'image_prompt': 'portrait', 'video_prompt': 'sing', 'window_prompts': ['old timing']}]
        slots = [{'clip': {'start': 0, 'end': 4}, 'sources': [0]}, {'clip': {'start': 4, 'end': 10}, 'sources': [0]}]
        clips, prompts, images = retime_scene_plan(timeline, plans, ['frame.jpg'], slots, 24, 1, 8)
        self.assertEqual(images, ['frame.jpg', 'frame.jpg'])
        self.assertEqual(clips[-1]['end'], 10)
        self.assertNotIn('window_prompts', prompts[0])
        self.assertNotEqual(review_digest('review_prompts', prompts), review_digest('review_prompts', plans))
        slots[1]['clip']['start'] = 5
        with self.assertRaises(ValueError): retime_scene_plan(timeline, plans, ['frame.jpg'], slots)

    def test_merge_and_invalid_source(self):
        from services.creative_review import retime_scene_plan
        timeline = [{'start': 0, 'end': 4}, {'start': 4, 'end': 10}]
        plans = [{'image_prompt': 'a', 'video_prompt': 'one'}, {'image_prompt': 'b', 'video_prompt': 'two'}]
        slots = [{'clip': {'start': 0, 'end': 10}, 'sources': [0, 1]}]
        clips, prompts, images = retime_scene_plan(timeline, plans, ['a.jpg', 'b.jpg'], slots)
        self.assertEqual(prompts[0]['video_prompt'], 'one\ntwo')
        self.assertEqual(images, ['a.jpg'])
        slots[0]['sources'] = [-1]
        with self.assertRaises(ValueError): retime_scene_plan(timeline, plans, [], slots)


class GenerationReviewTests(unittest.TestCase):
    def test_nested_storyboard_assets_are_valid_but_escaping_paths_are_not(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            asset = Path(root) / '_director_assets/project/scene.jpg'
            asset.parent.mkdir(parents=True)
            asset.write_bytes(b'image')
            external = Path(outside) / 'outside.jpg'
            external.write_bytes(b'image')
            (Path(root) / 'escape.jpg').symlink_to(external)
            files = ['_director_assets/project/scene.jpg', '../outside.jpg', str(external), 'escape.jpg']
            self.assertEqual(pipeline._invalid_saved_media_numbers(files, 4, root, 'image'), [2, 3, 4])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = GenerationReviews(Path(self.temp.name) / 'reviews')

    def ready(self, params=None):
        review = self.store.create(params or {'prompt': 'original', 'seed': -1})
        self.store.prepare(review['id'], lambda source: {'params': source, 'workspace': 'project', 'out_dir': self.temp.name})
        return self.store.get(review['id'])

    def test_approved_request_is_frozen_and_idempotent(self):
        source = {'prompt': 'original', 'references': [{'name': 'Ana'}]}
        review = self.ready(source)
        source['references'][0]['name'] = 'Changed'
        submit = Mock(return_value={'job_id': 'one'})
        self.store.confirm(review['id'], submit, held=True)
        self.store.confirm(review['id'], submit, held=False)
        submit.assert_called_once()
        params = submit.call_args.args[0]['params']
        self.assertEqual(params['references'][0]['name'], 'Ana')
        self.assertGreaterEqual(params['seed'], 0)
        self.assertTrue(submit.call_args.args[1])

    def test_ready_plan_survives_restart_and_retains_seed(self):
        review = self.ready()
        restarted = GenerationReviews(self.store.root)
        self.assertEqual(restarted.get(review['id'])['prepared'], review['prepared'])

    def test_interrupted_planning_cannot_render(self):
        review = self.store.create({'prompt': 'test'})
        restarted = GenerationReviews(self.store.root)
        self.assertEqual(restarted.get(review['id'])['status'], 'failed')
        with self.assertRaises(ValueError):
            restarted.confirm(review['id'], Mock())

    def test_planner_failure_and_deferred_work_cannot_render(self):
        for prepare in (lambda _: (_ for _ in ()).throw(ValueError('failed')), lambda _: {'params': {'_deferred_prompt_enhance': {'prompt': 'x'}}}):
            review = self.store.create({'prompt': 'test'})
            self.store.prepare(review['id'], prepare)
            self.assertEqual(self.store.get(review['id'])['status'], 'failed')
            with self.assertRaises(ValueError):
                self.store.confirm(review['id'], Mock())

    def test_changed_or_missing_asset_invalidates_approval(self):
        asset = Path(self.temp.name) / 'source.png'
        asset.write_bytes(b'original')
        review = self.ready({'prompt': 'test', 'image_start': str(asset)})
        asset.write_bytes(b'different')
        submit = Mock()
        with self.assertRaisesRegex(ValueError, 'Source media changed'):
            self.store.confirm(review['id'], submit)
        asset.unlink()
        with self.assertRaisesRegex(ValueError, 'Source media changed'):
            self.store.confirm(review['id'], submit)
        submit.assert_not_called()

    def test_edit_is_new_revision_and_keeps_parent_unchanged(self):
        review = self.ready({'prompt': 'story', 'h3_window_prompts': ['a', 'b'], 'multi_prompts_gen_type': 3})
        edited = self.store.revise(review['id'], 'edited story', ['c', 'd'])
        self.assertNotEqual(review['id'], edited['id'])
        self.assertEqual(edited['prepared']['params']['prompt'], 'c\n---CLIP_BOUNDARY---\nd')
        self.assertEqual(self.store.get(review['id'])['prepared']['params']['h3_window_prompts'], ['a', 'b'])
        self.assertEqual(edited['prepared']['params']['seed'], review['prepared']['params']['seed'])
        with self.assertRaises(ValueError):
            self.store.revise(review['id'], 'story', ['too few'])

    def test_submission_failure_does_not_consume_approval(self):
        review = self.ready()
        with self.assertRaises(RuntimeError):
            self.store.confirm(review['id'], Mock(side_effect=RuntimeError('offline')))
        self.assertEqual(self.store.get(review['id'])['status'], 'ready')

    def test_rejects_invalid_identifiers(self):
        for review_id in ('../outside', '', 'a' * 33):
            with self.assertRaises(ValueError):
                self.store.get(review_id)


class CreativeContractTests(unittest.TestCase):
    def test_edits_preserve_hidden_continuity_and_window_metadata(self):
        original = [{'video_prompt': 'a', 'image_prompt': 'b', '_director_dialogue_beats': ['literal'], 'window_count': 2}]
        edited = apply_review_edits(original, [{'video_prompt': 'c', 'image_prompt': 'b'}])
        self.assertEqual(edited[0]['_director_dialogue_beats'], ['literal'])
        self.assertEqual(edited[0]['window_count'], 2)
        self.assertEqual(original[0]['video_prompt'], 'a')

    def test_locks_and_scene_count_are_enforced(self):
        original = [{'video_prompt': 'a', 'image_prompt': 'b'}]
        with self.assertRaisesRegex(ValueError, 'locked'):
            apply_review_edits(original, [{'video_prompt': 'changed'}], {'0': ['video_prompt']})
        with self.assertRaises(ValueError):
            apply_review_edits(original, [])

    def test_approval_invalidated_by_prompts_images_or_render_settings(self):
        digest = review_digest('review_render', ['a'], ['image.png'], {'seed': 10})
        for plans, images, params in ((['b'], ['image.png'], {'seed': 10}), (['a'], ['other.png'], {'seed': 10}), (['a'], ['image.png'], {'seed': 11})):
            self.assertNotEqual(digest, review_digest('review_render', plans, images, params))

    def test_approved_take_survives_new_alternative(self):
        original = {'video_filename': 'a.mp4', 'video_prompt': 'original', 'tag': 'good'}
        candidate = {'video_filename': 'b.mp4', 'video_prompt': 'changed', 'tag': 'good'}
        record_take(original, candidate, 'video')
        self.assertEqual(candidate['video_filename'], 'a.mp4')
        self.assertEqual(candidate['video_prompt'], 'original')
        self.assertEqual(len(candidate['video_takes']), 2)
        select_take(candidate, 'video', 'b.mp4')
        self.assertEqual(candidate['video_prompt'], 'changed')
        select_take(candidate, 'video', 'a.mp4')
        self.assertEqual(candidate['video_prompt'], 'original')
        with self.assertRaises(ValueError):
            select_take(candidate, 'video', 'foreign.mp4')


class DirectorApprovalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.patches = [patch.object(pipeline, '_pipelines', {}),
                        patch.object(pipeline, '_pipeline_operations', set()),
                        patch.object(pipeline, '_pipeline_threads', {}),
                        patch.object(pipeline, '_pipeline_child_jobs', {}),
                        patch.object(pipeline, '_wgp', SimpleNamespace(save_path=self.temp.name)),
                        patch.object(pipeline, '_save_pipeline_state', return_value=True)]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        pipeline._pipelines['test'] = {
            'status': 'running', 'clip_plans': [{'image_prompt': 'portrait', 'video_prompt': 'walk', 'window_prompts': ['walk left']}],
            'clip_images': ['frame.png'], 'params': {'auto_mode': False},
        }

    def test_retime_paused_project_saves_new_stage_and_preserves_images(self):
        p = pipeline._pipelines['test']
        p.update(out_dir=self.temp.name, _planned_clips=[{'start': 0, 'end': 10}])
        pipeline._pause_for_creative_review('test', 'review_images', p['clip_plans'], p['clip_images'])
        digest = review_digest('review_images', p['clip_plans'], p['clip_images'])
        slots = [{'clip': {'start': 0, 'end': 4}, 'sources': [0]}, {'clip': {'start': 4, 'end': 10}, 'sources': [0]}]
        pipeline.retime_pipeline_review(self.temp.name, 'test', slots, digest)
        self.assertEqual(p['pause_reason'], 'review_prompts')
        self.assertEqual(p['clip_images'], ['frame.png', 'frame.png'])
        self.assertEqual(p['review_approvals'], {})
        self.assertEqual(len(p['params']['prepared_planned_clips']), 2)
        self.assertNotIn('test', pipeline._pipeline_operations)
        with self.assertRaisesRegex(ValueError, 'changed'):
            pipeline.retime_pipeline_review(self.temp.name, 'test', slots, digest)

    def test_review_pause_returns_without_waiting_for_browser(self):
        plans = pipeline._pipelines['test']['clip_plans']
        with patch.object(pipeline, '_wait_for_resume') as wait:
            self.assertTrue(pipeline._pause_for_creative_review('test', 'review_prompts', plans))
            wait.assert_not_called()
        self.assertEqual(pipeline._pipelines['test']['status'], 'paused')
        pipeline._save_pipeline_state.assert_called_once()

    def test_approval_preserves_windows_rejects_stale_and_dispatches_once(self):
        p = pipeline._pipelines['test']
        pipeline._pause_for_creative_review('test', 'review_prompts', p['clip_plans'])
        with self.assertRaisesRegex(ValueError, 'changed'):
            pipeline.continue_pipeline('test', {'review_digest': 'stale'})
        with patch.object(pipeline.threading, 'Thread') as worker:
            self.assertTrue(pipeline.continue_pipeline('test', {'clip_plans': [{'image_prompt': 'portrait', 'video_prompt': 'run'}]}))
            self.assertFalse(pipeline.continue_pipeline('test'))
            worker.return_value.start.assert_called_once()
        self.assertEqual(p['clip_plans'][0]['window_prompts'], ['walk left'])
        self.assertFalse(pipeline._pause_for_creative_review('test', 'review_prompts', p['clip_plans']))

    def test_lock_can_be_added_to_newly_edited_prompt(self):
        p = pipeline._pipelines['test']
        pipeline._pause_for_creative_review('test', 'review_prompts', p['clip_plans'])
        with patch.object(pipeline.threading, 'Thread'):
            self.assertTrue(pipeline.continue_pipeline('test', {'clip_plans': [{'video_prompt': 'new draft'}], 'creative_locks': {'0': ['video_prompt']}}))
        self.assertEqual(p['clip_plans'][0]['video_prompt'], 'new draft')
        self.assertEqual(p['creative_locks'], {'0': ['video_prompt']})

    def test_failed_approval_save_never_starts_worker(self):
        p = pipeline._pipelines['test']
        pipeline._pause_for_creative_review('test', 'review_prompts', p['clip_plans'])
        with patch.object(pipeline, '_save_pipeline_state', return_value=False), patch.object(pipeline.threading, 'Thread') as worker:
            with self.assertRaisesRegex(ValueError, 'Unable to save approval'):
                pipeline.continue_pipeline('test')
            worker.assert_not_called()
        self.assertEqual(p['status'], 'paused')

    def test_invalid_lock_payload_is_a_validation_error(self):
        p = pipeline._pipelines['test']
        pipeline._pause_for_creative_review('test', 'review_prompts', p['clip_plans'])
        with self.assertRaisesRegex(ValueError, 'Invalid creative locks'):
            pipeline.continue_pipeline('test', {'creative_locks': ['invalid']})

    def test_paused_disk_snapshot_preserves_exact_plan_and_digest(self):
        p = pipeline._pipelines['test']
        p['out_dir'] = self.temp.name
        p['created_at'] = 1
        pipeline._pause_for_creative_review('test', 'review_prompts', p['clip_plans'])
        self.assertTrue(pipeline._save_pipeline_state_locked('test'))
        expected = pipeline.get_pipeline_status('test', self.temp.name)
        pipeline._pipelines.pop('test')
        restored = pipeline.get_pipeline_status('test', self.temp.name)
        self.assertEqual(restored['status'], 'paused')
        self.assertEqual(restored['clip_plans'], expected['clip_plans'])
        self.assertEqual(restored['review_digest'], expected['review_digest'])

    def test_storyboard_image_regeneration_restores_saved_review(self):
        restored = pipeline._pipelines.pop('test')
        restored.update(status='paused', pause_reason='review_images')
        saved = {'status': 'paused', 'pause_reason': 'review_images', 'clips': [
            {'start_image_filename': 'new.png', 'image_prompt': 'portrait', 'image_takes': []}
        ]}
        def restore(pid, out_dir):
            pipeline._pipelines[pid] = restored
            return True, 'awaiting_review'
        with patch.object(pipeline, 'load_pipeline_state', return_value=saved), \
             patch.object(pipeline, 'resume_pipeline', side_effect=restore) as resume, \
             patch.object(pipeline, '_rerun_clip_image_impl', return_value={'ok': True}) as render:
            self.assertEqual(pipeline.rerun_review_image(self.temp.name, 'test', 0), {'ok': True})
            resume.assert_called_once_with('test', self.temp.name)
            render.assert_called_once()
        self.assertEqual(restored['clip_images'], ['new.png'])
        self.assertNotIn('test', pipeline._pipeline_operations)

    def test_regeneration_does_not_resume_non_review_saved_project(self):
        pipeline._pipelines.pop('test')
        with patch.object(pipeline, 'load_pipeline_state', return_value={'status': 'failed'}), \
             patch.object(pipeline, 'resume_pipeline') as resume:
            with self.assertRaisesRegex(ValueError, 'storyboard review'):
                pipeline.rerun_review_image(self.temp.name, 'test', 0)
            resume.assert_not_called()

    def test_frontend_queue_never_overrides_manual_policy(self):
        source = (Path(__file__).resolve().parents[1] / 'ui/src/stores/useStore.ts').read_text()
        self.assertIn('auto_mode: directorAutoMode,', source)
        self.assertNotIn("auto_mode: mode === 'queue'", source)

    def test_render_approval_cannot_edit_compiled_prompt(self):
        p = pipeline._pipelines['test']
        p['review_render_params'] = {'prompt': 'compiled', 'seed': 12}
        pipeline._pause_for_creative_review('test', 'review_render', p['clip_plans'], p['clip_images'])
        with self.assertRaisesRegex(ValueError, 'immutable'):
            pipeline.continue_pipeline('test', {'clip_plans': [{'video_prompt': 'changed'}]})

    def test_paused_project_does_not_block_next_queue_entry(self):
        p = pipeline._pipelines['test']
        p['status'] = 'paused'
        state = {'entries': [{'id': 'next', 'status': 'queued', 'params': {}}], 'paused': False}
        with patch.object(pipeline, '_load_director_queue_locked', return_value=state), patch.object(pipeline, '_write_director_queue_locked'), patch.object(pipeline, 'start_pipeline', return_value='next-run') as start, patch.object(pipeline, 'get_pipeline', return_value={'status': 'completed'}):
            pipeline._run_director_queue(self.temp.name)
        start.assert_called_once()
        self.assertEqual(state['entries'][0]['status'], 'completed')

    def test_queue_yields_at_review_and_runs_next_project(self):
        state = {'entries': [{'id': 'first', 'status': 'queued', 'params': {}}, {'id': 'second', 'status': 'queued', 'params': {}}], 'paused': False}
        pipeline._pipelines.clear()
        with patch.object(pipeline, '_load_director_queue_locked', return_value=state), patch.object(pipeline, '_write_director_queue_locked'), patch.object(pipeline, 'start_pipeline', side_effect=['a', 'b']), patch.object(pipeline, 'get_pipeline', side_effect=[{'status': 'paused'}, {'status': 'completed'}]):
            pipeline._run_director_queue(self.temp.name)
        self.assertEqual([e['status'] for e in state['entries']], ['awaiting_review', 'completed'])

    def test_full_manual_flow_plans_and_images_once_then_submits_approved_payload(self):
        p = pipeline._pipelines['test']
        p['params'].update(video_model='ltx2_22B_distilled_1_1', pipeline_type='short_film_story', seamless=False, fps=25)
        p['clip_plans'] = [{'image_prompt': 'portrait', 'video_prompt': 'walk'}]
        p['clip_images'] = []
        timeline = [{'start': 0, 'end': 5, 'duration_sec': 5}]
        image = Path(self.temp.name) / 'frame.png'
        image.write_bytes(b'image')
        pipeline._wgp = SimpleNamespace(save_path=self.temp.name, server_config={'services': {'director_prompt_polish': 'none'}},
            get_model_def=lambda _: {'fps': 25}, get_model_min_frames_and_step=lambda _: (17, 8, 8))
        with patch.object(pipeline, '_wait_for_gpu', return_value=True), patch.object(pipeline, '_run_planning', return_value=(p['clip_plans'], timeline)) as planner, patch.object(pipeline, '_run_image_generation', return_value=(['frame.png'], [[]])) as images, patch.object(pipeline, '_submit_and_wait', return_value=['clip.mp4']) as submit, patch.object(pipeline.threading, 'Thread'):
            pipeline._run_pipeline('test')
            self.assertEqual(p.get('pause_reason'), 'review_prompts', p.get('error'))
            self.assertTrue(pipeline.continue_pipeline('test'))
            pipeline._run_pipeline('test', resume=True)
            self.assertEqual(p.get('pause_reason'), 'review_images', p.get('error'))
            self.assertTrue(pipeline.continue_pipeline('test'))
            pipeline._run_pipeline('test', resume=True)
            self.assertEqual(p.get('pause_reason'), 'review_render', p.get('error'))
            frozen = copy.deepcopy(p['review_render_params'])
            submit.assert_not_called()
            self.assertTrue(pipeline.continue_pipeline('test'))
            pipeline._run_pipeline('test', resume=True)
            self.assertEqual(p['status'], 'completed', p.get('error'))
            planner.assert_called_once()
            images.assert_called_once()
            submit.assert_called_once()
            self.assertEqual(submit.call_args.args[0], frozen)

    def test_explicit_automatic_mode_survives_queue(self):
        state = {'entries': [], 'paused': True}
        with patch.object(pipeline, '_load_director_queue_locked', return_value=state), patch.object(pipeline, '_write_director_queue_locked'), patch.object(pipeline, '_materialize_director_assets'):
            pipeline.enqueue_director_pipeline(self.temp.name, {'auto_mode': True})
            pipeline.enqueue_director_pipeline(self.temp.name, {'auto_mode': False})
        self.assertEqual([e['params']['auto_mode'] for e in state['entries']], [True, False])


if __name__ == '__main__':
    unittest.main()
