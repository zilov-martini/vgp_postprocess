import yaml
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ConfigurationError(Exception):
    """Custom exception for configuration errors"""
    pass

class ConfigLoader:
    """Load and manage pipeline configuration"""
    
    REQUIRED_FIELDS = [
        'assembly_path',
        'species_name',
        'prefix'
    ]

    LSF_DEFAULTS = {
        'lsf': {
            'default_queue': 'normal',
            'log_directory': 'pipeline/logs/lsf',
            'memory_units': 'MB',
            'default_memory': '4000',
            'default_threads': 1,
            'rusage_memory_units': 'MB',
            'latency_wait': 5,
            'resubmit_on_fail': True
        }
    }
    
    DEFAULT_CONFIG = {
        'memory_multiplier': 1.0,
        'default_queue': 'normal',
        'retry_attempts': 3,
        'logging': {
            'level': 'INFO',
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            'file': 'pipeline/logs/pipeline.log'
        },
        'resources': {
            'scrub_assembly': {'mem_mb': 5000},
            'trim_Ns': {'mem_mb': 5000},
            'clip_regions': {'mem_mb': 5000},
            'sum_chrs': {'mem_mb': 10000},
            'gather_vgp_stats': {'mem_mb': 10000},
            'gfastats': {'mem_mb': 10000}
        },
        'paths': {
            'scripts_dir': 'pipeline/scripts',
            'output_dir': 'output',
            'logs_dir': 'pipeline/logs',
            'temp_dir': 'pipeline/temp'
        }
    }

    def __init__(self, config_path: Optional[str] = None, lsf_profile_path: Optional[str] = None):
        """Initialize configuration with optional custom config and LSF profile files"""
        # Start with default configuration
        self.config = self.DEFAULT_CONFIG.copy()
        self._deep_update(self.config, self.LSF_DEFAULTS)
        
        # Load custom configuration if provided
        if config_path:
            self._load_custom_config(config_path)
            
        # Load LSF profile if provided
        if lsf_profile_path:
            self._load_lsf_profile(lsf_profile_path)
            
        # Validate configuration
        self._validate_config()
            
        # Ensure directories exist
        self._create_directories()
            
    def _load_custom_config(self, config_path: str) -> None:
        """Load custom configuration from YAML file"""
        try:
            with open(config_path) as f:
                custom_config = yaml.safe_load(f)
            
            if not isinstance(custom_config, dict):
                raise ConfigurationError("Configuration file must contain a YAML dictionary")
            
            # Deep update of configuration
            self._deep_update(self.config, custom_config)
            
        except Exception as e:
            logger.error(f"Failed to load custom config from {config_path}: {e}")
            raise
            
    def _load_lsf_profile(self, profile_path: str) -> None:
        """Load LSF profile configuration"""
        try:
            with open(profile_path) as f:
                lsf_config = yaml.safe_load(f)
                
            if not isinstance(lsf_config, dict):
                raise ConfigurationError("LSF profile must contain a YAML dictionary")
                
            # Update LSF configuration
            if 'lsf' not in self.config:
                self.config['lsf'] = {}
            self._deep_update(self.config['lsf'], lsf_config)
            
        except Exception as e:
            logger.error(f"Failed to load LSF profile from {profile_path}: {e}")
            raise
            
    def _validate_config(self) -> None:
        """Validate configuration completeness and correctness"""
        missing_fields = [
            field for field in self.REQUIRED_FIELDS
            if field not in self.config
        ]
        
        if missing_fields:
            raise ConfigurationError(
                f"Missing required configuration fields: {', '.join(missing_fields)}"
            )
            
        # Validate paths
        for path_key, path in self.config['paths'].items():
            if not isinstance(path, str):
                raise ConfigurationError(
                    f"Invalid path configuration for {path_key}: must be a string"
                )
                
    def _create_directories(self) -> None:
        """Create necessary directories"""
        directories = [
            self.output_dir,
            self.logs_dir,
            self.config['paths'].get('temp_dir', 'pipeline/temp'),
            self.config['lsf'].get('log_directory', 'pipeline/logs/lsf')
        ]
        
        for dir_path in directories:
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            
    def _deep_update(self, base_dict: Dict, update_dict: Dict) -> None:
        """Recursively update a dictionary"""
        for key, value in update_dict.items():
            if (
                key in base_dict 
                and isinstance(base_dict[key], dict) 
                and isinstance(value, dict)
            ):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value
                
    def get_resource_config(self, job_name: str) -> Dict[str, Any]:
        """Get resource configuration for a specific job"""
        base_resources = self.config['resources'].get(job_name, {}).copy()
        
        # Apply memory multiplier
        if 'mem_mb' in base_resources:
            base_resources['mem_mb'] = int(
                base_resources['mem_mb'] * self.config['memory_multiplier']
            )
            
        return base_resources
        
    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration"""
        return self.config['logging']
        
    @property
    def memory_multiplier(self) -> float:
        """Get memory multiplier"""
        return float(self.config['memory_multiplier'])
        
    @property
    def default_queue(self) -> str:
        """Get default queue name"""
        return str(self.config['default_queue'])
        
    @property
    def retry_attempts(self) -> int:
        """Get number of retry attempts"""
        return int(self.config['retry_attempts'])
        
    @property
    def scripts_dir(self) -> str:
        """Get scripts directory path"""
        return str(self.config['paths']['scripts_dir'])
        
    @property
    def output_dir(self) -> str:
        """Get output directory path"""
        return str(self.config['paths']['output_dir'])
        
    @property
    def logs_dir(self) -> str:
        """Get logs directory path"""
        return str(self.config['paths']['logs_dir'])
        
    @property
    def temp_dir(self) -> str:
        """Get temporary directory path"""
        return str(self.config['paths'].get('temp_dir', 'pipeline/temp'))

    # LSF Configuration Properties
    @property
    def lsf_queue(self) -> str:
        """Get LSF queue name"""
        return str(self.config['lsf'].get('default_queue', 'normal'))
        
    @property
    def lsf_log_dir(self) -> str:
        """Get LSF log directory"""
        return str(self.config['lsf'].get('log_directory', 'pipeline/logs/lsf'))
        
    @property
    def lsf_memory_units(self) -> str:
        """Get LSF memory units"""
        return str(self.config['lsf'].get('memory_units', 'MB'))
        
    @property
    def lsf_default_memory(self) -> str:
        """Get LSF default memory"""
        return str(self.config['lsf'].get('default_memory', '4000'))
        
    @property
    def lsf_default_threads(self) -> int:
        """Get LSF default thread count"""
        return int(self.config['lsf'].get('default_threads', 1))
        
    @property
    def lsf_latency_wait(self) -> int:
        """Get LSF latency wait time"""
        return int(self.config['lsf'].get('latency_wait', 5))
        
    @property
    def lsf_resubmit_on_fail(self) -> bool:
        """Get LSF resubmission policy"""
        return bool(self.config['lsf'].get('resubmit_on_fail', True))
        
if __name__ == "__main__":
    # Example usage with custom config and LSF profile
    try:
        config = ConfigLoader(
            config_path="pipeline/config/pipeline_config.yaml",
            lsf_profile_path="pipeline/config/lsf_profile.yaml"
        )
        
        # Basic configuration
        print(f"Memory multiplier: {config.memory_multiplier}")
        print(f"Resource config for scrub_assembly: {config.get_resource_config('scrub_assembly')}")
        
        # LSF configuration
        print(f"\nLSF Configuration:")
        print(f"Queue: {config.lsf_queue}")
        print(f"Memory Units: {config.lsf_memory_units}")
        print(f"Default Memory: {config.lsf_default_memory}")
        print(f"Default Threads: {config.lsf_default_threads}")
        print(f"Log Directory: {config.lsf_log_dir}")
        
    except ConfigurationError as e:
        print(f"Configuration error: {e}")
    except Exception as e:
        print(f"Error: {e}")