#!/usr/bin/env python

from sre_constants import MIN_REPEAT_ONE
import re
import os
import sys
import argparse
import glob
from string import Template
import GritJiraIssue
import EnaBioSample
import NcbiRestAssembly
import NcbiRestBioProject
import NcbiEutils
import Taxonomy
import TolSpreadsheet
import traceback

def main():

	# TODO: Substitute in list of data types in header
	# TODO: Substitute in list of data types at start of text

	parser = argparse.ArgumentParser(description='Generate text for ENA submission')
	parser.add_argument("ticket", metavar='GRIT-42', type=str, help='Ticket for assembly')
	parser.add_argument("--output_dir", metavar='./output/', type=str, help='Override default output dir', default=None)
	parser.add_argument("--test", help='Write to test directory', action="store_true")
	parser.add_argument("--clobber", help='Overwrite existing output', action="store_true")
	parser.add_argument("--clean", help='Remove pre-existing .info and .bioproject files', action="store_true")
	parser.add_argument("--rerun", help='This is a rerun due to delayed run accessions', action="store_true")
	parser.add_argument("--no_yaml_pipeline", help='Do not get pipeline info from YAML', action="store_true")
	parser.add_argument("--no_biosample", help='No BioSample available', action="store_true")
	parser.add_argument("--not_in_goat", help='Species is not in GOAT', action="store_true")
	parser.add_argument("--no_run_ref", help='Omit run refs', action="store_true")
	parser.add_argument("--empty_fields_ok", help='Allow empty spreadsheet fields', action="store_true")
	parser.add_argument("--non_standard_synteny_source", help='Allow non-standard synteny source', action="store_true")
	parser.add_argument("--primary_only", help='Only produce primary .info file and BioProject', action="store_true")
	parser.add_argument("--any_chromosome_list", help='Use any chromosome list file', action="store_true")

	args = parser.parse_args()

	try:
		submission_text_maker(args)
	except:
		print(traceback.format_exc())
		error_message = str(sys.exc_info()[1])
		jira_issue = GritJiraIssue.GritJiraIssue(args.ticket)
		jira_issue.add_comment('Submission text maker failed: ' + error_message)
		if args.rerun:
			jira_issue.add_label('manual_submission')
		exit(args.ticket + ': ' + error_message)

