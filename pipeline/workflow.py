import logging
from enum import Enum
from typing import List, Dict, Optional
import os
import subprocess
from pathlib import Path
import GritJiraIssue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class AssemblyType(Enum):
    """Assembly types supported by the pipeline"""
    STANDARD = "standard"  # Regular diploid assembly
    GENOMEARK = "genomeark"  # GenomeArk submission
    TEST = "test"  # Test mode
    TEST_HAPLOID = "test_haploid"  # Haploid test mode
    NO_CHR = "no_chr"  # No chromosome assembly
    NO_H = "no_h"  # No haplotigs
    NO_H_OR_CHR = "no_h_or_chr"  # No haplotigs or chromosomes

class PipelineError(Exception):
    """Base class for pipeline errors"""
    pass

class ValidationError(PipelineError):
    """Raised when workflow validation fails"""
    pass

class ExecutionError(PipelineError):
    """Raised when job execution fails"""
    pass

class Job:
    def __init__(self, name: str, command: str = None, dependencies: List['Job'] = None,
                 resources: Dict[str, int] = None, input_files: List[str] = None,
                 output_files: List[str] = None):
        self.name = name
        self.command = command
        self.dependencies = dependencies or []
        self.resources = resources or {}
        self.input_files = input_files or []
        self.output_files = output_files or []
        self.status = JobStatus.PENDING
        self.error_message: Optional[str] = None
        
    def is_ready(self) -> bool:
        """Check if all dependencies are completed and input files exist"""
        if not all(dep.status == JobStatus.COMPLETED for dep in self.dependencies):
            return False
        return all(os.path.exists(f) for f in self.input_files)

    def set_failed(self, message: str) -> None:
        """Mark job as failed with error message"""
        self.status = JobStatus.FAILED
        self.error_message = message

