#!/usr/bin/env python

import re
import sys
import csv
import os
import GritJiraIssue
import argparse

def main():
	# Get data from config file
	parser = argparse.ArgumentParser()
	parser.add_argument("ticket", type=str, help='JIRA ticket, eg GRIT-42')
	args = parser.parse_args()

	jira_issue = GritJiraIssue.GritJiraIssue(args.ticket)

	# Ready Pretext for GenomeArk assemblies
	if jira_issue.get_custom_field('release_to') == 'S3':
		pretext_files = jira_issue.fetch_pretext_files()

		# Generate image
		jira_issue.generate_pretext_images(pretext_files)

	# Don't otherwise do anything for GenomeArk assemblies
	if jira_issue.get_release_version() != '0' and jira_issue.get_custom_field('release_to') not in ('Internal', 'S3', 'FTP', 'ERGA'):

		sample_and_version = jira_issue.get_custom_field('sample_id') + '.' + jira_issue.get_release_version()

		assembly_submission_dir = jira_issue.get_curated_tolid_dir()

		# release_dir = contamination_class.get_assembly_dir(jira_issue.get_custom_field('sample_id'), sample_and_version)
		release_dir = jira_issue.get_curated_tolid_dir()

		haplotypes = ['primary']
		if len(jira_issue.get_haplotypes()) > 0:
			haplotypes = jira_issue.get_haplotypes()

		for haplotype in haplotypes:
			details_for_assembly = {
				'primary': {
					'info_suffix': '.primary.info',
					'fasta_filename_pattern': jira_issue.get_assembly_name_for_haplotype(haplotype) + '\.primary.final(\.\d+)?\.fa',
					'chromosome_list_filename_pattern': jira_issue.get_assembly_name_for_haplotype(haplotype) +  '\.primary\.chromosome\.list\.(\d+\.)?tsv',
					'unlocalised_list_filename_pattern': jira_issue.get_assembly_name_for_haplotype(haplotype) + '\.primary\.unlocalised\.list(\.\d+)?.tsv',
				},
			}

			# Only assume there are haplotigs if the assembly is not haplotype-resolved:
			if len(jira_issue.get_haplotypes()) == 0:
				details_for_assembly['haplotigs'] = {
					'info_suffix': '.haplotigs.info',
					'fasta_filename_pattern': jira_issue.get_assembly_name() + '\.all_haplotigs.final(\.\d+)?\.fa',
				}

				if jira_issue.get_haplotig_chromosome_mode():
					details_for_assembly['haplotigs']['chromosome_list_filename_pattern'] = jira_issue.get_assembly_name_for_haplotype(haplotype) +  '\.all_haplotigs\.chromosome\.list\.(\d+\.)?tsv'
					details_for_assembly['haplotigs']['unlocalised_list_filename_pattern'] = jira_issue.get_assembly_name_for_haplotype(haplotype) + '\.all_haplotigs\.unlocalised\.list(\.\d+)?.tsv'

			# Don't attempt to open haplotigs file for a haploid assembly
			if not jira_issue.is_there_a_chromosome_csv_for_haplotype(haplotype) or 'haploid' in jira_issue.get_labels() or jira_issue.assembly_is_mag() or jira_issue.assembly_is_asg_draft_submission() or jira_issue.assembly_is_darwin_cobiont_draft_submission():
				del details_for_assembly['haplotigs']

			# Open info files for primary and haplotigs
			source_target_pairs = []
			for assembly_type in details_for_assembly:
				assembly_info_file = assembly_submission_dir + jira_issue.get_assembly_name_for_haplotype(haplotype) + details_for_assembly[assembly_type]['info_suffix']
				if os.path.isfile(assembly_info_file):
					with open(assembly_info_file) as assembly_info_handle:
						info_reader = csv.reader(assembly_info_handle, delimiter='\t')
						for row in info_reader:
							if row[0] == 'FASTA':
								if 'fasta_filename_pattern' not in details_for_assembly[assembly_type]:
									exit('ERROR: Cannot find source file location for ' + assembly_type)
								source_file = find_file_from_template(details_for_assembly[assembly_type]['fasta_filename_pattern'], release_dir)
								submission_fasta_file_zipped = row[1]
								source_target_pairs.append([source_file, submission_fasta_file_zipped])
							elif row[0] == 'CHROMOSOME_LIST':
								if 'chromosome_list_filename_pattern' not in details_for_assembly[assembly_type]:
									exit('ERROR: Cannot find chr list')
								source_target_pairs.append([find_file_from_template(details_for_assembly[assembly_type]['chromosome_list_filename_pattern'], release_dir), row[1]])
							elif row[0] == 'UNLOCALISED_LIST':
								if 'unlocalised_list_filename_pattern' not in details_for_assembly[assembly_type]:
									exit('ERROR: Cannot find unlocalised list')
								source_target_pairs.append([find_file_from_template(details_for_assembly[assembly_type]['unlocalised_list_filename_pattern'], release_dir), row[1]])
				else:
					exit('File ' + assembly_info_file + ' does not exist')

			for source_target_pair in source_target_pairs:
				(source, target) = source_target_pair
				full_target = assembly_submission_dir + target
				move_and_zip(source, full_target)

def find_file_from_template(file_template, directory):
	filenames = os.listdir(directory)
	matching_filenames = []
	for filename in filenames:
		if re.match(file_template, filename):
			matching_filenames.append(filename)

	if len(matching_filenames) != 1:
		exit(f'Cannot find unique matching filename for {file_template} in {directory}; candidates include {matching_filenames}')
	return(directory + matching_filenames[0])

def move_and_zip(source, zipped_target):
	# If source is already zipped, exit
	if re.search('\.gz$', source):
		exit('ERROR: Source file is already zipped: ' + source)	

	if re.search('\.gz$', zipped_target):
		target = re.sub('\.gz$', '', zipped_target)

		if not os.path.isfile(source):
			exit('Cannot find source ' + source)
		if source != target:
			if os.path.isfile(target):
				exit('Target ' + target + ' already exists')

			print('Moving to ' + target)
			os.system("mv " + source + " " + target)
		print('Zipping ' + target)
		# -n ensures original filename is not retained
		os.system("gzip -fn " + target)

	else:
		quit('Non-zipped target file: ' + zipped_target)


if __name__ == "__main__":
		main()
