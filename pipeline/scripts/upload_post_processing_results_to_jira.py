#!/usr/bin/env python

import argparse
import GritJiraIssue
import re

def main():
	parser = argparse.ArgumentParser(description='Upload post-processing results to JIRA')
	parser.add_argument("--ticket", help='JIRA ticket key')
	parser.add_argument("--chr", help='Chromosome report file', default = None)
	parser.add_argument("--stats", help='Stats file', default = None)
	parser.add_argument("--gfastats", help='Stats file', default = None)
	args = parser.parse_args()

	issue = GritJiraIssue.GritJiraIssue(args.ticket)
	data_file_for_custom_field = {
		'chromosome_result' : args.chr,
		'assembly_statistics' : args.stats,
		'gfastats' : args.gfastats,
	}

	if re.search('\.(hap2|paternal)\.', args.stats):
		data_file_for_custom_field = {
			'hap2_chromosome_result' : args.chr,
			'hap2_assembly_statistics' : args.stats,
			'hap2_gfastats' : args.gfastats,
		}

	if not re.search('DEV4AC', args.ticket):
		for custom_field in data_file_for_custom_field:
			if data_file_for_custom_field[custom_field] != None:
				write_to_issue(issue, custom_field, data_file_for_custom_field[custom_field])

	# Fast-forward DS tickets
	if issue.assembly_is_mag() or issue.assembly_is_asg_draft_submission() or issue.assembly_is_darwin_cobiont_draft_submission():
		transition_for_status = {
			'Open': 11,
			'Decontamination': 481,
			'Post Processing++': 91,
		}
		while issue.get_status() in transition_for_status:
			print(f'Status is {issue.get_status()}, doing transition {transition_for_status[issue.get_status()]}')
			issue.transition(transition_for_status[issue.get_status()])

	if issue.get_status() == 'Post Processing++' and not(re.search('\.(hap2|paternal)\.', args.stats)):
		end_post_processing_transition_id = 91
		issue.transition(end_post_processing_transition_id)

		# Divert plants without organelles to "on hold"
		#if ('hold_submission' in issue.yaml and (issue.yaml['hold_submission'] == True or issue.yaml['hold_submission'].lower() == 'true')) or (issue.get_tol_group_from_species() == 'dicots' and ('mito' not in issue.yaml or issue.yaml['mito'] == None or re.match('^\s*$', issue.yaml['mito'])) and ('plastid' not in issue.yaml or issue.yaml['plastid'] == None or re.match('^\s*$', issue.yaml['plastid']))) or issue.get_project_list_from_yaml()[0] == 'BGE':
		if ('hold_submission' in issue.yaml and (issue.yaml['hold_submission'] == True or issue.yaml['hold_submission'].lower() == 'true')) or (issue.get_tol_group_from_species() == 'dicots' and ('mito' not in issue.yaml or issue.yaml['mito'] == None or re.match('^\s*$', issue.yaml['mito'])) and ('plastid' not in issue.yaml or issue.yaml['plastid'] == None or re.match('^\s*$', issue.yaml['plastid']))) or issue.get_project_list_from_yaml()[0] == 'AEGIS':
			submission_hold_transition_id = 431
			issue.transition(submission_hold_transition_id)

def write_to_issue(issue, custom_field, data_file):
	with open(data_file, 'r') as data_handle:
		issue.set_custom_field(custom_field, data_handle.read())

if __name__ == "__main__":
		main()