def submission_text_maker(args):

	jira_issue = GritJiraIssue.GritJiraIssue(args.ticket)

	filename_for_method_template_name_for_primary = {
		'Faculty': 'faculty.method.template',
		'ASG': 'asg.method.template',
		'ASG_draft_submission': 'asg_draft_submission.method.template',
		'Darwin_cobiont_draft_submission': 'darwin_cobiont_draft_submission.method.template',
		'Wolbachia_cobiont': 'wolbachia_cobiont.method.template',
		'Full VGP': 'darwin.method.template',
		'VGP orders v1.5': 'full_vgp.method.template',
		'vgp_pb_10X_only': 'vgp_pb_10X_only.method.template',
		'10X': 'supernova.method.template',
		'trio_canu': 'trio_canu.method.template',
	}

	filename_for_method_template_name_for_haplotigs = {
		'Faculty': 'faculty.haplotigs.method.template',
		'ASG_draft_submission': None,
		'Darwin_cobiont_draft_submission': None,
		'Wolbachia_cobiont': None,
		'Full VGP': 'darwin.haplotigs.method.template',
		'VGP orders v1.5': 'full_vgp.method.template',
		'vgp_pb_10X_only': 'vgp_pb_10X_only.method.template',
		'10X': 'supernova.method.template',
		'trio_canu': 'trio_canu.method.template',
	}

	bioproject_abstract_filename_for_project = {
		'VGP+': 'vgp_bioproject_abstract.template',
		'25 Genomes': '25_genomes_bioproject_abstract.template',
		'Darwin_VGP': 'darwin_vgp_bioproject_abstract.template',
		'Faculty': 'faculty_bioproject_abstract.template',
	}

	platform_for_method_template_name = {
		'Faculty': '', # Darwin cases are handled elsewhere
		'ASG_draft_submission': '', # ASG cases are handled elsewhere
		'Darwin_cobiont_draft_submission': '', # ASG cases are handled elsewhere
		'Wolbachia_cobiont': '', # ASG cases are handled elsewhere
		'Full VGP': 'PacBio,Illumina,$HIC_COMPANY',
		'VGP orders v1.5': 'PacBio,Illumina,BioNano,$HIC_COMPANY',
		'vgp_pb_10X_only': 'PacBio,Illumina',
		'10X': 'Illumina',
		'trio_canu': 'PacBio,Illumina,BioNano,$HIC_COMPANY',
	}

	empty_fields_ok = args.empty_fields_ok
	if jira_issue.yaml_key_has_content('assembly_description') or jira_issue.yaml_key_has_content('bioproject_abstract'):
		empty_fields_ok = True

	for internal_project in jira_issue.get_internal_projects():
		if internal_project != 'VGP':
			filename_for_method_template_name_for_primary[internal_project] = f'{internal_project.lower()}.method.template'
			filename_for_method_template_name_for_haplotigs[internal_project] = f'{internal_project.lower()}.haplotigs.method.template'
			platform_for_method_template_name[internal_project] = ''
		bioproject_abstract_filename_for_project[internal_project] = f'{internal_project.lower()}_bioproject_abstract.template'
	
	metagenome_method_template_names = []
	for metagenome_project in jira_issue.get_metagenome_projects():
		metagenome_method_template_names.append(f'{metagenome_project}_primary_metagenome')
		metagenome_method_template_names.append(f'{metagenome_project}_binned_metagenome_and_mag')

		filename_for_method_template_name_for_primary[f'{metagenome_project}_primary_metagenome'] = f'{metagenome_project.lower()}_primary_metagenome.method.template'
		filename_for_method_template_name_for_primary[f'{metagenome_project}_binned_metagenome_and_mag'] = f'{metagenome_project.lower()}_binned_metagenome_and_mag.method.template'

		bioproject_abstract_filename_for_project[f'{metagenome_project}_primary_metagenome'] = f'{metagenome_project.lower()}_primary_metagenome_bioproject_abstract.template'
		bioproject_abstract_filename_for_project[f'{metagenome_project}_binned_metagenome_and_mag'] = f'{metagenome_project.lower()}_binned_metagenome_and_mag_bioproject_abstract.template'

		filename_for_method_template_name_for_haplotigs[f'{metagenome_project}_primary_metagenome'] = None
		filename_for_method_template_name_for_haplotigs[f'{metagenome_project}_binned_metagenome_and_mag'] = None

		platform_for_method_template_name[f'{metagenome_project}_primary_metagenome'] = None
		platform_for_method_template_name[f'{metagenome_project}_binned_metagenome_and_mag'] = None

	data_for_sample = {}
	sample_for_assembly_version = {}
	if jira_issue.get_release_version() != '0' and jira_issue.get_custom_field('release_to') not in ('Internal', 'S3', 'FTP', 'ERGA'):
		sample = jira_issue.get_custom_field('sample_id')
		assembly_version = jira_issue.get_custom_field('sample_id') +  '.' + str(jira_issue.get_release_version())
		sample_for_assembly_version[assembly_version] = sample
		data_for_sample[sample] = {
			'SAMPLE':	sample,
		}
		if not(jira_issue.assembly_is_mag()) and (jira_issue.assembly_is_asg_draft_submission() or jira_issue.assembly_is_darwin_cobiont_draft_submission() or jira_issue.assembly_is_from_markerscan()) :
			host_sample = None

			sample_match = re.match('^([^\.]+)\.', sample)
			if sample_match:
				host_sample = sample_match.group(1)
			if jira_issue.yaml_key_has_content('host_specimen'):
				host_sample = jira_issue.yaml['host_specimen']
			if host_sample != None:
				data_for_sample[sample]['HOST_SAMPLE'] = host_sample
				data_for_sample[host_sample] = {'HOST': True}
		if jira_issue.assembly_is_mag():
			host_sample = None
			sample_match = re.match('^([^\.]+)\.', sample)
			if sample_match:
				host_sample = sample_match.group(1)
				metagenome_sample = host_sample + '.metagenome'
				data_for_sample[sample]['METAGENOME_SAMPLE'] = metagenome_sample
				if metagenome_sample not in data_for_sample:
					data_for_sample[metagenome_sample] = {}
				data_for_sample[metagenome_sample]['METAGENOME'] = True
			else:
				exit('Could not determine metagenome name')
	else:
		return

	script_dir = os.path.dirname(__file__)
	csv_dir = script_dir + '/../data/'
	output_dir = args.output_dir
	if output_dir == None:
		output_dir = jira_issue.get_curated_tolid_dir()
	if args.clean:
		for suffix in ('.info', '.bioproject'):
			for file_to_remove in glob.glob(f'{output_dir}/*{suffix}'):
				os.remove(file_to_remove)

	sample_column_for_sheet = {
		'Status': 'sample',
		'Cobiont Submission': 'cobiont_tolid',
		'samples_specimens': 'VGP_id',
		'Primary Metagenome Submission': 'tolid',
		'Binned Metagenome Submission': 'tolid',
	}

	field_mapping_for_sheet = {
		'Status': {
			'species': 'SPREADSHEET_LATIN_NAME',
			'common name': 'COMMON_NAME',
			'BioSample': 'BIOSAMPLE',
			'long read cov (gscope)': 'PBCOV',
			'BioProject': 'UMBRELLA_BIOPROJECT',
		},
		'Cobiont Submission': {
			'cobiont_biosample': 'BIOSAMPLE',
			'cobiont_taxname': 'SPREADSHEET_LATIN_NAME',
			'cobiont_taxid': 'SPREADSHEET_TAXID',
		},
		'Primary Metagenome Submission': {
			'biosample': 'BIOSAMPLE',
			'taxname': 'SPREADSHEET_LATIN_NAME', # This will need modification for [species]
			'taxid': 'SPREADSHEET_TAXID',
			'bioproject': 'METAGENOME_BIOPROJECT',
			'coverage': 'PBCOV',
		},
		'Binned Metagenome Submission': {
			'biosample': 'BIOSAMPLE',
			'taxname': 'SPREADSHEET_LATIN_NAME',
			'mean_coverage': 'PBCOV',
			'taxid': 'SPREADSHEET_TAXID',
		},

	}

	optional_fields = [
		'common name',
	]

	for sheet_name in field_mapping_for_sheet:

		# print('DEBUG: ' + sheet_name)

		tol_spreadsheet = TolSpreadsheet.TolSpreadsheet(sheet_name)
		spamreader = tol_spreadsheet.csv_reader()

		rows_for_sample = {}

		for row in spamreader:
			sample = row[sample_column_for_sheet[sheet_name]]
			sample = re.sub('\.(mat|pat|\d+)$', '', sample) # Eliminate mat/pat distinctions
			# print(sample_column_for_sheet[sheet_name], sample)

			# Skip rows that have no JIRA entry if the TOLID has already occurred, to avoid issues with multiple rows for the same TOLID
			if sample in rows_for_sample and sheet_name == 'Status' and not re.match('^\S+\-\d+', row['jira']):
				continue

			if sheet_name == 'informatics_hic' and sample != '':
				sample_match = re.match('^([^\.]+)\.', sample)
				if sample_match:
					sample = sample_match.group(1)
				else:
					# If there is no suffix after a ".", use the whole field contents
					sample_match = re.match('^([^\.]+)$', sample)
					if sample_match:
						sample = sample_match.group(1)					
					else:
						exit('Cannot convert sample name ' + sample + ' for Hi-C spreadsheet')

			if sample in data_for_sample:
				if sample in rows_for_sample:
					exit(sheet_name + ': Multiple entries for ' + sample)
					# Skip row in 10X sheet if the version number is lower than one already encountered
					#if 'SN VERSION' in row and 'SN_VERSION' in data_for_sample[sample] and row['SN VERSION'] < data_for_sample[sample]['SN_VERSION']:
					#	continue
					# Skip row in Status sheet in favour of the first one encountered
					#if sheet_name == 'Status':
					#	continue
				else:
					rows_for_sample[sample] = 1

				for column_name in ( field_mapping_for_sheet[sheet_name].keys() ):
					if column_name in row:
						if re.match('\S', row[column_name]):
							if re.search('COV$', field_mapping_for_sheet[sheet_name][column_name]):
								row[column_name] = round(float(row[column_name]))

							data_for_sample[sample][ field_mapping_for_sheet[sheet_name][column_name] ] = row[column_name]
