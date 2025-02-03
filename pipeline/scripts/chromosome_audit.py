#!/usr/bin/env python

import argparse
import re
import sys

# Download
parser = argparse.ArgumentParser()
parser.add_argument("--chr")
parser.add_argument("--unlocalised")
parser.add_argument("--lengths")
parser.add_argument("--test", action="store_true")
args = parser.parse_args()

error_flag = False

length_for_scaffold = {}
with open(args.lengths, 'r') as lengths_handle:
	for line in lengths_handle:
			line = line.rstrip()
			fields = re.split('\s+', line)
			if len(fields) == 2:
				length_for_scaffold[fields[1]] = int(fields[0])

unlocalised_lines = []

scaffold_for_chr_number = {}
scaffold_present = {}
length_for_chr_number = {} # Length including unlocalised regions
if args.chr:
	with open(args.chr, 'r') as chr_handle:
		for line in chr_handle:
			if not re.match('^#', line):
				line = line.rstrip()
				fields = re.split('\s+|,', line)
				if len(fields) == 3:
					if fields[2] == 'no':
						unlocalised_lines.append(line)
					else:	
						if fields[1] in scaffold_for_chr_number:
							print('Multiple entries for chr ' + fields[1] + ' in chr file\n', file=sys.stderr)
							error_flag = True
						scaffold_for_chr_number[fields[1]] = fields[0]
						length_for_chr_number[fields[1]] = length_for_scaffold[fields[0]]
						if not re.match('^(\d+A?|[BXYZW](\d+)?|X[LR]|(\d+)?[ABTLRSXYZW]|(LG|GRC)\d*.*|[AEOUJXIVLC_]+|dot|(\d+|X|Y)_\d+[SL]?|\dRL)$', fields[1]):
							print("Chr", fields[1], "is not numeric or a sex chromosome or a B chromosome or a Roman numeral or an RL suffix or S/L suffix or 'dot' or '1_1' broken chromosome format", file=sys.stderr)
							error_flag = True
						if fields[0] in scaffold_present:
							print('Multiple entries for scaffold ' + fields[0] + ' in chr file\n', file=sys.stderr)
							error_flag = True
						scaffold_present[fields[0]] = 1
						if fields[0] not in length_for_scaffold:
							print('Scaffold ' + fields[0] + ' not present in FASTA\n', file=sys.stderr)
							error_flag = True
						if not re.match('^(Chromosome|yes|no)$', fields[2]):
							print('Third field should be Chromosome, yes, or no\n', file=sys.stderr)
							error_flag = True
						if length_for_scaffold[fields[0]] > 2**31:
							print(f'Scaffold {fields[1]} is larger than INSDC limit of 2^31')
							error_flag = True

# Add in checks for unplaced
# Have output not die
if args.unlocalised:
	if args.test:
		print("\n** Unlocalised")
	with open(args.unlocalised, 'r') as unlocalised_handle:
		for line in unlocalised_handle:
			unlocalised_lines.append(line)

# Process lines that are in unlocalised file *or* in NCBI-format file
for line in unlocalised_lines:
	if not re.match('^#', line):
		line = line.rstrip()
		fields = re.split('\s+|,', line)
		# Is this unlocalised scaffold in the FASTA?
		line_error_flag = False
		if fields[0] not in length_for_scaffold:
			print('Unlocalised scaffold ' + fields[0] + ' not present in FASTA', file=sys.stderr)
			error_flag = True
			line_error_flag = True
		if fields[1] not in scaffold_for_chr_number:
			print('Unlocalised chr name ' + fields[1] + ' not present in main chr file', file=sys.stderr)
			error_flag = True
			line_error_flag = True
		if not line_error_flag:
			length_for_chr_number[fields[1]] += length_for_scaffold[fields[0]]
		if args.test and not line_error_flag:
			print(fields[0], fields[1], length_for_scaffold[fields[0]], "corresponds to", scaffold_for_chr_number[fields[1]])

# Are the chromosomes in size order?
last_chr_length = None

# Only test numeric chrs
numeric_chrs = list(filter(lambda x: re.search('^\d+$', str(x)), scaffold_for_chr_number.keys()))
for chr_number in sorted(list(map(lambda x: int(x), numeric_chrs))):
	chr_number = str(chr_number)
	if args.test:
		print(chr_number, scaffold_for_chr_number[chr_number], length_for_chr_number[chr_number] )
	if last_chr_length != None and length_for_chr_number[chr_number] > last_chr_length:
		print('Chromosome not in order of size: ' + str(chr_number) + '\n', file=sys.stderr)
		# Note that this does not set an error
	last_chr_length = length_for_chr_number[chr_number]
				
if error_flag:
	exit('Errors detected\n')
