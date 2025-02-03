import logging
from enum import Enum
from typing import List, Dict, Optional
import os
import subprocess

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

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
        
    def is_ready(self) -> bool:
        """Check if all dependencies are completed and input files exist"""
        if not all(dep.status == JobStatus.COMPLETED for dep in self.dependencies):
            return False
        return all(os.path.exists(f) for f in self.input_files)

class PostProcessingWorkflow:
    """Main workflow class for genome post-processing pipeline"""
    
    def __init__(self, ticket_id: str, memory_multiplier: float = 1.0):
        self.ticket_id = ticket_id
        self.memory_multiplier = memory_multiplier
        self.jobs: Dict[str, Job] = {}
        
    def add_job(self, job: Job) -> None:
        """Add a job to the workflow"""
        self.jobs[job.name] = job
        
    def create_post_processing_jobs(self, input_paths: Dict[str, str], test_mode: bool = False) -> None:
        """Create the complete set of post-processing jobs based on Snakemake rules"""
        
        if not test_mode:
            # 1. Incorporate MT
            mt_job = Job(
                name="incorporate_mt",
                command=f"python scripts/incorporate_mt.py {input_paths['input_fasta']} {input_paths['mt_fasta']}",
                resources={"mem_mb": 5000 * self.memory_multiplier},
                input_files=[input_paths['input_fasta']],
                output_files=[input_paths['mt_incorporated_fasta']]
            )
            self.add_job(mt_job)

        if not test_mode:
            # 2. Combine haplotig files
            combine_job = Job(
                name="combine_haplotigs",
                command=f"python scripts/combine_post_processing_haplotig_files.py {input_paths['mt_incorporated_fasta']}",
                dependencies=[mt_job],
                resources={"mem_mb": 5000 * self.memory_multiplier},
                input_files=[input_paths['mt_incorporated_fasta']],
                output_files=[input_paths['combined_fasta']]
            )
            self.add_job(combine_job)

            # 3. Scrub assembly
            scrub_job = Job(
                name="scrub_assembly",
                command=f"python scripts/scrub_short_contigs.py --input {input_paths['combined_fasta']} --output {input_paths['scrubbed_fasta']}",
                dependencies=[combine_job],
                resources={"mem_mb": 5000 * self.memory_multiplier},
                input_files=[input_paths['combined_fasta']],
                output_files=[input_paths['scrubbed_fasta']]
            )
            self.add_job(scrub_job)

        # Core processing jobs (always included)

        # 1. Calculate lengths
        last_job = mt_job if not test_mode else None
        lengths_job = Job(
            name="fastalength_sorted",
            command=f"python scripts/sequence_length.py {input_paths['input_fasta']} | sort -nr > {input_paths['lengths_file']}",
            dependencies=[last_job] if last_job else [],
            resources={"mem_mb": 2000 * self.memory_multiplier},
            input_files=[input_paths['input_fasta']],
            output_files=[input_paths['lengths_file']]
        )
        self.add_job(lengths_job)

        # 2. Chromosome audit
        chr_audit_job = Job(
            name="chr_audit",
            command=f"python scripts/chromosome_audit.py {input_paths['input_fasta']} {input_paths['chr_list']}",
            dependencies=[last_job] if last_job else [],
            resources={"mem_mb": 2000 * self.memory_multiplier},
            input_files=[input_paths['input_fasta'], input_paths['chr_list']],
            output_files=[input_paths['chr_audit_out']]
        )
        self.add_job(chr_audit_job)

        # 3. Trim Ns
        trim_job = Job(
            name="trim_Ns",
            command=f"python scripts/trim_Ns.py {input_paths['input_fasta']} {input_paths['trim_out']}",
            dependencies=[last_job] if last_job else [],
            resources={"mem_mb": 5000 * self.memory_multiplier},
            input_files=[input_paths['input_fasta']],
            output_files=[input_paths['trim_out'], input_paths['trimmed_fasta']]
        )
        self.add_job(trim_job)

        if not test_mode:
            # Add remaining jobs for full pipeline mode
            clip_job = Job(
                name="clip_regions",
                command=f"python scripts/clip_regions.py {input_paths['trimmed_fasta']} {input_paths['trim_out']} {input_paths['final_fasta']}",
                dependencies=[trim_job],
                resources={"mem_mb": 5000 * self.memory_multiplier},
                input_files=[input_paths['trimmed_fasta'], input_paths['trim_out']],
                output_files=[input_paths['final_fasta']]
            )
            self.add_job(clip_job)

            stats_job = Job(
                name="gather_vgp_stats",
                command=f"python scripts/gather_vgp_stats.py {input_paths['final_fasta']}",
                dependencies=[clip_job],
                resources={"mem_mb": 10000 * self.memory_multiplier},
                input_files=[input_paths['final_fasta']],
                output_files=[input_paths['stats_out']]
            )
            self.add_job(stats_job)

            gfastats_job = Job(
                name="gfastats",
                command=f"scripts/gfastats {input_paths['final_fasta']} > {input_paths['gfastats_out']}",
                dependencies=[clip_job],
                resources={"mem_mb": 10000 * self.memory_multiplier},
                input_files=[input_paths['final_fasta']],
                output_files=[input_paths['gfastats_out']]
            )
            self.add_job(gfastats_job)

            submission_job = Job(
                name="submission_text",
                command=f"python scripts/submission_text_maker.py {input_paths['final_fasta']} {input_paths['chr_list']}",
                dependencies=[chr_audit_job, clip_job],
                resources={"mem_mb": 2000 * self.memory_multiplier},
                input_files=[input_paths['final_fasta'], input_paths['chr_list']],
                output_files=[input_paths['submission_text']]
            )
            self.add_job(submission_job)

            ready_job = Job(
                name="ready_files_for_submission",
                command=f"python scripts/ready_files_for_submission.py {self.ticket_id}",
                dependencies=[submission_job, stats_job, gfastats_job],
                resources={"mem_mb": 2000 * self.memory_multiplier},
                input_files=[input_paths['submission_text'], input_paths['stats_out'], input_paths['gfastats_out']],
                output_files=[input_paths['ready_flag']]
            )
            self.add_job(ready_job)

            upload_job = Job(
                name="upload_post_processing_results_to_jira",
                command=f"python scripts/upload_post_processing_results_to_jira.py {self.ticket_id}",
                dependencies=[ready_job],
                resources={"mem_mb": 2000 * self.memory_multiplier},
                input_files=[input_paths['ready_flag']],
                output_files=[input_paths['upload_complete']]
            )
            self.add_job(upload_job)

    def get_next_jobs(self) -> List[Job]:
        """Get list of jobs that are ready to run"""
        return [job for job in self.jobs.values() 
                if job.status == JobStatus.PENDING and job.is_ready()]
    
    def update_job_status(self, job_name: str, status: JobStatus) -> None:
        """Update status of a job"""
        if job_name in self.jobs:
            self.jobs[job_name].status = status
            logger.info(f"Job {job_name} status updated to {status.value}")

    def validate_workflow(self) -> bool:
        """Validate workflow configuration and dependencies"""
        for job in self.jobs.values():
            # Check command exists
            if not job.command:
                logger.error(f"Job {job.name} has no command")
                return False
            
            # Check circular dependencies
            visited = set()
            def check_circular(job_name: str, path: List[str]) -> bool:
                if job_name in path:
                    logger.error(f"Circular dependency detected: {' -> '.join(path + [job_name])}")
                    return False
                if job_name in visited:
                    return True
                visited.add(job_name)
                job = self.jobs[job_name]
                for dep in job.dependencies:
                    if not check_circular(dep.name, path + [job_name]):
                        return False
                return True
            
            if not check_circular(job.name, []):
                return False

        return True

    def run(self, job_manager) -> bool:
        """Execute the workflow using provided job manager"""
        logger.info(f"Starting workflow for ticket {self.ticket_id}")
        
        # Validate workflow before running
        if not self.validate_workflow():
            logger.error("Workflow validation failed")
            return False
        
        while True:
            next_jobs = self.get_next_jobs()
            if not next_jobs:
                # Check if all jobs completed or some failed
                if any(job.status == JobStatus.FAILED for job in self.jobs.values()):
                    logger.error("Workflow failed: some jobs failed to complete")
                    return False
                if all(job.status == JobStatus.COMPLETED for job in self.jobs.values()):
                    logger.info("Workflow completed successfully")
                    return True
                # If no jobs are ready but some are still running, wait for job manager
                if any(job.status == JobStatus.RUNNING for job in self.jobs.values()):
                    job_manager.monitor_jobs()
                    continue
                logger.error("Workflow deadlocked: no jobs ready but not all completed")
                return False
                    
            for job in next_jobs:
                try:
                    logger.info(f"Submitting job: {job.name}")
                    job_manager.submit_job(job)
                except Exception as e:
                    logger.error(f"Failed to submit job {job.name}: {e}")
                    return False
            
            # Monitor running jobs
            job_manager.monitor_jobs()

if __name__ == "__main__":
    # Example usage
    input_paths = {
        "input_fasta": "input.fa",
        "mt_fasta": "mt.fa",
        "mt_incorporated_fasta": "mt_incorporated.fa",
        "combined_fasta": "combined.fa",
        "scrubbed_fasta": "scrubbed.fa",
        "trim_out": "trim.out",
        "trimmed_fasta": "trimmed.fa",
        "final_fasta": "final.fa",
        "lengths_file": "lengths.txt",
        "chr_list": "chromosomes.csv",
        "chr_audit_out": "chr_audit.txt",
        "stats_out": "stats.txt",
        "gfastats_out": "gfastats.txt",
        "submission_text": "submission.txt",
        "ready_flag": "ready.flag",
        "upload_complete": "upload.complete"
    }
    
    workflow = PostProcessingWorkflow("GRIT-123")
    workflow.create_post_processing_jobs(input_paths)
    # Would need proper job manager instance in practice:
    # workflow.run(job_manager)