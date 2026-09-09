"""Interactive UI contracts against mocked APIs; requires a running Vite dev server.

Run: python tests/browser_control_gauntlet.py [http://127.0.0.1:5173]
No models, accounts, or production rendering endpoints are used.
"""
import asyncio
import json
import sys
from pathlib import Path
from playwright.async_api import async_playwright


async def main():
    base = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:5173'
    requests = []
    errors = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=['--no-sandbox'])
        page = await browser.new_page(viewport={'width': 1280, 'height': 900})
        page.on('pageerror', lambda error: errors.append(str(error)))

        async def api_route(route):
            request = route.request
            payload = json.loads(request.post_data or '{}')
            requests.append((request.method, request.url, payload))
            response = {}
            if '/file/' in request.url:
                await route.fulfill(content_type='image/svg+xml', body='<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180"><rect width="320" height="180" fill="#334155"/><text x="65" y="95" fill="white">Storyboard test reference</text></svg>')
                return
            if '/generation-reviews/' in request.url and request.method == 'PUT':
                response = {'id': 'b' * 32, 'status': 'ready', 'prepared': {'params': {
                    'model_type': 'test-model', 'prompt': payload['prompt'], 'seed': 123,
                    'video_length': 240, 'h3_window_prompts': payload['window_prompts'],
                }}}
            elif request.url.endswith('/confirm'):
                response = {'job_id': 'frozen-job', 'status': 'held'}
            elif '/jobs' in request.url:
                response = {'jobs': []}
            elif '/queue' in request.url:
                response = {'entries': [], 'running': False, 'paused': True}
            await route.fulfill(json=response)
        await page.route('**/api/v1/**', api_route)
        await page.goto(base + '/tests/control.html')
        await page.get_by_role('heading', name='Review scene plan').wait_for()
        scenes = page.locator('article')
        await scenes.nth(0).get_by_role('button', name='Approve scene', exact=True).click()
        await scenes.nth(0).locator('textarea').nth(1).fill('Ana says hello')
        assert await page.get_by_text('0/2 scenes approved', exact=True).count() == 1
        await scenes.nth(0).get_by_role('button', name='Lock scene 1 video_prompt', exact=True).click()
        assert await scenes.nth(0).locator('textarea').nth(1).is_disabled()
        await page.get_by_role('button', name='Approve all scenes', exact=True).click()
        await page.get_by_role('button', name='Continue with approved plan', exact=True).click()
        approval = next(body for method, url, body in requests if url.endswith('/continue'))
        assert approval['clip_plans'][0]['video_prompt'] == 'Ana says hello'
        assert approval['creative_locks']['0'] == ['video_prompt']
        assert approval['review_digest'] == 'revision-1'

        await page.evaluate("window.controlHarness.showDirector('review_render')")
        await page.get_by_role('heading', name='Approve final render request').wait_for()
        assert await page.locator('textarea').first.is_disabled()
        await page.get_by_text('Prepared render settings and effective prompts', exact=True).click()
        assert '123' in await page.locator('pre').inner_text()
        await page.screenshot(path='/tmp/maestro-director-review-desktop.png', full_page=True)
        await page.set_viewport_size({'width': 390, 'height': 844})
        assert await page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        await page.screenshot(path='/tmp/maestro-director-review-mobile.png', full_page=True)

        await page.evaluate('window.controlHarness.showStudio()')
        await page.get_by_role('heading', name='Review before generating').wait_for()
        assert await page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        await page.screenshot(path='/tmp/maestro-studio-review-mobile.png', full_page=True)
        await page.get_by_role('button', name='Edit prepared prompts', exact=True).click()
        await page.locator('textarea').first.fill('edited prepared story')
        await page.get_by_role('button', name='Save as new revision', exact=True).click()
        await page.get_by_text('Saved revision:', exact=False).filter(has_text='bbbbbbbb').wait_for()
        await page.evaluate('window.controlHarness.changeDraft()')
        await page.get_by_role('button', name='Add to queue', exact=True).click()
        await page.wait_for_timeout(200)
        confirms = [(url, body) for method, url, body in requests if url.endswith('/confirm')]
        assert len(confirms) == 1
        assert '/'+ 'b' * 32 + '/confirm' in confirms[0][0]
        assert confirms[0][1] == {'held': True}, confirms
        assert not any(url.endswith('/generate') for _, url, _ in requests)

        await page.evaluate('window.controlHarness.showTakes()')
        await page.get_by_text('Compare 2 video takes', exact=True).click()
        assert await page.locator('video').count() == 2
        await page.get_by_role('button', name='Approve this take', exact=True).last.click()
        assert any(url.endswith('/take') and body.get('filename') == 'b.mp4' for _, url, body in requests)
        assert not errors, errors
        await browser.close()
    print('Browser gauntlet passed: per-scene approval invalidation, locks, final request, mobile layout, edited revision submission, frozen request and take selection.')


asyncio.run(main())
