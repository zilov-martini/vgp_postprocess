import argparse
import logging
import os
import sys
from typing import Dict, Any
from pathlib import Path

from workflow import PostProcessingWorkflow
from job_manager import LSFJobManager, LocalJobManager
from config.config_loader import ConfigLoader
from utils.env_checker import EnvironmentChecker

# Only import JIRA module when needed
def get_jira_module():
    try:
        import GritJiraIssue
        return GritJiraIssue
    except ImportError as e:
        if '--test_env' not in sys.argv:
            raise e
        return None

def setup_logging(config=None):
    """Configure logging based on configuration"""
    if config:
        logging_config = config.get_logging_config()
    else:
        # Default logging config for environment testing
        logging_config = {
            'level': 'INFO',
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            'file': 'pipeline/logs/pipeline.log'
        }
    
    # Create logs directory if it doesn't exist
    log_path = Path(logging_config['file']).parent
    log_path.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=logging_config['level'],
        format=logging_config['format'],
        handlers=[
            logging.FileHandler(logging_config['file']),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger(__name__)

def get_input_paths(jira_issue, config: ConfigLoader) -> Dict[str, str]:
    """Determine input and output paths based on JIRA ticket"""
    working_dir = jira_issue.get_curated_tolid_dir()
    if not os.path.isdir(working_dir):
        os.makedirs(working_dir)

    stems = jira_issue.get_final_stems()
    paths = {}
    
    # Define paths for primary assembly
    primary_stem = f"{stems[0]}.primary"
    paths.update({
        'input_fasta': f"{working_dir}/{primary_stem}.curated.fa",
        'output_fasta': f"{working_dir}/{primary_stem}.untrimmed.fa",
        'trim_out': f"{working_dir}/{primary_stem}.trim_Ns.out",
        'final_fasta': f"{working_dir}/{primary_stem}.final.fa",
        'chromosome_list': f"{working_dir}/{primary_stem}.chromosome.list.csv"
    })
    
    # Add paths for haplotigs if present
    if len(stems) > 1 and not jira_issue.yaml_key_is_true('no_assembly_haplotigs'):
        haplotig_stem = f"{stems[1]}.additional_haplotigs"
        paths.update({
            'haplotig_input': f"{working_dir}/{haplotig_stem}.curated.fa",
            'haplotig_output': f"{working_dir}/{haplotig_stem}.final.fa",
            'haplotig_chromosome_list': f"{working_dir}/{haplotig_stem}.chromosome.list.csv"
        })
    
    return paths

def validate_jira_ticket(jira_issue) -> None:
    """Validate JIRA ticket status and labels"""
    if 'abnormal_contamination_report' in jira_issue.get_labels():
        raise ValueError(
            'This ticket has an abnormal_contamination_report label set. '
            'Please address that report and remove the label before post-processing.'
        )

def test_environment() -> bool:
    """Run environment checks and report results"""
    logger = setup_logging()
    logger.info("Running environment checks...")
    
    # Initialize environment checker
    pipeline_root = Path(__file__).parent
    checker = EnvironmentChecker(pipeline_root)
    
    # Run all checks
    issues = checker.run_all_checks()
    
    # Print results
    checker.print_check_results(issues)
    
    return len(issues) == 0

def run_pipeline(args: argparse.Namespace) -> None:
    """Main pipeline execution function"""
    # Handle environment testing
    if args.test_env:
        sys.exit(0 if test_environment() else 1)

    # Load configuration
    config = ConfigLoader(args.config)
    logger = setup_logging(config)
    
    try:
        # Test environment before proceeding
        if not test_environment():
            raise RuntimeError("Environment check failed. Please fix the issues and try again.")

        # Import and initialize JIRA issue
        GritJiraIssue = get_jira_module()
        if not GritJiraIssue:
            raise ImportError("GritJiraIssue module is required for pipeline execution")
            
        jira_issue = GritJiraIssue.GritJiraIssue(args.ticket)
        validate_jira_ticket(jira_issue)
        
        # Get input/output paths
        input_paths = get_input_paths(jira_issue, config)
        
        # Initialize workflow
        workflow = PostProcessingWorkflow(
            ticket_id=args.ticket,
            memory_multiplier=args.memory_multiplier
        )
        
        # Create post-processing jobs
        workflow.create_post_processing_jobs(input_paths)
        
        # Initialize job manager
        job_manager = LSFJobManager(default_queue=config.default_queue) if not args.local else LocalJobManager()
        
        # Run workflow
        success = workflow.run(job_manager)
        
        if success:
            logger.info("Pipeline completed successfully")
            if 'post_processing_error' in jira_issue.get_labels():
                jira_issue.remove_label('post_processing_error')
        else:
            logger.error("Pipeline failed")
            jira_issue.add_label('post_processing_error')
            jira_issue.add_comment('Post processing failed')
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Pipeline failed with error: {str(e)}")
        if 'jira_issue' in locals():
            jira_issue.add_label('post_processing_error')
            jira_issue.add_comment(f'Post processing failed: {str(e)}')
        sys.exit(1)

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Post-processing pipeline")
    
    # Make ticket optional if running environment test
    parser.add_argument(
        "--ticket",
        type=str,
        help="JIRA ticket identifier (required unless running --test_env)",
    )
    parser.add_argument(
        "--memory-multiplier",
        type=float,
        default=1.0,
        help="Memory multiplier for job resources"
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to custom config file"
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Run jobs locally instead of submitting to LSF"
    )
    parser.add_argument(
        "--test_env",
        action="store_true",
        help="Test the environment for required dependencies and exit"
    )
    
    args = parser.parse_args()
    
    # Validate args
    if not args.test_env and not args.ticket:
        parser.error("--ticket is required unless running with --test_env")
    
    run_pipeline(args)

if __name__ == "__main__":
    main()