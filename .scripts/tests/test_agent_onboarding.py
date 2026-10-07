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
            self.assertEqual(json.loads((root / agents.CONFIG).read_text()), {'schema_version': '1.0', 'agent': 'claude'})
            self.assertEqual(agents.resolve(root)['agent'], 'claude')

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
