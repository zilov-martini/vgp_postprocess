import subprocess
import logging
import time
from typing import List, Dict, Optional
from workflow import Job, JobStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LSFJobManager:
    """Job manager for LSF (Load Sharing Facility) batch system"""
    
    def __init__(self, default_queue: str = "normal"):
        self.default_queue = default_queue
        self.jobs: Dict[str, str] = {}  # job_name -> LSF job ID mapping
        
    def _format_bsub_command(self, job: Job) -> str:
        """Format the bsub command with appropriate resource requests"""
        cmd = ["bsub"]
        
        # Add memory request if specified
        if "mem_mb" in job.resources:
            cmd.extend(["-M", str(job.resources["mem_mb"])])
            
        # Add queue
        queue = job.resources.get("queue", self.default_queue)
        cmd.extend(["-q", queue])
        
        # Add job name
        cmd.extend(["-J", job.name])
        
        # Add output file
        cmd.extend(["-o", f"logs/{job.name}.out"])
        cmd.extend(["-e", f"logs/{job.name}.err"])
        
        # Add dependencies if any
        if job.dependencies:
            dep_string = " && ".join(f"done({self.jobs[dep.name]})" 
                                   for dep in job.dependencies 
                                   if dep.name in self.jobs)
            if dep_string:
                cmd.extend(["-w", dep_string])
        
        # Add the actual command
        cmd.append(job.command)
        
        return " ".join(cmd)
        
    def submit_job(self, job: Job) -> None:
        """Submit a job to LSF"""
        if not job.is_ready():
            raise ValueError(f"Job {job.name} is not ready to run")
            
        try:
            # Format and submit the bsub command
            cmd = self._format_bsub_command(job)
            logger.info(f"Submitting job: {cmd}")
            
            result = subprocess.run(cmd, shell=True, check=True,
                                 capture_output=True, text=True)
            
            # Extract job ID from bsub output (format: "Job <ID> is submitted")
            job_id = result.stdout.split("<")[1].split(">")[0]
            self.jobs[job.name] = job_id
            job.status = JobStatus.RUNNING
            
            logger.info(f"Job {job.name} submitted with ID {job_id}")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to submit job {job.name}: {e}")
            job.status = JobStatus.FAILED
            raise
            
    def monitor_jobs(self) -> None:
        """Monitor status of submitted jobs"""
        running_jobs = {name: job_id for name, job_id in self.jobs.items()}
        
        while running_jobs:
            try:
                # Use bjobs to check job status
                job_ids = " ".join(running_jobs.values())
                result = subprocess.run(f"bjobs -noheader {job_ids}",
                                     shell=True, capture_output=True, text=True)
                
                # Process each line of bjobs output
                for line in result.stdout.splitlines():
                    fields = line.split()
                    if len(fields) >= 3:
                        job_id, status = fields[0], fields[2]
                        
                        # Find job name by job ID
                        job_name = next(name for name, jid in running_jobs.items() 
                                      if jid == job_id)
                        
                        if status == "DONE":
                            logger.info(f"Job {job_name} completed successfully")
                            del running_jobs[job_name]
                        elif status == "EXIT":
                            logger.error(f"Job {job_name} failed")
                            del running_jobs[job_name]
                            
            except subprocess.CalledProcessError as e:
                logger.error(f"Error monitoring jobs: {e}")
                
            if running_jobs:
                time.sleep(30)  # Check every 30 seconds
                
    def kill_job(self, job_name: str) -> None:
        """Kill a running job"""
        if job_name in self.jobs:
            try:
                subprocess.run(f"bkill {self.jobs[job_name]}", 
                             shell=True, check=True)
                logger.info(f"Killed job {job_name}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to kill job {job_name}: {e}")
                
    def cleanup(self) -> None:
        """Clean up any remaining jobs"""
        for job_name in list(self.jobs.keys()):
            self.kill_job(job_name)
            
class LocalJobManager:
    """Job manager for running jobs locally (for testing)"""
    
    def submit_job(self, job: Job) -> None:
        """Run a job locally using subprocess"""
        if not job.is_ready():
            raise ValueError(f"Job {job.name} is not ready to run")
            
        try:
            logger.info(f"Running job locally: {job.name}")
            subprocess.run(job.command, shell=True, check=True)
            job.status = JobStatus.COMPLETED
            logger.info(f"Job {job.name} completed successfully")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Job {job.name} failed: {e}")
            job.status = JobStatus.FAILED
            raise
            
    def monitor_jobs(self) -> None:
        """No monitoring needed for local jobs"""
        pass
        
    def cleanup(self) -> None:
        """No cleanup needed for local jobs"""
        pass

if __name__ == "__main__":
    # Example usage
    manager = LSFJobManager()
    job = Job("test", "echo hello", resources={"mem_mb": 1000})
    manager.submit_job(job)
    manager.monitor_jobs()