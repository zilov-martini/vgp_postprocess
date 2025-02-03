#!/usr/bin/env python

import argparse
import GritJiraIssue
import os
import re

def main():
	parser = argparse.ArgumentParser(description='Combine post-processing haplotig files')
	parser.add_argument("--ticket", help='JIRA ticket key')
	parser.add_argument("--additional", help='Additional haplotigs file')
	parser.add_argument("--no_assembly_haplotigs", action='store_true', help='No haplotigs generated at assembly stage')
	args = parser.parse_args()

	issue = GritJiraIssue.GritJiraIssue(args.ticket)

	contamination_directory = issue.get_contamination_directory()

	# Name output file
	all_haplotigs_file = args.additional
	if not re.search('.(additional|all)_haplotigs.curated.', args.additional):
		exit('Non-standard file name: ' + args.additional)
	all_haplotigs_file = re.sub('.(additional|all)_haplotigs.curated.', '.all_haplotigs.unscrubbed.', args.additional)
	if all_haplotigs_file == args.additional:
		exit('Failed to establish all haplotigs file name')

	# Is the assembly haploid?
	haploid = False
	if issue.get_yaml_attachment_url() != None:
		if 'ploidy' in issue.yaml and issue.yaml['ploidy'] == 'haploid':
			haploid = True
	if 'haploid' in issue.get_labels():
			haploid = True
	if haploid and issue.yaml_key_has_content('haplotigs'):
		if 'combine_haplotigs_with_primary' in issue.get_labels():
			issue.add_comment('Combining haplotigs with primary')
			haploid = False
		else:
			exit('Listed as haploid in YAML but haplotigs available')

	# Find decontaminated file
	if not(args.no_assembly_haplotigs or haploid or len(issue.get_haplotypes()) > 0 or issue.yaml_key_is_true('combine_for_curation')):
		decontaminated_haplotigs = []

		# If YAML available, then use YAML for this
		if issue.get_yaml_attachment_url() != None:
			if 'haplotigs' in issue.yaml and issue.yaml['haplotigs'] != None and re.search('\S', issue.yaml['haplotigs']):
				haplotigs_file = os.path.basename(issue.yaml['haplotigs'])
				decontaminated_haplotigs.append(re.sub('\.(fa|fasta)\.gz$', '.decontaminated.fa.gz', haplotigs_file))

		# If using the YAML didn't work, fall back to looking for likely file names
		if len(decontaminated_haplotigs) != 1:
			for contamination_file in os.listdir(contamination_directory):
				if re.search('\.(h|haplotig|haplotigs|alt)\..*decontaminated\.(fa|fasta)\.gz', contamination_file):
					decontaminated_haplotigs.append(contamination_file)

		if len(decontaminated_haplotigs) != 1:
			print('Cannot find unique assembly haplotig file; ' + str(len(decontaminated_haplotigs)) + ' files found')
		else:
			os.system('gunzip -c ' + contamination_directory + '/' + decontaminated_haplotigs[0] + ' > ' + all_haplotigs_file )

	os.system('cat ' + args.additional +  ' >> ' + all_haplotigs_file )

if __name__ == "__main__":
		main()
