import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
import harness_common
import research_todo as todo


class ResearchTodoTests(unittest.TestCase):
    def dispatch(self, root, settings):
        root = root.resolve()
        brief = root / 'idea.md'
        brief.write_text('test brief', encoding='utf-8')
        task = {'idea_path': 'idea.md', 'brief_sha256': todo.sha(brief), 'task_id': 'task1',
                'question': 'question', 'budget': {}, 'dispatches': [], 'attempts': 0}
        calls = []
        def run(argv, **kwargs):
            calls.append(argv)
            if argv[1:2] == ['status']:
                result = {'runtime': {'state': 'ready'}}
            elif argv[1:3] == ['worktree', 'current']:
                result = {'worktree': {'path': str(root)}}
            elif argv[1:3] == ['orchestration', 'run-create']:
                result = {'runId': 'run1'}
            else:
                number = sum(call[1:3] == ['orchestration', 'worker-start'] for call in calls)
                result = {'dispatchId': f'd{number}', 'taskId': f't{number}'}
            return SimpleNamespace(returncode=0, stdout=json.dumps({'result': result}), stderr='')
        settings_path = root / '.research-harness-agent.json'
        if settings is not None:
            settings_path.write_text(json.dumps(settings))
        with patch.object(todo, 'ROOT', root), patch.object(todo.shutil, 'which', return_value='/fake/orca'), \
                patch.object(harness_common, 'orca_executable', return_value='/fake/orca'), \
                patch.object(harness_common, 'omp_model_roles', return_value={
                    'paper-analysis': 'provider/explorer:high,provider/fallback',
                    'paper-critique': 'provider/verifier:high'}), \
                patch.object(todo, 'prompt_for', side_effect=lambda task, role: 'prompt:' + role), \
                patch.object(todo.subprocess, 'run', side_effect=run):
            todo.dispatch_orca(task, {'tasks': [task]}, root / 'queue.json')
        return task, [call for call in calls if call[1:3] == ['orchestration', 'worker-start']]

    def test_default_worker_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            task, calls = self.dispatch(Path(directory), None)
        self.assertEqual(len(calls), 4)
        for call in calls:
            self.assertEqual(call[:9], ['/fake/orca', 'orchestration', 'worker-start', '--run', 'run1',
                                        '--worktree', 'current', '--agent', 'codex'])
            self.assertNotIn('--model', call)
            self.assertNotIn('--effort', call)
            self.assertEqual(call[-1], '--json')
        self.assertEqual(task['dispatches'][0]['agent'], 'codex')

    def test_omp_worker_arguments_resolve_each_role_without_effort(self):
        with tempfile.TemporaryDirectory() as directory:
            task, calls = self.dispatch(Path(directory), {'orca': {'agent': 'omp',
                'explorer_model': '@paper-analysis', 'verifier_model': '@paper-critique', 'effort': 'high'}})
        self.assertEqual(len(calls), 4)
        for index, call in enumerate(calls):
            self.assertEqual(call[call.index('--agent') + 1], 'omp')
            self.assertEqual(call[call.index('--model') + 1],
                             'provider/explorer:high' if index < 3 else 'provider/verifier:high')
            self.assertNotIn('--effort', call)
        self.assertEqual(task['dispatches'][0]['models'], {'explorer': 'provider/explorer:high', 'verifier': 'provider/verifier:high'})

    def test_exit_one_json_is_preserved_without_relaunch(self):
        failure = {'ok': False, 'stage': 'setup', 'failedStage': 'launch',
                   'setup': {'detail': 'failure evidence'}, 'effects': ['created'], 'residualResources': ['worker-1']}
        response = SimpleNamespace(returncode=1, stdout=json.dumps(failure), stderr='unrelated stderr')
        with patch.object(harness_common, 'orca_executable', return_value='/fake/orca'), \
                patch.object(todo.subprocess, 'run', return_value=response) as run:
            with self.assertRaises(RuntimeError) as error:
                todo.orca_json(['orchestration', 'worker-start'])
        run.assert_called_once()
        message = str(error.exception)
        for key in ('setup', 'launch', 'failure evidence', 'created', 'worker-1'):
            self.assertIn(key, message)

    def test_worker_start_failures_persist_and_do_not_advance_or_relaunch(self):
        for failure_number, outcome in ((1, "failed"), (2, "outcome_unknown")):
            with self.subTest(failure_number=failure_number), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                brief = root / "idea.md"
                brief.write_text("test brief", encoding="utf-8")
                task = {"idea_path": "idea.md", "brief_sha256": todo.sha(brief), "task_id": "task1",
                        "question": "question", "budget": {}, "dispatches": [], "attempts": 0,
                        "status": "queued", "logs": [], "partial_results": [], "result_path": "result.md"}
                queue = {"tasks": [task]}
                queue_path = root / "queue.json"
                calls = []
                failure = {"ok": False, "outcome": outcome, "failedStage": "launch",
                           "effects": ["worker-may-exist"], "residualResources": ["inspect-run"]}
                def run(argv, **kwargs):
                    calls.append(argv)
                    if argv[1:2] == ["status"]:
                        result = {"runtime": {"state": "ready"}}
                    elif argv[1:3] == ["worktree", "current"]:
                        result = {"worktree": {"path": str(root)}}
                    elif argv[1:3] == ["orchestration", "run-create"]:
                        result = {"runId": "run1"}
                    elif argv[1:3] == ["orchestration", "worker-start"]:
                        number = sum(call[1:3] == ["orchestration", "worker-start"] for call in calls)
                        if number == failure_number:
                            return SimpleNamespace(returncode=1, stdout=json.dumps(failure), stderr="")
                        result = {"dispatchId": f"d{number}", "taskId": f"t{number}"}
                    else:
                        result = {"workers": [{"dispatchId": f"d{number}", "projection": {"outcome": "success"}}
                                              for number in range(1, failure_number)]}
                    return SimpleNamespace(returncode=0, stdout=json.dumps({"result": result}), stderr="")
                with patch.object(todo, "ROOT", root), patch.object(todo.shutil, "which", return_value="/fake/orca"), \
                        patch.object(harness_common, "orca_executable", return_value="/fake/orca"), \
                        patch.object(todo, "prompt_for", return_value="fixture prompt"), \
                        patch.object(todo.subprocess, "run", side_effect=run):
                    with self.assertRaises(RuntimeError):
                        todo.dispatch_orca(task, queue, queue_path)
                    persisted = json.loads(queue_path.read_text(encoding="utf-8"))["tasks"][0]
                    self.assertEqual(persisted["status"], "failed" if outcome == "failed" else "needs_input")
                    self.assertEqual(persisted["dispatches"][-1]["state"],
                                     "failed" if outcome == "failed" else "uncertain")
                    self.assertIn("inspect-run", json.dumps(persisted))
                    try:
                        todo.sync_orca(persisted)
                    except RuntimeError:
                        pass
                self.assertNotEqual(persisted["status"], "verifying")
                starts = [call for call in calls if call[1:3] == ["orchestration", "worker-start"]]
                self.assertEqual(len(starts), failure_number)

    def test_sync_requires_all_four_successful_roles(self):
        roles = ("solution_search", "reference_trace", "counterevidence", "evidence_verifier")
        with tempfile.TemporaryDirectory() as directory, patch.object(todo, "ROOT", Path(directory).resolve()):
            for count in range(5):
                with self.subTest(count=count):
                    workers = [{"role": role, "dispatch_id": f"d{index}", "orca_task_id": f"t{index}"}
                               for index, role in enumerate(roles[:count])]
                    task = {"status": "running", "budget": {}, "logs": [], "partial_results": [],
                            "result_path": "result.md", "dispatches": [{"run_id": "run1",
                            "started_at": todo.now(), "workers": workers}]}
                    observations = [{"dispatchId": f"d{index}", "projection": {"outcome": "success"}}
                                    for index in range(count)]
                    with patch.object(todo, "orca_json", return_value={"workers": observations}):
                        try:
                            todo.sync_orca(task)
                        except RuntimeError:
                            pass
                    self.assertEqual(task["status"] == "verifying", count == 4)

    def test_sync_rejects_duplicate_roles(self):
        roles = ("solution_search", "reference_trace", "counterevidence", "counterevidence")
        workers = [{"role": role, "dispatch_id": f"d{index}", "orca_task_id": f"t{index}"}
                   for index, role in enumerate(roles)]
        task = {"status": "running", "dispatches": [{"run_id": "run1", "workers": workers}]}
        with patch.object(todo, "orca_json") as call, self.assertRaises(RuntimeError):
            todo.sync_orca(task)
        call.assert_not_called()
        self.assertNotEqual(task["status"], "verifying")


if __name__ == '__main__':
    unittest.main()