#							exit('Column not found')

							if field_mapping_for_sheet[sheet_name][column_name] == 'HIC_COMPANY':
								hic_company_match = re.match('^^([^\.]+)\.([^\.]+)\.?', row[column_name])
								if hic_company_match:
									data_for_sample[sample][ field_mapping_for_sheet[sheet_name][column_name] ] = hic_company_match.group(2).title()
							elif field_mapping_for_sheet[sheet_name][column_name] == 'SPREADSHEET_LATIN_NAME':
								# Eliminate [species] tag from Noah's MAG species names
								data_for_sample[sample][ field_mapping_for_sheet[sheet_name][column_name] ] = re.sub('\s*\[species\]\s*', '', row[column_name])

						else:
							if column_name not in optional_fields and not empty_fields_ok and 'HOST' not in data_for_sample[sample]:
								# Could convert this into a warning if it becomes an issue
								exit('Column ' + column_name + ' is empty for sample ' + sample)
					else:
						exit('Column ' + column_name + ' not found for sample ' + sample)

	print(data_for_sample)

	sample = jira_issue.get_custom_field('sample_id')
	assembly_version = jira_issue.get_custom_field('sample_id') +  '.' + str(jira_issue.get_release_version())

	release_dir = jira_issue.get_curated_tolid_dir()

	curated_file_name_for_type = jira_issue.get_curated_file_name_for_type()

	haplotypes = ['primary']
	if len(jira_issue.get_haplotypes()) > 0:
		haplotypes = jira_issue.get_haplotypes()

	for haplotype in haplotypes:
		data_for_sample[sample]['ASSEMBLY_VERSION'] = jira_issue.get_assembly_name_for_haplotype(haplotype)

		# Detect unlocalised regions in the input chr list file
		primary_chromosome_list_file = release_dir + '/' + curated_file_name_for_type['chromosome_list_csv'][haplotype]

		if not(file_has_content(primary_chromosome_list_file)) and args.any_chromosome_list:
			curated_files = os.listdir(release_dir)
			curated_csv_files = [curated_file for curated_file in curated_files if re.search('chromosome.*\.csv', curated_file)]
			if len(curated_csv_files) != 1:
				exit(f'There is no unique chromosome list file- instances include {curated_csv_files}.')
			primary_chromosome_list_file = curated_csv_files[0]

		if file_has_content(primary_chromosome_list_file) and not jira_issue.assembly_is_primary_metagenome() and not jira_issue.assembly_is_binned_metagenome():
			data_for_sample[sample]['PRIMARY_LIST_FILES'] = '\nCHROMOSOME_LIST\t$ASSEMBLY_VERSION.primary.chromosome_list.tsv.gz'
			if chromosome_list_csv_has_unlocalised_regions(primary_chromosome_list_file) and not jira_issue.assembly_is_primary_metagenome() and not jira_issue.assembly_is_binned_metagenome():
				data_for_sample[sample]['PRIMARY_LIST_FILES'] += '\nUNLOCALISED_LIST\t$ASSEMBLY_VERSION.primary.unlocalised_list.tsv.gz'
		elif file_is_empty(primary_chromosome_list_file):
			data_for_sample[sample]['PRIMARY_LIST_FILES'] = ''
		else:
			# Throw an error if it looks like there's a chr list file following different naming conventions
			curated_files = os.listdir(release_dir)
			curated_csv_files = [curated_file for curated_file in curated_files if re.search('\.csv', curated_file)]
			if len(curated_csv_files) > 0:
				exit(f'There appears to be a chromosome list file with the wrong naming format- instances include: {curated_csv_files}. Expected to see {primary_chromosome_list_file}')
			data_for_sample[sample]['PRIMARY_LIST_FILES'] = ''

		data_for_sample[sample]['HAPLOTIG_LIST_FILES'] = ''

		# We only have to worry about haplotig chromosome list files if this isn't a hap-resolved assembly
		if haplotype == 'primary':
			haplotig_chromosome_list_file = release_dir + '/' + curated_file_name_for_type['chromosome_list_csv']['all_haplotigs']
			if os.path.isfile(haplotig_chromosome_list_file):
				if file_has_content(haplotig_chromosome_list_file) and not jira_issue.assembly_is_primary_metagenome() and not jira_issue.assembly_is_binned_metagenome():
					data_for_sample[sample]['HAPLOTIG_LIST_FILES'] = '\nCHROMOSOME_LIST\t$ASSEMBLY_VERSION.haplotigs.chromosome_list.tsv.gz'
					if chromosome_list_csv_has_unlocalised_regions(haplotig_chromosome_list_file) and not jira_issue.assembly_is_primary_metagenome() and not jira_issue.assembly_is_binned_metagenome():
						data_for_sample[sample]['HAPLOTIG_LIST_FILES'] += '\nUNLOCALISED_LIST\t$ASSEMBLY_VERSION.haplotigs.unlocalised_list.tsv.gz'

		if jira_issue.get_custom_field('submission_note') == None:
			data_for_sample[sample]['SUBMISSION_NOTE'] = ''
		else:
			data_for_sample[sample]['SUBMISSION_NOTE'] = jira_issue.get_custom_field('submission_note')
			# Handle line breaks
			data_for_sample[sample]['SUBMISSION_NOTE'] = re.sub('[\r\n]', '', data_for_sample[sample]['SUBMISSION_NOTE'])

		method_template_name = jira_issue.get_custom_field('assembly_type')
		if jira_issue.get_issue_type() == 'Darwin':	# Darwin assemblies use "Darwin" rather than the assembly-type
			method_template_name = 'Darwin'
			if jira_issue.assembly_is_mag():
				if jira_issue.assembly_is_primary_metagenome():
					method_template_name = 'Darwin_primary_metagenome'
				else:
					method_template_name = 'Darwin_binned_metagenome_and_mag'
			elif jira_issue.assembly_is_from_markerscan():
				method_template_name = 'Wolbachia_cobiont'
			elif jira_issue.assembly_is_darwin_cobiont_draft_submission():
				method_template_name = 'Darwin_cobiont_draft_submission'
			elif jira_issue.get_project() == 'DS':
