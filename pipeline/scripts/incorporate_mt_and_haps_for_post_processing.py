#!/usr/bin/env python

import enum
import os
import re
import gzip
import argparse
from Bio import SeqIO
from Bio.SeqRecord import SeqRecord
import GritJiraIssue

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("--ticket", type = str, help='JIRA ticket ID', required=True)
	parser.add_argument("--nuclear_in", type = str, help='Nuclear FASTA', required=True)
	parser.add_argument("--haplotigs_in", type = str, help='Haplotig FASTA', required=True)
	parser.add_argument("--chr_in", type= str, help='Chr list file', required = True)
	parser.add_argument("--fasta_out", type= str, help='FASTA output')
	parser.add_argument("--chr_out", type= str, help='Chr list file output')
	args = parser.parse_args()

	nuclear_handle = None
	haplotig_handle = None

	if re.search('\.gz$', args.nuclear_in):
		nuclear_handle = gzip.open(args.nuclear_in, "rt")
	else:
		nuclear_handle = open(args.nuclear_in, "rt")

	# Find MT using ticket
	issue = GritJiraIssue.GritJiraIssue(args.ticket)

	decontaminated_mt_assembly = None
	decontaminated_plastid_assembly = None

	# Don't try to incorporate MT for GenomeArk assemblies or second haplotypes
	if (issue.get_release_version() != '0' and issue.get_custom_field('release_to') != 'S3') and not (issue.has_two_haplotypes() and re.search('\.(paternal|hap2)\.', args.nuclear_in)):

		# Initially try YAML
		if issue.get_yaml_attachment_url() != None:
			mt_assembly = issue.get_mito_assembly()
			if mt_assembly != None:
				decontaminated_mt_assembly = re.sub('\.(fa|fasta)\.gz', '.decontaminated.fa.gz', mt_assembly)
				if not os.path.isfile(decontaminated_mt_assembly):
					exit('Cannot find decontaminated version of MT file given in YAML: ' + decontaminated_mt_assembly + '. Perhaps YAML file and/or directory names are wrong/outdated.')
			plastid_assembly = issue.get_plastid_assembly()
			if plastid_assembly != None:
				decontaminated_plastid_assembly = re.sub('\.(fa|fasta)\.gz', '.decontaminated.fa.gz', plastid_assembly)
				if not os.path.isfile(decontaminated_plastid_assembly):
					exit('Cannot find decontaminated version of plastid file given in YAML: ' + decontaminated_plastid_assembly + '. Perhaps YAML file and/or directory names are wrong/outdated.')

		# Otherwise check for a standard file name
		if decontaminated_mt_assembly == None:
			contamination_directory = issue.get_contamination_directory()
			decontaminated_mt_candidates = []

			for contamination_file in os.listdir(contamination_directory):
				if re.search('([-.]MT)\..*decontaminated\.(fa|fasta)\.gz', contamination_file):
					decontaminated_mt_candidates.append(contamination_file)

			if len(decontaminated_mt_candidates) > 1:
				exit('Cannot find unique MT file; ' + str(len(decontaminated_mt_candidates)) + ' files found')
			if len(decontaminated_mt_candidates) == 1:
				decontaminated_mt_assembly = contamination_directory + '/' + decontaminated_mt_candidates[0]

	# Initially try YAML
	if 'haploid' in issue.get_labels():
		if re.search('\.gz$', args.haplotigs_in):
			haplotig_handle = gzip.open(args.haplotigs_in, "rt")
		else:
			haplotig_handle = open(args.haplotigs_in, "rt")


	fasta_output_handle = open(args.fasta_out, 'w')

	for record in SeqIO.parse(nuclear_handle, "fasta"):
		SeqIO.write([record], fasta_output_handle, 'fasta')

	if haplotig_handle != None:
		haplotig_records = SeqIO.parse(haplotig_handle, "fasta")
		for record in haplotig_records:
			SeqIO.write([record], fasta_output_handle, 'fasta')
		haplotig_handle.close()

	# CHANGE UP THIS BIT TO MATCH THE ABOVE!!!
	file_for_organelle = {
		'mt': decontaminated_mt_assembly,
		'plastid': decontaminated_plastid_assembly,
	}

	label_for_organelle = {
		'mt': 'MT',
		'plastid': 'Pltd',
	}

	name_for_organelle = {
		'mt': 'Mitochondrion',
		'plastid': 'Chloroplast',
	}

	scaffolds_for_organelle = {
		'mt': 0,
		'plastid': 0,
	}

	for organelle in file_for_organelle.keys():
		if file_for_organelle[organelle] != None:
			if re.search('\.gz$', file_for_organelle[organelle]):
				organelle_handle = gzip.open(file_for_organelle[organelle], "rt")
			else:
				organelle_handle = open(file_for_organelle[organelle], "rt")
			organelle_records = SeqIO.parse(organelle_handle, "fasta")
			#NEED A DIFFERENT TEST OF MT
		#	if len(mt_records) != 1:
		#		exit('Number of MT records is not 1')
			for record in organelle_records:
				scaffolds_for_organelle[organelle] += 1
				record.name = ''
				record.description = ''
				record.id=f'scaffold_{label_for_organelle[organelle]}_{scaffolds_for_organelle[organelle]}'
				SeqIO.write([record], fasta_output_handle, 'fasta')
			organelle_handle.close()

	nuclear_handle.close()
	fasta_output_handle.close()

	# Append MT line to chr file
	chr_handle = None
	if re.search('\.gz$', args.chr_in):
		chr_handle = gzip.open(args.chr_in, "rt")
	else:
		chr_handle = open(args.chr_in, "rt")
	chr_output_handle = open(args.chr_out, 'w')

	chromosome_label = 'Chromosome'
	if issue.yaml_key_is_true('linear_mito'):
		chromosome_label = 'Linear-Chromosome'

	for line in chr_handle:
		chr_output_handle.write(line)
	for organelle in file_for_organelle.keys():
		if file_for_organelle[organelle] != None:
			if scaffolds_for_organelle[organelle] == 1:
				chr_output_handle.write(f'scaffold_{label_for_organelle[organelle]}_1\t{label_for_organelle[organelle]}\t{chromosome_label}\t{name_for_organelle[organelle]}\n')
			else:
				for organelle_index in range(1,(scaffolds_for_organelle[organelle]+1)):
					chr_output_handle.write(f'scaffold_{label_for_organelle[organelle]}_{organelle_index}\t{label_for_organelle[organelle]}{organelle_index}\t{chromosome_label}\t{name_for_organelle[organelle]}\n')
	
	chr_handle.close()
	chr_output_handle.close()

	#* Copy to new compgen dir

if __name__ == "__main__":
		main()
