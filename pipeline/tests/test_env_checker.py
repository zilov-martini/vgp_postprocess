import unittest
from unittest.mock import patch, Mock
import os
import sys
import shutil
from pathlib import Path

from pipeline.utils.env_checker import EnvironmentChecker

class TestEnvironmentChecker(unittest.TestCase):
    def setUp(self):
        self.pipeline_root = Path("/test/pipeline")
        self.checker = EnvironmentChecker(self.pipeline_root)

    @patch('shutil.which')
    def test_check_executables(self, mock_which):
        # Test when all executables are found
        mock_which.return_value = "/usr/bin/test"
        missing = self.checker.check_executables()
        self.assertEqual(len(missing), 0)

        # Test when some executables are missing
        mock_which.side_effect = lambda x: None if x == "gfastats" else "/usr/bin/test"
        missing = self.checker.check_executables()
        self.assertEqual(len(missing), 1)
        self.assertIn("gfastats", missing)

    @patch('pathlib.Path.exists')
    def test_check_scripts(self, mock_exists):
        # Test when all scripts exist
        mock_exists.return_value = True
        missing = self.checker.check_scripts()
        self.assertEqual(len(missing), 0)

        # Test when some scripts are missing
        mock_exists.side_effect = lambda: False
        missing = self.checker.check_scripts()
        self.assertTrue(len(missing) > 0)

    def test_check_env_vars(self):
        # Save original environment
        orig_env = os.environ.copy()
        
        try:
            # Test when variables are set
            os.environ['JIRA_TOKEN'] = 'test_token'
            os.environ['JIRA_SERVER'] = 'test_server'
            missing = self.checker.check_env_vars()
            self.assertEqual(len(missing), 0)

            # Test when variables are missing
            del os.environ['JIRA_TOKEN']
            missing = self.checker.check_env_vars()
            self.assertEqual(len(missing), 1)
            self.assertIn('JIRA_TOKEN', missing)
        
        finally:
            # Restore original environment
            os.environ.clear()
            os.environ.update(orig_env)

    @patch('importlib.import_module')
    def test_check_python_packages(self, mock_import):
        # Test when all packages are available
        mock_import.return_value = Mock()
        missing = self.checker.check_python_packages()
        self.assertEqual(len(missing), 0)

        # Test when some packages are missing
        mock_import.side_effect = ImportError()
        missing = self.checker.check_python_packages()
        self.assertTrue(len(missing) > 0)

    @patch('subprocess.run')
    def test_check_lsf_access(self, mock_run):
        # Test when LSF is accessible
        mock_run.return_value.returncode = 0
        error = self.checker.check_lsf_access()
        self.assertIsNone(error)

        # Test when LSF command fails
        mock_run.side_effect = FileNotFoundError()
        error = self.checker.check_lsf_access()
        self.assertIsNotNone(error)
        self.assertIn("LSF commands not found", error)

    @patch('pathlib.Path.is_dir')
    def test_check_directory_structure(self, mock_is_dir):
        # Test when all directories exist
        mock_is_dir.return_value = True
        missing = self.checker.check_directory_structure()
        self.assertEqual(len(missing), 0)

        # Test when directories are missing
        mock_is_dir.return_value = False
        missing = self.checker.check_directory_structure()
        self.assertTrue(len(missing) > 0)

    @patch('pipeline.utils.env_checker.EnvironmentChecker.check_executables')
    @patch('pipeline.utils.env_checker.EnvironmentChecker.check_scripts')
    @patch('pipeline.utils.env_checker.EnvironmentChecker.check_env_vars')
    @patch('pipeline.utils.env_checker.EnvironmentChecker.check_python_packages')
    @patch('pipeline.utils.env_checker.EnvironmentChecker.check_lsf_access')
    @patch('pipeline.utils.env_checker.EnvironmentChecker.check_directory_structure')
    def test_run_all_checks(
        self, mock_dirs, mock_lsf, mock_pkgs, 
        mock_env, mock_scripts, mock_execs
    ):
        # Test when everything passes
        mock_execs.return_value = []
        mock_scripts.return_value = []
        mock_env.return_value = []
        mock_pkgs.return_value = []
        mock_lsf.return_value = None
        mock_dirs.return_value = []

        issues = self.checker.run_all_checks()
        self.assertEqual(len(issues), 0)

        # Test when there are issues
        mock_execs.return_value = ["gfastats"]
        mock_env.return_value = ["JIRA_TOKEN"]
        mock_lsf.return_value = "LSF error"

        issues = self.checker.run_all_checks()
        self.assertEqual(len(issues), 3)
        self.assertIn("missing_executables", issues)
        self.assertIn("missing_env_vars", issues)
        self.assertIn("lsf_error", issues)

if __name__ == '__main__':
    unittest.main()