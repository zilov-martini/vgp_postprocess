import os
import sys
import shutil
import subprocess
import logging
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class EnvironmentChecker:
    def __init__(self, pipeline_root: Path, local_mode: bool = False, test_only: bool = False):
        self.pipeline_root = pipeline_root
        self.local_mode = local_mode
        self.test_only = test_only
        
        # Base executables needed regardless of mode
        self.required_executables = [
            'gfastats',
        ]
        
        # Add LSF executables only if not in local mode
        if not local_mode:
            self.required_executables.extend([
                'bsub',  # LSF
                'bjobs'  # LSF
            ])
            
        # Scripts needed for pipeline operation
        self.required_scripts = [
            'sequence_length.py',
            'incorporate_mt.py',
            'incorporate_mt_and_haps_for_post_processing.py',
            'combine_post_processing_haplotig_files.py',
            'chromosome_audit.py',
            'sum_chrs.pl',
            'ncbi_chr_file_to_ena_format.py',
            'submission_text_maker.py',
            'ready_files_for_submission.py',
            'upload_post_processing_results_to_jira.py'
        ]
        
        # Environment variables needed for full pipeline
        # Skip if just testing environment in local mode
        self.required_env_vars = [] if (local_mode and test_only) else [
            'JIRA_TOKEN',
            'JIRA_SERVER'
        ]
        
        # Python packages needed
        # Skip JIRA if just testing environment in local mode
        self.required_python_packages = ['yaml']
        if not (local_mode and test_only):
            self.required_python_packages.append('jira')

    def check_executables(self) -> List[str]:
        """Check if required executables are available in PATH or scripts directory"""
        missing = []
        scripts_dir = self.pipeline_root / 'scripts'
        
        for executable in self.required_executables:
            # First check in scripts directory
            if executable == 'gfastats' and (scripts_dir / executable).exists():
                # Make sure it's executable
                os.chmod(scripts_dir / executable, 0o755)
                continue
                
            # Then check in PATH
            if not shutil.which(executable):
                missing.append(executable)
        return missing

    def check_scripts(self) -> List[str]:
        """Check if required scripts exist in the pipeline scripts directory"""
        missing = []
        scripts_dir = self.pipeline_root / 'scripts'
        for script in self.required_scripts:
            if not (scripts_dir / script).exists():
                missing.append(script)
        return missing

    def check_env_vars(self) -> List[str]:
        """Check if required environment variables are set"""
        missing = []
        for var in self.required_env_vars:
            if not os.environ.get(var):
                missing.append(var)
        return missing

    def check_python_packages(self) -> List[str]:
        """Check if required Python packages are installed"""
        missing = []
        for package in self.required_python_packages:
            try:
                __import__(package)
            except ImportError:
                missing.append(package)
        return missing

    def check_lsf_access(self) -> Optional[str]:
        """Check if LSF is accessible and functioning"""
        if self.local_mode:
            return None
            
        try:
            subprocess.run(['bqueues'], capture_output=True, check=True)
            return None
        except subprocess.CalledProcessError as e:
            return f"LSF error: {str(e)}"
        except FileNotFoundError:
            return "LSF commands not found in PATH"

    def check_directory_structure(self) -> List[str]:
        """Check if required directories exist"""
        required_dirs = [
            'scripts',
            'config',
            'logs',
            'modules'
        ]
        missing = []
        for dir_name in required_dirs:
            if not (self.pipeline_root / dir_name).is_dir():
                missing.append(dir_name)
        return missing

    def run_all_checks(self) -> Dict[str, List[str]]:
        """Run all environment checks and return issues found"""
        issues = {}
        
        # Check executables
        missing_executables = self.check_executables()
        if missing_executables:
            issues['missing_executables'] = missing_executables

        # Check scripts
        missing_scripts = self.check_scripts()
        if missing_scripts:
            issues['missing_scripts'] = missing_scripts

        # Check environment variables
        missing_env_vars = self.check_env_vars()
        if missing_env_vars:
            issues['missing_env_vars'] = missing_env_vars

        # Check Python packages
        missing_packages = self.check_python_packages()
        if missing_packages:
            issues['missing_packages'] = missing_packages

        # Check LSF only if not in local mode
        if not self.local_mode:
            lsf_error = self.check_lsf_access()
            if lsf_error:
                issues['lsf_error'] = [lsf_error]

        # Check directory structure
        missing_dirs = self.check_directory_structure()
        if missing_dirs:
            issues['missing_directories'] = missing_dirs

        return issues

    def print_check_results(self, issues: Dict[str, List[str]]) -> None:
        """Print results of environment checks in a user-friendly format"""
        if not issues:
            logger.info("✓ Environment check passed! All dependencies are satisfied.")
            return

        logger.error("❌ Environment check failed! The following issues were found:\n")

        if 'missing_executables' in issues:
            logger.error("Missing executables (add to PATH):")
            for exe in issues['missing_executables']:
                logger.error(f"  - {exe}")

        if 'missing_scripts' in issues:
            logger.error("\nMissing pipeline scripts:")
            for script in issues['missing_scripts']:
                logger.error(f"  - {script}")

        if 'missing_env_vars' in issues:
            logger.error("\nMissing environment variables:")
            for var in issues['missing_env_vars']:
                logger.error(f"  - {var}")

        if 'missing_packages' in issues:
            logger.error("\nMissing Python packages (install with pip):")
            for package in issues['missing_packages']:
                logger.error(f"  - {package}")

        if 'lsf_error' in issues:
            logger.error("\nLSF issue detected:")
            logger.error(f"  {issues['lsf_error'][0]}")

        if 'missing_directories' in issues:
            logger.error("\nMissing directories:")
            for dir_name in issues['missing_directories']:
                logger.error(f"  - {dir_name}")

        logger.error("\nPlease resolve these issues before running the pipeline.")