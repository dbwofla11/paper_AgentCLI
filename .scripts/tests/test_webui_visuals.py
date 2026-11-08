"""Contract tests for review-derived visual summaries using isolated paper data."""
import hashlib
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.scripts/bin'))
import research_agent
from webui import jobs, reader, reviews, visuals


class VisualDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.library = self.root / '01-Papers/library'
        self.library.mkdir(parents=True)
        self.review = self.root / '01-Papers/reviews/other/example.md'
        self.review.parent.mkdir(parents=True)
        self.review.write_text('# Review\n', encoding='utf-8')
        self.figures = self.review.parent / 'figures'
        self.figures.mkdir()
        self.visual = self.figures / 'example-visual.html'
        self.sidecar = self.figures / 'example-visual.json'
        (self.library / 'example.json').write_text(json.dumps({
            'slug': 'example', 'title': 'Example',
            'source': {'review_path': '01-Papers/reviews/other/example.md'}}), encoding='utf-8')
        for p in (patch.object(reviews, 'ROOT', self.root), patch.object(reviews, 'LIBRARY', self.library)):
            p.start()
            self.addCleanup(p.stop)

    def test_listing_presence_and_bundle_staleness(self):
        self.assertFalse(reader.list_papers()['papers'][0]['has_visual'])
        absent = reader.paper_bundle('example')['visual']
        self.assertFalse(absent['available'])
        self.assertIsNone(absent['stale'])
        self.visual.write_text('<html></html>', encoding='utf-8')
        self.assertTrue(reader.list_papers()['papers'][0]['has_visual'])
        visual = reader.paper_bundle('example')['visual']
        self.assertTrue(visual['available'])
        self.assertEqual(visual['url'], '/api/papers/example/visual')
        self.assertIsNone(visual['stale'])
        digest = hashlib.sha256(self.review.read_bytes()).hexdigest()
        self.sidecar.write_text(json.dumps({'schema_version': '1.0', 'review_sha256': digest,
                                           'generated_at': '2026-01-01T00:00:00+00:00',
                                           'source': 'visual-job', 'check': 'passed'}), encoding='utf-8')
        self.assertIs(reader.paper_bundle('example')['visual']['stale'], False)
        self.review.write_text('# Changed review\n', encoding='utf-8')
        self.assertIs(reader.paper_bundle('example')['visual']['stale'], True)

    def test_checked_visual_rejects_invalid_outputs(self):
        valid = b'<html><style data-ve-kit></style><script data-ve-kit></script></html>'
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            path = workspace / 'example-visual.html'
            for label, data in (('missing', None), ('empty', b''), ('markers', b'<html></html>'),
                                ('utf8', valid + b'\xff'), ('ve-ask', valid + b'<ve-ask>'),
                                ('too-large', valid + b'x' * (3 * 1024 * 1024))):
                with self.subTest(label=label):
                    if data is None:
                        path.unlink(missing_ok=True)
                    else:
                        path.write_bytes(data)
                    with self.assertRaises((ValueError, OSError)):
                        visuals.checked_visual(workspace, 'example')
            path.write_bytes(valid)
            self.assertIsNotNone(visuals.checked_visual(workspace, 'example'))
            path.write_bytes(valid + b'x' * (3 * 1024 * 1024 - len(valid)))
            self.assertEqual(len(visuals.checked_visual(workspace, 'example')), 3 * 1024 * 1024)
            target = workspace / 'target.html'
            target.write_bytes(valid)
            path.unlink()
            path.symlink_to(target)
            with self.assertRaises((ValueError, OSError)):
                visuals.checked_visual(workspace, 'example')

    def test_workspace_skill_copy_is_not_review_output_or_snapshot(self):
        private = self.root / '.visual-explainer'
        (private / 'kit').mkdir(parents=True)
        (private / 'kit/render.mjs').write_text('fixture', encoding='utf-8')
        (private / 'SKILL.md').write_text('fixture', encoding='utf-8')
        name = '.visual-explainer/SKILL.md'
        self.assertFalse(reviews.allowed_output(name, self.library / 'example.json', self.review))
        self.assertNotIn(name, reviews.snapshot(self.root))


