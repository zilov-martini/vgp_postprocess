# Pipeline Dependencies

## Core Python Dependencies
From requirements.txt:
- pyyaml>=6.0.1
- jira>=3.5.1  
- pytest>=7.4.0
- typing-extensions>=4.7.1

## Custom Modules Required
The following custom modules must be available in the pipeline modules directory:

### Currently Available
- GritJiraAuth (from pipeline/modules/)
- GritJiraIssue (from snakemake/modules/)

### Needed from Old Pipeline
These modules need to be copied from the snakemake repository:

1. Database/API Integration
- EnaBioSample - Used for ENA BioSample integration
- NcbiRestAssembly - Used for NCBI Assembly database access
- NcbiRestBioProject - Used for NCBI BioProject access  
- NcbiEutils - Used for NCBI E-utilities API integration
- Taxonomy - Used for taxonomic validation and lookup

2. Spreadsheet/Data Management
- TolSpreadsheet - Used for Tree of Life spreadsheet operations

## External Tool Dependencies
From env_checker.py:

### Required Executables
- gfastats
- bsub (LSF)
- bjobs (LSF)

### Custom Pipeline Scripts
- sequence_length.py - Custom Python implementation for FASTA sequence length calculation
  (Replaces external fastalength dependency)

### Environment Variables
- JIRA_TOKEN
- JIRA_SERVER

## Action Items

1. Copy existing modules from snakemake/modules/ to pipeline/modules/:
- [ ] GritJiraIssue.py
- [ ] Taxonomy.py

2. Copy/implement missing modules in pipeline/modules/:
- [ ] EnaBioSample.py
- [ ] NcbiRestAssembly.py  
- [ ] NcbiRestBioProject.py
- [ ] NcbiEutils.py
- [ ] TolSpreadsheet.py

3. Update environment checker to verify:
- [ ] All required Python modules can be imported
- [ ] External tool dependencies are available
- [ ] Required environment variables are set

4. Update documentation:
- [ ] Add installation instructions for external tools
- [ ] Document environment variable setup
- [ ] Add troubleshooting guide for dependency issues

## Notes

- Modules under "Needed from Old Pipeline" are critical for assembly submission and metadata handling
- All listed modules are used in the submission and validation steps
- Some modules have interdependencies (e.g., GritJiraIssue depends on Taxonomy)
- Migration should maintain backward compatibility where possible