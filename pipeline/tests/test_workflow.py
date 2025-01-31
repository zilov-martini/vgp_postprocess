import unittest
from unittest.mock import Mock, patch
from pipeline.workflow import Job, JobStatus, PostProcessingWorkflow

class TestJob(unittest.TestCase):
    def setUp(self):
        self.job = Job(
            name="test_job",
            command="echo test",
            resources={"mem_mb": 1000}
        )

    def test_job_initialization(self):
        self.assertEqual(self.job.name, "test_job")
        self.assertEqual(self.job.command, "echo test")
        self.assertEqual(self.job.resources, {"mem_mb": 1000})
        self.assertEqual(self.job.status, JobStatus.PENDING)
        self.assertEqual(self.job.dependencies, [])

    def test_is_ready_no_dependencies(self):
        self.assertTrue(self.job.is_ready())

    def test_is_ready_with_completed_dependency(self):
        dependency = Job("dep_job", "echo dep")
        dependency.status = JobStatus.COMPLETED
        self.job.dependencies = [dependency]
        
        self.assertTrue(self.job.is_ready())

    def test_is_ready_with_pending_dependency(self):
        dependency = Job("dep_job", "echo dep")
        dependency.status = JobStatus.PENDING
        self.job.dependencies = [dependency]
        
        self.assertFalse(self.job.is_ready())

    def test_is_ready_with_failed_dependency(self):
        dependency = Job("dep_job", "echo dep")
        dependency.status = JobStatus.FAILED
        self.job.dependencies = [dependency]
        
        self.assertFalse(self.job.is_ready())

class TestPostProcessingWorkflow(unittest.TestCase):
    def setUp(self):
        self.workflow = PostProcessingWorkflow(
            ticket_id="GRIT-123",
            memory_multiplier=1.0
        )
        self.mock_job_manager = Mock()

    def test_workflow_initialization(self):
        self.assertEqual(self.workflow.ticket_id, "GRIT-123")
        self.assertEqual(self.workflow.memory_multiplier, 1.0)
        self.assertEqual(len(self.workflow.jobs), 0)

    def test_add_job(self):
        job = Job("test_job", "echo test")
        self.workflow.add_job(job)
        
        self.assertEqual(len(self.workflow.jobs), 1)
        self.assertEqual(self.workflow.jobs["test_job"], job)

    def test_create_post_processing_jobs(self):
        input_paths = {
            "input_fasta": "input.fa",
            "output_fasta": "output.fa",
            "trim_out": "trim.out",
            "final_fasta": "final.fa"
        }
        
        self.workflow.create_post_processing_jobs(input_paths)
        
        # Verify core jobs were created
        self.assertIn("scrub_assembly", self.workflow.jobs)
        self.assertIn("trim_Ns", self.workflow.jobs)
        self.assertIn("clip_regions", self.workflow.jobs)
        
        # Verify job dependencies
        trim_job = self.workflow.jobs["trim_Ns"]
        self.assertEqual(len(trim_job.dependencies), 1)
        self.assertEqual(trim_job.dependencies[0].name, "scrub_assembly")
        
        clip_job = self.workflow.jobs["clip_regions"]
        self.assertEqual(len(clip_job.dependencies), 1)
        self.assertEqual(clip_job.dependencies[0].name, "trim_Ns")

    def test_get_next_jobs(self):
        # Add jobs with dependencies
        job1 = Job("job1", "echo 1")
        job2 = Job("job2", "echo 2", dependencies=[job1])
        job3 = Job("job3", "echo 3", dependencies=[job2])
        
        self.workflow.add_job(job1)
        self.workflow.add_job(job2)
        self.workflow.add_job(job3)
        
        # Initially only job1 should be ready
        next_jobs = self.workflow.get_next_jobs()
        self.assertEqual(len(next_jobs), 1)
        self.assertEqual(next_jobs[0].name, "job1")
        
        # After job1 completes, job2 should be ready
        job1.status = JobStatus.COMPLETED
        next_jobs = self.workflow.get_next_jobs()
        self.assertEqual(len(next_jobs), 1)
        self.assertEqual(next_jobs[0].name, "job2")

    def test_run_successful_workflow(self):
        # Create simple workflow
        job1 = Job("job1", "echo 1")
        job2 = Job("job2", "echo 2", dependencies=[job1])
        self.workflow.add_job(job1)
        self.workflow.add_job(job2)
        
        # Mock successful job execution
        def mock_submit(job):
            job.status = JobStatus.COMPLETED
        self.mock_job_manager.submit_job.side_effect = mock_submit
        
        # Run workflow
        success = self.workflow.run(self.mock_job_manager)
        
        self.assertTrue(success)
        self.assertEqual(self.mock_job_manager.submit_job.call_count, 2)
        self.assertEqual(job1.status, JobStatus.COMPLETED)
        self.assertEqual(job2.status, JobStatus.COMPLETED)

    def test_run_failed_workflow(self):
        job = Job("failing_job", "echo fail")
        self.workflow.add_job(job)
        
        # Mock failed job execution
        def mock_submit(job):
            job.status = JobStatus.FAILED
            raise Exception("Job failed")
        self.mock_job_manager.submit_job.side_effect = mock_submit
        
        # Run workflow
        success = self.workflow.run(self.mock_job_manager)
        
        self.assertFalse(success)
        self.assertEqual(job.status, JobStatus.FAILED)

if __name__ == '__main__':
    unittest.main()