#				exit('Cannot yet generate text for Darwin non-MAG non-cobiont cases')
				print('Warning: running on DS Darwin case')
		elif jira_issue.get_issue_type() == 'ASG':	# ASG assemblies use "ASG" rather than the assembly-type
			method_template_name = 'ASG'
			if jira_issue.assembly_is_mag():
				if jira_issue.assembly_is_primary_metagenome():
					method_template_name = 'ASG_primary_metagenome'
				else:
					method_template_name = 'ASG_binned_metagenome_and_mag'
			elif jira_issue.assembly_is_asg_draft_submission():
				method_template_name = 'ASG_draft_submission'

		elif jira_issue.get_issue_type() == 'ERGA':	# ERGA assemblies use "ERGA" rather than the assembly-type
			method_template_name = 'ERGA'
			if jira_issue.assembly_is_mag():
				if jira_issue.assembly_is_primary_metagenome():
					method_template_name = 'ERGA_primary_metagenome'
				else:
					method_template_name = 'ERGA_binned_metagenome_and_mag'
			elif jira_issue.get_project() == 'DS':
				exit('Cannot yet generate text for ERGA non-MAG non-cobiont cases')
		elif jira_issue.get_issue_type() == 'Faculty':	# ERGA assemblies use "ERGA" rather than the assembly-type
			method_template_name = 'Faculty'
		else:
			for internal_project in jira_issue.get_internal_projects():
				if jira_issue.get_issue_type() == internal_project:	# TOL assemblies use "TOL" rather than the assembly-type
					method_template_name = internal_project

		# Linked read type. In future, this should be obtained from the ticket
		if '10X' in jira_issue.get_datatypes_available():
			data_for_sample[sample]['LINKEDREADTYPE'] = '10X Genomics Chromium'
		else:
			# This shouldn't get substituted in
			data_for_sample[sample]['LINKEDREADTYPE'] = ''

		# If the HiC kit is available from the JIRA entry, this trumps the spreadsheet
		if jira_issue.get_custom_field('hic_kit') != None:
			data_for_sample[sample]['HIC_COMPANY'] = jira_issue.get_custom_field('hic_kit')

		if args.no_biosample:
			data_for_sample[sample]['BIOSAMPLE'] = ''
			if 'SPREADSHEET_LATIN_NAME' in data_for_sample[sample]:
				data_for_sample[sample]['LATIN_NAME'] = data_for_sample[sample]['SPREADSHEET_LATIN_NAME']
			else:
				data_for_sample[sample]['LATIN_NAME'] = jira_issue.get_species()
			data_for_sample[sample]['TAXONOMY_ID'] = ''
		elif jira_issue.assembly_is_from_markerscan():
			data_for_sample[sample]['TAXONOMY_ID'] = jira_issue.yaml['taxid']
			data_for_sample[sample]['LATIN_NAME'] = jira_issue.yaml['species']
			data_for_sample[sample]['BIOSAMPLE'] = jira_issue.yaml['biosample']
		elif jira_issue.assembly_is_mag() or jira_issue.assembly_is_asg_draft_submission():
			# Ignore BioSample details for MAGs
			# Get TAXID from spreadsheet
			if 'SPREADSHEET_LATIN_NAME' not in data_for_sample[sample]:
				exit(f'Cannot find Latin name in spreadsheet')
			if 'SPREADSHEET_TAXID' not in data_for_sample[sample]:
				exit(f'Cannot find taxonomy ID  in spreadsheet')
			data_for_sample[sample]['TAXONOMY_ID'] = data_for_sample[sample]['SPREADSHEET_TAXID']
			data_for_sample[sample]['LATIN_NAME'] =  data_for_sample[sample]['SPREADSHEET_LATIN_NAME']

	#		PROVISIONALLY NOT USING LOOKUP FROM NCBI FOR MAGs
	#		eutils = NcbiEutils.NcbiEutils()
	#		ncbi_lookup_result = eutils.esearch_query(
	#			db = 'taxonomy',
	#			field = 'All Names',
	#			search_term = data_for_sample[sample]['SPREADSHEET_LATIN_NAME'],
	#			extra_args = ''
	#		)
	#		
	#		if 'esearchresult' in ncbi_lookup_result and 'idlist' in ncbi_lookup_result['esearchresult']:
	#			data_for_sample[sample]['TAXONOMY_ID'] = ncbi_lookup_result['esearchresult']['idlist'][0]
	#			data_for_sample[sample]['LATIN_NAME'] =  data_for_sample[sample]['SPREADSHEET_LATIN_NAME']
	#
	#		else:
	#			exit(f'Cannot find {data_for_sample[sample]["SPREADSHEET_LATIN_NAME"]} in NCBI')
		elif jira_issue.yaml_key_has_content('assembly_description') or jira_issue.yaml_key_has_content('bioproject_abstract'):
			if jira_issue.yaml_key_has_content('assembly_description') and jira_issue.yaml_key_has_content('bioproject_abstract') and jira_issue.yaml_key_has_content('coverage') and jira_issue.yaml_key_has_content('biosample'):

				data_for_sample[sample]['PBCOV'] = jira_issue.yaml['coverage']
				data_for_sample[sample]['BIOSAMPLE'] = jira_issue.yaml['biosample']
				data_for_sample[sample]['BIOPROJECT_ABSTRACT'] = jira_issue.yaml['bioproject_abstract'].rstrip()

				data_for_sample[sample]['CHROMOSOME_NAMING_DESCRIPTION'] = ''
				data_for_sample[sample]['HAPLOTIG_PRODUCTION_METHOD'] = ''

				data_for_sample[sample]['LATIN_NAME'] = jira_issue.get_species()

				if not jira_issue.yaml_key_has_content('run_accessions'):
					args.no_run_ref = True

				if jira_issue.yaml_key_has_content('taxonomy_id'):
					data_for_sample[sample]['TAXONOMY_ID'] = str(jira_issue.yaml['taxonomy_id'])
				else:
					eutils = NcbiEutils.NcbiEutils()
					ncbi_lookup_result = eutils.esearch_query(
						db = 'taxonomy',
						field = 'All Names',
						search_term = data_for_sample[sample]['LATIN_NAME'],
						extra_args = ''
					)
					
					if 'esearchresult' in ncbi_lookup_result and 'idlist' in ncbi_lookup_result['esearchresult']:
						data_for_sample[sample]['TAXONOMY_ID'] = ncbi_lookup_result['esearchresult']['idlist'][0]
					else:
						exit(f'Cannot find {data_for_sample[sample]["LATIN_NAME"]} in NCBI')

			else:
				exit('Partial information for Faculty assembly submission.')

		elif args.not_in_goat:
			biosample = EnaBioSample.EnaBioSample(data_for_sample[sample]['BIOSAMPLE'])
			data_for_sample[sample]['LATIN_NAME'] = biosample.species()
			data_for_sample[sample]['TAXONOMY_ID'] = biosample.taxonomy_id()
			if data_for_sample[sample]['LATIN_NAME'] !=  data_for_sample[sample]['SPREADSHEET_LATIN_NAME']:
				jira_issue.add_comment('Warning: species from BioSample is ' + data_for_sample[sample]['LATIN_NAME'] + ' and that from spreadsheet is ' + data_for_sample[sample]['SPREADSHEET_LATIN_NAME'])
			data_for_sample[sample]['LATIN_NAME'] =  data_for_sample[sample]['SPREADSHEET_LATIN_NAME']
		else:
			biosample = EnaBioSample.EnaBioSample(data_for_sample[sample]['BIOSAMPLE'])
			data_for_sample[sample]['LATIN_NAME'] = biosample.species()
			data_for_sample[sample]['TAXONOMY_ID'] = biosample.taxonomy_id()
			if data_for_sample[sample]['LATIN_NAME'] !=  data_for_sample[sample]['SPREADSHEET_LATIN_NAME']:
				jira_issue.add_comment('Warning: species from BioSample is ' + data_for_sample[sample]['LATIN_NAME'] + ' and that from spreadsheet is ' + data_for_sample[sample]['SPREADSHEET_LATIN_NAME'])
				spreadsheet_taxonomy = Taxonomy.GoatTaxonomy(data_for_sample[sample]['SPREADSHEET_LATIN_NAME'])
				if spreadsheet_taxonomy.tax_id_for_query_name() != int(data_for_sample[sample]['TAXONOMY_ID']):
					error_message = f'Fatal warning: these species names have different taxonomy IDs: {data_for_sample[sample]["TAXONOMY_ID"]} vs {spreadsheet_taxonomy.tax_id_for_query_name()}'
					jira_issue.add_comment(error_message)
					exit(error_message)
				else:
					data_for_sample[sample]['LATIN_NAME'] =  data_for_sample[sample]['SPREADSHEET_LATIN_NAME']

		if 'COMMON_NAME' in data_for_sample[sample] and re.search('\S', data_for_sample[sample]['COMMON_NAME']):
			data_for_sample[sample]['COMMON_NAME'] = re.sub('\&', 'and', data_for_sample[sample]['COMMON_NAME'])
			data_for_sample[sample]['LATIN_NAME_AND_COMMON_NAME_FOR_TITLE'] = "$LATIN_NAME ($COMMON_NAME)"
			data_for_sample[sample]['LATIN_NAME_AND_COMMON_NAME_FOR_ABSTRACT'] = "$LATIN_NAME, common name $COMMON_NAME"
		else:
			data_for_sample[sample]['LATIN_NAME_AND_COMMON_NAME_FOR_TITLE'] = "$LATIN_NAME"
			data_for_sample[sample]['LATIN_NAME_AND_COMMON_NAME_FOR_ABSTRACT'] = "$LATIN_NAME"

		data_for_sample[sample]['PLATFORM'] = platform_for_method_template_name[method_template_name]

		# Get PBCOV from host for MAGs
		if not(jira_issue.assembly_is_mag()) and (jira_issue.assembly_is_asg_draft_submission() or jira_issue.assembly_is_darwin_cobiont_draft_submission() or jira_issue.assembly_is_from_markerscan()):
			if data_for_sample[sample]['HOST_SAMPLE'] in data_for_sample:
				if jira_issue.yaml_key_has_content('coverage'):
					data_for_sample[sample]['PBCOV'] = jira_issue.yaml['coverage']
				if 'PBCOV' not in data_for_sample[sample]:
					if 'PBCOV' in data_for_sample[data_for_sample[sample]['HOST_SAMPLE']]:
						data_for_sample[sample]['PBCOV'] = data_for_sample[data_for_sample[sample]['HOST_SAMPLE']]['PBCOV']
					else:
						exit('Cannot find host PBCOV')
				if 'SPREADSHEET_LATIN_NAME' in data_for_sample[data_for_sample[sample]['HOST_SAMPLE']]:
						data_for_sample[sample]['HOST_LATIN_NAME_AND_COMMON_NAME_FOR_ABSTRACT'] = data_for_sample[data_for_sample[sample]['HOST_SAMPLE']]['SPREADSHEET_LATIN_NAME']
				else:
					exit('Cannot find host Latin name')
			else:
				exit('Cannot find host details')

		warnings = []
		data_for_sample[sample]['PRIMARY_BIOPROJECT'] = ''
		data_for_sample[sample]['ALTERNATE_BIOPROJECT'] = ''

		# For MAGs, get the primary BioProject from the spreadsheet
		if jira_issue.assembly_is_mag():
			if data_for_sample[sample]['METAGENOME_SAMPLE'] in data_for_sample:
				if 'METAGENOME_BIOPROJECT' in data_for_sample[data_for_sample[sample]['METAGENOME_SAMPLE']]:
					data_for_sample[sample]['PRIMARY_BIOPROJECT'] = data_for_sample[data_for_sample[sample]['METAGENOME_SAMPLE']]['METAGENOME_BIOPROJECT']
				else:
					exit('Cannot determine metagenome BioProject for MAG')
			else:
				exit('Cannot determine metagenome BioProject for MAG')
		elif int(jira_issue.get_release_version()) > 1:
			if haplotype in ('hap1','hap2'):
				if jira_issue.get_bioproject_for_haplotype(haplotype) != None:
					data_for_sample[sample]['PRIMARY_BIOPROJECT'] = jira_issue.get_bioproject_for_haplotype(haplotype)
				else:
					exit('Cannot find haplotype BioProject for previous version')
			else:
				if jira_issue.get_primary_bioproject() != None:
					data_for_sample[sample]['PRIMARY_BIOPROJECT'] = jira_issue.get_primary_bioproject()
				else:
					exit('Cannot find primary BioProject for previous version')
				if jira_issue.get_alternate_bioproject() != None:
					data_for_sample[sample]['ALTERNATE_BIOPROJECT'] = jira_issue.get_alternate_bioproject()
				elif not jira_issue.is_haploid():
					exit('Cannot find alternate BioProject for previous version')

		data_for_sample[sample]['ASSEMBLY_TYPE'] = 'clone or isolate'
		if 'assembly_type' in jira_issue.yaml:
			permitted_assembly_types = [
				'clone or isolate',
				'primary metagenome',
				'binned metagenome',
				'Metagenome-Assembled Genome (MAG)',
			]
			if jira_issue.yaml['assembly_type'] not in permitted_assembly_types:
				exit(jira_issue.yaml['assembly_type'] + ' is not a permitted assembly type')
			data_for_sample[sample]['ASSEMBLY_TYPE'] = jira_issue.yaml['assembly_type']

		data_for_sample[sample]['RUN_REF_LINE'] = ''
		if not args.no_run_ref:
			run_refs = None
			if jira_issue.yaml_key_has_content('run_accessions'):
				run_refs_string = jira_issue.yaml['run_accessions']
				run_refs = re.split(',', run_refs_string)
			else:
				my_spreadsheet = TolSpreadsheet.TolSpreadsheet()
				# Remove anything after a period in order to get run refs for cobionts
				sample_for_spreadsheet = re.sub('\..*$','',sample)
				if jira_issue.yaml_key_has_content('host_specimen'):
					sample_for_spreadsheet = jira_issue.yaml['host_specimen']
				run_refs = my_spreadsheet.run_refs_for_sample(sample_for_spreadsheet)

			if len(run_refs) > 0:
				data_for_sample[sample]['RUN_REF_LINE'] = '\nRUN_REF\t' + ','.join(run_refs)
			if 'pending' in map(str.lower, run_refs):
				warnings.append('Run accessions still pending')
			if 'none' in map(str.lower, run_refs):
				warnings.append('Run accessions not available')
			if len(run_refs) == 0:
				warnings.append('No run accessions')

		# Select custom field naming clause
		if not jira_issue.assembly_is_mag() and not jira_issue.assembly_is_asg_draft_submission() and not jira_issue.assembly_is_darwin_cobiont_draft_submission() and not jira_issue.assembly_is_from_markerscan() and not jira_issue.yaml_key_has_content('assembly_description'):
			if not file_has_content(primary_chromosome_list_file):
				data_for_sample[sample]['CHROMOSOME_NAMING_DESCRIPTION'] = ''
			elif jira_issue.get_custom_field('chromosome_naming') == None:
				exit('No chromosome naming method has been specified in the JIRA ticket.')
			elif jira_issue.get_custom_field('chromosome_naming') == 'Size':
				data_for_sample[sample]['CHROMOSOME_NAMING_DESCRIPTION'] = 'Chromosome-scale scaffolds confirmed by the Hi-C data have been named in order of size.'
			elif jira_issue.get_custom_field('chromosome_naming') == 'Synteny':
				if jira_issue.get_custom_field('synteny_source') == None:
					exit('No synteny source specified')
				synteny_source = jira_issue.get_custom_field('synteny_source')
				if re.match('^GC[AF]\S+$', synteny_source): # If this is a GCA, get further details
					ncbi_assembly = NcbiRestAssembly.NcbiRestAssembly(synteny_source)
					synteny_source = ncbi_assembly.species_and_common_name() + ' ' + synteny_source
				elif re.match('^hap[12]$', synteny_source): # If this is an alternate haplotype, explain that
					synteny_source = f'the alternate haplotype ({synteny_source}) for this sample'
				elif not args.non_standard_synteny_source and not re.match('^(\S+.*\s+GC[AF]\S+|PMID:?\s*\d+)$', jira_issue.get_custom_field('synteny_source')):
					exit('Synteny source is not in standard format, eg "Oryzias latipes (Japanese medaka) GCA_002234675.1" or "PMID 123456"')
				data_for_sample[sample]['CHROMOSOME_NAMING_DESCRIPTION'] = 'Chromosome-scale scaffolds are named by synteny based on '  + synteny_source +  '.'

		data_for_sample[sample]['CURATED_ASSEMBLY'] = 'the primary assembly'
		if len(jira_issue.get_haplotypes()) > 0:
			data_for_sample[sample]['CURATED_ASSEMBLY'] = 'each haplotype assembly'

		# This will need to be varied for rapid curation cases
		data_for_sample[sample]['CURATION'] = 'gEVAL'
		if jira_issue.get_project() == 'RC':
			data_for_sample[sample]['CURATION'] = 'rapid curation'
		if jira_issue.get_project() == 'DS':
			data_for_sample[sample]['CURATION'] = 'draft curation'
		if jira_issue.custom_field_has_content('treeval'):
			data_for_sample[sample]['CURATION'] = 'TreeVal'

		if args.no_yaml_pipeline or jira_issue.yaml_key_has_content('assembly_description'):
			data_for_sample[sample]['HIFI_ASSEMBLER'] = 'ASSEMBLER_UNKNOWN'
			data_for_sample[sample]['HIC_ASSEMBLER'] = 'ASSEMBLER_UNKNOWN'
		elif jira_issue.assembly_is_mag():
			data_for_sample[sample]['HIFI_ASSEMBLER'] = jira_issue.get_assembler()
			data_for_sample[sample]['HIC_ASSEMBLER'] = 'ASSEMBLER_UNKNOWN'
		else:
			data_for_sample[sample]['HIFI_ASSEMBLER'] = jira_issue.get_assembler()
			if jira_issue.assembly_is_asg_draft_submission() or jira_issue.assembly_is_darwin_cobiont_draft_submission() or jira_issue.assembly_is_from_markerscan():
				data_for_sample[sample]['HIC_ASSEMBLER'] = 'ASSEMBLER_UNKNOWN'
			else:
				if 'HiC' in jira_issue.get_datatypes_available():
					data_for_sample[sample]['HIC_ASSEMBLER'] = jira_issue.get_hic_assembler()
				else:
					warnings.append('No HiC; no template for assemblies without this data')

			if data_for_sample[sample]['HIFI_ASSEMBLER'] == 'Hifiasm' and len(jira_issue.get_haplotypes()) > 0:
				data_for_sample[sample]['HIFI_ASSEMBLER'] = 'Hifiasm in Hi-C integrated assembly mode'

		# Organelle type clause
		if jira_issue.get_mito_assembly() != None:
			if jira_issue.get_plastid_assembly() != None:
				data_for_sample[sample]['ORGANELLE_TYPE_CLAUSE'] = 'mitochondrial and chloroplast genomes were'
			else:
				data_for_sample[sample]['ORGANELLE_TYPE_CLAUSE'] = 'mitochondrial genome was'

		# Check for scenario where mito assembler is specified but no mito is present
		if not (jira_issue.yaml_key_has_content('assembly_description')) and not(jira_issue.assembly_is_mag()) and 'mito_assembler' in jira_issue.get_pipeline_software_types() and data_for_sample[sample]['ORGANELLE_TYPE_CLAUSE'] == None:
			exit('Mito assembler is listed in pipeline but no organelle is submitted')

		# MT assembly clause
		if args.no_yaml_pipeline or jira_issue.yaml_key_has_content('assembly_description'):
			data_for_sample[sample]['ORGANELLE_ASSEMBLER_CLAUSE'] = 'ASSEMBLER_UNKNOWN'
		elif jira_issue.get_organelle_assemblers_from_yaml() == 'MitoHiFi':
			data_for_sample[sample]['ORGANELLE_ASSEMBLER_CLAUSE'] = 'MitoHiFi'
		elif jira_issue.get_organelle_assemblers_from_yaml() == 'OATK':
			data_for_sample[sample]['ORGANELLE_ASSEMBLER_CLAUSE'] = 'OATK'
		elif jira_issue.get_organelle_assemblers_from_yaml() == 'MBG':
			data_for_sample[sample]['ORGANELLE_ASSEMBLER_CLAUSE'] = 'MBG from PacBio HiFi reads mapping to related genomes. A representative circular sequence was selected for each from the graph based on read coverage'
		elif jira_issue.get_organelle_assemblers_from_yaml() == 'MBG and MitoHiFi':
			data_for_sample[sample]['ORGANELLE_ASSEMBLER_CLAUSE'] = 'MBG from PacBio HiFi reads mapping to related genomes. A representative sequence was selected for each from the graph based on read coverage, contig size, and its alignments to the related genomes, then MitoHiFi was run on this sequence for circularisation and annotation with MitoFinder'
		elif jira_issue.get_organelle_assemblers_from_yaml() == 'MBG and MITOS WebServer and MitoHiFi':
			data_for_sample[sample]['ORGANELLE_ASSEMBLER_CLAUSE'] = 'MBG from the trimmed PacBio HiFi reads. A representative circular sequence was selected and annotated using MITOS WebServer. The produced annotation was used to perform a final MitoHiFi round to allow for the mitocondrial contig rotation and circularisation'
		elif jira_issue.get_organelle_assemblers_from_yaml() == 'MitoHiFi and OATK':
			data_for_sample[sample]['ORGANELLE_ASSEMBLER_CLAUSE'] = 'MitoHiFi and OATK'
		elif jira_issue.get_organelle_assemblers_from_yaml() == 'MBG and MitoHiFi and Tiara':
			data_for_sample[sample]['ORGANELLE_ASSEMBLER_CLAUSE'] = 'the following method: mitochondrial reads were identified with Tiara, then assembled with MBG, and rotated and circularized with MitoHiFi'
		elif jira_issue.get_organelle_assemblers_from_yaml() == 'Mitos and Tiara':
			data_for_sample[sample]['ORGANELLE_ASSEMBLER_CLAUSE'] = data_for_sample[sample]['HIFI_ASSEMBLER'] + ' alongside the nuclear genome, and identified using Tiara and Mitos'
		elif jira_issue.get_organelle_assemblers_from_yaml() == 'MitoHiFi and Tiara':
			data_for_sample[sample]['ORGANELLE_ASSEMBLER_CLAUSE'] = ''
		elif jira_issue.get_mito_assembly() != None or jira_issue.get_plastid_assembly() != None:
			exit('MT or plastid assembly is present but no standard organelle assembler is specified')
		else:
			data_for_sample[sample]['ORGANELLE_ASSEMBLER_CLAUSE'] = ''

		# Check whether this is a standard Darwin assembly
		# Raise a warning if there is no YAML
		if not jira_issue.is_yaml_available():
			warnings.append('No YAML')
		if jira_issue.is_standard_darwin_pipeline() == False and not jira_issue.assembly_is_mag() and not jira_issue.assembly_is_asg_draft_submission() and not jira_issue.assembly_is_darwin_cobiont_draft_submission() and not jira_issue.assembly_is_from_markerscan():
			warnings.append('Did not use standard Darwin pipeline')

		# If this is a standard Darwin assembly
		if method_template_name in jira_issue.get_internal_projects() + metagenome_method_template_names + ['Wolbachia_cobiont', 'Darwin_cobiont_draft_submission', 'ASG_draft_submission', 'ERGA_draft_submission', 'Full VGP', 'Faculty']:
			data_type_clause_for_type = {
				'Pacbio': '${PBCOV}x PacBio data',
				'10X': '${LINKEDREADTYPE} data',
				'HiC': '$HIC_COMPANY Hi-C data'
			}

			if jira_issue.assembly_is_primary_metagenome():
				data_type_clause_for_type['Pacbio'] = 'PacBio data'

			platform_clause_for_type = {
				'Pacbio': 'PacBio',
				'10X': 'Illumina',
				'HiC': '$HIC_COMPANY',
			}

			ordered_data_types = [
				'Pacbio',
				'10X',
				'HiC',
			]

			if re.search('bespoke', data_for_sample[sample]['HIC_COMPANY']):
				data_for_sample[sample]['HIC_COMPANY'] = 'HiC'

			data_type_clauses = []
			platform_clauses = []
			for ordered_data_type in ordered_data_types:
				if ordered_data_type in jira_issue.get_datatypes_available():
					# Special case clause: ignore 10X data if there is no polisher in the YAML
					if not(ordered_data_type == '10X' and 'polishers' not in jira_issue.get_pipeline_software_types()):
						data_type_clauses.append(data_type_clause_for_type[ordered_data_type])
						platform_clauses.append(platform_clause_for_type[ordered_data_type])

			data_for_sample[sample]['DATA_TYPES']  = join_with_commas_and_and(data_type_clauses)
			data_for_sample[sample]['PLATFORM']  = ','.join(platform_clauses)

			method_steps_text = ''
			if not jira_issue.is_yaml_available() or args.no_yaml_pipeline:
				no_yaml_method_steps_file =	'darwin.no_yaml_method_steps.template'
				with open(csv_dir + no_yaml_method_steps_file) as no_yaml_method_steps_handle:
					for line in no_yaml_method_steps_handle:
						method_steps_text += line.rstrip()
			elif jira_issue.yaml_key_has_content('assembly_description'):
				method_steps_text = jira_issue.yaml['assembly_description'].rstrip()

				data_for_sample[sample]['HAPLOTIG_METHOD_STEPS'] = method_steps_text
				if jira_issue.yaml_key_has_content('haplotig_assembly_description'):
					data_for_sample[sample]['HAPLOTIG_METHOD_STEPS'] = jira_issue.yaml['haplotig_assembly_description'].rstrip()
			# If YAML is available, base it on the pipeline
			elif not jira_issue.assembly_is_mag():
				method_steps = []

				method_step_clauses = {
					'hifi_assemblers': 'initial PacBio assembly generation with $HIFI_ASSEMBLER',
					'haplotig_purgers': 'retained haplotig separation with purge_dups',
					'polishers': 'short-read polishing using FreeBayes-called variants from ${LINKEDREADTYPE} reads aligned with LongRanger',
					'hic_assemblers': 'and Hi-C based scaffolding with ${HIC_ASSEMBLER}',
					'mito_assemblers': 'The ${ORGANELLE_TYPE_CLAUSE} assembled using ${ORGANELLE_ASSEMBLER_CLAUSE}',
				}

				software_types = [
					'hifi_assemblers',
					'haplotig_purgers',
					'polishers',
					'hic_assemblers',
				]

				for software_type in software_types:
					if software_type in jira_issue.get_pipeline_software_types():
						if software_type not in method_step_clauses:
							exit('No description available for this software type')
						method_steps.append(method_step_clauses[software_type])

				method_steps_text = ', '.join(method_steps)

				software_types_for_separate_sentence = [
					'mito_assemblers',
				]

				method_steps_for_separate_sentences = []

				for software_type in software_types_for_separate_sentence:
					if software_type in jira_issue.get_pipeline_software_types():
						if software_type not in method_step_clauses:
							exit('No description available for this software type')
						method_steps_for_separate_sentences.append(method_step_clauses[software_type])

				data_for_sample[sample]['HAPLOTIG_PRODUCTION_METHOD'] ='This alternate haplotype assembly combines the haplotigs separated by purge_dups with haplotigs separated from the primary assembly during curation. '

				if jira_issue.yaml_key_is_true('combine_for_curation') and len(jira_issue.get_haplotypes()) == 0:
					method_steps_for_separate_sentences.append('A manually phased assembly (based on HiC signal) was generated from a jointly curated primary and alt assembly')
					data_for_sample[sample]['HAPLOTIG_PRODUCTION_METHOD'] = ''
				if haplotype == 'primary' and jira_issue.get_haplotig_chromosome_mode():
					method_steps_for_separate_sentences.append('Both haplotypes are assembled to chromosome scale')
					data_for_sample[sample]['HAPLOTIG_PRODUCTION_METHOD'] = 'Chromosomes in the alt assembly are named after their homolog in the primary assembly. '

				method_steps_text = '. '.join([method_steps_text] + method_steps_for_separate_sentences)

			data_for_sample[sample]['METHOD_STEPS'] = method_steps_text

		fields_to_use_as_templates = [
			'PLATFORM',
			'LATIN_NAME_AND_COMMON_NAME_FOR_TITLE',
			'LATIN_NAME_AND_COMMON_NAME_FOR_ABSTRACT',
			'PRIMARY_LIST_FILES',
			'HAPLOTIG_LIST_FILES',
			'DATA_TYPES',
			'METHOD_STEPS',
		]

		# Some fields need to be treated as templates before being put in the main template
		for field in fields_to_use_as_templates:
			if field in data_for_sample[sample]:
				field_template = Template(data_for_sample[sample][field])
				data_for_sample[sample][field] = field_template.safe_substitute(data_for_sample[sample])

		filename_for_template_name = {
			'bioproject': 'bioproject.template',
			'primary.info.method': filename_for_method_template_name_for_primary[method_template_name],
			'haplotigs.info.method': filename_for_method_template_name_for_haplotigs[method_template_name],
			'primary.info': 'primary.info.template',
			'haplotigs.info': 'haplotigs.info.template'
		}

		if haplotype != 'primary':
			filename_for_template_name = {
				'bioproject': 'bioproject.template',
				'primary.info.method': filename_for_method_template_name_for_primary[method_template_name],
				'primary.info': 'primary.info.template',
			}

		if jira_issue.get_issue_type() == 'Faculty':
			filename_for_template_name['bioproject'] = 'bioproject_with_umbrella.template'

		if 'haploid' in jira_issue.get_labels() or args.primary_only or jira_issue.assembly_is_asg_draft_submission() or jira_issue.assembly_is_darwin_cobiont_draft_submission() or jira_issue.assembly_is_from_markerscan():
			filename_for_template_name = {
				'bioproject': 'bioproject_haploid.template',
				'primary.info.method': filename_for_method_template_name_for_primary[method_template_name],
				'primary.info': 'primary.info.template',
			}

		if 'hap1' in jira_issue.get_haplotypes() and 'hap2' in jira_issue.get_haplotypes():
			# Only produce the BioProject file once
			if haplotype != haplotypes[0]:
				filename_for_template_name.pop('bioproject')
			else:
				filename_for_template_name['bioproject'] = 'bioproject_haplotype_resolved.template'

		if 'maternal' in jira_issue.get_haplotypes() and 'paternal' in jira_issue.get_haplotypes():
			# Only produce the BioProject file once
			if haplotype != haplotypes[0]:
				filename_for_template_name.pop('bioproject')
			else:
				filename_for_template_name['bioproject'] = 'bioproject_mat_pat.template'

		if jira_issue.assembly_is_mag():
			filename_for_template_name = {
				'primary.info.method': filename_for_method_template_name_for_primary[method_template_name],
				'primary.info': 'primary.info.template',
			}



		# Substitute in BioProject abstract
		if 'BIOPROJECT_ABSTRACT' not in data_for_sample[sample]:
			data_for_sample[sample]['BIOPROJECT_ABSTRACT'] = ''

		if jira_issue.assembly_is_from_markerscan():
			data_for_sample[sample]['MARKER_PIPELINE'] = jira_issue.get_marker_pipeline_from_yaml()

		issue_type_for_bioproject = jira_issue.get_issue_type()
		if jira_issue.get_project_list_from_yaml() != None and 'Darwin' in jira_issue.get_project_list_from_yaml() and 'VGP' in jira_issue.get_project_list_from_yaml():
			issue_type_for_bioproject = 'Darwin_VGP'
		if issue_type_for_bioproject == 'ASG' and jira_issue.assembly_is_mag():
			if jira_issue.assembly_is_primary_metagenome():
				issue_type_for_bioproject = 'ASG_primary_metagenome'
			else:
				issue_type_for_bioproject = 'ASG_binned_metagenome_and_mag'

		if issue_type_for_bioproject not in bioproject_abstract_filename_for_project:
			exit('Cannot process issue type ' + issue_type_for_bioproject)
		if not jira_issue.yaml_key_has_content('bioproject_abstract'):
			with open(csv_dir + bioproject_abstract_filename_for_project[issue_type_for_bioproject]) as bioproject_abstract_handle:
				for line in bioproject_abstract_handle:
					data_for_sample[sample]['BIOPROJECT_ABSTRACT'] += line
		bioproject_abstract_template = Template(data_for_sample[sample]['BIOPROJECT_ABSTRACT'])
		data_for_sample[sample]['BIOPROJECT_ABSTRACT'] = bioproject_abstract_template.safe_substitute(data_for_sample[sample])

		# ERGA is different, get the abstract from the parent
		if not(jira_issue.assembly_is_mag()) and jira_issue.get_issue_type() in ['ERGA', 'VGP']:
			umbrella_bioproject = NcbiRestBioProject.NcbiRestBioProject(data_for_sample[sample]['UMBRELLA_BIOPROJECT'])
			(data_for_sample[sample]['BIOPROJECT_ABSTRACT'], replacements) = re.subn(
				'This project collects the sequencing data and assemblies generated for ',
				'This project provides the genome assembly of ',
				umbrella_bioproject.description()
			)
			if replacements != 1:
				exit('Did not get expected umbrella BioProject text')
			
		text_for_template_name = {}

		for template_name in filename_for_template_name:
			with open(csv_dir + filename_for_template_name[template_name], 'r') as template_handle:

				text_for_template_name[template_name] = ''
				for line in template_handle:
					line_template = Template(line)
					text_for_template_name[template_name] += line_template.safe_substitute(data_for_sample[sample])

		for template_name in filename_for_template_name:
			if not re.search('method', template_name):

				full_output_dir = output_dir

				if args.test:
					full_output_dir += 'test/'
				else:
					if not os.path.isdir(full_output_dir):
						os.mkdir(full_output_dir)

				output_file = full_output_dir + jira_issue.get_assembly_name_for_haplotype(haplotype) + '.' + template_name

				if template_name == 'bioproject':
					output_file = full_output_dir + jira_issue.get_assembly_name_without_haplotype() + '.' + template_name

				if os.path.isfile(output_file) and not args.clobber:
					exit('Cannot clobber existing file ' + output_file)

				print(output_file)
				output_handle = open(output_file, 'w')
				output_handle.write(text_for_template_name[template_name])

				if re.search('info', template_name):
					output_handle.write('DESCRIPTION\t' + text_for_template_name[f'{template_name}.method'])

				output_handle.close()
		
	# Report warnings to ticket
	if len(warnings) > 0:
		jira_issue.add_comment('submission_text_maker warning: ' + ', '.join(warnings))
		jira_issue.add_label('submission_text_error')

def join_with_commas_and_and(string_list):
	if len(string_list) == 0:
		return ''
	elif len(string_list) == 1:
		return string_list[0]
	elif len(string_list) == 2:
		return ' and '.join(string_list)
	else:
		joined_text = ', '.join(string_list[:-1])
		joined_text += ', and ' + string_list[-1]
		return joined_text

def chromosome_list_csv_has_unlocalised_regions(chromosome_list_csv_file):
	unlocalised_regions = False
	with open(chromosome_list_csv_file, 'r') as chromosome_list_csv_handle:
		for row in chromosome_list_csv_handle:
			fields = re.split( ',', row.rstrip() )
			if len(fields) != 3:
					print('Non-standard line format: ' + row + ': field-count ' + str(len(fields)))
			if fields[2] == 'no':
				unlocalised_regions = True
	return unlocalised_regions

def file_has_content(file):
	if os.path.isfile(file) and os.stat(file).st_size > 0:
		return True
	else:
		return False

def file_is_empty(file):
	if os.path.isfile(file) and os.stat(file).st_size == 0:
		return True
	else:
		return False

if __name__ == "__main__":
		main()
