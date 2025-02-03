import unittest
from unittest.mock import mock_open, patch
import os
from pathlib import Path
import yaml

from pipeline.config.config_loader import ConfigLoader

class TestConfigLoader(unittest.TestCase):
    def setUp(self):
        self.valid_config = {
            "ticket": "VGP-123",
            "species_name": "test_species",
            "prefix": "test",
            "memory_multiplier": 1.0,
            "default_queue": "normal",
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "file": "pipeline.log"
            }
        }

    @patch("builtins.open", new_callable=mock_open)
    def test_load_valid_config(self, mock_file):
        # Prepare mock file with valid YAML
        mock_file.return_value.read.return_value = yaml.dump(self.valid_config)
        
        # Initialize config loader
        config = ConfigLoader("test_config.yaml")
        
        # Verify core configuration
        self.assertEqual(config.default_queue, "normal")
        self.assertEqual(config.memory_multiplier, 1.0)
        
    @patch("builtins.open", new_callable=mock_open)
    def test_missing_required_fields(self, mock_file):
        # Remove required fields
        invalid_config = self.valid_config.copy()
        del invalid_config["ticket"]
        
        mock_file.return_value.read.return_value = yaml.dump(invalid_config)
        
        # Check that missing required field raises error
        with self.assertRaises(ValueError):
            ConfigLoader("test_config.yaml")
            
    def test_get_logging_config(self):
        with patch("builtins.open", new_callable=mock_open) as mock_file:
            mock_file.return_value.read.return_value = yaml.dump(self.valid_config)
            
            config = ConfigLoader("test_config.yaml")
            log_config = config.get_logging_config()
            
            self.assertEqual(log_config["level"], "INFO")
            self.assertEqual(log_config["format"], 
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            self.assertEqual(log_config["file"], "pipeline.log")
            
    @patch("builtins.open", new_callable=mock_open)
    def test_memory_scaling(self, mock_file):
        # Test config with memory multiplier
        test_config = self.valid_config.copy()
        test_config["memory_multiplier"] = 2.0
        
        mock_file.return_value.read.return_value = yaml.dump(test_config)
        config = ConfigLoader("test_config.yaml")
        
        # Check base memory is scaled correctly
        self.assertEqual(config.get_memory_mb("default"), 2000)  # Assuming 1000MB base
        
    @patch("builtins.open", new_callable=mock_open)
    def test_queue_configuration(self, mock_file):
        # Test LSF queue configuration
        test_config = self.valid_config.copy()
        test_config["queues"] = {
            "high_mem": {"memory_mb": 16000},
            "fast": {"max_runtime": "1h"}
        }
        
        mock_file.return_value.read.return_value = yaml.dump(test_config)
        config = ConfigLoader("test_config.yaml")
        
        # Verify queue configurations
        self.assertEqual(config.get_queue_memory("high_mem"), 16000)
        
    @patch("pathlib.Path.exists")
    @patch("builtins.open", new_callable=mock_open)
    def test_path_resolution(self, mock_file, mock_exists):
        # Setup mock paths
        mock_exists.return_value = True
        
        test_config = self.valid_config.copy()
        test_config["paths"] = {
            "scripts": "scripts",
            "output": "output"
        }
        
        mock_file.return_value.read.return_value = yaml.dump(test_config)
        config = ConfigLoader("test_config.yaml")
        
        # Verify path resolution
        self.assertTrue(os.path.isabs(config.get_path("scripts")))
        self.assertTrue(os.path.isabs(config.get_path("output")))
        
    @patch("builtins.open", new_callable=mock_open)
    def test_invalid_yaml(self, mock_file):
        # Test handling of invalid YAML
        mock_file.return_value.read.return_value = "invalid: yaml: content: ["
        
        with self.assertRaises(yaml.YAMLError):
            ConfigLoader("test_config.yaml")
            
    @patch("pathlib.Path.exists")
    @patch("builtins.open", new_callable=mock_open)
    def test_file_not_found(self, mock_file, mock_exists):
        # Test handling of missing config file
        mock_exists.return_value = False
        mock_file.side_effect = FileNotFoundError
        
        with self.assertRaises(FileNotFoundError):
            ConfigLoader("nonexistent_config.yaml")

if __name__ == '__main__':
    unittest.main()