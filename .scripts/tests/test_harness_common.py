import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
import harness_common as common


class HarnessCommonTests(unittest.TestCase):
    def test_orca_executable_precedence(self):
        with patch.dict(os.environ, {'ORCA_CLI_COMMAND': '/custom/orca'}), \
                patch.object(common.sys, 'platform', 'linux'), patch.object(common.shutil, 'which', return_value='/bin/orca-ide'):
            self.assertEqual(common.orca_executable(), '/custom/orca')
        with patch.dict(os.environ, {}, clear=True), patch.object(common.sys, 'platform', 'linux'):
            with patch.object(common.shutil, 'which', return_value='/bin/orca-ide'):
                self.assertEqual(common.orca_executable(), 'orca-ide')
            with patch.object(common.shutil, 'which', return_value=None):
                self.assertEqual(common.orca_executable(), 'orca')
        with patch.dict(os.environ, {}, clear=True), patch.object(common.sys, 'platform', 'darwin'), \
                patch.object(common.shutil, 'which', return_value='/bin/orca-ide'):
            self.assertEqual(common.orca_executable(), 'orca')

    def test_resolve_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(common, 'omp_model_roles', return_value={'analysis': ' provider/first:high,provider/second '}) as roles:
                self.assertEqual(common.resolve_model('@analysis', root), 'provider/first:high')
                self.assertIsNone(common.resolve_model('@missing', root))
                self.assertEqual(common.resolve_model('provider/literal', root), 'provider/literal')
                self.assertIsNone(common.resolve_model(None, root))
                self.assertIsNone(common.resolve_model('', root))
                self.assertEqual(roles.call_count, 2)
                roles.assert_called_with(root)

    def test_local_settings_missing_invalid_and_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / '.research-harness-agent.json'
            self.assertEqual(common.local_settings(root), {})
            for invalid in ('{invalid', '[]', 'null'):
                path.write_text(invalid)
                self.assertEqual(common.local_settings(root), {})
            path.write_text('{"agent":"omp"}')
            self.assertEqual(common.local_settings(root), {'agent': 'omp'})


if __name__ == '__main__':
    unittest.main()