class VisualCommandTests(unittest.TestCase):
    def test_commands_are_write_capable_and_limit_network(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(research_agent.shutil, 'which', side_effect=lambda name: '/bin/' + name), \
             patch.object(research_agent, 'codex_mcp_servers', return_value=[]):
            cwd = Path(directory)
            claude = research_agent.visual_command('claude', cwd, 'prompt', skill_dir=cwd)
            self.assertNotIn('--add-dir', claude)
            review = research_agent.command('claude', cwd, cwd / 'last.txt', 'prompt')
            self.assertNotIn('--add-dir', review)
            staged_review = reviews.review_command(cwd, cwd / 'last.txt', 'prompt', 'claude')
            self.assertNotIn('--add-dir', staged_review)
            self.assertIn('Write', claude[claude.index('--tools') + 1])
            settings = json.loads(claude[claude.index('--settings') + 1])
            self.assertEqual(set(settings['sandbox']['network']['allowedDomains']),
                             {'fonts.googleapis.com', 'fonts.gstatic.com'})
            codex = research_agent.visual_command('codex', cwd, 'prompt', skill_dir=cwd)
            self.assertEqual(codex[codex.index('--sandbox') + 1], 'workspace-write')
            self.assertNotIn('sandbox_workspace_write.network_access=true', codex)
            omp = research_agent.visual_command('omp', cwd, 'prompt', skill_dir=cwd)
            self.assertNotIn('--no-skills', omp)
            self.assertIn('write', omp[omp.index('--tools') + 1])



class VisualCancellationTests(VisualDataTests):
    def test_cancel_after_publish_commit_is_not_accepted(self):
        valid = b'<html><style data-ve-kit></style><script data-ve-kit></script></html>'
        entered, release = threading.Event(), threading.Event()
        broker = jobs.JobBroker()
        original_write = visuals._write_at

        def events(ctx, key, workspace, slug, title, system, pinned, seen):
            (workspace / 'example-visual.html').write_bytes(valid)
            return [{'type': 'result', 'text': 'CHECK: passed'}]

        def write(folder, name, data):
            if name == 'example-visual.html':
                entered.set()
                if not release.wait(5):
                    raise RuntimeError('publish barrier timed out')
            return original_write(folder, name, data)

        with patch.object(visuals, '_agent_events', side_effect=events), \
             patch.object(visuals, '_write_at', side_effect=write), \
             patch.object(visuals.roles, 'agent_definition', return_value=(None, 'fixture')):
            job = broker.submit('review.visual', {'slug': 'example'}, visuals.visual_work('example', None))
            try:
                self.assertTrue(entered.wait(3))
                self.assertFalse(broker.cancel(job['job_id']))
            finally:
                release.set()
            self.assertTrue(broker.wait_finished([job['job_id']], 5))
            self.assertEqual(broker.get(job['job_id'])['status'], 'completed')
            self.assertEqual(self.visual.read_bytes(), valid)

    def test_cancel_before_publish_commit_and_shutdown(self):
        valid = b'<html><style data-ve-kit></style><script data-ve-kit></script></html>'
        for point, shutdown in (('validation', False), ('lock', False), ('lock', True)):
            with self.subTest(point=point, shutdown=shutdown):
                self.visual.write_bytes(b'old page')
                self.sidecar.write_bytes(b'old metadata')
                entered, release = threading.Event(), threading.Event()
                broker = jobs.JobBroker()
                original_check = visuals.checked_visual
                original_publish = visuals.publish_visual

                def events(ctx, key, workspace, slug, title, system, pinned, seen):
                    (workspace / 'example-visual.html').write_bytes(valid)
                    return [{'type': 'result', 'text': 'CHECK: passed'}]

                def check(*args, **kwargs):
                    if point == 'validation':
                        entered.set()
                        if not release.wait(5):
                            raise RuntimeError('validation barrier timed out')
                    return original_check(*args, **kwargs)

                def publish(*args, **kwargs):
                    entered.set()
                    return original_publish(*args, **kwargs)

                lock = reviews.LOCK if point == 'lock' else None
                if lock:
                    lock.acquire()
                try:
                    with patch.object(visuals, '_agent_events', side_effect=events), \
                         patch.object(visuals, 'checked_visual', side_effect=check), \
                         patch.object(visuals, 'publish_visual', side_effect=publish), \
                         patch.object(visuals.roles, 'agent_definition', return_value=(None, 'fixture')):
                        job = broker.submit('review.visual', {'slug': 'example'}, visuals.visual_work('example', None))
                        self.assertTrue(entered.wait(3), 'worker did not reach barrier')
                        if shutdown:
                            stopped, decisions = [], []
                            requested = threading.Event()
                            original_cancel = broker.cancel
                            def cancel(job_id):
                                decisions.append(original_cancel(job_id))
                                requested.set()
                                return decisions[-1]
                            with patch.object(broker, 'cancel', side_effect=cancel):
                                thread = threading.Thread(target=lambda: stopped.append(visuals.shutdown(broker, 5)))
                                thread.start()
                                self.assertTrue(requested.wait(3))
                            accepted = decisions[0]
                        else:
                            accepted = broker.cancel(job['job_id'])
                        if point == 'validation':
                            self.assertTrue(accepted)
                        release.set()
                        if lock:
                            lock.release()
                            lock = None
                        self.assertTrue(broker.wait_finished([job['job_id']], 5))
                        if shutdown:
                            thread.join(5)
                            self.assertEqual(stopped, [True])
                        status = broker.get(job['job_id'])['status']
                        if accepted:
                            self.assertEqual(status, 'cancelled')
                            self.assertEqual(self.visual.read_bytes(), b'old page')
                            self.assertEqual(self.sidecar.read_bytes(), b'old metadata')
                        else:
                            self.assertEqual(status, 'completed')
                            self.assertEqual(self.visual.read_bytes(), valid)
                finally:
                    release.set()
                    if lock:
                        lock.release()
