# Post-Processing Pipeline

A Python-based pipeline for genome assembly post-processing and submission to ENA and other databases. This implementation replaces the previous Snakemake-based pipeline while maintaining the same functionality.

## Overview

The pipeline processes genome assemblies through several steps:
- Assembly scrubbing
- N trimming
- Region clipping
- Chromosome handling
- Statistics gathering
- Submission preparation

## Architecture

The pipeline consists of several key components:

### Core Components

- `pipeline.py`: Main entry point and orchestration
- `workflow.py`: Job dependency management and execution flow
- `job_manager.py`: Job submission and monitoring (LSF support)
- `config/`: Configuration management

### Key Features

- LSF job submission and monitoring
- Flexible configuration system
- JIRA integration for tracking
- Comprehensive logging
- Error handling and recovery
- Resource management
- Test coverage

## Requirements

- Python 3.9+
- LSF batch system
- External tools:
  - gfastats
  - fastalength
  - Other bioinformatics tools as needed

## Installation

1. Clone the repository:
```bash
git clone <repository_url>
cd pipeline
```

2. Run the setup script:
```bash
python scripts/setup.py
```

This will:
- Create required directories
- Set up Python virtual environment
- Install dependencies
- Check for required tools
- Verify environment variables

## Configuration

### Environment Variables

Required environment variables:
```bash
JIRA_TOKEN=your_token_here
JIRA_SERVER=your_server_url
```

### Pipeline Configuration

The main configuration file is `config/pipeline_config.yaml`. Key settings include:

- Resource configurations (memory, queue)
- Input/output paths
- Retry settings
- Logging configuration

Example configuration:
```yaml
memory_multiplier: 1.0
default_queue: "normal"
retry_attempts: 3

logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: "pipeline/logs/pipeline.log"

resources:
  scrub_assembly:
    mem_mb: 5000
    queue: "normal"
  # ... other job configurations
```

## Usage

### Basic Usage

Run the pipeline with:
```bash
python pipeline.py --ticket TICKET_ID [options]
```

Options:
- `--ticket`: Required. JIRA ticket identifier
- `--memory-multiplier`: Optional. Memory multiplier (default: 1.0)
- `--config`: Optional. Path to custom config file
- `--local`: Optional. Run jobs locally instead of using LSF

### Examples

Standard run:
```bash
python pipeline.py --ticket GRIT-123
```

With increased memory:
```bash
python pipeline.py --ticket GRIT-123 --memory-multiplier 1.5
```

Using custom configuration:
```bash
python pipeline.py --ticket GRIT-123 --config my_config.yaml
```

## Pipeline Steps

1. **Pre-processing**
   - Validate JIRA ticket
   - Check for contamination reports
   - Prepare working directory

2. **Assembly Processing**
   - Scrub assembly
   - Trim N's
   - Clip regions
   - Handle chromosomes (if applicable)

3. **Statistics and Validation**
   - Generate assembly statistics
   - Run gfastats
   - Perform chromosome audit

4. **Submission Preparation**
   - Prepare submission text
   - Format files for submission
   - Upload results to JIRA

## Error Handling

The pipeline includes comprehensive error handling:

- Job retry mechanism
- JIRA status updates
- Error logging
- Resource cleanup

## Extending the Pipeline

### Adding New Job Types

1. Define the job in `workflow.py`:
```python
def create_new_job_type(self, input_paths):
    job = Job(
        name="new_job",
        command="command_here",
        resources={"mem_mb": 5000}
    )
    self.add_job(job)
```

2. Add resource configuration in `pipeline_config.yaml`:
```yaml
resources:
  new_job:
    mem_mb: 5000
    queue: "normal"
```

### Adding New Features

1. Update configuration schema
2. Implement feature logic
3. Add tests
4. Update documentation

## Testing

Run the test suite:
```bash
python -m pytest pipeline/tests/
```

### Test Coverage

The test suite includes:
- Unit tests for core components
- Integration tests for workflows
- Configuration validation tests
- Error handling tests

## Troubleshooting

Common issues and solutions:

1. **LSF submission fails**
   - Check queue availability
   - Verify resource requests
   - Check LSF configuration

2. **Missing dependencies**
   - Run setup script
   - Check PATH for required tools
   - Verify environment variables

3. **Configuration issues**
   - Validate YAML syntax
   - Check file paths
   - Verify resource settings

## Support

For issues and questions:
1. Check the troubleshooting guide
2. Review logs in pipeline/logs/
3. Contact the development team

## License

[Your license information here]