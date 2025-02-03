# Pipeline Dependencies

## Current Dependencies

Currently installed via requirements.txt:
- pyyaml>=6.0.1 - YAML file handling
- jira>=3.5.1 - Jira integration
- pytest>=7.4.0 - Testing framework
- typing-extensions>=4.7.1 - Type hinting support

## Required Additional Modules

### Available in Old Pipeline
These modules are available in the old pipeline and need to be copied to the new implementation:

1. GritJiraIssue
   - Status: Available and copied
   - Location: pipeline/modules/GritJiraAuth.py
   - Purpose: Jira ticket management and integration

2. Taxonomy (imported by GritJiraIssue)
   - Status: Found in old pipeline, needs copying
   - Location: Used in snakemake/modules/GritJiraIssue.py
   - Purpose: Species taxonomy handling

### Missing Modules
The following modules are required but not found in the old pipeline:

1. EnaBioSample
   - Status: Not found
   - Purpose: ENA BioSample data handling
   - Required by: Pipeline submission functionality

2. NcbiRestAssembly
   - Status: Not found
   - Purpose: NCBI Assembly data access
   - Required by: Assembly processing

3. NcbiRestBioProject
   - Status: Not found
   - Purpose: NCBI BioProject data access
   - Required by: Project metadata handling

4. NcbiEutils
   - Status: Not found
   - Purpose: NCBI E-utilities interface
   - Required by: NCBI data access

5. TolSpreadsheet
   - Status: Not found
   - Purpose: Tree of Life data handling
   - Required by: Pipeline data processing

## Action Items

1. Copy Taxonomy module from old pipeline to new implementation
2. Either:
   - Locate missing modules in other related repositories
   - Or implement new versions of these modules based on their expected functionality
3. Update requirements.txt with any additional dependencies needed by these modules

## Notes

- The missing modules may be available in other repositories or may need to be reimplemented
- Some modules may be replaced with direct API calls or alternative implementations
- Consider using modern alternatives for NCBI/ENA access (like Biopython)