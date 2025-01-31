import unittest
from unittest.mock import Mock, patch
import subprocess
from pipeline.job_manager import LSFJobManager, LocalJobManager
from pipeline.workflow import Job, JobStatus

class TestLSFJobManager(unittest.TestCase):
    def setUp(self):
        self.manager = LSFJobManager(default_queue="normal")
        self.job = Job(
            name="test_job",
            command="echo 'test'",
            resources={"mem_mb": 1000}
        )

    @patch('subprocess.run')
    def test_submit_job_success(self, mock_run):
        # Mock successful job submission
        mock_run.return_value.stdout = "Job <123> is submitted to queue <normal>"
        mock_run.return_value.stderr = ""
        
        self.manager.submit_job(self.job)
        
        # Verify job was submitted with correct parameters
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        self.assertIn("-M 1000", cmd)
        self.assertIn("-q normal", cmd)
        self.assertIn("-J test_job", cmd)
        
        # Verify job status was updated
        self.assertEqual(self.job.status, JobStatus.RUNNING)
        self.assertEqual(self.manager.jobs["test_job"], "123")

    @patch('subprocess.run')
    def test_submit_job_failure(self, mock_run):
        # Mock failed job submission
        mock_run.side_effect = subprocess.CalledProcessError(1, "bsub", "Error")
        
        with self.assertRaises(subprocess.CalledProcessError):
            self.manager.submit_job(self.job)
            
        self.assertEqual(self.job.status, JobStatus.FAILED)

    @patch('subprocess.run')
    def test_monitor_jobs(self, mock_run):
        # Setup job in monitoring state
        self.manager.jobs["test_job"] = "123"
        self.job.status = JobStatus.RUNNING
        
        # Mock bjobs output for completed job
        mock_run.return_value.stdout = "123 user normal DONE"
        
        self.manager.monitor_jobs()
        
        # Verify bjobs was called correctly
        mock_run.assert_called_with(
            "bjobs -noheader 123",
            shell=True,
            capture_output=True,
            text=True
        )

    def test_kill_job(self):
        self.manager.jobs["test_job"] = "123"
        
        with patch('subprocess.run') as mock_run:
            self.manager.kill_job("test_job")
            mock_run.assert_called_with(
                "bkill 123",
                shell=True,
                check=True
            )

class TestLocalJobManager(unittest.TestCase):
    def setUp(self):
        self.manager = LocalJobManager()
        self.job = Job(
            name="test_job",
            command="echo 'test'",
            resources={"mem_mb": 1000}
        )

    @patch('subprocess.run')
    def test_submit_job_success(self, mock_run):
        self.manager.submit_job(self.job)
        
        # Verify command was run
        mock_run.assert_called_with(
            "echo 'test'",
            shell=True,
            check=True
        )
        
        # Verify job status was updated
        self.assertEqual(self.job.status, JobStatus.COMPLETED)

    @patch('subprocess.run')
    def test_submit_job_failure(self, mock_run):
        # Mock command failure
        mock_run.side_effect = subprocess.CalledProcessError(1, "cmd", "Error")
        
        with self.assertRaises(subprocess.CalledProcessError):
            self.manager.submit_job(self.job)
            
        self.assertEqual(self.job.status, JobStatus.FAILED)

    def test_not_ready_job(self):
        # Create job with unmet dependencies
        dependency = Job("dep_job", "echo 'dep'")
        self.job.dependencies = [dependency]
        
        with self.assertRaises(ValueError):
            self.manager.submit_job(self.job)

if __name__ == '__main__':
    unittest.main()