import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
import research_agent as agents
import install_research_harness as installer


class AgentOnboardingTests(unittest.TestCase):
    def test_auto_chooses_authenticated_agent(self):
        def probe(name):
            return {'agent': name, 'installed': True, 'ready': name == 'claude', 'authenticated': name == 'claude'}
        with tempfile.TemporaryDirectory() as directory, patch.object(agents, 'probe', side_effect=probe):
            root = Path(directory)
            self.assertEqual(agents.connect(root)['agent'], 'claude')
            self.assertEqual(json.loads((root / agents.CONFIG).read_text()), {'schema_version': '1.1', 'agent': 'claude'})
            self.assertEqual(agents.resolve(root)['agent'], 'claude')

    def test_auto_order_and_existing_orca_settings(self):
        for ready, expected in [({'codex', 'claude', 'omp'}, 'codex'),
                                ({'claude', 'omp'}, 'claude'), ({'omp'}, 'omp')]:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                config = {'schema_version': '1.0', 'agent': 'auto',
                          'orca': {'agent': 'omp', 'explorer_model': '@paper-analysis'},
                          'custom': {'retained': True}}
                (root / agents.CONFIG).write_text(json.dumps(config))
                def probe(name):
                    return {'agent': name, 'installed': True, 'authenticated': name in ready,
                            'ready': name in ready}
                with patch.object(agents, 'probe', side_effect=probe):
                    result = agents.connect(root)
                self.assertEqual(result['agent'], expected)
                self.assertEqual([item['agent'] for item in result['candidates']], ['codex', 'claude', 'omp'])
                self.assertEqual(json.loads((root / agents.CONFIG).read_text()),
                                 {**config, 'schema_version': '1.1', 'agent': expected})

    def test_legacy_argv_is_unchanged(self):
        stage, last = Path('/tmp/work'), Path('/tmp/out')
        with patch.object(agents.shutil, 'which', side_effect=lambda name: '/bin/' + name):
            self.assertEqual(agents.command('codex', stage, last, 'review'), [
                '/bin/codex', 'exec', '--skip-git-repo-check', '--cd', str(stage),
                '--sandbox', 'workspace-write', '-c', 'approval_policy="never"',
                '--output-last-message', str(last), 'review'])
            self.assertEqual(agents.command('claude', stage, last, 'review'), [
                '/bin/claude', '--print', '--output-format', 'text', '--restricted',
                '--permission-mode', 'dontAsk', '--tools', 'Read,Edit,Write,Bash,Glob,Grep,WebSearch,WebFetch',
                '--allowedTools', 'Read,Edit,Write,Bash,Glob,Grep,WebSearch,WebFetch',
                '--settings', '{"sandbox": {"enabled": true, "autoAllowBashIfSandboxed": true, "allowUnsandboxedCommands": false}}',
                '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}', 'review'])

    @unittest.skipIf(os.name == 'nt', 'Executable fixture uses Unix permissions')
    def test_omp_argv_with_and_without_role(self):
        import harness_common
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / 'omp'
            binary.write_text('#!/bin/sh\nexit 0\n')
            binary.chmod(0o755)
            stage = root / 'stage'
            for roles, model in [({'paper-analysis': 'provider/model'}, ['--model', '@paper-analysis']), ({}, [])]:
                with self.subTest(roles=roles), patch.dict(os.environ, {'PATH': str(root)}), \
                        patch.object(harness_common, 'omp_model_roles', return_value=roles), \
                        patch.object(agents, 'omp_model_roles', return_value=roles, create=True):
                    actual = agents.command('omp', stage, root / 'last', 'review', timeout_seconds=120, root=root)
                self.assertEqual(actual, [str(binary), '-p', '--no-session', '--no-title', '--no-extensions',
                                          *model, '--approval-mode', 'yolo', '--tools',
                                          'read,grep,glob,bash,edit,write,web_search', '--max-time', '120',
                                          f'@{stage}/.agents/skills/paper-review/SKILL.md', '--', 'review'])
            with patch.dict(os.environ, {'PATH': str(root)}), \
                    patch.object(agents, 'omp_model_roles', return_value={}):
                command = agents.command('omp', stage, root / 'last', 'review')
            self.assertNotIn('--max-time', command)
            self.assertNotIn('--model', command)

    def test_omp_probe_requires_version_and_a_model_selector(self):
        for version, models, expected in [(0, '[{"selector":"provider/model"}]', True),
                                          (1, '[{"selector":"provider/model"}]', False),
                                          (0, '[]', False), (0, '[{}]', False), (0, 'invalid', False)]:
            with self.subTest(version=version, models=models), \
                    patch.object(agents.shutil, 'which', return_value='/fake/omp'), \
                    patch.object(agents.subprocess, 'run', side_effect=[
                        subprocess.CompletedProcess([], version, stdout='', stderr=''),
                        subprocess.CompletedProcess([], 0, stdout=models, stderr='')]):
                result = agents.probe('omp')
            self.assertEqual(result['ready'], expected)
            self.assertEqual(result['login_command'], 'omp login')

    def test_explicit_choice_does_not_switch_accounts(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(agents, 'probe', return_value={'agent': 'claude', 'installed': True, 'ready': False}) as probe:
            self.assertFalse(agents.connect(Path(directory), 'claude')['ready'])
            probe.assert_called_once_with('claude')
            self.assertFalse((Path(directory) / agents.CONFIG).exists())

    def test_missing_cli_and_invalid_config(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(agents.shutil, 'which', return_value=None):
            root = Path(directory)
            self.assertFalse(agents.resolve(root)['ready'])
            (root / agents.CONFIG).write_text('{bad json')
            self.assertFalse(agents.resolve(root)['ready'])

    @unittest.skipIf(os.name == 'nt', 'Executable fixture uses a Unix shebang; Windows uses WSL setup')
    def test_fresh_user_install_connects_without_private_data(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); root = base / 'new repo'; root.mkdir(); bins = base / 'bin'; bins.mkdir()
            cli = bins / 'codex'
            cli.write_text('#!' + sys.executable + '\nimport sys\nif "--help" in sys.argv: print("help");sys.exit(0)\nif sys.argv[1:]==["login","status"]: sys.exit(0)\nsys.exit(2)\n')
            cli.chmod(0o755)
            operations, conflicts = installer.plan(root, ['codex', 'claude'], 'copy', 'preserve', 'papers')
            self.assertFalse(conflicts)
            installer.apply(root, operations, ['codex', 'claude'])
            env = {**os.environ, 'PATH': str(bins) + os.pathsep + '/usr/bin:/bin', 'HOME': str(base / 'new-user-home')}
            result = subprocess.run([sys.executable, str(root / '.scripts/bin/onboard_research.py'), '--connect-only'], cwd=root, env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads((root / agents.CONFIG).read_text())['agent'], 'codex')
            self.assertFalse(list((root / '01-Papers/library').glob('*.json')))
            self.assertFalse((root / '.mcp.json').exists())
            self.assertFalse((root / '.codex/auth.json').exists())
            check = subprocess.run([sys.executable, str(root / '.scripts/bin/verify_harness.py')], cwd=root, env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
            self.assertIn('0 records', result.stdout)

    def test_claude_adapter_uses_restricted_sandboxed_mode(self):
        with patch.object(agents.shutil, 'which', return_value='/user/bin/claude'):
            command = agents.command('claude', Path('/tmp/work'), Path('/tmp/out'), 'review')
        self.assertIn('--restricted', command)
        self.assertIn('dontAsk', command)
        self.assertNotIn('--dangerously-skip-permissions', command)
        settings = json.loads(command[command.index('--settings') + 1])
        self.assertFalse(settings['sandbox']['allowUnsandboxedCommands'])


if __name__ == '__main__':
    unittest.main()
