import yaml
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ConfigLoader:
    """Load and manage pipeline configuration"""
    
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
            'logs_dir': 'pipeline/logs'
        }
    }

    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration with optional custom config file"""
        self.config = self.DEFAULT_CONFIG.copy()
        
        if config_path:
            self._load_custom_config(config_path)
            
        # Ensure directories exist
        for dir_path in [self.output_dir, self.logs_dir]:
            os.makedirs(dir_path, exist_ok=True)
            
    def _load_custom_config(self, config_path: str) -> None:
        """Load custom configuration from YAML file"""
        try:
            with open(config_path) as f:
                custom_config = yaml.safe_load(f)
            
            # Deep update of configuration
            self._deep_update(self.config, custom_config)
            
        except Exception as e:
            logger.error(f"Failed to load custom config from {config_path}: {e}")
            raise
            
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
        
if __name__ == "__main__":
    # Example usage
    config = ConfigLoader()
    print(f"Memory multiplier: {config.memory_multiplier}")
    print(f"Resource config for scrub_assembly: {config.get_resource_config('scrub_assembly')}")