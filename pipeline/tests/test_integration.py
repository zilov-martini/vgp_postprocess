import unittest
import os
import shutil
import tempfile
from pathlib import Path
import yaml

from pipeline.config.config_loader import ConfigLoader
from pipeline.job_manager import LocalJobManager
from pipeline.workflow import PostProcessingWorkflow

class TestPipelineIntegration(unittest.TestCase):
    def setUp(self):
        # Create temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.test_dir))
        
        # Create test config
        self.config_path = os.path.join(self.test_dir, "test_config.yaml")
        self.create_test_config()
        
        # Create test input files
        self.create_test_files()
        
        # Initialize workflow
        self.workflow = PostProcessingWorkflow(
            ticket_id="TEST-123",
            memory_multiplier=1.0
        )
    
    def create_test_config(self):
        config = {
            "ticket": "TEST-123",
            "species_name": "test_species",
            "prefix": "test",
            "memory_multiplier": 1.0,
            "default_queue": "normal",
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "file": os.path.join(self.test_dir, "pipeline.log")
            }
        }
        
        with open(self.config_path, 'w') as f:
            yaml.dump(config, f)
    
    def create_test_files(self):
        # Create test FASTA file
        with open(os.path.join(self.test_dir, "input.fa"), 'w') as f:
            f.write(">seq1\nACGT\n>seq2\nTGCA\n")
            
        # Create test chromosome list
        with open(os.path.join(self.test_dir, "chr.list"), 'w') as f:
            f.write("1,seq1\n2,seq2\n")
    
    def test_single_task_execution(self):
        """Test execution of a single task"""
        # Create simple task that copies a file
        input_file = os.path.join(self.test_dir, "input.fa")
        output_file = os.path.join(self.test_dir, "output.fa")
        
        job = self.workflow.create_job(
            name="copy_file",
            command=f"cp {input_file} {output_file}",
            resources={"mem_mb": 1000}
        )
        self.workflow.add_job(job)
        
        # Run with local job manager
        job_manager = LocalJobManager()
        success = self.workflow.run(job_manager)
        
        # Verify execution
        self.assertTrue(success)
        self.assertTrue(os.path.exists(output_file))
        with open(input_file) as f1, open(output_file) as f2:
            self.assertEqual(f1.read(), f2.read())
    
    def test_dependent_tasks(self):
        """Test execution of dependent tasks"""
        # Create chain of tasks that process a file
        input_file = os.path.join(self.test_dir, "input.fa")
        temp_file = os.path.join(self.test_dir, "temp.fa")
        final_file = os.path.join(self.test_dir, "final.fa")
        
        # Task 1: Copy input to temp
        job1 = self.workflow.create_job(
            name="task1",
            command=f"cp {input_file} {temp_file}",
            resources={"mem_mb": 1000}
        )
        
        # Task 2: Copy temp to final
        job2 = self.workflow.create_job(
            name="task2",
            command=f"cp {temp_file} {final_file}",
            resources={"mem_mb": 1000},
            dependencies=[job1]
        )
        
        self.workflow.add_job(job1)
        self.workflow.add_job(job2)
        
        # Run workflow
        job_manager = LocalJobManager()
        success = self.workflow.run(job_manager)
        
        # Verify execution
        self.assertTrue(success)
        self.assertTrue(os.path.exists(final_file))
        with open(input_file) as f1, open(final_file) as f2:
            self.assertEqual(f1.read(), f2.read())
    
    def test_error_handling(self):
        """Test handling of task failures"""
        # Create task with invalid command
        job = self.workflow.create_job(
            name="failing_task",
            command="invalid_command",
            resources={"mem_mb": 1000}
        )
        self.workflow.add_job(job)
        
        # Run workflow
        job_manager = LocalJobManager()
        success = self.workflow.run(job_manager)
        
        # Verify failure handling
        self.assertFalse(success)
        self.assertEqual(job.status, "FAILED")
    
    def test_basic_post_processing(self):
        """Test basic post-processing workflow"""
        input_paths = {
            "input_fasta": os.path.join(self.test_dir, "input.fa"),
            "output_fasta": os.path.join(self.test_dir, "output.fa"),
            "trim_out": os.path.join(self.test_dir, "trim.out"),
            "final_fasta": os.path.join(self.test_dir, "final.fa"),
            "chromosome_list": os.path.join(self.test_dir, "chr.list")
        }
        
        # Create post-processing jobs
        self.workflow.create_post_processing_jobs(input_paths)
        
        # Run with local job manager (will use echo instead of real commands)
        job_manager = LocalJobManager()
        success = self.workflow.run(job_manager)
        
        # Verify basic workflow completion
        self.assertTrue(success)
        for job in self.workflow.jobs.values():
            self.assertEqual(job.status, "COMPLETED")

if __name__ == '__main__':
    unittest.main()