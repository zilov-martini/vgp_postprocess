#!/usr/bin/env python

import os
import re
import gzip
import argparse
from Bio import SeqIO
from Bio.SeqRecord import SeqRecord
from datetime import date

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("--mt", type = str, help='MT FASTA', required=True)
	parser.add_argument("--plastid", type = str, help='Plastid FASTA')
	parser.add_argument("--nuclear", type = str, help='Nuclear FASTA', required=True)
	parser.add_argument("--chr", type= str, help='Chr list file', required = True)
	parser.add_argument("--out", type= str, help='Output stem', default = 'incorporation_output')
	args = parser.parse_args()

	nuclear_handle = None

	if re.search('\.gz$', args.nuclear):
		nuclear_handle = gzip.open(args.nuclear, "rt")
	else:
		nuclear_handle = open(args.nuclear, "rt")

	date_6_figure = date.today().strftime("%Y%m%d")

	fasta_output_file = args.out + '.curated_primary.' + date_6_figure + '.fa'
	fasta_output_handle = open(fasta_output_file, 'w')

	for record in SeqIO.parse(nuclear_handle, "fasta"):
		SeqIO.write([record], fasta_output_handle, 'fasta')

	# Add all organelles
	file_for_organelle = {
		'mt': args.mt,
		'plastid': args.plastid,
	}

	label_for_organelle = {
		'mt': 'MT',
		'plastid': 'Pltd',
	}

	name_for_organelle = {
		'mt': 'Mitochondrion',
		'plastid': 'Chloroplast',
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
				record.name = ''
				record.description = ''
				record.id=f'scaffold_{label_for_organelle[organelle]}'
				SeqIO.write([record], fasta_output_handle, 'fasta')
			organelle_handle.close()

	nuclear_handle.close()
	fasta_output_handle.close()

	# Append MT line to chr file
	chr_handle = None
	if re.search('\.gz$', args.chr):
		chr_handle = gzip.open(args.chr, "rt")
	else:
		chr_handle = open(args.chr, "rt")
	chr_output_file = args.out + '.chromosome.list.' + date_6_figure + '.tsv'
	chr_output_handle = open(chr_output_file, 'w')

	for line in chr_handle:
		chr_output_handle.write(line)
	for organelle in file_for_organelle.keys():
		if file_for_organelle[organelle] != None:
			chr_output_handle.write(f'scaffold_{label_for_organelle[organelle]}\t{label_for_organelle[organelle]}\tChromosome\t{name_for_organelle[organelle]}\n')
	
	chr_handle.close()
	chr_output_handle.close()

	#* Copy to new compgen dir

if __name__ == "__main__":
		main()