class PostProcessingWorkflow:
    """Main workflow class for genome post-processing pipeline"""
    
    def __init__(self, ticket_id: str, memory_multiplier: float = 1.0,
                 assembly_type: AssemblyType = AssemblyType.STANDARD):
        self.ticket_id = ticket_id
        self.memory_multiplier = memory_multiplier
        self.assembly_type = assembly_type
        self.jobs: Dict[str, Job] = {}
        self.working_dir = Path.cwd()
        self.initial_haplotig_suffix = 'additional_haplotigs'
        
        # Initialize JIRA integration
        try:
            self.jira_issue = GritJiraIssue.GritJiraIssue(ticket_id)
        except Exception as e:
            raise ValidationError(f"Failed to initialize JIRA: {str(e)}")
        
    def validate_setup(self) -> None:
        """Validate workflow setup before running"""
        # Check for abnormal contamination report
        if 'abnormal_contamination_report' in self.jira_issue.get_labels():
            raise ValidationError(
                "This ticket has an abnormal_contamination_report label set. "
                "Please address that report and remove the label before post-processing."
            )
        
        # Set haplotig suffix based on JIRA config
        if self.jira_issue.yaml_key_is_true('combine_for_curation'):
            self.initial_haplotig_suffix = 'all_haplotigs'
            
        # Update assembly type if scaffold level
        if 'scaffold_level' in self.jira_issue.get_labels():
            if self.assembly_type not in [AssemblyType.TEST, AssemblyType.TEST_HAPLOID]:
                self.assembly_type = AssemblyType.NO_CHR

    def validate_workflow(self) -> None:
        """Validate workflow configuration and dependencies"""
        # Check all jobs have commands
        for job in self.jobs.values():
            if not job.command:
                raise ValidationError(f"Job {job.name} has no command")
        
        # Check for circular dependencies
        visited = set()
        path: List[str] = []
        
        def check_circular(job_name: str) -> None:
            if job_name in path:
                cycle = ' -> '.join(path[path.index(job_name):] + [job_name])
                raise ValidationError(f"Circular dependency detected: {cycle}")
            if job_name in visited:
                return
            visited.add(job_name)
            path.append(job_name)
            job = self.jobs[job_name]
            for dep in job.dependencies:
                check_circular(dep.name)
            path.pop()
        
        for job_name in self.jobs:
            check_circular(job_name)

    def run(self, job_manager) -> None:
        """Execute the workflow using provided job manager"""
        logger.info(f"Starting workflow for ticket {self.ticket_id}")
        
        try:
            # Initial validation
            self.validate_setup()
            self.validate_workflow()
            
            # Main execution loop
            while True:
                # Get next batch of ready jobs
                next_jobs = self.get_next_jobs()
                
                if not next_jobs:
                    # Check for completion or failure
                    failed_jobs = [j for j in self.jobs.values() if j.status == JobStatus.FAILED]
                    if failed_jobs:
                        errors = '\n'.join(f"{j.name}: {j.error_message}" for j in failed_jobs)
                        raise ExecutionError(f"Workflow failed:\n{errors}")
                        
                    if all(j.status == JobStatus.COMPLETED for j in self.jobs.values()):
                        logger.info("Workflow completed successfully")
                        self._handle_success()
                        return
                        
                    if any(j.status == JobStatus.RUNNING for j in self.jobs.values()):
                        job_manager.monitor_jobs()
                        continue
                        
                    raise ExecutionError("Workflow deadlocked: no jobs ready but not all completed")
                
                # Submit ready jobs
                for job in next_jobs:
                    try:
                        logger.info(f"Submitting job: {job.name}")
                        job_manager.submit_job(job)
                    except Exception as e:
                        job.set_failed(str(e))
                        raise ExecutionError(f"Failed to submit job {job.name}: {str(e)}")
                
                # Monitor running jobs
                job_manager.monitor_jobs()
                
        except Exception as e:
            self._handle_failure(str(e))
            raise

    def _handle_success(self) -> None:
        """Handle successful workflow completion"""
        # Remove error label if present
        if 'post_processing_error' in self.jira_issue.get_labels():
            self.jira_issue.remove_label('post_processing_error')
            
        # Add completion comment
        self.jira_issue.add_comment('Post processing completed successfully')

    def _handle_failure(self, error_msg: str) -> None:
        """Handle workflow failure"""
        self.jira_issue.add_label('post_processing_error')
        self.jira_issue.add_comment(f'Post processing failed: {error_msg}')

    def get_next_jobs(self) -> List[Job]:
        """Get list of jobs that are ready to run"""
        return [job for job in self.jobs.values() 
                if job.status == JobStatus.PENDING and job.is_ready()]
    
    def update_job_status(self, job_name: str, status: JobStatus, error_msg: Optional[str] = None) -> None:
        """Update status of a job"""
        if job_name in self.jobs:
            job = self.jobs[job_name]
            job.status = status
            if error_msg and status == JobStatus.FAILED:
                job.error_message = error_msg
            logger.info(f"Job {job_name} status updated to {status.value}")

if __name__ == "__main__":
    # Example configurations for different assembly types
    configs = {
        "standard": {
            "type": AssemblyType.STANDARD,
            "ticket": "GRIT-123",
            "description": "Regular diploid assembly"
        },
        "haploid": {
            "type": AssemblyType.NO_H,
            "ticket": "GRIT-124",
            "description": "Haploid assembly"
        },
        "scaffold": {
            "type": AssemblyType.NO_CHR,
            "ticket": "GRIT-125",
            "description": "Scaffold-level assembly"
        },
        "test": {
            "type": AssemblyType.TEST,
            "ticket": "GRIT-270",
            "description": "Test mode"
        },
        "test_haploid": {
            "type": AssemblyType.TEST_HAPLOID,
            "ticket": "GRIT-352",
            "description": "Haploid test mode"
        }
    }
    
    # Example usage
    for name, config in configs.items():
        logger.info(f"\nTesting {name} configuration: {config['description']}")
        try:
            workflow = PostProcessingWorkflow(
                ticket_id=config['ticket'],
                assembly_type=config['type']
            )
            workflow.validate_setup()
            logger.info(f"{name} configuration validated successfully")
        except Exception as e:
            logger.error(f"{name} configuration validation failed: {str(e)}")